from fastapi import FastAPI
import json
from pathlib import Path

app = FastAPI(title="catalogue")
BASE = Path(__file__).parent / "data"


def _load(name: str):
    p = BASE / name
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding='utf-8-sig'))


@app.get("/tools")
async def list_tools():
    return _load("tools.json")


@app.get("/materials")
async def list_materials():
    return _load("materials.json")


@app.get("/designs")
async def list_designs():
    return _load("designs.json")


@app.post("/designs")
async def add_design(design: dict):
    p = BASE / "designs.json"
    data = _load("designs.json")
    if isinstance(data, list):
        data.append(design)
    elif isinstance(data, dict):
        key = design.get("name", design.get("filename", str(len(data))))
        data[key] = design
    else:
        data = [design]
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"status": "added", "design": design}
