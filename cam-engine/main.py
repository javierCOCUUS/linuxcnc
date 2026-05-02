from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Dict, Literal, Optional
import logging
import os
import logic
from postprocessor import MachinePostProcessor

app = FastAPI(title="cam-engine")
logger = logging.getLogger(__name__)

OperationName = Literal["pocket", "profile_outside", "profile_inside"]
LeadinType = Literal["none", "ramp"]
CutStrategy = Literal["conventional", "climb"]
CutSide = Literal["outside", "inside", "center"]
CutterComp = Literal["none", "left", "right"]

# Workspace and G-code output directories
WORKSPACE = os.path.abspath(os.environ.get("DXF_WORKSPACE", "/workspace"))
GCODE_OUTPUT = os.path.abspath(os.environ.get("GCODE_OUTPUT", "/gcode"))


def _safe_path(root: str, *parts: str) -> str:
    candidate = os.path.abspath(os.path.join(root, *parts))
    root_prefix = os.path.join(root, "")
    if candidate != root and not candidate.startswith(root_prefix):
        raise HTTPException(status_code=422, detail="Path escapes workspace")
    return candidate


def _workspace_path(*parts: str) -> str:
    return _safe_path(WORKSPACE, *parts)


def _gcode_path(*parts: str) -> str:
    return _safe_path(GCODE_OUTPUT, *parts)

class CAMConfig(BaseModel):
    dxf_filename: str
    output_filename: str
    tool_id: str
    material_id: Optional[str] = None
    override_tool_number: Optional[int] = Field(default=None, gt=0)
    operation: OperationName = "profile_outside"
    cut_depth_mm: float = Field(default=5.0, gt=0)
    pass_depth_mm: Optional[float] = Field(default=None, gt=0)
    # Tabs
    tabs_enabled: bool = False
    tab_width_mm: float = Field(default=5.0, gt=0)
    tab_height_mm: float = Field(default=2.0, gt=0)
    tab_count: int = Field(default=4, ge=0)
    material_thickness_mm: float = Field(default=5.0, gt=0)
    # Lead-in / Lead-out
    leadin_type: LeadinType = "ramp"
    leadin_length_mm: float = Field(default=10.0, ge=0)
    # Start Point
    start_x_mm: Optional[float] = None
    start_y_mm: Optional[float] = None
    # Level-1 new params
    strategy: CutStrategy = "conventional"
    cut_side: CutSide = "outside"
    feed_rate_override: Optional[float] = Field(default=None, gt=0)
    plunge_rate_override: Optional[float] = Field(default=None, gt=0)
    safe_z_mm: Optional[float] = Field(default=None, ge=0)
    finish_pass_offset: Optional[float] = Field(default=None, ge=0)
    finish_pass_feed_pct: float = Field(default=0.6, gt=0, le=1)
    cutter_comp: CutterComp = "none"

class ProfileConfig(BaseModel):
    dxf_filename: str
    output_filename: str
    tool_id: str
    material_id: Optional[str] = None
    cut_depth_mm: float = Field(default=5.0, gt=0)
    pass_depth_mm: Optional[float] = Field(default=None, gt=0)
    cut_side: CutSide = "outside"
    strategy: CutStrategy = "conventional"
    tabs_enabled: bool = False
    tab_width_mm: float = Field(default=5.0, gt=0)
    tab_height_mm: float = Field(default=2.0, gt=0)
    tab_count: int = Field(default=4, ge=0)
    material_thickness_mm: float = Field(default=5.0, gt=0)
    leadin_type: LeadinType = "ramp"
    leadin_length_mm: float = Field(default=10.0, ge=0)
    feed_rate_override: Optional[float] = Field(default=None, gt=0)
    plunge_rate_override: Optional[float] = Field(default=None, gt=0)
    safe_z_mm: Optional[float] = Field(default=None, ge=0)
    finish_pass_offset: Optional[float] = Field(default=None, ge=0)
    finish_pass_feed_pct: float = Field(default=0.6, gt=0, le=1)
    cutter_comp: CutterComp = "none"

class PocketConfig(BaseModel):
    dxf_filename: str
    output_filename: str
    tool_id: str
    material_id: Optional[str] = None
    cut_depth_mm: float = Field(default=5.0, gt=0)
    pass_depth_mm: Optional[float] = Field(default=None, gt=0)
    stepover_pct: float = Field(default=0.4, gt=0, le=1)
    finish_pass: bool = True              # add a finishing contour at full depth
    feed_rate_override: Optional[float] = Field(default=None, gt=0)
    plunge_rate_override: Optional[float] = Field(default=None, gt=0)
    safe_z_mm: Optional[float] = Field(default=None, ge=0)

class DrillConfig(BaseModel):
    dxf_filename: str
    output_filename: str
    tool_id: str
    material_id: Optional[str] = None
    drill_depth_mm: float = Field(default=10.0, gt=0)
    peck_depth_mm: float = Field(default=2.0, ge=0)
    dwell_ms: int = Field(default=0, ge=0)
    feed_rate_override: Optional[float] = Field(default=None, gt=0)
    safe_z_mm: Optional[float] = Field(default=None, ge=0)

class EngraveConfig(BaseModel):
    dxf_filename: str
    output_filename: str
    tool_id: str
    material_id: Optional[str] = None
    cut_depth_mm: float = Field(default=0.5, gt=0)
    feed_rate_override: Optional[float] = Field(default=None, gt=0)
    plunge_rate_override: Optional[float] = Field(default=None, gt=0)
    safe_z_mm: Optional[float] = Field(default=None, ge=0)

def _build_cam(dxf_filename, tool_id, material_id, safe_z_override, feed_override, plunge_override):
    """Helper: instantiate and optionally override feed/plunge/safe-z."""
    dxf_path = _workspace_path(dxf_filename)
    if not os.path.exists(dxf_path):
        raise HTTPException(status_code=404, detail=f"DXF file not found: {dxf_filename}")
    try:
        cam = logic.GeneradorCAM(dxf_path, tool_id=tool_id, material_id=material_id)
    except logic.CatalogUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except logic.CatalogLookupError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    if safe_z_override is not None:
        cam.safe_z = safe_z_override
    if feed_override is not None:
        cam.feed_xy = feed_override
    if plunge_override is not None:
        cam.feed_z = plunge_override
    cam.postprocessor = MachinePostProcessor()
    return cam, dxf_path


def _save_gcode(cam, output_filename):
    os.makedirs(GCODE_OUTPUT, exist_ok=True)
    gcode_path = _gcode_path(output_filename)
    cam.inicializar_gcode()
    return gcode_path


def _raise_engine_failure(operation: str, output_filename: str, exc: Exception) -> None:
    logger.exception("%s failed for %s", operation, output_filename)
    raise HTTPException(status_code=500, detail=f"{operation} failed: {exc}")


@app.get("/")
async def root():
    return {"service": "cam-engine", "status": "ok"}


@app.get("/healthz")
async def healthz():
    return {"service": "cam-engine", "status": "ok"}


@app.get("/readyz")
async def readyz():
    workspace_ready = os.path.isdir(WORKSPACE)
    gcode_ready = os.path.isdir(GCODE_OUTPUT)
    status = "ready" if workspace_ready and gcode_ready else "not-ready"
    payload = {
        "service": "cam-engine",
        "status": status,
        "workspace": WORKSPACE,
        "gcode_output": GCODE_OUTPUT,
    }
    return JSONResponse(status_code=200 if status == "ready" else 503, content=payload)


@app.post("/generate")
async def generate_cam(config: CAMConfig):
    """Legacy all-in-one endpoint — kept for backward compatibility."""
    try:
        cam, _ = _build_cam(
            config.dxf_filename, config.tool_id, config.material_id,
            config.safe_z_mm, config.feed_rate_override, config.plunge_rate_override
        )
        if config.override_tool_number is not None:
            cam.tool_number = config.override_tool_number

        gcode_path = _save_gcode(cam, config.output_filename)
        cam.procesar_operacion_avanzada(config.dict())
        cam.finalizar_gcode()
        cam.exportar(gcode_path)

        return {
            "status": "success",
            "gcode_path": gcode_path,
            "tool_used": cam.tool_number,
            "final_feed_xy": cam.feed_xy,
            "final_step_z": cam.step_z,
        }
    except HTTPException:
        raise
    except Exception as e:
        _raise_engine_failure("CAM generation", config.output_filename, e)


@app.post("/profile")
async def cam_profile(config: ProfileConfig):
    """Profile operation: outside, inside, or center-line."""
    try:
        cam, _ = _build_cam(
            config.dxf_filename, config.tool_id, config.material_id,
            config.safe_z_mm, config.feed_rate_override, config.plunge_rate_override
        )
        offset_map = {"outside": cam.tool_radius + 0.1, "inside": -(cam.tool_radius + 0.1), "center": 0.0}
        buf = offset_map.get(config.cut_side, cam.tool_radius + 0.1)
        if config.strategy == "climb":
            buf = -buf  # reverse winding for climb milling

        gcode_path = _save_gcode(cam, config.output_filename)
        depth = -abs(config.cut_depth_mm)
        pass_depth = config.pass_depth_mm or cam.step_z

        # Roughing pass (with optional stock to leave)
        stock = config.finish_pass_offset or 0.0
        cfg = config.dict()
        polys = cam._extraer_poligonos()
        polys = cam._sort_paths_nearest_neighbor(polys)
        for poly in polys:
            cam._generar_perfil(poly, depth, pass_depth, buf + stock, cfg,
                                config.leadin_type, config.leadin_length_mm)

        # Finish pass at full depth if finish_pass_offset was set
        if stock > 0.02:
            orig_feed = cam.feed_xy
            cam.feed_xy *= config.finish_pass_feed_pct
            for poly in polys:
                cam._generar_perfil(poly, depth, abs(depth), buf, cfg, "none", 0)
            cam.feed_xy = orig_feed

        cam.finalizar_gcode()
        cam.exportar(gcode_path)
        return {"status": "success", "gcode_path": gcode_path, "tool_used": cam.tool_number,
                "cut_side": config.cut_side, "strategy": config.strategy}
    except HTTPException:
        raise
    except Exception as e:
        _raise_engine_failure("CAM profile", config.output_filename, e)


@app.post("/pocket")
async def cam_pocket(config: PocketConfig):
    """Pocket clearing with optional finish contour at full depth."""
    try:
        cam, _ = _build_cam(
            config.dxf_filename, config.tool_id, config.material_id,
            config.safe_z_mm, config.feed_rate_override, config.plunge_rate_override
        )
        gcode_path = _save_gcode(cam, config.output_filename)
        depth = -abs(config.cut_depth_mm)
        pass_depth = config.pass_depth_mm or cam.step_z
        stepover = config.stepover_pct * cam.tool_radius * 2  # mm

        polys = cam._extraer_poligonos()
        polys = cam._sort_paths_nearest_neighbor(polys)
        for poly in polys:
            cam._generar_pocket_adv(poly, depth, pass_depth, stepover)

        if config.finish_pass:
            orig_feed = cam.feed_xy
            cam.feed_xy *= 0.6
            cfg_dummy = {"tabs_enabled": False, "tab_height_mm": 2, "tab_width_mm": 5,
                         "tab_count": 0, "material_thickness_mm": abs(depth),
                         "leadin_type": "none", "leadin_length_mm": 0}
            for poly in polys:
                cam._generar_perfil(poly, depth, abs(depth), -(cam.tool_radius + 0.1),
                                    cfg_dummy, "none", 0)
            cam.feed_xy = orig_feed

        cam.finalizar_gcode()
        cam.exportar(gcode_path)
        return {"status": "success", "gcode_path": gcode_path, "tool_used": cam.tool_number,
                "stepover_mm": stepover}
    except HTTPException:
        raise
    except Exception as e:
        _raise_engine_failure("CAM pocket", config.output_filename, e)


@app.post("/drill")
async def cam_drill(config: DrillConfig):
    """Drill cycles: peck or plunge, with optional dwell."""
    try:
        cam, _ = _build_cam(
            config.dxf_filename, config.tool_id, config.material_id,
            config.safe_z_mm, config.feed_rate_override, None
        )
        gcode_path = _save_gcode(cam, config.output_filename)
        cam.generar_drill(
            drill_depth=-abs(config.drill_depth_mm),
            peck_depth=config.peck_depth_mm,
            dwell_ms=config.dwell_ms,
        )
        cam.finalizar_gcode()
        cam.exportar(gcode_path)
        holes = cam._drill_hole_count
        return {"status": "success", "gcode_path": gcode_path, "holes_drilled": holes,
                "peck_depth_mm": config.peck_depth_mm}
    except HTTPException:
        raise
    except Exception as e:
        _raise_engine_failure("CAM drill", config.output_filename, e)


@app.post("/engrave")
async def cam_engrave(config: EngraveConfig):
    """Single-pass engraving — follows all lines/curves at cut_depth."""
    try:
        cam, _ = _build_cam(
            config.dxf_filename, config.tool_id, config.material_id,
            config.safe_z_mm, config.feed_rate_override, config.plunge_rate_override
        )
        gcode_path = _save_gcode(cam, config.output_filename)
        cam.generar_engrave(-abs(config.cut_depth_mm))
        cam.finalizar_gcode()
        cam.exportar(gcode_path)
        return {"status": "success", "gcode_path": gcode_path, "tool_used": cam.tool_number,
                "cut_depth_mm": config.cut_depth_mm}
    except HTTPException:
        raise
    except Exception as e:
        _raise_engine_failure("CAM engrave", config.output_filename, e)
