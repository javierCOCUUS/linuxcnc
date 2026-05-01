from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional, Dict
import os
import json
import time
from datetime import datetime

app = FastAPI(title="linuxcnc-bridge")

# --- CONFIGURATION ---
NC_FILES_DIR = os.environ.get("GCODE_DIR", "/gcode")
CONFIG_DIR = "/machine/config"
MACROS_DIR = "/machine/macros"

# Ensure directories exist
for d in [NC_FILES_DIR, CONFIG_DIR, MACROS_DIR]:
    os.makedirs(d, exist_ok=True)

# --- MODELS ---

class CommandBase(BaseModel):
    confirm: bool = False

class JogParams(CommandBase):
    axis: str # X, Y, Z, A, B, C
    distance: float
    speed: float = 600

class GCodeParams(CommandBase):
    command: str

class SpindleParams(CommandBase):
    speed: int = 0
    direction: str = "CW" # CW, CCW, STOP

class MacroParams(BaseModel):
    name: str
    content: str

# --- SAFETY SYSTEM DECORATOR ---
def check_safety(level: str, confirm: bool):
    if level in ["DANGEROUS", "CRITICAL"] and not confirm:
        raise HTTPException(
            status_code=403, 
            detail=f"This operation is {level}. Please set 'confirm: true' to execute."
        )

# --- ENDPOINTS ---

# 1. STATUS (SAFE)
@app.get("/status")
async def get_machine_status():
    return {
        "position": {"x": 0.0, "y": 0.0, "z": 10.0},
        "state": "IDLE",
        "homed": ["X", "Y", "Z"],
        "spindle": {"on": False, "speed": 0},
        "feed_rate": 100.0,
        "active_gcode": "G54 G17 G90",
        "system": {"cpu": "arm64", "temp": 45.2}
    }

# 2. MOTION (CAUTION)
@app.post("/motion/jog")
async def jog(params: JogParams):
    check_safety("CAUTION", params.confirm)
    # Stub for movement
    return {"status": "moving", "axis": params.axis, "dist": params.distance}

@app.post("/motion/home")
async def home_axes(params: CommandBase):
    check_safety("CAUTION", params.confirm)
    return {"status": "homing_initiated"}

# 3. G-CODE (DANGEROUS)
@app.post("/gcode/send")
async def send_gcode(params: GCodeParams):
    check_safety("DANGEROUS", params.confirm)
    return {"status": "executed", "command": params.command}

@app.post("/gcode/spindle")
async def spindle_control(params: SpindleParams):
    check_safety("DANGEROUS", params.confirm)
    return {"status": "spindle_updated", "params": params.dict()}

# 4. SD CARD (FILES)
@app.get("/files")
async def list_files():
    files = os.listdir(NC_FILES_DIR)
    return {"files": files}

@app.post("/files/run")
async def run_file(filename: str, params: CommandBase):
    check_safety("DANGEROUS", params.confirm)
    return {"status": "program_started", "file": filename}

# 5. MACROS
@app.post("/macros/save")
async def save_macro(params: MacroParams):
    path = os.path.join(MACROS_DIR, f"{params.name}.ngc")
    with open(path, "w") as f:
        f.write(params.content)
    return {"status": "macro_saved", "name": params.name}

@app.get("/macros")
async def list_macros():
    return {"macros": os.listdir(MACROS_DIR)}

# 6. CONFIG (CRITICAL)
@app.post("/config/restore")
async def restore_config(backup_name: str, params: CommandBase):
    check_safety("CRITICAL", params.confirm)
    return {"status": "config_restored", "backup": backup_name}

@app.get("/")
async def root():
    return {"service": "linuxcnc-bridge", "mode": "STUB/SIMULATED", "status": "online"}
