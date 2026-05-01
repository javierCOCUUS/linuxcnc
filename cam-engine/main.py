from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict
import os
import logic
from postprocessor import MachinePostProcessor

app = FastAPI(title="cam-engine")

# Workspace and G-code output directories
WORKSPACE = os.environ.get("DXF_WORKSPACE", "/workspace")
GCODE_OUTPUT = os.environ.get("GCODE_OUTPUT", "/gcode")

class CAMConfig(BaseModel):
    dxf_filename: str
    output_filename: str
    tool_id: str
    material_id: Optional[str] = None
    override_tool_number: Optional[int] = None
    operation: str = "profile_outside"
    cut_depth_mm: float = 5.0
    pass_depth_mm: Optional[float] = None
    # Tabs
    tabs_enabled: bool = False
    tab_width_mm: float = 5.0
    tab_height_mm: float = 2.0
    tab_count: int = 4
    material_thickness_mm: float = 5.0
    # Lead-in / Lead-out
    leadin_type: str = "ramp"  # "none", "ramp"
    leadin_length_mm: float = 10.0
    # Start Point
    start_x_mm: Optional[float] = None
    start_y_mm: Optional[float] = None
    # Level-1 new params
    strategy: str = "conventional"         # "conventional" | "climb"
    cut_side: str = "outside"              # "outside" | "inside" | "center"
    feed_rate_override: Optional[float] = None   # mm/min, overrides tool default
    plunge_rate_override: Optional[float] = None # mm/min, overrides tool default
    safe_z_mm: Optional[float] = None           # overrides default safe Z
    finish_pass_offset: Optional[float] = None  # extra offset for roughing; 0 = no finish pass
    finish_pass_feed_pct: float = 0.6           # finish pass feed as fraction of normal feed
    cutter_comp: str = "none"                   # "none" | "left" (G41) | "right" (G42)

class ProfileConfig(BaseModel):
    dxf_filename: str
    output_filename: str
    tool_id: str
    material_id: Optional[str] = None
    cut_depth_mm: float = 5.0
    pass_depth_mm: Optional[float] = None
    cut_side: str = "outside"   # "outside" | "inside" | "center"
    strategy: str = "conventional"
    tabs_enabled: bool = False
    tab_width_mm: float = 5.0
    tab_height_mm: float = 2.0
    tab_count: int = 4
    material_thickness_mm: float = 5.0
    leadin_type: str = "ramp"
    leadin_length_mm: float = 10.0
    feed_rate_override: Optional[float] = None
    plunge_rate_override: Optional[float] = None
    safe_z_mm: Optional[float] = None
    finish_pass_offset: Optional[float] = None
    finish_pass_feed_pct: float = 0.6
    cutter_comp: str = "none"   # "none" | "left" (G41) | "right" (G42)

class PocketConfig(BaseModel):
    dxf_filename: str
    output_filename: str
    tool_id: str
    material_id: Optional[str] = None
    cut_depth_mm: float = 5.0
    pass_depth_mm: Optional[float] = None
    stepover_pct: float = 0.4             # lateral stepover as fraction of tool diameter
    finish_pass: bool = True              # add a finishing contour at full depth
    feed_rate_override: Optional[float] = None
    plunge_rate_override: Optional[float] = None
    safe_z_mm: Optional[float] = None

class DrillConfig(BaseModel):
    dxf_filename: str
    output_filename: str
    tool_id: str
    material_id: Optional[str] = None
    drill_depth_mm: float = 10.0
    peck_depth_mm: float = 2.0            # 0 = full depth in one plunge
    dwell_ms: int = 0                     # dwell at bottom in milliseconds
    feed_rate_override: Optional[float] = None
    safe_z_mm: Optional[float] = None

class EngraveConfig(BaseModel):
    dxf_filename: str
    output_filename: str
    tool_id: str
    material_id: Optional[str] = None
    cut_depth_mm: float = 0.5             # shallow engraving depth
    feed_rate_override: Optional[float] = None
    plunge_rate_override: Optional[float] = None
    safe_z_mm: Optional[float] = None

def _build_cam(dxf_filename, tool_id, material_id, safe_z_override, feed_override, plunge_override):
    """Helper: instantiate and optionally override feed/plunge/safe-z."""
    dxf_path = os.path.join(WORKSPACE, os.path.basename(dxf_filename))
    if not os.path.exists(dxf_path):
        raise HTTPException(status_code=404, detail=f"DXF file not found: {dxf_filename}")
    cam = logic.GeneradorCAM(dxf_path, tool_id=tool_id, material_id=material_id)
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
    gcode_path = os.path.join(GCODE_OUTPUT, os.path.basename(output_filename))
    cam.inicializar_gcode()
    return gcode_path


@app.get("/")
async def root():
    return {"service": "cam-engine", "status": "ok"}


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
        import traceback; print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


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
        import traceback; print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


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
        import traceback; print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


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
        import traceback; print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))


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
        import traceback; print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
