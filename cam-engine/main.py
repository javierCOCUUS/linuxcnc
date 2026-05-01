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
    leadin_type: str = "ramp" # "none", "ramp"
    leadin_length_mm: float = 10.0
    # Start Point
    start_x_mm: Optional[float] = None
    start_y_mm: Optional[float] = None

@app.get("/")
async def root():
    return {"service": "cam-engine", "status": "ok"}

@app.post("/generate")
async def generate_cam(config: CAMConfig):
    dxf_path = os.path.join(WORKSPACE, config.dxf_filename)
    gcode_path = os.path.join(GCODE_OUTPUT, config.output_filename)
    
    if not os.path.exists(dxf_path):
        raise HTTPException(status_code=404, detail=f"DXF file not found: {config.dxf_filename}")
    
    try:
        # Initialize CAM with tool and material
        cam = logic.GeneradorCAM(
            dxf_path, 
            tool_id=config.tool_id, 
            material_id=config.material_id
        )
        
        # Apply override if provided
        if config.override_tool_number is not None:
            cam.tool_number = config.override_tool_number
            
        pp = MachinePostProcessor()
        cam.postprocessor = pp
        
        cam.inicializar_gcode()
        cam.procesar_operacion_avanzada(config.dict())
        cam.finalizar_gcode()
        cam.exportar(gcode_path)
        
        return {
            "status": "success", 
            "gcode_path": gcode_path,
            "tool_used": cam.tool_number,
            "final_feed_xy": cam.feed_xy,
            "final_step_z": cam.step_z
        }
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
