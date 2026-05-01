from fastapi import FastAPI, HTTPException, Request, Depends, Header
from fastapi.openapi.utils import get_openapi
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional
import httpx
import os

PLUGIN_BASE_URL = os.environ.get("PLUGIN_BASE_URL", "https://javitnas.ddns.net/mcp-cnc")
PLUGIN_API_TOKEN = os.environ.get("PLUGIN_API_TOKEN", "1234")
app = FastAPI(
    title="mcp-orchestrator",
    description="CNC orchestration plugin that proxies typed DXF, CAM, catalogue and machine operations.",
    version="0.1.0",
    openapi_tags=[
        {"name": "dxf", "description": "DXF creation and manipulation operations."},
        {"name": "cam", "description": "CAM and G-code generation operations."},
        {"name": "catalogue", "description": "Catalogue lookup operations."},
        {"name": "machine", "description": "Machine control and status operations."},
    ],
    servers=[{"url": PLUGIN_BASE_URL or "https://javitnas.ddns.net/mcp-cnc", "description": "Public plugin base URL."}]
)


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags,
    )
    # Force OpenAPI 3.0.3 for ChatGPT compatibility (3.1.0 is not fully supported)
    schema["openapi"] = "3.0.3"
    # Add bearer security scheme
    schema.setdefault("components", {})
    schema["components"]["securitySchemes"] = {
        "bearerAuth": {"type": "http", "scheme": "bearer"}
    }
    # Apply security to all operations and remove the explicit authorization param
    for path_item in schema.get("paths", {}).values():
        for operation in path_item.values():
            if not isinstance(operation, dict):
                continue
            operation.setdefault("security", [{"bearerAuth": []}])
            operation["parameters"] = [
                p for p in operation.get("parameters", [])
                if not (isinstance(p, dict) and p.get("name") == "authorization")
            ]
    app.openapi_schema = schema
    return app.openapi_schema


app.openapi = custom_openapi

# Service URLs (internal to Docker network)
DXF_URL = os.environ.get("DXF_ENGINE_URL", "http://dxf-engine:8000")
CAM_URL = os.environ.get("CAM_ENGINE_URL", "http://cam-engine:8000")
CATALOGUE_URL = os.environ.get("CATALOGUE_URL", "http://catalogue:8000")
PLUGIN_NAME = os.environ.get("PLUGIN_NAME", "MCP CNC Orchestrator")
PLUGIN_DESCRIPTION = os.environ.get("PLUGIN_DESCRIPTION", "CNC design orchestration API for DXF, CAM and catalogue operations.")
PLUGIN_LOGO_URL = os.environ.get("PLUGIN_LOGO_URL", "https://upload.wikimedia.org/wikipedia/commons/0/04/Scalable_Vector_Graphics_SVG_logo.svg")
BRIDGE_URL = os.environ.get("BRIDGE_URL", "http://linuxcnc-bridge:8000")


def validate_token(authorization: Optional[str] = Header(None)):
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.split(" ", 1)[1]
    if token != PLUGIN_API_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


class RectangleParams(BaseModel):
    filename: str = Field(..., description="Output DXF filename.")
    width: float = Field(..., description="Rectangle width in millimeters.")
    height: float = Field(..., description="Rectangle height in millimeters.")
    radius: float = Field(0.0, description="Uniform corner radius in millimeters.")
    layer: str = Field("PERFIL", description="DXF layer for the rectangle.")
    r_br: Optional[float] = Field(None, description="Bottom-right corner radius override.")
    r_tr: Optional[float] = Field(None, description="Top-right corner radius override.")
    r_tl: Optional[float] = Field(None, description="Top-left corner radius override.")
    r_bl: Optional[float] = Field(None, description="Bottom-left corner radius override.")

    class Config:
        schema_extra = {
            "example": {
                "filename": "pieza_rectangulo.dxf",
                "width": 150.0,
                "height": 80.0,
                "radius": 10.0,
                "layer": "PERFIL"
            }
        }

class CircleParams(BaseModel):
    filename: str = Field(..., description="Output DXF filename.")
    radius: float = Field(..., description="Circle radius in millimeters.")
    center_x: float = Field(0.0, description="Center X coordinate in millimeters.")
    center_y: float = Field(0.0, description="Center Y coordinate in millimeters.")
    layer: str = Field("PERFIL", description="DXF layer for the circle.")

class TextParams(BaseModel):
    filename: str = Field(..., description="Output DXF filename.")
    text: str = Field(..., description="Text content to draw.")
    height: float = Field(..., description="Text height in millimeters.")
    x: float = Field(0.0, description="X coordinate in millimeters.")
    y: float = Field(0.0, description="Y coordinate in millimeters.")
    font_name: Optional[str] = Field(None, description="Optional font name.")
    font_type: str = Field("outline", description="Font rendering mode.")
    rotation: float = Field(0.0, description="Rotation angle in degrees.")
    alignment: str = Field("left", description="Text alignment.")
    layer: str = Field("GRABADO", description="DXF layer for the text.")

class NestingParams(BaseModel):
    output_filename: str = Field(..., description="DXF filename for the nested result.")
    input_filenames: List[str] = Field(..., description="List of input DXF filenames to nest.")
    sheet_width: float = Field(..., description="Sheet width in millimeters.")
    sheet_height: float = Field(..., description="Sheet height in millimeters.")
    padding: float = Field(5.0, description="Spacing between pieces in millimeters.")
    label_pieces: bool = Field(True, description="Whether to add labels for each nested piece.")

class BooleanParams(BaseModel):
    output_filename: str = Field(..., description="DXF filename for the boolean result.")
    filename_a: str = Field(..., description="First input DXF filename.")
    filename_b: str = Field(..., description="Second input DXF filename.")
    operacion: str = Field("union", description="Boolean operation: union, intersection, difference.")
    offset_x_b: float = Field(0.0, description="X offset for the second DXF before boolean.")
    offset_y_b: float = Field(0.0, description="Y offset for the second DXF before boolean.")

class CAMGenerateParams(BaseModel):
    dxf_filename: str = Field(..., description="Input DXF filename for CAM generation.")
    output_filename: str = Field(..., description="Output G-code filename.")
    tool_id: str = Field(..., description="Tool identifier to use for CAM.")
    material_id: Optional[str] = Field(None, description="Optional material identifier.")
    override_tool_number: Optional[int] = Field(None, description="Optional numeric override for the tool.")
    operation: str = Field("profile_outside", description="CAM operation type.")
    cut_depth_mm: float = Field(5.0, description="Cut depth in millimeters.")
    pass_depth_mm: Optional[float] = Field(None, description="Optional depth per pass in millimeters.")
    tabs_enabled: bool = Field(False, description="Whether to enable tabs.")
    tab_width_mm: float = Field(5.0, description="Tab width in millimeters.")
    tab_height_mm: float = Field(2.0, description="Tab height in millimeters.")
    tab_count: int = Field(4, description="Number of tabs to create.")
    material_thickness_mm: float = Field(5.0, description="Material thickness in millimeters.")
    leadin_type: str = Field("ramp", description="Lead-in type for cutter entry.")
    leadin_length_mm: float = Field(10.0, description="Lead-in length in millimeters.")
    start_x_mm: Optional[float] = Field(None, description="Optional start X coordinate.")
    start_y_mm: Optional[float] = Field(None, description="Optional start Y coordinate.")

class MachineJogParams(BaseModel):
    axis: str = Field(..., description="Axis to jog (e.g. X, Y, Z).")
    distance: float = Field(..., description="Distance to jog in millimeters.")
    speed: Optional[float] = Field(None, description="Optional jog speed.")

class MachineGCodeParams(BaseModel):
    gcode: str = Field(..., description="G-code commands to send to the machine.")

class MachineSpindleParams(BaseModel):
    spindle_speed: int = Field(..., description="Spindle speed in RPM.")
    state: str = Field(..., description="Spindle state, e.g. 'on' or 'off'.")

@app.get("/")
async def root():
    return {"service": "mcp-orchestrator", "status": "ok"}


# OAuth discovery endpoints required by ChatGPT Apps MCP flow
@app.get("/.well-known/oauth-protected-resource")
@app.get("/.well-known/ai-plugin.json/.well-known/oauth-protected-resource")
async def oauth_protected_resource(request: Request):
    base_url = PLUGIN_BASE_URL or f"{request.url.scheme}://{request.headers.get('host')}"
    return {
        "resource": base_url,
        "authorization_servers": [],
        "bearer_methods_supported": ["header"],
        "scopes_supported": []
    }

@app.get("/.well-known/oauth-authorization-server")
@app.get("/.well-known/ai-plugin.json/.well-known/oauth-authorization-server")
async def oauth_authorization_server():
    return {}

@app.get("/.well-known/openid-configuration")
@app.get("/.well-known/ai-plugin.json/.well-known/openid-configuration")
async def openid_configuration():
    return {}


@app.post("/mcp")
async def mcp_handler(request: Request):
    body = await request.json()
    method = body.get("method")
    request_id = body.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "mcp-orchestrator", "version": "0.1.0"}
            }
        }

    if method == "notifications/initialized":
        return {}

    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
            "tools": [
                {
                    "name": "dxf_rectangle",
                    "description": "Crea un DXF con un rectángulo parametrizado con esquinas opcionales redondeadas.",
                    "inputSchema": {
                        "type": "object",
                        "required": ["filename", "width", "height"],
                        "properties": {
                            "filename": {"type": "string", "description": "Nombre del archivo DXF de salida."},
                            "width": {"type": "number", "description": "Ancho en milímetros."},
                            "height": {"type": "number", "description": "Alto en milímetros."},
                            "radius": {"type": "number", "description": "Radio de esquina uniforme en milímetros."},
                            "layer": {"type": "string", "description": "Capa DXF."}
                        }
                    }
                },
                {
                    "name": "dxf_circle",
                    "description": "Crea un DXF con un círculo.",
                    "inputSchema": {
                        "type": "object",
                        "required": ["filename", "radius"],
                        "properties": {
                            "filename": {"type": "string", "description": "Nombre del archivo DXF de salida."},
                            "radius": {"type": "number", "description": "Radio en milímetros."},
                            "center_x": {"type": "number", "description": "Centro X en milímetros."},
                            "center_y": {"type": "number", "description": "Centro Y en milímetros."},
                            "layer": {"type": "string", "description": "Capa DXF."}
                        }
                    }
                },
                {
                    "name": "dxf_text",
                    "description": "Crea un DXF con un texto parametrizado. Usa catalogue_fonts para ver las tipografías disponibles y especifica font_name con el nombre del archivo (ej: 'romans.shx').",
                    "inputSchema": {
                        "type": "object",
                        "required": ["filename", "text", "height"],
                        "properties": {
                            "filename": {"type": "string"},
                            "text": {"type": "string"},
                            "height": {"type": "number"},
                            "x": {"type": "number"},
                            "y": {"type": "number"},
                            "font_name": {"type": "string", "description": "Nombre del archivo de fuente (ej: 'romans.shx', 'arial.ttf'). Usa catalogue_fonts para ver las disponibles."},
                            "layer": {"type": "string"}
                        }
                    }
                },
                {
                    "name": "dxf_nesting",
                    "description": "Anida múltiples piezas DXF en una plancha.",
                    "inputSchema": {
                        "type": "object",
                        "required": ["output_filename", "input_filenames", "sheet_width", "sheet_height"],
                        "properties": {
                            "output_filename": {"type": "string"},
                            "input_filenames": {"type": "array", "items": {"type": "string"}},
                            "sheet_width": {"type": "number"},
                            "sheet_height": {"type": "number"},
                            "padding": {"type": "number"}
                        }
                    }
                },
                {
                    "name": "dxf_boolean",
                    "description": "Realiza una operación booleana entre dos archivos DXF.",
                    "inputSchema": {
                        "type": "object",
                        "required": ["output_filename", "filename_a", "filename_b"],
                        "properties": {
                            "output_filename": {"type": "string"},
                            "filename_a": {"type": "string"},
                            "filename_b": {"type": "string"},
                            "operacion": {"type": "string", "description": "union, intersection o difference."}
                        }
                    }
                },
                {
                    "name": "dxf_polyline",
                    "description": "Crea un DXF con una polilínea arbitraria a partir de una lista de puntos [[x,y],...].",
                    "inputSchema": {
                        "type": "object",
                        "required": ["filename", "points"],
                        "properties": {
                            "filename": {"type": "string"},
                            "points": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}, "description": "Lista de puntos [[x1,y1],[x2,y2],...]"},
                            "closed": {"type": "boolean", "description": "Si true, cierra la polilínea uniendo el último punto con el primero."},
                            "layer": {"type": "string"}
                        }
                    }
                },
                {
                    "name": "dxf_spline",
                    "description": "Crea un DXF con una spline suave (curva Bézier) a partir de puntos de control [[x,y],...].",
                    "inputSchema": {
                        "type": "object",
                        "required": ["filename", "points"],
                        "properties": {
                            "filename": {"type": "string"},
                            "points": {"type": "array", "items": {"type": "array", "items": {"type": "number"}}, "description": "Puntos de control de la spline [[x1,y1],...]"},
                            "closed": {"type": "boolean"},
                            "layer": {"type": "string"}
                        }
                    }
                },
                {
                    "name": "dxf_arc",
                    "description": "Crea un DXF con un arco definido por centro, radio y ángulos de inicio y fin en grados.",
                    "inputSchema": {
                        "type": "object",
                        "required": ["filename", "center_x", "center_y", "radius", "start_angle", "end_angle"],
                        "properties": {
                            "filename": {"type": "string"},
                            "center_x": {"type": "number"},
                            "center_y": {"type": "number"},
                            "radius": {"type": "number"},
                            "start_angle": {"type": "number", "description": "Ángulo de inicio en grados (0=derecha, 90=arriba)."},
                            "end_angle": {"type": "number", "description": "Ángulo de fin en grados."},
                            "layer": {"type": "string"}
                        }
                    }
                },
                {
                    "name": "dxf_offset",
                    "description": "Genera el contorno con offset (interior o exterior) de un DXF existente. Distance positiva=exterior, negativa=interior.",
                    "inputSchema": {
                        "type": "object",
                        "required": ["input_filename", "output_filename", "distance"],
                        "properties": {
                            "input_filename": {"type": "string"},
                            "output_filename": {"type": "string"},
                            "distance": {"type": "number", "description": "Distancia del offset en mm. Positivo=hacia afuera, negativo=hacia adentro."},
                            "layer": {"type": "string"}
                        }
                    }
                },
                {
                    "name": "dxf_transform",
                    "description": "Aplica traslación, rotación y/o escala a un DXF existente y guarda el resultado.",
                    "inputSchema": {
                        "type": "object",
                        "required": ["input_filename", "output_filename"],
                        "properties": {
                            "input_filename": {"type": "string"},
                            "output_filename": {"type": "string"},
                            "translate_x": {"type": "number", "description": "Desplazamiento en X en mm."},
                            "translate_y": {"type": "number", "description": "Desplazamiento en Y en mm."},
                            "rotate_deg": {"type": "number", "description": "Rotación en grados (sentido antihorario)."},
                            "scale": {"type": "number", "description": "Factor de escala (1.0=sin cambio, 2.0=doble tamaño)."},
                            "layer": {"type": "string"}
                        }
                    }
                },
                {
                    "name": "dxf_merge",
                    "description": "Fusiona múltiples archivos DXF en uno solo sin operaciones booleanas, conservando todas las entidades.",
                    "inputSchema": {
                        "type": "object",
                        "required": ["output_filename", "input_filenames"],
                        "properties": {
                            "output_filename": {"type": "string"},
                            "input_filenames": {"type": "array", "items": {"type": "string"}, "description": "Lista de archivos DXF a fusionar."}
                        }
                    }
                },
                {
                    "name": "dxf_array",
                    "description": "Genera un array rectangular (cuadrícula de cols x rows) de un DXF con el espaciado especificado.",
                    "inputSchema": {
                        "type": "object",
                        "required": ["input_filename", "output_filename", "cols", "rows", "spacing_x", "spacing_y"],
                        "properties": {
                            "input_filename": {"type": "string"},
                            "output_filename": {"type": "string"},
                            "cols": {"type": "integer", "description": "Número de columnas."},
                            "rows": {"type": "integer", "description": "Número de filas."},
                            "spacing_x": {"type": "number", "description": "Separación entre columnas en mm."},
                            "spacing_y": {"type": "number", "description": "Separación entre filas en mm."},
                            "layer": {"type": "string"}
                        }
                    }
                },
                {
                    "name": "cam_generate",
                    "description": "Genera G-code desde un archivo DXF.",
                    "inputSchema": {
                        "type": "object",
                        "required": ["dxf_filename", "output_filename", "tool_id"],
                        "properties": {
                            "dxf_filename": {"type": "string"},
                            "output_filename": {"type": "string"},
                            "tool_id": {"type": "string"},
                            "material_id": {"type": "string"},
                            "cut_depth_mm": {"type": "number"},
                            "operation": {"type": "string"}
                        }
                    }
                },
                {
                    "name": "catalogue_designs",
                    "description": "Lista los diseños disponibles en el catálogo.",
                    "inputSchema": {"type": "object", "properties": {}}
                },
                {
                    "name": "catalogue_tools",
                    "description": "Lista las herramientas de corte disponibles en el catálogo.",
                    "inputSchema": {"type": "object", "properties": {}}
                },
                {
                    "name": "machine_status",
                    "description": "Obtiene el estado actual de la máquina CNC.",
                    "inputSchema": {"type": "object", "properties": {}}
                },
                {
                    "name": "catalogue_add_design",
                    "description": "Añade un diseño DXF al catálogo permanente para reutilizarlo en el futuro.",
                    "inputSchema": {
                        "type": "object",
                        "required": ["name", "filename"],
                        "properties": {
                            "name": {"type": "string", "description": "Nombre descriptivo del diseño."},
                            "filename": {"type": "string", "description": "Nombre del archivo DXF (solo el nombre, sin ruta)."},
                            "description": {"type": "string", "description": "Descripción opcional del diseño."},
                            "tags": {"type": "array", "items": {"type": "string"}, "description": "Etiquetas opcionales para clasificar el diseño."}
                        }
                    }
                },
                {
                    "name": "dxf_preview",
                    "description": "Genera una imagen PNG de previsualización de un archivo DXF y devuelve la URL pública para verla. Usa SOLO el nombre del archivo, sin ruta (ej: 'prueba.dxf', NO '/workspace/prueba.dxf').",
                    "inputSchema": {
                        "type": "object",
                        "required": ["filename"],
                        "properties": {
                            "filename": {"type": "string", "description": "Nombre del archivo DXF a previsualizar, solo el nombre sin ruta (ej: 'diseño.dxf')."}
                        }
                    }
                },
                {
                    "name": "workspace_list",
                    "description": "Lista todos los archivos disponibles en el workspace (DXF, PNG, G-code, etc.).",
                    "inputSchema": {"type": "object", "properties": {}}
                },
                {
                    "name": "catalogue_materials",
                    "description": "Lista los materiales disponibles en el catálogo (madera, aluminio, etc.) con sus parámetros de corte.",
                    "inputSchema": {"type": "object", "properties": {}}
                },
                {
                    "name": "catalogue_fonts",
                    "description": "Lista las tipografías/fuentes disponibles en el servidor (.shx, .ttf) que se pueden usar con la herramienta dxf_text.",
                    "inputSchema": {"type": "object", "properties": {}}
                },
                {
                    "name": "machine_run_file",
                    "description": "Ejecuta un archivo G-code en la máquina CNC. Requiere confirm=true para proceder. El archivo debe existir en el directorio de G-code.",
                    "inputSchema": {
                        "type": "object",
                        "required": ["filename", "confirm"],
                        "properties": {
                            "filename": {"type": "string", "description": "Nombre del archivo G-code a ejecutar."},
                            "confirm": {"type": "boolean", "description": "Debe ser true para confirmar la ejecución en la máquina real."}
                        }
                    }
                }
            ]
            }
        }

    if method == "tools/call":
        name = body.get("params", {}).get("name")
        args = body.get("params", {}).get("arguments", {})

        if name == "workspace_list":
            try:
                files = os.listdir(WORKSPACE_DIR)
            except Exception:
                files = []
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"content": [{"type": "text", "text": f"Archivos en workspace: {files}"}]}
            }

        async with httpx.AsyncClient() as client:
            if name == "dxf_rectangle":
                resp = await client.post(f"{DXF_URL}/create/rectangle", json=args)
            elif name == "dxf_circle":
                resp = await client.post(f"{DXF_URL}/create/circle", json=args)
            elif name == "dxf_text":
                resp = await client.post(f"{DXF_URL}/create/text", json=args)
            elif name == "dxf_nesting":
                resp = await client.post(f"{DXF_URL}/create/nesting", json=args)
            elif name == "dxf_boolean":
                resp = await client.post(f"{DXF_URL}/create/boolean", json=args)
            elif name == "dxf_polyline":
                resp = await client.post(f"{DXF_URL}/create/polyline", json=args)
            elif name == "dxf_spline":
                resp = await client.post(f"{DXF_URL}/create/spline", json=args)
            elif name == "dxf_arc":
                resp = await client.post(f"{DXF_URL}/create/arc", json=args)
            elif name == "dxf_offset":
                resp = await client.post(f"{DXF_URL}/create/offset", json=args)
            elif name == "dxf_transform":
                resp = await client.post(f"{DXF_URL}/create/transform", json=args)
            elif name == "dxf_merge":
                resp = await client.post(f"{DXF_URL}/create/merge", json=args)
            elif name == "dxf_array":
                resp = await client.post(f"{DXF_URL}/create/array", json=args)
            elif name == "cam_generate":
                resp = await client.post(f"{CAM_URL}/generate", json=args)
            elif name == "catalogue_designs":
                resp = await client.get(f"{CATALOGUE_URL}/designs")
            elif name == "catalogue_tools":
                resp = await client.get(f"{CATALOGUE_URL}/tools")
            elif name == "catalogue_add_design":
                args["filename"] = os.path.basename(args.get("filename", ""))
                resp = await client.post(f"{CATALOGUE_URL}/designs", json=args)
            elif name == "catalogue_materials":
                resp = await client.get(f"{CATALOGUE_URL}/materials")
            elif name == "catalogue_fonts":
                resp = await client.get(f"{DXF_URL}/fonts")
            elif name == "machine_status":
                resp = await client.get(f"{BRIDGE_URL}/status")
            elif name == "machine_run_file":
                filename = os.path.basename(args.get("filename", ""))
                confirm = args.get("confirm", False)
                resp = await client.post(f"{BRIDGE_URL}/files/run", params={"filename": filename}, json={"confirm": confirm})
            elif name == "dxf_preview":
                filename = os.path.basename(args.get("filename", ""))
                png_name = filename.rsplit(".", 1)[0] + ".png"
                resp = await client.get(f"{DXF_URL}/preview/{filename}", timeout=30.0)
                if resp.status_code == 200:
                    url = f"{PLUGIN_BASE_URL}/files/{png_name}"
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {"content": [{"type": "text", "text": f"Preview generado. URL: {url}"}]}
                    }
                else:
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {"content": [{"type": "text", "text": f"Error al generar preview: {resp.status_code} - {resp.text}"}]}
                    }
            else:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {"code": -32601, "message": f"Unknown tool: {name}"}
                }

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"content": [{"type": "text", "text": str(resp.json())}]}
        }

    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": f"Unknown method: {method}"}
    }


@app.get("/.well-known/ai-plugin.json")
async def ai_plugin_manifest(request: Request):
    base_url = PLUGIN_BASE_URL or f"{request.url.scheme}://{request.headers.get('host')}"
    return {
        "schema_version": "v1",
        "name_for_human": PLUGIN_NAME,
        "name_for_model": "mcp_cnc_orchestrator",
        "description_for_human": PLUGIN_DESCRIPTION,
        "description_for_model": "Plugin for creating DXF designs, analyzing DXF files, and generating G-code.",
        "auth": {
            "type": "service_http",
            "authorization_type": "bearer"
        },
        "api": {
            "type": "openapi",
            "url": f"{base_url}/openapi.json",
            "is_user_authenticated": False,
        },
        "logo_url": PLUGIN_LOGO_URL,
        "contact_email": "support@example.com",
    }

@app.get("/legal")
async def legal_info():
    return {
        "legal": "Use this plugin according to your organization policies.",
        "privacy_policy": "Data exchanged is limited to CNC design operations.",
    }


WORKSPACE_DIR = os.environ.get("WORKSPACE_DIR", "/workspace")

@app.get("/files/{filename}")
async def serve_file(filename: str):
    """Serve files (DXF, PNG, G-code) from the shared workspace."""
    import mimetypes
    path = os.path.join(WORKSPACE_DIR, filename)
    if not os.path.exists(path):
        # Try fetching from dxf-engine if not local
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")
    mime, _ = mimetypes.guess_type(filename)
    mime = mime or "application/octet-stream"
    from fastapi.responses import FileResponse
    return FileResponse(path, media_type=mime, filename=filename)

@app.get("/tools", dependencies=[Depends(validate_token)])
async def tools():
    return {"available_tools": [
        "dxf_create_rectangle", "dxf_create_circle", "dxf_create_text", "dxf_create_nesting",
        "catalogue_tools", "catalogue_designs",
        "cam_generate",
        "machine_status", "machine_jog", "machine_send_gcode", "machine_spindle"
    ]}

@app.get("/catalogue/tools", tags=["catalogue"], dependencies=[Depends(validate_token)])
async def get_tools():
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{CATALOGUE_URL}/tools")
        return resp.json()

@app.get("/catalogue/designs", tags=["catalogue"], dependencies=[Depends(validate_token)])
async def get_designs():
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{CATALOGUE_URL}/designs")
        return resp.json()

@app.get("/machine/status", tags=["machine"], dependencies=[Depends(validate_token)])
async def get_status():
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BRIDGE_URL}/status")
        return resp.json()

@app.post("/machine/jog", tags=["machine"], dependencies=[Depends(validate_token)])
async def proxy_jog(params: MachineJogParams):
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BRIDGE_URL}/motion/jog", json=params.dict())
        return resp.json()

@app.post("/machine/gcode", tags=["machine"], dependencies=[Depends(validate_token)])
async def proxy_gcode(params: MachineGCodeParams):
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BRIDGE_URL}/gcode/send", json=params.dict())
        return resp.json()

@app.post("/machine/spindle", tags=["machine"], dependencies=[Depends(validate_token)])
async def proxy_spindle(params: MachineSpindleParams):
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BRIDGE_URL}/gcode/spindle", json=params.dict())
        return resp.json()

@app.post("/dxf/rectangle", tags=["dxf"], dependencies=[Depends(validate_token)])
async def proxy_rectangle(params: RectangleParams):
    payload = params.dict()
    if payload["radius"]:
        payload["r_br"] = payload["r_br"] or payload["radius"]
        payload["r_tr"] = payload["r_tr"] or payload["radius"]
        payload["r_tl"] = payload["r_tl"] or payload["radius"]
        payload["r_bl"] = payload["r_bl"] or payload["radius"]
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{DXF_URL}/create/rectangle", json=payload)
        return resp.json()

@app.post("/dxf/circle", tags=["dxf"], dependencies=[Depends(validate_token)])
async def proxy_circle(params: CircleParams):
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{DXF_URL}/create/circle", json=params.dict())
        return resp.json()

@app.post("/dxf/text", tags=["dxf"], dependencies=[Depends(validate_token)])
async def proxy_text(params: TextParams):
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{DXF_URL}/create/text", json=params.dict())
        return resp.json()

@app.post("/dxf/nesting", tags=["dxf"], dependencies=[Depends(validate_token)])
async def proxy_nesting(params: NestingParams):
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{DXF_URL}/create/nesting", json=params.dict())
        return resp.json()

@app.post("/dxf/boolean", tags=["dxf"], dependencies=[Depends(validate_token)])
async def proxy_boolean(params: BooleanParams):
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{DXF_URL}/create/boolean", json=params.dict())
        return resp.json()

@app.post("/cam/generate", tags=["cam"], dependencies=[Depends(validate_token)])
async def proxy_cam(params: CAMGenerateParams):
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{CAM_URL}/generate", json=params.dict())
        return resp.json()
