from fastapi import FastAPI, HTTPException, Request, Depends, Header
from fastapi.openapi.utils import get_openapi
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import List, Optional
import httpx
import asyncio
import os
import mimetypes

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
WORKSPACE_DIR = os.environ.get("WORKSPACE_DIR", "/workspace")


def validate_token(authorization: Optional[str] = Header(None)):
    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid Authorization header")
    token = authorization.split(" ", 1)[1]
    if token != PLUGIN_API_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")


# ---------------------------------------------------------------------------
# Tabla de rutas para batch_preview (tool_name -> (base_url, path, method))
# ---------------------------------------------------------------------------
_TOOL_ROUTES = {
    "dxf_rectangle":  (DXF_URL, "/create/rectangle",  "POST"),
    "dxf_circle":     (DXF_URL, "/create/circle",     "POST"),
    "dxf_text":       (DXF_URL, "/create/text",       "POST"),
    "dxf_nesting":    (DXF_URL, "/create/nesting",    "POST"),
    "dxf_boolean":    (DXF_URL, "/create/boolean",    "POST"),
    "dxf_polyline":   (DXF_URL, "/create/polyline",   "POST"),
    "dxf_spline":     (DXF_URL, "/create/spline",     "POST"),
    "dxf_arc":        (DXF_URL, "/create/arc",        "POST"),
    "dxf_offset":     (DXF_URL, "/create/offset",     "POST"),
    "dxf_transform":  (DXF_URL, "/create/transform",  "POST"),
    "dxf_merge":      (DXF_URL, "/create/merge",      "POST"),
    "dxf_array":      (DXF_URL, "/create/array",      "POST"),
    "dxf_fillet":        (DXF_URL, "/create/fillet",        "POST"),
    "dxf_chamfer":       (DXF_URL, "/create/chamfer",       "POST"),
    "dxf_get_bounds":    (DXF_URL, "/bounds/{filename}",     "GET"),
    "dxf_finger_joint":  (DXF_URL, "/create/finger_joint",   "POST"),
    "dxf_box":           (DXF_URL, "/create/box",            "POST"),
    "dxf_dogbones":      (DXF_URL, "/create/dogbones",       "POST"),
    "dxf_align":         (DXF_URL, "/create/align",          "POST"),
    "dxf_center":        (DXF_URL, "/create/center",         "POST"),
    "cam_generate":      (CAM_URL, "/generate",              "POST"),
    "cam_profile":    (CAM_URL, "/profile",            "POST"),
    "cam_pocket":     (CAM_URL, "/pocket",             "POST"),
    "cam_drill":      (CAM_URL, "/drill",              "POST"),
    "cam_engrave":    (CAM_URL, "/engrave",            "POST"),
}

async def _dispatch_tool(client, tool_name, tool_args):
    if tool_name not in _TOOL_ROUTES:
        raise ValueError(f"Tool not available in batch: {tool_name}")
    base, path, method = _TOOL_ROUTES[tool_name]
    if method == "POST":
        return await client.post(f"{base}{path}", json=tool_args, timeout=60.0)
    return await client.get(f"{base}{path}", params=tool_args, timeout=60.0)


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
                            "operacion": {"type": "string", "description": "union, intersection o difference."},
                            "offset_x_b": {"type": "number", "description": "Desplazamiento X de la forma B en mm."},
                            "offset_y_b": {"type": "number", "description": "Desplazamiento Y de la forma B en mm."},
                            "arc_tolerance": {"type": "number", "description": "Tolerancia de discretización de arcos en mm (defecto 0.1). Menor = más suave."}
                        }
                    }
                },
                {
                    "name": "dxf_get_bounds",
                    "description": "Devuelve el bounding box, centro y tamaño de un archivo DXF. Útil para alinear, escalar o posicionar piezas.",
                    "inputSchema": {
                        "type": "object",
                        "required": ["filename"],
                        "properties": {
                            "filename": {"type": "string", "description": "Nombre del archivo DXF en el workspace."}
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
                    "name": "dxf_fillet",
                    "description": "Aplica redondeo (fillet) con arco tangente a todas las esquinas de un DXF. Ideal para suavizar esquinas agudas antes de generar G-code.",
                    "inputSchema": {
                        "type": "object",
                        "required": ["input_filename", "output_filename", "radius"],
                        "properties": {
                            "input_filename": {"type": "string", "description": "Archivo DXF de entrada con esquinas agudas."},
                            "output_filename": {"type": "string", "description": "Archivo DXF de salida con esquinas redondeadas."},
                            "radius": {"type": "number", "description": "Radio del arco de redondeo en mm."},
                            "layer": {"type": "string"}
                        }
                    }
                },
                {
                    "name": "dxf_chamfer",
                    "description": "Aplica chaflán plano a 45° a todas las esquinas de un DXF. Usa el parámetro distance (equivalente al valor C en CAD estándar).",
                    "inputSchema": {
                        "type": "object",
                        "required": ["input_filename", "output_filename", "distance"],
                        "properties": {
                            "input_filename": {"type": "string", "description": "Archivo DXF de entrada con esquinas agudas."},
                            "output_filename": {"type": "string", "description": "Archivo DXF de salida con chaflán aplicado."},
                            "distance": {"type": "number", "description": "Distancia del chaflán en mm medida desde cada vértice."},
                            "layer": {"type": "string"}
                        }
                    }
                },
                {
                    "name": "cam_generate",
                    "description": "Genera G-code desde un archivo DXF (modo básico todo-en-uno).",
                    "inputSchema": {
                        "type": "object",
                        "required": ["dxf_filename", "output_filename", "tool_id"],
                        "properties": {
                            "dxf_filename": {"type": "string"},
                            "output_filename": {"type": "string"},
                            "tool_id": {"type": "string"},
                            "material_id": {"type": "string"},
                            "cut_depth_mm": {"type": "number"},
                            "pass_depth_mm": {"type": "number", "description": "Profundidad por pasada. Por defecto usa el valor de la herramienta."},
                            "operation": {"type": "string", "description": "profile_outside | profile_inside | pocket"},
                            "strategy": {"type": "string", "description": "conventional (defecto) | climb"},
                            "cut_side": {"type": "string", "description": "outside | inside | center"},
                            "tabs_enabled": {"type": "boolean"},
                            "tab_count": {"type": "integer"},
                            "tab_width_mm": {"type": "number"},
                            "tab_height_mm": {"type": "number"},
                            "material_thickness_mm": {"type": "number"},
                            "leadin_type": {"type": "string", "description": "none | ramp"},
                            "leadin_length_mm": {"type": "number"},
                            "feed_rate_override": {"type": "number", "description": "Sobreescribe el avance XY en mm/min."},
                            "plunge_rate_override": {"type": "number", "description": "Sobreescribe el avance Z en mm/min."},
                            "safe_z_mm": {"type": "number", "description": "Altura de seguridad Z en mm."},
                            "finish_pass_offset": {"type": "number", "description": "Dejar este stock (mm) para pasada de acabado. 0 = sin acabado."}
                        }
                    }
                },
                {
                    "name": "cam_profile",
                    "description": "Genera G-code de perfilado (contorno) de un DXF. Permite elegir lado de corte, estrategia climb/conventional, tabs y lead-in.",
                    "inputSchema": {
                        "type": "object",
                        "required": ["dxf_filename", "output_filename", "tool_id"],
                        "properties": {
                            "dxf_filename": {"type": "string"},
                            "output_filename": {"type": "string"},
                            "tool_id": {"type": "string"},
                            "material_id": {"type": "string"},
                            "cut_depth_mm": {"type": "number", "description": "Profundidad total de corte en mm."},
                            "pass_depth_mm": {"type": "number", "description": "Profundidad por pasada. Por defecto usa el valor de la herramienta."},
                            "cut_side": {"type": "string", "description": "outside (defecto) | inside | center"},
                            "strategy": {"type": "string", "description": "conventional (defecto) | climb"},
                            "tabs_enabled": {"type": "boolean"},
                            "tab_count": {"type": "integer"},
                            "tab_width_mm": {"type": "number"},
                            "tab_height_mm": {"type": "number"},
                            "material_thickness_mm": {"type": "number"},
                            "leadin_type": {"type": "string", "description": "none | ramp"},
                            "leadin_length_mm": {"type": "number"},
                            "feed_rate_override": {"type": "number"},
                            "plunge_rate_override": {"type": "number"},
                            "safe_z_mm": {"type": "number"},
                            "finish_pass_offset": {"type": "number", "description": "Stock a dejar para pasada de acabado (mm). 0 = sin acabado."},
                            "cutter_comp": {"type": "string", "description": "Compensación de radio en controlador: 'none' (defecto, Python compensa) | 'left' (G41) | 'right' (G42)."}
                        }
                    }
                },
                {
                    "name": "cam_pocket",
                    "description": "Genera G-code de vaciado (pocket) de un DXF con stepover configurable y pasada de acabado opcional.",
                    "inputSchema": {
                        "type": "object",
                        "required": ["dxf_filename", "output_filename", "tool_id"],
                        "properties": {
                            "dxf_filename": {"type": "string"},
                            "output_filename": {"type": "string"},
                            "tool_id": {"type": "string"},
                            "material_id": {"type": "string"},
                            "cut_depth_mm": {"type": "number"},
                            "pass_depth_mm": {"type": "number"},
                            "stepover_pct": {"type": "number", "description": "Fracción del diámetro de la herramienta para el stepover lateral (defecto 0.4)."},
                            "finish_pass": {"type": "boolean", "description": "Añadir pasada de acabado en contorno interior (defecto true)."},
                            "feed_rate_override": {"type": "number"},
                            "plunge_rate_override": {"type": "number"},
                            "safe_z_mm": {"type": "number"}
                        }
                    }
                },
                {
                    "name": "cam_drill",
                    "description": "Genera G-code de taladrado para todos los círculos del DXF. Soporta peck drilling y dwell.",
                    "inputSchema": {
                        "type": "object",
                        "required": ["dxf_filename", "output_filename", "tool_id"],
                        "properties": {
                            "dxf_filename": {"type": "string"},
                            "output_filename": {"type": "string"},
                            "tool_id": {"type": "string"},
                            "material_id": {"type": "string"},
                            "drill_depth_mm": {"type": "number", "description": "Profundidad de taladrado en mm."},
                            "peck_depth_mm": {"type": "number", "description": "Profundidad de pico por ciclo. 0 = plunge directo."},
                            "dwell_ms": {"type": "integer", "description": "Tiempo de pausa al fondo del taladro en milisegundos (G4)."},
                            "feed_rate_override": {"type": "number"},
                            "safe_z_mm": {"type": "number"}
                        }
                    }
                },
                {
                    "name": "cam_engrave",
                    "description": "Genera G-code de grabado superficial siguiendo todas las líneas y curvas del DXF a una profundidad fija.",
                    "inputSchema": {
                        "type": "object",
                        "required": ["dxf_filename", "output_filename", "tool_id"],
                        "properties": {
                            "dxf_filename": {"type": "string"},
                            "output_filename": {"type": "string"},
                            "tool_id": {"type": "string"},
                            "material_id": {"type": "string"},
                            "cut_depth_mm": {"type": "number", "description": "Profundidad de grabado (defecto 0.5 mm)."},
                            "feed_rate_override": {"type": "number"},
                            "plunge_rate_override": {"type": "number"},
                            "safe_z_mm": {"type": "number"}
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
                    "name": "dxf_finger_joint",
                    "description": "Genera un panel rectangular DXF con una unión de dientes (finger joint / box joint) en uno de sus lados. Los dientes se extruden FUERA del bounding box nominal por 'thickness' mm. Genera la pieza lista para corte CNC plano.",
                    "inputSchema": {
                        "type": "object",
                        "required": ["output_filename", "panel_width", "panel_height", "thickness"],
                        "properties": {
                            "output_filename": {"type": "string"},
                            "panel_width": {"type": "number", "description": "Ancho nominal del panel en mm."},
                            "panel_height": {"type": "number", "description": "Alto nominal del panel en mm."},
                            "thickness": {"type": "number", "description": "Grosor del material en mm. Determina la profundidad de los dientes."},
                            "finger_width": {"type": "number", "description": "Ancho de cada diente en mm (defecto = thickness)."},
                            "side": {"type": "string", "description": "'a' = empieza con diente (defecto), 'b' = complementario (empieza con hueco). Usar 'a' en un panel y 'b' en el panel que encaja."},
                            "edge": {"type": "string", "description": "Lado que recibe los dientes: 'bottom' | 'top' | 'left' | 'right' (defecto: 'bottom')."},
                            "layer": {"type": "string"}
                        }
                    }
                },
                {
                    "name": "dxf_box",
                    "description": "Genera en un solo DXF todas las piezas de una caja rectangular con unión por dientes (finger joint). Incluye frente, fondo-trasero, laterales y base opcional. Las piezas se colocan planas para corte CNC directo.",
                    "inputSchema": {
                        "type": "object",
                        "required": ["output_filename", "box_width", "box_height", "box_depth", "thickness"],
                        "properties": {
                            "output_filename": {"type": "string"},
                            "box_width": {"type": "number", "description": "Dimensión de la caja en X (ancho) en mm."},
                            "box_height": {"type": "number", "description": "Dimensión de la caja en Z (alto) en mm."},
                            "box_depth": {"type": "number", "description": "Dimensión de la caja en Y (profundidad) en mm."},
                            "thickness": {"type": "number", "description": "Grosor del material en mm."},
                            "finger_width": {"type": "number", "description": "Ancho de cada diente en mm (defecto = thickness)."},
                            "include_bottom": {"type": "boolean", "description": "Si true (defecto), incluye la pieza de fondo de la caja."},
                            "layer": {"type": "string"}
                        }
                    }
                },
                {
                    "name": "dxf_dogbones",
                    "description": "Añade 'huesos de perro' (dogbone cutouts) en las esquinas interiores cóncavas de perfiles LWPOLYLINE. Imprescindible para que piezas con finger joints encajen físicamente al cortarlas con una fresa cilíndrica. El círculo tiene radio = bit_diameter/2 y se coloca a lo largo de la bisectriz de cada esquina interior.",
                    "inputSchema": {
                        "type": "object",
                        "required": ["input_filename", "output_filename", "bit_diameter"],
                        "properties": {
                            "input_filename": {"type": "string", "description": "Archivo DXF de entrada con el perfil."},
                            "output_filename": {"type": "string", "description": "Archivo DXF de salida con los dogbones añadidos."},
                            "bit_diameter": {"type": "number", "description": "Diámetro de la fresa en mm (ej: 6 para fresa de 6mm)."},
                            "corner_type": {"type": "string", "description": "'round' (dogbone clásico diagonal, defecto) | 'tbone' (T-bone, círculo a lo largo de un borde, menos visible)."},
                            "layer": {"type": "string"}
                        }
                    }
                },
                {
                    "name": "dxf_align",
                    "description": "Traslada un DXF para alinear un punto de anclaje con una coordenada o con el bounding box de otro archivo de referencia. Ejemplo: 'pon el borde izquierdo de B pegado al borde derecho de A'. Permite offset adicional tras la alineación.",
                    "inputSchema": {
                        "type": "object",
                        "required": ["input_filename", "output_filename"],
                        "properties": {
                            "input_filename": {"type": "string", "description": "DXF a mover."},
                            "output_filename": {"type": "string", "description": "DXF resultado."},
                            "anchor_x": {"type": "string", "description": "Qué punto del input usar en X: 'left' | 'center' | 'right'."},
                            "anchor_y": {"type": "string", "description": "Qué punto del input usar en Y: 'bottom' | 'center' | 'top'."},
                            "target_x": {"type": "number", "description": "Coordenada X absoluta donde colocar el anchor."},
                            "target_y": {"type": "number", "description": "Coordenada Y absoluta donde colocar el anchor."},
                            "ref_filename": {"type": "string", "description": "Si se indica, el target se calcula desde este archivo."},
                            "ref_anchor_x": {"type": "string", "description": "Qué punto del ref usar como target en X: 'left' | 'center' | 'right'."},
                            "ref_anchor_y": {"type": "string", "description": "Qué punto del ref usar como target en Y: 'bottom' | 'center' | 'top'."},
                            "offset_x": {"type": "number", "description": "Offset adicional en X tras la alineación (mm, defecto 0)."},
                            "offset_y": {"type": "number", "description": "Offset adicional en Y tras la alineación (mm, defecto 0)."}
                        }
                    }
                },
                {
                    "name": "dxf_center",
                    "description": "Centra un DXF en unas coordenadas absolutas o en el centro del bounding box de otro DXF. Util para colocar piezas sin calcular offsets manualmente.",
                    "inputSchema": {
                        "type": "object",
                        "required": ["input_filename", "output_filename"],
                        "properties": {
                            "input_filename": {"type": "string", "description": "DXF a centrar."},
                            "output_filename": {"type": "string", "description": "DXF resultado."},
                            "target_x": {"type": "number", "description": "Coordenada X absoluta del centro destino si no se usa ref_filename."},
                            "target_y": {"type": "number", "description": "Coordenada Y absoluta del centro destino si no se usa ref_filename."},
                            "ref_filename": {"type": "string", "description": "Archivo DXF de referencia para centrar respecto a su bounding box."},
                            "offset_x": {"type": "number", "description": "Offset adicional en X tras centrar."},
                            "offset_y": {"type": "number", "description": "Offset adicional en Y tras centrar."}
                        }
                    }
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
                },
                {
                    "name": "batch_preview",
                    "description": "Ejecuta una lista de trabajos DXF en secuencia. Cada trabajo tiene una descripción legible y uno o varios pasos (herramientas encadenadas). Al terminar devuelve una tabla Markdown con descripción, estado (✅/❌) y URL del PNG para validar visualmente cada resultado.",
                    "inputSchema": {
                        "type": "object",
                        "required": ["jobs"],
                        "properties": {
                            "jobs": {
                                "type": "array",
                                "description": "Lista de trabajos a ejecutar en orden.",
                                "items": {
                                    "type": "object",
                                    "required": ["description", "steps", "preview_filename"],
                                    "properties": {
                                        "description": {"type": "string", "description": "Descripción legible del trabajo (ej: 'Rectángulo 100x50 con fillet 5mm')."},
                                        "preview_filename": {"type": "string", "description": "Nombre del archivo DXF final a previsualizar (ej: 'pieza.dxf')."},
                                        "steps": {
                                            "type": "array",
                                            "description": "Pasos encadenados del trabajo. Cada paso es una llamada a una herramienta DXF o CAM.",
                                            "items": {
                                                "type": "object",
                                                "required": ["tool"],
                                                "properties": {
                                                    "tool": {"type": "string", "description": "Nombre de la herramienta (ej: dxf_rectangle, dxf_fillet, cam_profile)."},
                                                    "args": {"type": "object", "description": "Argumentos opcionales de la herramienta. Si se omite, la herramienta se ejecuta con un objeto vacio."}
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                {
                    "name": "machine_simulate",
                    "description": "Devuelve la URL para visualizar la simulación 3D de un archivo G-code en la máquina Elephant. Útil para validar trayectorias antes del corte.",
                    "inputSchema": {
                        "type": "object",
                        "required": ["filename"],
                        "properties": {
                            "filename": {"type": "string", "description": "Nombre del archivo G-code (.nc, .ngc, .tap) a simular."}
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
                # Accept 'columns' as alias for 'cols'
                if "columns" in args and "cols" not in args:
                    args["cols"] = args.pop("columns")
                resp = await client.post(f"{DXF_URL}/create/array", json=args)
            elif name == "dxf_fillet":
                resp = await client.post(f"{DXF_URL}/create/fillet", json=args)
            elif name == "dxf_chamfer":
                resp = await client.post(f"{DXF_URL}/create/chamfer", json=args)
            elif name == "dxf_finger_joint":
                resp = await client.post(f"{DXF_URL}/create/finger_joint", json=args)
            elif name == "dxf_box":
                resp = await client.post(f"{DXF_URL}/create/box", json=args)
            elif name == "dxf_dogbones":
                resp = await client.post(f"{DXF_URL}/create/dogbones", json=args)
            elif name == "dxf_align":
                resp = await client.post(f"{DXF_URL}/create/align", json=args)
            elif name == "dxf_center":
                resp = await client.post(f"{DXF_URL}/create/center", json=args)
            elif name == "dxf_get_bounds":
                filename = os.path.basename(args.get("filename", ""))
                resp = await client.get(f"{DXF_URL}/bounds/{filename}")
            elif name == "cam_generate":
                resp = await client.post(f"{CAM_URL}/generate", json=args)
            elif name == "cam_profile":
                resp = await client.post(f"{CAM_URL}/profile", json=args)
            elif name == "cam_pocket":
                resp = await client.post(f"{CAM_URL}/pocket", json=args)
            elif name == "cam_drill":
                resp = await client.post(f"{CAM_URL}/drill", json=args)
            elif name == "cam_engrave":
                resp = await client.post(f"{CAM_URL}/engrave", json=args)
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
                if not filename or not filename.lower().endswith(".dxf"):
                    return {
                        "jsonrpc": "2.0", "id": request_id,
                        "result": {"content": [{"type": "text", "text": "Error: 'filename' debe ser un archivo .dxf (ej: 'pieza.dxf'). No incluyas rutas."}]}
                    }
                png_name = filename.rsplit(".", 1)[0] + ".png"
                last_err = None
                for attempt in range(3):
                    try:
                        preview_resp = await client.get(f"{DXF_URL}/preview/{filename}", timeout=30.0)
                        if preview_resp.status_code == 200:
                            url = f"{PLUGIN_BASE_URL}/files/{png_name}"
                            return {
                                "jsonrpc": "2.0", "id": request_id,
                                "result": {"content": [{"type": "text", "text": f"Preview generado. URL: {url}"}]}
                            }
                        elif preview_resp.status_code == 404:
                            return {
                                "jsonrpc": "2.0", "id": request_id,
                                "result": {"content": [{"type": "text", "text": f"Archivo '{filename}' no encontrado en el workspace. Usa workspace_list para ver los archivos disponibles."}]}
                            }
                        else:
                            last_err = f"HTTP {preview_resp.status_code}: {preview_resp.text[:300]}"
                    except Exception as e:
                        last_err = str(e)
                    if attempt < 2:
                        await asyncio.sleep(1.5)
                return {
                    "jsonrpc": "2.0", "id": request_id,
                    "result": {"content": [{"type": "text", "text": f"Error al generar preview de '{filename}' tras 3 intentos. Último error: {last_err}"}]}
                }
            elif name == "batch_preview":
                jobs = args.get("jobs", [])
                results = []
                for i, job in enumerate(jobs):
                    desc = job.get("description", f"Job {i+1}")
                    steps = job.get("steps", [])
                    preview_file = os.path.basename(job.get("preview_filename", ""))
                    job_ok = True
                    error_msg = ""
                    # Ejecutar cada paso en orden
                    for step in steps:
                        tool_name = step.get("tool", "")
                        tool_args = step.get("args", {})
                        try:
                            step_resp = await _dispatch_tool(client, tool_name, tool_args)
                            if step_resp.status_code >= 400:
                                job_ok = False
                                error_msg = step_resp.text[:300]
                                break
                        except ValueError as ve:
                            job_ok = False
                            error_msg = str(ve)
                            break
                        except Exception as e:
                            job_ok = False
                            error_msg = str(e)[:300]
                            break
                    # Generar preview del DXF final
                    png_url = ""
                    if job_ok and preview_file:
                        try:
                            prev = await client.get(f"{DXF_URL}/preview/{preview_file}", timeout=30.0)
                            if prev.status_code == 200:
                                png_name = preview_file.rsplit(".", 1)[0] + ".png"
                                png_url = f"{PLUGIN_BASE_URL}/files/{png_name}"
                            else:
                                job_ok = False
                                error_msg = f"Preview HTTP {prev.status_code}"
                        except Exception as e:
                            error_msg = f"Preview error: {e}"
                    results.append({"index": i + 1, "description": desc,
                                    "ok": job_ok, "error": error_msg, "png_url": png_url})
                # Tabla Markdown
                table = "| # | Descripcion | Estado | Vista previa |\n"
                table += "|---|-------------|--------|--------------|\n"
                for r in results:
                    status = "OK" if r["ok"] else f"FAIL `{r['error']}`"
                    preview = f"[ver PNG]({r['png_url']})" if r["png_url"] else "-"
                    table += f"| {r['index']} | {r['description']} | {status} | {preview} |\n"
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"content": [{"type": "text", "text": table}]}
                }
            elif name == "machine_simulate":
                filename = os.path.basename(args.get("filename", ""))
                if not filename:
                    return {
                        "jsonrpc": "2.0", "id": request_id,
                        "error": {"code": -32602, "message": "Falta el parámetro 'filename'"}
                    }
                file_path = os.path.join(WORKSPACE_DIR, filename)
                if not os.path.isfile(file_path):
                    return {
                        "jsonrpc": "2.0", "id": request_id,
                        "error": {"code": -32602, "message": f"Archivo no encontrado: {filename}"}
                    }
                # La URL apunta al nuevo servicio de visualización configurado en Caddy
                sim_url = f"{PLUGIN_BASE_URL}/visualizer/?gcode={filename}"
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"content": [{"type": "text", "text": f"Simulación 3D lista: {sim_url}"}]}
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


@app.get("/files/{filename}")
async def serve_file(filename: str):
    """Proxy file requests to dxf-engine which holds the workspace volume."""
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(f"{DXF_URL}/files/{filename}", timeout=15.0)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Could not reach dxf-engine: {e}")
    if resp.status_code == 404:
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    from fastapi.responses import Response
    mime, _ = mimetypes.guess_type(filename)
    mime = mime or "application/octet-stream"
    return Response(content=resp.content, media_type=mime,
                    headers={"Content-Disposition": f'inline; filename="{filename}"'})

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

@app.get("/machine/health", tags=["machine"], dependencies=[Depends(validate_token)])
async def get_machine_health():
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BRIDGE_URL}/health", timeout=15.0)
        return resp.json()

@app.get("/machine/status", tags=["machine"], dependencies=[Depends(validate_token)])
async def get_status():
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BRIDGE_URL}/status", timeout=10.0)
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

@app.get("/workspace/files", tags=["workspace"], dependencies=[Depends(validate_token)])
async def list_workspace_files():
    try:
        names = os.listdir(WORKSPACE_DIR)
    except OSError:
        names = []
    result = []
    for name in sorted(names):
        path = os.path.join(WORKSPACE_DIR, name)
        try:
            st = os.stat(path)
            result.append({"name": name, "size": st.st_size, "modified": st.st_mtime})
        except OSError:
            pass
    return {"files": result}
