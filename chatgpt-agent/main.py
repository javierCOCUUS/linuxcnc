from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
import os
import json
import httpx

app = FastAPI(title="chatgpt-agent")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
MCP_URL = os.getenv("MCP_URL", "http://mcp-orchestrator:8000")
OPENAI_API_URL = os.getenv("OPENAI_API_URL", "https://api.openai.com/v1/chat/completions")

SYSTEM_PROMPT = (
    "You are a CNC design assistant. Interpret the user's instructions and call the appropriate function to create, analyze, or generate CNC designs. "
    "Always use the defined functions when the user asks for an action, and do not invent data outside of the available tool names. "
    "If the user asks for information about tools or designs, use the catalog functions. "
    "When a design action is requested, return the result of the executed operation."
)

FUNCTIONS = [
    {
        "name": "create_rectangle",
        "description": "Create a parametric DXF rectangle.",
        "parameters": {
            "type": "object",
            "properties": {
                "output_filename": {"type": "string", "description": "DXF filename to create."},
                "width": {"type": "number", "description": "Rectangle width in mm."},
                "height": {"type": "number", "description": "Rectangle height in mm."},
                "r_br": {"type": "number", "description": "Bottom-right radius."},
                "r_tr": {"type": "number", "description": "Top-right radius."},
                "r_tl": {"type": "number", "description": "Top-left radius."},
                "r_bl": {"type": "number", "description": "Bottom-left radius."},
                "c_br": {"type": "number", "description": "Bottom-right chamfer."},
                "c_tr": {"type": "number", "description": "Top-right chamfer."},
                "c_tl": {"type": "number", "description": "Top-left chamfer."},
                "c_bl": {"type": "number", "description": "Bottom-left chamfer."},
                "layer": {"type": "string", "description": "DXF layer name."},
            },
            "required": ["output_filename", "width", "height"],
        },
    },
    {
        "name": "create_circle",
        "description": "Create a parametric DXF circle.",
        "parameters": {
            "type": "object",
            "properties": {
                "output_filename": {"type": "string"},
                "radius": {"type": "number"},
                "center_x": {"type": "number"},
                "center_y": {"type": "number"},
                "layer": {"type": "string"},
            },
            "required": ["output_filename", "radius"],
        },
    },
    {
        "name": "create_text",
        "description": "Create a DXF text entity.",
        "parameters": {
            "type": "object",
            "properties": {
                "output_filename": {"type": "string"},
                "text": {"type": "string"},
                "height": {"type": "number"},
                "x": {"type": "number"},
                "y": {"type": "number"},
                "font_name": {"type": ["string", "null"]},
                "font_type": {"type": "string"},
                "rotation": {"type": "number"},
                "alignment": {"type": "string"},
                "layer": {"type": "string"},
            },
            "required": ["output_filename", "text", "height"],
        },
    },
    {
        "name": "create_nesting",
        "description": "Nest multiple DXF pieces onto a sheet.",
        "parameters": {
            "type": "object",
            "properties": {
                "output_filename": {"type": "string"},
                "input_filenames": {"type": "array", "items": {"type": "string"}},
                "sheet_width": {"type": "number"},
                "sheet_height": {"type": "number"},
                "padding": {"type": "number"},
                "label_pieces": {"type": "boolean"},
            },
            "required": ["output_filename", "input_filenames", "sheet_width", "sheet_height"],
        },
    },
    {
        "name": "create_boolean",
        "description": "Perform a boolean operation between two DXF files.",
        "parameters": {
            "type": "object",
            "properties": {
                "output_filename": {"type": "string"},
                "filename_a": {"type": "string"},
                "filename_b": {"type": "string"},
                "operacion": {"type": "string", "enum": ["union", "difference", "intersection"]},
                "offset_x_b": {"type": "number"},
                "offset_y_b": {"type": "number"},
            },
            "required": ["output_filename", "filename_a", "filename_b", "operacion"],
        },
    },
    {
        "name": "analyze_dxf",
        "description": "Analyze a DXF file and return its bounding box and size.",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {"type": "string"},
            },
            "required": ["filename"],
        },
    },
    {
        "name": "generate_gcode",
        "description": "Generate G-code from a DXF file using cam-engine.",
        "parameters": {
            "type": "object",
            "properties": {
                "dxf_filename": {"type": "string"},
                "output_filename": {"type": "string"},
                "tool_id": {"type": "string"},
                "material_id": {"type": ["string", "null"]},
                "override_tool_number": {"type": ["integer", "null"]},
                "operation": {"type": "string"},
                "cut_depth_mm": {"type": "number"},
                "pass_depth_mm": {"type": ["number", "null"]},
                "tabs_enabled": {"type": "boolean"},
                "tab_width_mm": {"type": "number"},
                "tab_height_mm": {"type": "number"},
                "tab_count": {"type": "integer"},
                "material_thickness_mm": {"type": "number"},
                "leadin_type": {"type": "string"},
                "leadin_length_mm": {"type": "number"},
                "start_x_mm": {"type": ["number", "null"]},
                "start_y_mm": {"type": ["number", "null"]},
            },
            "required": ["dxf_filename", "output_filename", "tool_id"],
        },
    },
    {
        "name": "list_tools",
        "description": "List available catalogue tools.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "list_materials",
        "description": "List available catalogue materials.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "list_designs",
        "description": "List available catalogue designs.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
]

class ChatRequest(BaseModel):
    prompt: str = Field(..., description="Natural language instruction for CNC design.")
    history: Optional[List[Dict[str, str]]] = Field(default_factory=list, description="Optional prior conversation history.")

class ChatResponse(BaseModel):
    assistant_message: str
    function_call: Optional[Dict[str, Any]] = None
    function_result: Optional[Any] = None


@app.get("/")
async def root():
    return {"service": "chatgpt-agent", "status": "ok"}


async def _openai_chat(messages: List[Dict[str, str]], model: str) -> Dict[str, Any]:
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=500, detail="OPENAI_API_KEY is not configured.")

    payload = {
        "model": model,
        "messages": messages,
        "functions": FUNCTIONS,
        "function_call": "auto",
        "temperature": 0.2,
        "max_tokens": 512,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            OPENAI_API_URL,
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        if response.status_code >= 300:
            raise HTTPException(status_code=502, detail=f"OpenAI API error: {response.status_code} {response.text}")
        return response.json()


async def _proxy_post(path: str, data: Dict[str, Any]) -> Any:
    url = f"{MCP_URL}{path}"
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(url, json=data)
        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        return response.json()


async def _proxy_get(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    url = f"{MCP_URL}{path}"
    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.get(url, params=params)
        if response.status_code >= 400:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        return response.json()


async def _execute_function_call(function_call: Dict[str, Any]) -> Any:
    name = function_call.get("name")
    args_raw = function_call.get("arguments", "{}")
    try:
        arguments = json.loads(args_raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid function arguments: {exc}")

    if name == "create_rectangle":
        return await _proxy_post("/dxf/rectangle", arguments)
    if name == "create_circle":
        return await _proxy_post("/dxf/circle", arguments)
    if name == "create_text":
        return await _proxy_post("/dxf/text", arguments)
    if name == "create_nesting":
        return await _proxy_post("/dxf/nesting", arguments)
    if name == "create_boolean":
        return await _proxy_post("/dxf/boolean", arguments)
    if name == "analyze_dxf":
        return await _proxy_get("/dxf/analyze", params=arguments)
    if name == "generate_gcode":
        return await _proxy_post("/cam/generate", arguments)
    if name == "list_tools":
        return await _proxy_get("/catalogue/tools")
    if name == "list_materials":
        return await _proxy_get("/catalogue/materials")
    if name == "list_designs":
        return await _proxy_get("/catalogue/designs")

    raise HTTPException(status_code=400, detail=f"Unsupported function: {name}")


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    for item in request.history:
        if item.get("role") and item.get("content"):
            messages.append(item)
    messages.append({"role": "user", "content": request.prompt})

    completion = await _openai_chat(messages, OPENAI_MODEL)
    choice = completion.get("choices", [])[0]
    message = choice.get("message", {})

    function_call = message.get("function_call")
    if function_call:
        result = await _execute_function_call(function_call)
        return ChatResponse(
            assistant_message=f"Executed function {function_call.get('name')}.",
            function_call=function_call,
            function_result=result,
        )

    return ChatResponse(assistant_message=message.get("content", ""))
