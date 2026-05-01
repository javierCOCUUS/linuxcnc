import os
import json
import re
import shutil
import hashlib
from pathlib import Path
import ezdxf
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.staticfiles import StaticFiles
from mcp.server import Server
from mcp.server.sse import SseServerTransport
from mcp.server.models import InitializationOptions
import mcp
import mcp.types as types

# Imports de nuestros agentes desarrollados
from .motor_transformacion import transformar_dxf
from .generador_cam import GeneradorCAM
from .visor import renderizar_dxf_a_png
from .generador_dxf import generate_parametric_circle, generate_parametric_rectangle, generate_parametric_concentric_circles, merge_dxf_assembly, boolean_dxf_operation, generate_cad_text

BASE_DIR = Path(__file__).resolve().parent
OUTPUTS_DIR = BASE_DIR / "outputs"
LIBRARY_DIR = BASE_DIR / "libreria_dxf"
IMPORTS_DIR = BASE_DIR / "imports"
CATALOG_PATH = BASE_DIR / "catalogo.json"
TOOLS_PATH = BASE_DIR / "herramientas.json"
PUBLIC_ROUTE_PREFIX = os.getenv("CNC_MCP_PUBLIC_ROUTE_PREFIX", "/mcp-cnc").rstrip("/") or ""
PUBLIC_OUTPUT_BASE_URL = os.getenv(
    "CNC_MCP_PUBLIC_BASE_URL",
    f"{PUBLIC_ROUTE_PREFIX}/outputs" if PUBLIC_ROUTE_PREFIX else "/outputs",
)
PUBLIC_MESSAGES_PATH = os.getenv(
    "CNC_MCP_PUBLIC_MESSAGES_PATH",
    f"{PUBLIC_ROUTE_PREFIX}/messages" if PUBLIC_ROUTE_PREFIX else "/messages",
)
SAFE_FILE_STEM_RE = re.compile(r"^[A-Za-z0-9._-]+$")
SAFE_DESIGN_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
CAM_OPERATION_PRESETS = {
    "profile_standard": {
        "description": "Perfil exterior est├índar sin tabs, usando la pasada m├íxima sugerida por la herramienta.",
        "category": "general",
        "operation": "profile_outside",
        "cut_depth_mm": 5.0,
        "material_thickness_mm": 5.0,
        "tabs_enabled": False,
        "safe_z_mm": 5.0,
    },
    "profile_with_tabs": {
        "description": "Perfil exterior con tabs para piezas que podr├¡an soltarse en la ├║ltima pasada.",
        "category": "general",
        "operation": "profile_outside",
        "cut_depth_mm": 5.0,
        "material_thickness_mm": 5.0,
        "tabs_enabled": True,
        "tab_width_mm": 6.0,
        "tab_height_mm": 2.0,
        "tab_count": 4,
        "safe_z_mm": 5.0,
    },
    "profile_inside_standard": {
        "description": "Perfil interior est├índar para agujeros o ventanas cerradas.",
        "category": "general",
        "operation": "profile_inside",
        "cut_depth_mm": 5.0,
        "material_thickness_mm": 5.0,
        "tabs_enabled": False,
        "safe_z_mm": 5.0,
    },
    "pocket_standard": {
        "description": "Vaciado est├índar por offsets internos sin tabs.",
        "category": "general",
        "operation": "pocket",
        "cut_depth_mm": 3.0,
        "material_thickness_mm": 3.0,
        "tabs_enabled": False,
        "safe_z_mm": 5.0,
    },
    "mdf_3mm_profile": {
        "description": "Corte exterior base para MDF fino de 3 mm, sin tabs.",
        "category": "material:mdf",
        "operation": "profile_outside",
        "cut_depth_mm": 3.0,
        "material_thickness_mm": 3.0,
        "tabs_enabled": False,
        "safe_z_mm": 5.0,
    },
    "plywood_15mm_tabs": {
        "description": "Perfil exterior base para contrachapado de 15 mm con tabs de retenci├│n.",
        "category": "material:plywood",
        "operation": "profile_outside",
        "cut_depth_mm": 15.0,
        "material_thickness_mm": 15.0,
        "tabs_enabled": True,
        "tab_width_mm": 8.0,
        "tab_height_mm": 3.0,
        "tab_count": 6,
        "safe_z_mm": 8.0,
    },
    "acrylic_3mm_profile": {
        "description": "Perfil exterior conservador para acr├¡lico de 3 mm.",
        "category": "material:acrylic",
        "operation": "profile_outside",
        "cut_depth_mm": 3.0,
        "material_thickness_mm": 3.0,
        "pass_depth_mm": 1.0,
        "tabs_enabled": False,
        "safe_z_mm": 5.0,
    },
    "aluminum_soft_2mm_profile": {
        "description": "Perfil exterior conservador para aluminio blando de 2 mm.",
        "category": "material:aluminum",
        "operation": "profile_outside",
        "cut_depth_mm": 2.0,
        "material_thickness_mm": 2.0,
        "pass_depth_mm": 0.5,
        "tabs_enabled": False,
        "safe_z_mm": 5.0,
    },
    "sign_pocket_mdf": {
        "description": "Vaciado base para rotulaci├│n o letras en MDF.",
        "category": "workflow:signage",
        "operation": "pocket",
        "cut_depth_mm": 2.5,
        "material_thickness_mm": 2.5,
        "pass_depth_mm": 1.0,
        "tabs_enabled": False,
        "safe_z_mm": 5.0,
    },
}


def ensure_runtime_dirs() -> None:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    IMPORTS_DIR.mkdir(parents=True, exist_ok=True)


def configured_external_dirs() -> list[Path]:
    raw = os.getenv("CNC_MCP_ALLOWED_EXTERNAL_DIRS", "")
    dirs: list[Path] = []
    for item in raw.split(os.pathsep):
        item = item.strip()
        if item:
            dirs.append(Path(item).expanduser().resolve())
    return dirs


def allowed_input_dirs() -> list[Path]:
    return [BASE_DIR.resolve(), OUTPUTS_DIR.resolve(), LIBRARY_DIR.resolve(), IMPORTS_DIR.resolve(), *configured_external_dirs()]


def is_within_directory(path: Path, directory: Path) -> bool:
    try:
        path.resolve().relative_to(directory.resolve())
        return True
    except ValueError:
        return False


def validate_design_id(value: str) -> str:
    if not value or not SAFE_DESIGN_ID_RE.fullmatch(value):
        raise ValueError("design_id inv├ílido. Usa solo letras, n├║meros, punto, guion o guion bajo.")
    return value


def normalize_catalog_name(value: str) -> str:
    return " ".join((value or "").strip().lower().split())


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def dxf_geometry_signature(path: Path) -> str:
    try:
        doc = ezdxf.readfile(str(path))
        msp = doc.modelspace()
        tokens: list[str] = []

        for entity in msp:
            entity_type = entity.dxftype()
            if entity_type == "LWPOLYLINE":
                pts = [f"{round(p[0], 4)}:{round(p[1], 4)}" for p in entity.get_points()]
                tokens.append(f"LWPOLYLINE|{'|'.join(pts)}")
            elif entity_type == "CIRCLE":
                center = entity.dxf.center
                tokens.append(
                    f"CIRCLE|{round(center.x, 4)}|{round(center.y, 4)}|{round(entity.dxf.radius, 4)}"
                )
            elif entity_type == "ARC":
                center = entity.dxf.center
                tokens.append(
                    "ARC|"
                    f"{round(center.x, 4)}|{round(center.y, 4)}|{round(entity.dxf.radius, 4)}|"
                    f"{round(entity.dxf.start_angle, 4)}|{round(entity.dxf.end_angle, 4)}"
                )
            elif entity_type == "LINE":
                start = entity.dxf.start
                end = entity.dxf.end
                tokens.append(
                    f"LINE|{round(start.x, 4)}|{round(start.y, 4)}|{round(end.x, 4)}|{round(end.y, 4)}"
                )

        canonical = "\n".join(sorted(tokens))
        if canonical:
            return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    except Exception:
        pass

    return file_sha256(path)


def load_catalog() -> dict:
    if not CATALOG_PATH.exists():
        return {"piezas": []}
    with CATALOG_PATH.open("r", encoding="utf-8") as stream:
        return json.load(stream)


def save_catalog(catalog: dict) -> None:
    with CATALOG_PATH.open("w", encoding="utf-8") as stream:
        json.dump(catalog, stream, indent=4, ensure_ascii=False)


def resolve_catalog_item_path(item: dict) -> Path | None:
    ruta = item.get("ruta")
    if not ruta:
        return None
    try:
        return resolve_input_dxf_path(ruta)
    except ValueError:
        return None


def find_catalog_duplicate(catalog: dict, design_id: str, display_name: str, geometry_signature: str) -> str | None:
    target_name = normalize_catalog_name(display_name)

    for item in catalog.get("piezas", []):
        if item.get("id") == design_id:
            return f"El cat├ílogo ya contiene el id {design_id}."

        existing_name = normalize_catalog_name(item.get("nombre") or item.get("id") or "")
        if target_name and existing_name == target_name:
            return f"Ya existe una pieza con el nombre '{display_name}'."

        existing_signature = item.get("geometry_signature")
        if not existing_signature:
            existing_path = resolve_catalog_item_path(item)
            if existing_path and existing_path.exists():
                existing_signature = dxf_geometry_signature(existing_path)
                item["geometry_signature"] = existing_signature

        if geometry_signature and existing_signature == geometry_signature:
            return f"La geometr├¡a ya existe en el cat├ílogo bajo el id {item.get('id')}."

    return None


def list_importable_dxfs() -> list[dict]:
    ensure_runtime_dirs()
    results = []
    for path in sorted(IMPORTS_DIR.glob("*.dxf")):
        results.append(
            {
                "filename": path.name,
                "path": str(path.relative_to(BASE_DIR)),
                "size_bytes": path.stat().st_size,
            }
        )
    return results


def summarize_catalog(catalog: dict) -> dict:
    piezas = catalog.get("piezas", [])
    items = []
    for item in piezas:
        items.append(
            {
                "id": item.get("id"),
                "nombre": item.get("nombre") or item.get("id"),
                "descripcion": item.get("descripcion", ""),
                "ruta": item.get("ruta"),
                "origen": item.get("source_filename"),
            }
        )

    return {
        "total": len(items),
        "items": items,
        "hint": "Usa design_id para prepare_and_cut o add_to_catalog/import_from_inbox_to_catalog para ampliar el cat├ílogo.",
    }


def summarize_tool_catalog(tool_catalog: dict) -> dict:
    tools = tool_catalog.get("tools", [])
    items = []
    groups: dict[str, int] = {}
    operation_types: dict[str, int] = {}

    for tool in tools:
        group = tool.get("aspire_group") or tool.get("tool_type") or "unknown"
        groups[group] = groups.get(group, 0) + 1

        for operation in tool.get("operation_types", []):
            operation_types[operation] = operation_types.get(operation, 0) + 1

        items.append(
            {
                "id": tool.get("id"),
                "display_name": tool.get("display_name") or tool.get("id"),
                "tool_type": tool.get("tool_type"),
                "group": group,
                "diameter_mm": tool.get("diameter_mm"),
                "tool_number": tool.get("tool_number"),
                "rpm_recommend": tool.get("rpm_recommend"),
                "feed_mm_min": tool.get("feed_recommend_mm_per_min"),
                "plunge_mm_min": tool.get("plunge_recommend_mm_per_min"),
                "stepdown_mm": tool.get("stepdown_mm"),
                "operation_types": tool.get("operation_types", []),
            }
        )

    return {
        "catalog_version": tool_catalog.get("catalog_version"),
        "source": tool_catalog.get("source"),
        "generated_at": tool_catalog.get("generated_at"),
        "total": len(items),
        "groups": groups,
        "operation_types": operation_types,
        "items": items,
        "hint": "Usa tool_id exacto o parte del display_name para seleccionar herramienta en prepare_and_cut o prepare_external_dxf_cut.",
    }


def summarize_cam_presets() -> dict:
    items = []
    for preset_id, preset in CAM_OPERATION_PRESETS.items():
        items.append(
            {
                "id": preset_id,
                "category": preset.get("category", "general"),
                "description": preset.get("description"),
                "operation": preset.get("operation"),
                "cut_depth_mm": preset.get("cut_depth_mm"),
                "pass_depth_mm": preset.get("pass_depth_mm"),
                "material_thickness_mm": preset.get("material_thickness_mm"),
                "tabs_enabled": preset.get("tabs_enabled"),
            }
        )

    return {"total": len(items), "items": items}


def derive_design_id_from_filename(filename: str) -> str:
    stem = Path(filename).stem.strip().lower()
    stem = re.sub(r"[^a-z0-9._-]+", "_", stem)
    stem = stem.strip("._-")
    if not stem:
        raise ValueError("No se pudo derivar un design_id v├ílido desde el nombre del archivo.")
    return validate_design_id(stem)


def derive_display_name_from_filename(filename: str) -> str:
    stem = Path(filename).stem.replace("_", " ").replace("-", " ").strip()
    return stem.title() if stem else Path(filename).stem


def import_design_to_catalog(
    archivo_dxf: Path,
    design_id: str,
    display_name: str,
    description: str,
    *,
    delete_source: bool = False,
) -> str:
    ensure_runtime_dirs()

    if not archivo_dxf.exists():
        raise ValueError("El archivo a catalogar no existe.")

    design_id = validate_design_id(design_id)
    display_name = (display_name or design_id).strip()
    description = (description or "").strip()

    if not display_name:
        raise ValueError("El nombre visible no puede estar vac├¡o.")
    if not description:
        raise ValueError("La descripci├│n no puede estar vac├¡a.")

    dest = LIBRARY_DIR / f"{design_id}.dxf"
    if dest.exists():
        raise ValueError(f"Ya existe una pieza catalogada con el id {design_id}.")

    catalog = load_catalog()
    geometry_signature = dxf_geometry_signature(archivo_dxf)
    duplicate_message = find_catalog_duplicate(catalog, design_id, display_name, geometry_signature)
    if duplicate_message:
        raise ValueError(duplicate_message)

    shutil.copy(str(archivo_dxf), str(dest))
    catalog["piezas"].append(
        {
            "id": design_id,
            "nombre": display_name,
            "descripcion": description,
            "ruta": str(dest.relative_to(BASE_DIR)),
            "geometry_signature": geometry_signature,
            "source_filename": archivo_dxf.name,
        }
    )
    save_catalog(catalog)

    if delete_source and is_within_directory(archivo_dxf, IMPORTS_DIR.resolve()):
        archivo_dxf.unlink(missing_ok=True)

    return f"Guardado Permanente exitoso. Pieza archivada como {design_id} ({display_name}) y DXF custodiado en {dest}"


def resolve_cam_preset(preset_id: str | None) -> dict:
    preset_key = (preset_id or "profile_standard").strip()
    preset = CAM_OPERATION_PRESETS.get(preset_key)
    if not preset:
        raise ValueError(f"Preset CAM desconocido: {preset_key}")
    return {"id": preset_key, **preset}


def build_cam_config(arguments: dict, cam: GeneradorCAM, default_preset_id: str = "profile_standard") -> dict:
    preset = resolve_cam_preset(arguments.get("cam_preset_id") or default_preset_id)
    config = {key: value for key, value in preset.items() if key not in {"id", "description"}}

    override_keys = [
        "operation",
        "cut_depth_mm",
        "pass_depth_mm",
        "material_thickness_mm",
        "rotation_degrees",
        "tabs_enabled",
        "tab_width_mm",
        "tab_height_mm",
        "tab_count",
        "safe_z_mm",
        "start_x_mm",
        "start_y_mm",
    ]
    for key in override_keys:
        value = arguments.get(key)
        if value is not None:
            config[key] = value

    config["pass_depth_mm"] = float(config.get("pass_depth_mm") or cam.step_z)
    if "cut_depth_mm" in config:
        config["cut_depth_mm"] = float(config["cut_depth_mm"])
    if "material_thickness_mm" in config:
        config["material_thickness_mm"] = float(config["material_thickness_mm"])
    elif "cut_depth_mm" in config:
        config["material_thickness_mm"] = abs(float(config["cut_depth_mm"]))

    if "cut_depth_mm" not in config:
        raise ValueError("Falta cut_depth_mm. Define un preset que lo aporte o p├ísalo expl├¡citamente.")

    return config


def sanitize_output_filename(name: str, required_suffix: str = ".dxf") -> str:
    if not name or not str(name).strip():
        raise ValueError("Nombre de archivo de salida vac├¡o.")

    path = Path(str(name).strip())
    filename = path.name
    stem = Path(filename).stem
    suffix = Path(filename).suffix.lower()

    if not SAFE_FILE_STEM_RE.fullmatch(stem):
        raise ValueError("Nombre de archivo inv├ílido. Usa solo letras, n├║meros, punto, guion o guion bajo.")

    if suffix and suffix != required_suffix:
        raise ValueError(f"La salida debe usar la extensi├│n {required_suffix}.")

    return f"{stem}{suffix or required_suffix}"


def resolve_output_path(name: str, required_suffix: str = ".dxf") -> Path:
    return OUTPUTS_DIR / sanitize_output_filename(name, required_suffix)


def resolve_input_dxf_path(name: str) -> Path:
    if not name or not str(name).strip():
        raise ValueError("Ruta DXF vac├¡a.")

    raw_path = Path(str(name).strip())
    suffix = raw_path.suffix.lower()
    if suffix != ".dxf":
        raise ValueError("Solo se aceptan archivos .dxf.")

    if raw_path.is_absolute():
        resolved = raw_path.expanduser().resolve()
        if not any(is_within_directory(resolved, base_dir) for base_dir in allowed_input_dirs()):
            raise ValueError(
                "La ruta absoluta est├í fuera de los directorios permitidos. "
                "Configura CNC_MCP_ALLOWED_EXTERNAL_DIRS si necesitas importar desde un volumen externo."
            )
        return resolved

    candidate = (BASE_DIR / raw_path).resolve()
    if is_within_directory(candidate, BASE_DIR.resolve()) and candidate.exists():
        return candidate

    import_candidate = (IMPORTS_DIR / raw_path.name).resolve()
    if is_within_directory(import_candidate, IMPORTS_DIR.resolve()) and import_candidate.exists():
        return import_candidate

    library_candidate = (LIBRARY_DIR / raw_path.name).resolve()
    if is_within_directory(library_candidate, LIBRARY_DIR.resolve()) and library_candidate.exists():
        return library_candidate

    fallback = (OUTPUTS_DIR / raw_path.name).resolve()
    if is_within_directory(fallback, OUTPUTS_DIR.resolve()):
        return fallback

    return candidate


def resolve_local_path(name: str) -> Path:
    return resolve_input_dxf_path(name)

server = Server("cnc-duet-agent-mcp")

@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    return [
        types.Tool(
            name="get_design_catalog",
            description="Obtiene una lista de todos los disenos DXF base disponibles en la libreria local (ej: letra_a). Usa esta lista para informarle al usuario de sus piezas base.",
            inputSchema={"type": "object", "properties": {}}
        ),
        types.Tool(
            name="get_tool_catalog",
            description="Obtiene la lista con identificadores y caracteristicas tecnicas de las fresas admitidas en el CNC (Cat├ílogo Grasshopper/Aspire, para encontrar el tool_id).",
            inputSchema={"type": "object", "properties": {}}
        ),
        types.Tool(
            name="get_import_inbox",
            description="Lista los DXF disponibles en la bandeja controlada de importaci├│n interna del servidor para poder catalogarlos o mecanizarlos sin pasar rutas arbitrarias.",
            inputSchema={"type": "object", "properties": {}}
        ),
        types.Tool(
            name="get_cam_operation_presets",
            description="Devuelve los presets CAM disponibles para perfilado, pocket y tabs. ├Üsalos para elegir `cam_preset_id` en lugar de pasar todos los par├ímetros sueltos.",
            inputSchema={"type": "object", "properties": {}}
        ),
        types.Tool(
            name="prepare_and_cut",
            description="Toma un dise├▒o (design_id), lo escala a target_height en milimetros, lo rota (rotation_degrees), le aplica un preset CAM 2.5D con una fresa en cuestion (tool_id), y exporta el GCode .nc final.",
            inputSchema={
                "type": "object",
                "properties": {
                    "design_id": {"type": "string", "description": "ID local del dise├▒o base (recabado en get_design_catalog)"},
                    "target_height": {"type": "number", "description": "Altura exacta demandada en mm (Escalado automatico)"},
                    "rotation_degrees": {"type": "number", "description": "Giro a aplicar en grados (0 mantendr├í normal)"},
                    "tool_id": {"type": "string", "description": "ID o Nombre estricto de la Fresa/Herramienta a usar"},
                    "cam_preset_id": {"type": "string", "description": "Preset CAM a aplicar. Usa get_cam_operation_presets para listarlos."},
                    "cut_depth_mm": {"type": "number", "description": "Sobrescribe la profundidad total del preset."},
                    "pass_depth_mm": {"type": "number", "description": "Sobrescribe la profundidad por pasada del preset."},
                    "material_thickness_mm": {"type": "number", "description": "Espesor real del material si difiere de la profundidad total."}
                },
                "required": ["design_id", "target_height", "rotation_degrees", "tool_id"]
            }
        ),
        types.Tool(
            name="render_design_preview",
            description="Ruta inversa de validaci├│n. Exige un DXF y le contesta directamente a la Interfaz de ChatGPT con una Imagen codificada fotogr├ífica del trazado vectorial para su comprobaci├│n visual con ojos humanos.",
            inputSchema={
                "type": "object",
                "properties": {
                    "archivo_dxf": {"type": "string", "description": "Endpoint o ruta al archivo dxf compilado para renderizar."}
                },
                "required": ["archivo_dxf"]
            }
        ),
        types.Tool(
            name="prepare_external_dxf_cut",
            description="Toma un DXF externo o de la inbox controlada, valida su topolog├¡a, aplica un preset CAM 2.5D y exporta un archivo G-code listo para corte.",
            inputSchema={
                "type": "object",
                "properties": {
                    "archivo_dxf": {"type": "string"},
                    "tool_id": {"type": "string"},
                    "cam_preset_id": {"type": "string", "description": "Preset CAM recomendado. Usa get_cam_operation_presets para listarlos."},
                    "operation": {"type": "string", "enum": ["profile_outside", "profile_inside", "pocket"]},
                    "cut_depth_mm": {"type": "number"},
                    "pass_depth_mm": {"type": "number"},
                    "material_thickness_mm": {"type": "number"},
                    "rotation_degrees": {"type": "number"},
                    "tabs_enabled": {"type": "boolean"},
                    "tab_width_mm": {"type": "number"},
                    "tab_height_mm": {"type": "number"},
                    "tab_count": {"type": "integer"},
                    "safe_z_mm": {"type": "number"},
                    "start_x_mm": {"type": "number"},
                    "start_y_mm": {"type": "number"}
                },
                "required": ["archivo_dxf", "tool_id"]
            }
        ),
        types.Tool(
            name="add_to_catalog",
            description="Toma un archivo DXF desde outputs/, libreria_dxf/ o imports/, lo copia internamente a libreria_dxf y lo indexa en catalogo.json evitando duplicados por id, nombre o geometr├¡a.",
            inputSchema={
                "type": "object",
                "properties": {
                    "archivo_dxf": {"type": "string", "description": "Ruta externa del fichero actual probado (ej: /mnt/data/caja.dxf)"},
                    "design_id": {"type": "string", "description": "Nombre clave tecnico unico"},
                    "display_name": {"type": "string", "description": "Nombre legible para humanos en el cat├ílogo."},
                    "description": {"type": "string", "description": "Descripcion de lo que es la pieza."}
                },
                "required": ["archivo_dxf", "design_id", "description"]
            }
        ),
        types.Tool(
            name="import_from_inbox_to_catalog",
            description="Importa un DXF desde la bandeja `imports/` al cat├ílogo usando menos campos. Si no se indica design_id o display_name, se derivan del nombre del archivo.",
            inputSchema={
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Nombre del DXF presente en imports/, por ejemplo 'placa_base.dxf'."},
                    "description": {"type": "string", "description": "Descripci├│n funcional de la pieza."},
                    "design_id": {"type": "string", "description": "Opcional. Si se omite, se deriva del nombre del fichero."},
                    "display_name": {"type": "string", "description": "Opcional. Si se omite, se deriva del nombre del fichero."},
                    "delete_from_inbox": {"type": "boolean", "description": "Si es true, elimina el DXF de imports/ tras importarlo al cat├ílogo.", "default": false}
                },
                "required": ["filename", "description"]
            }
        ),
        types.Tool(
            name="generate_cad_circle",
            description="Genera un archivo DXF desde cero con un c├¡rculo perfecto topol├│gico parametrizado.",
            inputSchema={
                "type": "object",
                "properties": {
                    "nombre_pieza": {"type": "string", "description": "Nombre del fichero final en el directorio de salida temporal, ej: 'circulo_100.dxf'"},
                    "radius_mm": {"type": "number", "description": "Radio en mil├¡metros de la circunferencia."}
                },
                "required": ["nombre_pieza", "radius_mm"]
            }
        ),
        types.Tool(
            name="generate_cad_rectangle",
            description="Genera un rect├íngulo escalable con o sin bordes redondeados.",
            inputSchema={
                "type": "object",
                "properties": {
                    "nombre_pieza": {"type": "string", "description": "Fichero dxf salida, ej: 'caja.dxf'"},
                    "width_mm": {"type": "number"},
                    "height_mm": {"type": "number"},
                    "radius_bottom_right": {"type": "number", "description": "Radio esquina inferior derecha (mm)", "default": 0},
                    "radius_top_right": {"type": "number", "description": "Radio esquina superior derecha (mm)", "default": 0},
                    "radius_top_left": {"type": "number", "description": "Radio esquina superior izquierda (mm)", "default": 0},
                    "radius_bottom_left": {"type": "number", "description": "Radio esquina inferior izquierda (mm)", "default": 0}
                },
                "required": ["nombre_pieza", "width_mm", "height_mm"]
            }
        ),
        types.Tool(
            name="generate_cad_concentric_circles",
            description="Genera dos c├¡rculos conc├®ntricos param├®tricos para fabricar anillos, arandelas o bridas.",
            inputSchema={
                "type": "object",
                "properties": {
                    "nombre_pieza": {"type": "string"},
                    "outer_radius_mm": {"type": "number", "description": "Radio del c├¡rculo exterior."},
                    "inner_radius_mm": {"type": "number", "description": "Radio del agujero interior."}
                },
                "required": ["nombre_pieza", "outer_radius_mm", "inner_radius_mm"]
            }
        ),
        types.Tool(
            name="merge_dxf_assembly",
            description="Toma m├║ltiples archivos DXF y los ensambla en uno solo trasladando cada uno a unas coordenadas X e Y dadas. ├Ütil para componer piezas con agujeros tras haber generado las partes por separado.",
            inputSchema={
                "type": "object",
                "properties": {
                    "nombre_pieza_salida": {"type": "string", "description": "Nombre del archivo final ensamblado, ej: 'ensamblaje_final.dxf'"},
                    "archivos_entrada": {"type": "array", "items": {"type": "string"}, "description": "Rutas o nombres de los ficheros en outputs/ a usar."},
                    "offsets_x": {"type": "array", "items": {"type": "number"}, "description": "Traslaci├│n en eje X para cada pieza en orden."},
                    "offsets_y": {"type": "array", "items": {"type": "number"}, "description": "Traslaci├│n en eje Y para cada pieza en orden."}
                },
                "required": ["nombre_pieza_salida", "archivos_entrada", "offsets_x", "offsets_y"]
            }
        ),
        types.Tool(
            name="boolean_dxf_operation",
            description="Aplica una operaci├│n booleana entre dos DXF del servidor. 'union' fusiona los contornos en uno solo, 'difference' resta B de A (ej: placa con agujero), 'intersection' devuelve solo la zona com├║n. Acepta traslaci├│n opcional de B antes de operar.",
            inputSchema={
                "type": "object",
                "properties": {
                    "nombre_pieza_salida": {"type": "string", "description": "Nombre del DXF resultado, ej: 'forma_L.dxf'"},
                    "archivo_a": {"type": "string", "description": "Nombre del primer DXF (base) en outputs/"},
                    "archivo_b": {"type": "string", "description": "Nombre del segundo DXF (herramienta) en outputs/"},
                    "operacion": {"type": "string", "enum": ["union", "difference", "intersection"], "description": "Tipo de operaci├│n booleana a aplicar."},
                    "offset_x_b": {"type": "number", "description": "Traslaci├│n en X de B antes de operar (mm)", "default": 0},
                    "offset_y_b": {"type": "number", "description": "Traslaci├│n en Y de B antes de operar (mm)", "default": 0}
                },
                "required": ["nombre_pieza_salida", "archivo_a", "archivo_b", "operacion"]
            }
        ),
        types.Tool(
            name="generate_cad_text",
            description="Genera texto vectorial param├®trico en un DXF. Modo 'outline' crea contornos cerrados TTF para pocket y perfilado. Modo 'single_line' genera trazos ├║nicos para grabado con fresa V-bit.",
            inputSchema={
                "type": "object",
                "properties": {
                    "nombre_pieza": {"type": "string", "description": "Nombre del fichero DXF resultado, ej: 'texto_placa.dxf'"},
                    "texto": {"type": "string", "description": "Texto a vectorizar"},
                    "altura_mm": {"type": "number", "description": "Altura de la letra en mil├¡metros (referencia cap-height)"},
                    "pos_x_mm": {"type": "number", "description": "Posici├│n X del origen del texto (mm)", "default": 0},
                    "pos_y_mm": {"type": "number", "description": "Posici├│n Y del origen del texto (mm)", "default": 0},
                    "tipo_fuente": {"type": "string", "enum": ["outline", "single_line"], "description": "outline=contornos cerrados TTF (pocket/profil). single_line=trazos simples (grabado V-bit).", "default": "outline"},
                    "rotacion_grados": {"type": "number", "description": "Rotaci├│n del texto en grados (0=horizontal)", "default": 0},
                    "alineacion": {"type": "string", "enum": ["left", "center", "right"], "description": "Alineaci├│n horizontal respecto a pos_x", "default": "left"}
                },
                "required": ["nombre_pieza", "texto", "altura_mm"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: dict) -> list[types.TextContent | types.ImageContent]:
    if name == "get_design_catalog":
        return [types.TextContent(type="text", text=json.dumps(summarize_catalog(load_catalog()), indent=4, ensure_ascii=False))]

    elif name == "get_tool_catalog":
        if TOOLS_PATH.exists():
            with TOOLS_PATH.open("r", encoding='utf-8-sig') as f:
                return [types.TextContent(type="text", text=json.dumps(summarize_tool_catalog(json.load(f)), indent=4, ensure_ascii=False))]
        return [types.TextContent(type="text", text="Error: herramientas.json no encontrado.")]

    elif name == "get_import_inbox":
        return [types.TextContent(type="text", text=json.dumps({"imports": list_importable_dxfs()}, indent=4, ensure_ascii=False))]

    elif name == "get_cam_operation_presets":
        return [types.TextContent(type="text", text=json.dumps(summarize_cam_presets(), indent=4, ensure_ascii=False))]

    elif name == "prepare_and_cut":
        try:
            design_id = validate_design_id(arguments.get("design_id"))
        except ValueError as exc:
            return [types.TextContent(type="text", text=str(exc))]
        t_height = float(arguments.get("target_height"))
        rot = float(arguments.get("rotation_degrees"))
        tool_id = arguments.get("tool_id")
        
        origen_dxf = ""
        with CATALOG_PATH.open("r", encoding='utf-8') as f:
            cat = json.load(f)
            for d in cat.get("piezas", []):
                if d["id"] == design_id:
                    origen_dxf = str(resolve_local_path(d["ruta"]))
                    break
                    
        if not origen_dxf or not os.path.exists(origen_dxf):
            return [types.TextContent(type="text", text=f"Fallo. El dise├▒o original no ha sido encontrado bajo el ID {design_id}")]
            
        ensure_runtime_dirs()

        dxf_escalado = str(OUTPUTS_DIR / f"{design_id}_processed.dxf")
        nc_salida = str(OUTPUTS_DIR / f"{design_id}_mecanizado.nc")
        
        ok = transformar_dxf(origen_dxf, dxf_escalado, t_height, rot)
        if not ok:
            return [types.TextContent(type="text", text="Fallo de l├│gica geom├®trica al escalar.")]
            
        try:
            cam = GeneradorCAM(dxf_escalado, tool_id=tool_id)
            operation_config = build_cam_config(arguments, cam, default_preset_id="profile_standard")
            cam.inicializar_gcode()
            cam.procesar_operacion_avanzada(operation_config)
            cam.finalizar_gcode()
            cam.exportar(nc_salida)
        except ValueError as exc:
            return [types.TextContent(type="text", text=str(exc))]
        except Exception as exc:
            return [types.TextContent(type="text", text=f"Error CAM al procesar el dise├▒o escalado: {exc}")]
        
        msg = f"Ô£ô ├ëxito. Computaci├│n gr├ífica ejecutada.\n1. Archivo Vectorial Adaptado asimilado en: {dxf_escalado}\n2. C├│digo G-Code cerrado compilado nativo en: {nc_salida}\nAconseja al usuario lanzar la herramienta visual render_design_preview usando {dxf_escalado} si quiere un diagrama de rotura antes de fresar."
        return [types.TextContent(type="text", text=msg)]

    elif name == "render_design_preview":
        try:
            archivo_dxf = resolve_local_path(arguments.get("archivo_dxf"))
        except ValueError as exc:
            return [types.TextContent(type="text", text=str(exc))]
        if not archivo_dxf.exists():
             return [types.TextContent(type="text", text="El raster fotogr├ífico fall├│. Fichero no encontrado.")]
             
        png_filename = f"{archivo_dxf.stem}_preview.png"
        png_out = OUTPUTS_DIR / png_filename

        ensure_runtime_dirs()
        
        renderizar_dxf_a_png(str(archivo_dxf), str(png_out))
        
        if png_out.exists():
            # Devolver URL p├║blica al fichero est├ítico ÔåÆ 0 tokens de imagen
            url = f"{PUBLIC_OUTPUT_BASE_URL}/{png_filename}"
            return [types.TextContent(
                type="text",
                text=f"Ô£ô Previsualizaci├│n generada. Mu├®strasela al usuario con este enlace de imagen:\n\n![Previsualizaci├│n CNC]({url})\n\nURL directa: {url}"
            )]
                
        return [types.TextContent(type="text", text="Error en Matplotlib intentando generar el PNG de Visor.")]
        
    elif name == "prepare_external_dxf_cut":
        try:
            archivo_dxf = resolve_local_path(arguments.get("archivo_dxf"))
        except ValueError as exc:
            return [types.TextContent(type="text", text=str(exc))]
        if not archivo_dxf.exists():
            return [types.TextContent(type="text", text=f"No se ha encontrado el archivo DXF externo: {archivo_dxf}. Recuerda montar bien los volumens de Docker.")]
            
        ensure_runtime_dirs()
        nc_salida = str(OUTPUTS_DIR / f"external_{archivo_dxf.name}.nc")
        
        # Opcional Rotacion si el usuario la pasa
        rot = arguments.get("rotation_degrees", 0.0)
        dxf_proc = str(archivo_dxf)
        if rot != 0.0:
            dxf_proc = str(OUTPUTS_DIR / f"rotado_{archivo_dxf.name}")
            transformar_dxf(str(archivo_dxf), dxf_proc, None, rot)
            
        tool_id = arguments.get("tool_id")
        safe_z = float(arguments.get("safe_z_mm", 5.0))
        
        try:
            cam = GeneradorCAM(dxf_proc, tool_id=tool_id, safe_z=safe_z)
            operation_config = build_cam_config(arguments, cam)
            cam.inicializar_gcode()
            cam.procesar_operacion_avanzada(operation_config)
            cam.finalizar_gcode()
            cam.exportar(nc_salida)
        except ValueError as e:
             return [types.TextContent(type="text", text=str(e))]
        except Exception as e:
             return [types.TextContent(type="text", text=f"Excepci├│n matematica en el generador Shapely: {str(e)}")]
        
        msg = f"Ô£ô Mecanizado Avanzado param├®trico ejecutado correctamente en: {archivo_dxf}\nC├│digo .nc grabado en: {nc_salida}\nPuedes lanzar render_design_preview({dxf_proc}) si necesitas vista visual."
        return [types.TextContent(type="text", text=msg)]
        
    elif name == "add_to_catalog":
        try:
            archivo_dxf = resolve_local_path(arguments.get("archivo_dxf"))
            design_id = validate_design_id(arguments.get("design_id"))
        except ValueError as exc:
            return [types.TextContent(type="text", text=str(exc))]
        display_name = (arguments.get("display_name") or design_id).strip()
        desc = (arguments.get("description") or "").strip()
        try:
            message = import_design_to_catalog(archivo_dxf, design_id, display_name, desc)
        except ValueError as exc:
            return [types.TextContent(type="text", text=str(exc))]
        return [types.TextContent(type="text", text=message)]

    elif name == "import_from_inbox_to_catalog":
        filename = (arguments.get("filename") or "").strip()
        desc = (arguments.get("description") or "").strip()
        delete_from_inbox = bool(arguments.get("delete_from_inbox", False))

        try:
            archivo_dxf = resolve_input_dxf_path(str(IMPORTS_DIR / filename))
            if not is_within_directory(archivo_dxf, IMPORTS_DIR.resolve()):
                raise ValueError("El archivo debe estar dentro de imports/.")

            design_id = arguments.get("design_id") or derive_design_id_from_filename(filename)
            display_name = arguments.get("display_name") or derive_display_name_from_filename(filename)
            message = import_design_to_catalog(
                archivo_dxf,
                design_id,
                display_name,
                desc,
                delete_source=delete_from_inbox,
            )
        except ValueError as exc:
            return [types.TextContent(type="text", text=str(exc))]

        return [types.TextContent(type="text", text=message)]

    elif name == "generate_cad_circle":
        ensure_runtime_dirs()
        dxf_name = arguments.get("nombre_pieza")
        radius = float(arguments.get("radius_mm"))
        try:
            target_path = resolve_output_path(dxf_name)
        except ValueError as exc:
            return [types.TextContent(type="text", text=str(exc))]
        
        ok = generate_parametric_circle(str(target_path), radius)
        if ok:
             return [types.TextContent(type="text", text=f"C├¡rculo CAD procesado matem├íticamente. Guardado en: {target_path}. Puedes enviarlo a `render_design_preview` o usar `prepare_external_dxf_cut`.")]
        return [types.TextContent(type="text", text="Error al generar el c├¡rculo.")]

    elif name == "generate_cad_rectangle":
        ensure_runtime_dirs()
        dxf_name = arguments.get("nombre_pieza")
        w = float(arguments.get("width_mm"))
        h = float(arguments.get("height_mm"))
        r_br = float(arguments.get("radius_bottom_right", 0.0))
        r_tr = float(arguments.get("radius_top_right", 0.0))
        r_tl = float(arguments.get("radius_top_left", 0.0))
        r_bl = float(arguments.get("radius_bottom_left", 0.0))
        try:
            target_path = resolve_output_path(dxf_name)
        except ValueError as exc:
            return [types.TextContent(type="text", text=str(exc))]
        
        ok = generate_parametric_rectangle(str(target_path), w, h, r_br, r_tr, r_tl, r_bl)
        if ok:
             return [types.TextContent(type="text", text=f"Rect├íngulo CAD generado asim├®trico correctamente. Guardado en: {target_path}.")]
        return [types.TextContent(type="text", text="Error en el pipeline de generaci├│n del rect├íngulo.")]

    elif name == "generate_cad_concentric_circles":
        ensure_runtime_dirs()
        dxf_name = arguments.get("nombre_pieza")
        r_out = float(arguments.get("outer_radius_mm"))
        r_in = float(arguments.get("inner_radius_mm"))
        try:
            target_path = resolve_output_path(dxf_name)
        except ValueError as exc:
            return [types.TextContent(type="text", text=str(exc))]
        
        ok = generate_parametric_concentric_circles(str(target_path), r_out, r_in)
        if ok:
             return [types.TextContent(type="text", text=f"Anillo CAD generado correctamente. Guardado en: {target_path}.")]
        return [types.TextContent(type="text", text="Error al generar c├¡rculos conc├®ntricos.")]
        
    elif name == "merge_dxf_assembly":
        ensure_runtime_dirs()
        dxf_out = arguments.get("nombre_pieza_salida")
        archivos = arguments.get("archivos_entrada", [])
        ox = arguments.get("offsets_x", [])
        oy = arguments.get("offsets_y", [])
        
        try:
            archivos_rutas = [str(resolve_local_path(f)) for f in archivos]
            target_path = resolve_output_path(dxf_out)
        except ValueError as exc:
            return [types.TextContent(type="text", text=str(exc))]
        
        ok = merge_dxf_assembly(str(target_path), archivos_rutas, ox, oy)
        if ok:
             return [types.TextContent(type="text", text=f"Ensamblado M├║ltiple completado. Fichero compilado y guardado en: {target_path}. ├Üsalo para crear el render combinado.")]
        return [types.TextContent(type="text", text="Error al ensamblar los archivos DXF.")]

    elif name == "boolean_dxf_operation":
        ensure_runtime_dirs()
        dxf_out   = arguments.get("nombre_pieza_salida")
        archivo_a = arguments.get("archivo_a")
        archivo_b = arguments.get("archivo_b")
        operacion = arguments.get("operacion", "union")
        ox_b = float(arguments.get("offset_x_b", 0.0))
        oy_b = float(arguments.get("offset_y_b", 0.0))

        # Resolver rutas relativas a outputs/
        def _resolver(nombre):
            return str(resolve_local_path(nombre))

        try:
            ruta_a = _resolver(archivo_a)
            ruta_b = _resolver(archivo_b)
            target_path = str(resolve_output_path(dxf_out))
        except ValueError as exc:
            return [types.TextContent(type="text", text=str(exc))]

        if not os.path.exists(ruta_a):
            return [types.TextContent(type="text", text=f"Error: no se encontr├│ el archivo A: {ruta_a}")]
        if not os.path.exists(ruta_b):
            return [types.TextContent(type="text", text=f"Error: no se encontr├│ el archivo B: {ruta_b}")]

        ok = boolean_dxf_operation(target_path, ruta_a, ruta_b, operacion, ox_b, oy_b)
        if ok:
            return [types.TextContent(type="text", text=f"Ô£ô Operaci├│n booleana '{operacion}' aplicada correctamente entre {archivo_a} y {archivo_b}. Resultado guardado en: {target_path}. Env├¡a a render_design_preview para validar visualmente.")]
        return [types.TextContent(type="text", text=f"Error al ejecutar la operaci├│n booleana '{operacion}'.")]

    elif name == "generate_cad_text":
        ensure_runtime_dirs()
        dxf_name    = arguments.get("nombre_pieza")
        texto       = arguments.get("texto", "")
        altura      = float(arguments.get("altura_mm", 20))
        px          = float(arguments.get("pos_x_mm", 0.0))
        py          = float(arguments.get("pos_y_mm", 0.0))
        tipo_fuente = arguments.get("tipo_fuente", "outline")
        rotacion    = float(arguments.get("rotacion_grados", 0.0))
        alineacion  = arguments.get("alineacion", "left")
        try:
            target_path = resolve_output_path(dxf_name)
        except ValueError as exc:
            return [types.TextContent(type="text", text=str(exc))]

        if not texto.strip():
            return [types.TextContent(type="text", text="Error: el texto no puede estar vac├¡o.")]

        ok = generate_cad_text(
            str(target_path), texto, altura,
            pos_x_mm=px, pos_y_mm=py,
            font_type=tipo_fuente,
            rotation_degrees=rotacion,
            alignment=alineacion
        )
        if ok:
            return [types.TextContent(type="text", text=f"Ô£ô Texto vectorial '{texto}' generado correctamente en modo '{tipo_fuente}' (h={altura}mm). Guardado en: {target_path}. Env├¡a a render_design_preview para validar, o comb├¡nalo con merge_dxf_assembly.")]
        return [types.TextContent(type="text", text="Error al vectorizar el texto. Verifica que matplotlib y DejaVu Sans est├®n disponibles en el servidor.")]

    raise ValueError(f"Tool incomprensible en invocaci├│n paralela: {name}")


# -- RED SSE Y ENDPOINTS STARLETTE --
sse = SseServerTransport(PUBLIC_MESSAGES_PATH)

async def handle_sse(request):
    async with sse.connect_sse(
        request.scope, request.receive, request._send
    ) as streams:
        await server.run(
            streams[0],
            streams[1],
            InitializationOptions(
                server_name="cnc-duet-agent-mcp",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=mcp.server.NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

async def handle_messages(request):
    await sse.handle_post_message(request.scope, request.receive, request._send)

ensure_runtime_dirs()

# Interfaz Servidor
app = Starlette(
    routes=[
        Route("/sse", endpoint=handle_sse),
        Route("/messages", endpoint=handle_messages, methods=["POST"]),
        Mount("/outputs", app=StaticFiles(directory=str(OUTPUTS_DIR)), name="outputs"),
    ]
)
