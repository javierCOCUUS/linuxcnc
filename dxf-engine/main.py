from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import List, Optional
import os
import logic

app = FastAPI(title="dxf-engine")

# Workspace directory for DXF files
WORKSPACE = os.environ.get("DXF_WORKSPACE", "/workspace")
FONTS_DIR = os.environ.get("FONTS_DIR", "/fonts")

class RectangleParams(BaseModel):
    filename: str
    width: float
    height: float
    r_br: float = 0.0
    r_tr: float = 0.0
    r_tl: float = 0.0
    r_bl: float = 0.0
    c_br: float = 0.0
    c_tr: float = 0.0
    c_tl: float = 0.0
    c_bl: float = 0.0
    layer: str = "PERFIL"

class CircleParams(BaseModel):
    filename: str
    radius: float
    center_x: float = 0.0
    center_y: float = 0.0
    layer: str = "PERFIL"

class TextParams(BaseModel):
    filename: str
    text: str
    height: float
    x: float = 0.0
    y: float = 0.0
    font_name: Optional[str] = None
    font_type: str = "outline" 
    rotation: float = 0.0
    alignment: str = "left"
    layer: str = "GRABADO"

class PatternParams(BaseModel):
    input_filename: str
    output_filename: str
    cols: int
    rows: int
    spacing_x: float
    spacing_y: float

class NestingParams(BaseModel):
    output_filename: str
    input_filenames: List[str]
    sheet_width: float
    sheet_height: float
    padding: float = 5.0
    label_pieces: bool = True

class CollisionParams(BaseModel):
    filename_a: str
    filename_b: str
    offset_x_b: float = 0.0
    offset_y_b: float = 0.0
    min_distance: float = 0.0

class BooleanParams(BaseModel):
    output_filename: str
    filename_a: str
    filename_b: str
    operacion: str = "union"
    offset_x_b: float = 0.0
    offset_y_b: float = 0.0
    arc_tolerance: float = 0.1  # mm — controla suavidad de arcos (menor = más segmentos, más preciso)

@app.get("/")
async def root():
    return {"service": "dxf-engine", "status": "ok"}

@app.get("/analyze")
async def analyze_dxf(filename: str):
    path = os.path.join(WORKSPACE, filename)
    info = logic.get_dxf_info(path)
    if not info:
        raise HTTPException(status_code=404, detail="File not found or empty")
    return info

@app.post("/create/nesting")
async def create_nesting(params: NestingParams):
    input_paths = [os.path.join(WORKSPACE, f) for f in params.input_filenames]
    output_path = os.path.join(WORKSPACE, params.output_filename)
    success = logic.perform_nesting(
        output_path, input_paths, params.sheet_width, params.sheet_height, 
        params.padding, params.label_pieces
    )
    if not success:
        raise HTTPException(status_code=500, detail="Nesting failed")
    return {"status": "success", "path": output_path}

@app.post("/create/boolean")
async def create_boolean(params: BooleanParams):
    output_path = os.path.join(WORKSPACE, params.output_filename)
    success = logic.boolean_dxf_operation(
        output_path,
        os.path.join(WORKSPACE, params.filename_a),
        os.path.join(WORKSPACE, params.filename_b),
        operacion=params.operacion,
        offset_x_b=params.offset_x_b,
        offset_y_b=params.offset_y_b,
        arc_tolerance=params.arc_tolerance,
    )
    if not success:
        raise HTTPException(status_code=500, detail="Boolean DXF operation failed")
    return {"status": "success", "path": output_path}

@app.get("/bounds/{filename}")
async def get_bounds(filename: str):
    """Returns bounding box, center, and size of a DXF file."""
    path = os.path.join(WORKSPACE, filename)
    info = logic.get_dxf_info(path)
    if not info:
        raise HTTPException(status_code=404, detail=f"File not found or empty: {filename}")
    return info

@app.post("/create/rectangle")
async def create_rectangle(params: RectangleParams):
    path = os.path.join(WORKSPACE, params.filename)
    success = logic.generate_parametric_rectangle(
        path, params.width, params.height, 
        params.r_br, params.r_tr, params.r_tl, params.r_bl,
        params.c_br, params.c_tr, params.c_tl, params.c_bl,
        params.layer
    )
    if not success:
        raise HTTPException(status_code=500, detail="Failed to generate DXF")
    return {"status": "success", "path": path}

@app.post("/create/circle")
async def create_circle(params: CircleParams):
    path = os.path.join(WORKSPACE, params.filename)
    success = logic.generate_parametric_circle(path, params.radius, (params.center_x, params.center_y), params.layer)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to generate DXF")
    return {"status": "success", "path": path}

@app.get("/fonts")
async def list_fonts():
    """List available SHX and TTF fonts in the fonts directory."""
    if not os.path.exists(FONTS_DIR):
        return {"fonts": [], "fonts_dir": FONTS_DIR}
    fonts = [
        f for f in os.listdir(FONTS_DIR)
        if f.lower().endswith((".shx", ".ttf", ".otf"))
    ]
    return {"fonts": sorted(fonts), "fonts_dir": FONTS_DIR}


class PolylineParams(BaseModel):
    filename: str
    points: List[List[float]]
    closed: bool = False
    layer: str = "PERFIL"

class SplineParams(BaseModel):
    filename: str
    points: List[List[float]]
    closed: bool = False
    layer: str = "PERFIL"

class ArcParams(BaseModel):
    filename: str
    center_x: float
    center_y: float
    radius: float
    start_angle: float
    end_angle: float
    layer: str = "PERFIL"

class OffsetParams(BaseModel):
    input_filename: str
    output_filename: str
    distance: float
    layer: str = "PERFIL"

class TransformParams(BaseModel):
    input_filename: str
    output_filename: str
    translate_x: float = 0.0
    translate_y: float = 0.0
    rotate_deg: float = 0.0
    scale: float = 1.0
    layer: str = "PERFIL"

class MergeParams(BaseModel):
    output_filename: str
    input_filenames: List[str]

class ArrayParams(BaseModel):
    input_filename: str
    output_filename: str
    cols: int
    rows: int
    spacing_x: float
    spacing_y: float
    layer: str = "PERFIL"

class FilletParams(BaseModel):
    input_filename: str
    output_filename: str
    radius: float
    corner_type: str = "round"   # "round" | "chamfer"
    layer: str = "PERFIL"

class ChamferParams(BaseModel):
    input_filename: str
    output_filename: str
    distance: float
    layer: str = "PERFIL"


@app.post("/create/polyline")
async def create_polyline(params: PolylineParams):
    path = os.path.join(WORKSPACE, params.filename)
    success = logic.generate_polyline(path, params.points, params.closed, params.layer)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to generate polyline DXF")
    return {"status": "success", "path": path}

@app.post("/create/spline")
async def create_spline(params: SplineParams):
    path = os.path.join(WORKSPACE, params.filename)
    success = logic.generate_spline(path, params.points, params.closed, params.layer)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to generate spline DXF")
    return {"status": "success", "path": path}

@app.post("/create/arc")
async def create_arc(params: ArcParams):
    path = os.path.join(WORKSPACE, params.filename)
    success = logic.generate_arc(path, params.center_x, params.center_y, params.radius, params.start_angle, params.end_angle, params.layer)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to generate arc DXF")
    return {"status": "success", "path": path}

@app.post("/create/offset")
async def create_offset(params: OffsetParams):
    success = logic.offset_dxf(
        os.path.join(WORKSPACE, params.input_filename),
        os.path.join(WORKSPACE, params.output_filename),
        params.distance, params.layer
    )
    if not success:
        raise HTTPException(status_code=500, detail="Offset failed")
    return {"status": "success", "path": os.path.join(WORKSPACE, params.output_filename)}

@app.post("/create/transform")
async def create_transform(params: TransformParams):
    success = logic.transform_dxf(
        os.path.join(WORKSPACE, params.input_filename),
        os.path.join(WORKSPACE, params.output_filename),
        params.translate_x, params.translate_y,
        params.rotate_deg, params.scale, params.layer
    )
    if not success:
        raise HTTPException(status_code=500, detail="Transform failed")
    return {"status": "success", "path": os.path.join(WORKSPACE, params.output_filename)}

@app.post("/create/merge")
async def create_merge(params: MergeParams):
    input_paths = [os.path.join(WORKSPACE, f) for f in params.input_filenames]
    output_path = os.path.join(WORKSPACE, params.output_filename)
    success = logic.merge_dxf(output_path, input_paths)
    if not success:
        raise HTTPException(status_code=500, detail="Merge failed")
    return {"status": "success", "path": output_path}

@app.post("/create/fillet")
async def create_fillet(params: FilletParams):
    success = logic.fillet_dxf(
        os.path.join(WORKSPACE, params.input_filename),
        os.path.join(WORKSPACE, params.output_filename),
        params.radius, params.corner_type, params.layer
    )
    if not success:
        raise HTTPException(status_code=500, detail="Fillet failed — check radius is smaller than the smallest feature")
    return {"status": "success", "path": os.path.join(WORKSPACE, params.output_filename)}

@app.post("/create/chamfer")
async def create_chamfer(params: ChamferParams):
    success = logic.chamfer_dxf(
        os.path.join(WORKSPACE, params.input_filename),
        os.path.join(WORKSPACE, params.output_filename),
        params.distance, params.layer
    )
    if not success:
        raise HTTPException(status_code=500, detail="Chamfer failed — check distance is smaller than the smallest feature")
    return {"status": "success", "path": os.path.join(WORKSPACE, params.output_filename)}

@app.post("/create/array")
async def create_array(params: ArrayParams):
    success = logic.array_dxf(
        os.path.join(WORKSPACE, params.input_filename),
        os.path.join(WORKSPACE, params.output_filename),
        params.cols, params.rows, params.spacing_x, params.spacing_y, params.layer
    )
    if not success:
        raise HTTPException(status_code=500, detail="Array failed")
    return {"status": "success", "path": os.path.join(WORKSPACE, params.output_filename)}


class FingerJointParams(BaseModel):
    output_filename: str
    panel_width: float
    panel_height: float
    thickness: float
    finger_width: Optional[float] = None
    side: str = "a"          # "a" = starts with finger, "b" = complement
    edge: str = "bottom"     # "bottom" | "top" | "left" | "right"
    layer: str = "PERFIL"

class BoxParams(BaseModel):
    output_filename: str
    box_width: float
    box_height: float
    box_depth: float
    thickness: float
    finger_width: Optional[float] = None
    include_bottom: bool = True
    layer: str = "PERFIL"

@app.post("/create/finger_joint")
async def create_finger_joint(params: FingerJointParams):
    path = os.path.join(WORKSPACE, params.output_filename)
    success = logic.generate_finger_joint(
        path, params.panel_width, params.panel_height,
        params.thickness, params.finger_width,
        params.side, params.edge, params.layer
    )
    if not success:
        raise HTTPException(status_code=500, detail="Finger joint generation failed — check parameters")
    return {"status": "success", "path": path}

@app.post("/create/box")
async def create_box(params: BoxParams):
    path = os.path.join(WORKSPACE, params.output_filename)
    success = logic.generate_box(
        path, params.box_width, params.box_height, params.box_depth,
        params.thickness, params.finger_width,
        params.include_bottom, params.layer
    )
    if not success:
        raise HTTPException(status_code=500, detail="Box generation failed")
    return {"status": "success", "path": path}


class DogbonesParams(BaseModel):
    input_filename: str
    output_filename: str
    bit_diameter: float
    corner_type: str = "round"   # "round" | "tbone"
    layer: str = "PERFIL"

class AlignParams(BaseModel):
    input_filename: str
    output_filename: str
    anchor_x: Optional[str] = None   # "left" | "center" | "right"
    anchor_y: Optional[str] = None   # "bottom" | "center" | "top"
    target_x: Optional[float] = None
    target_y: Optional[float] = None
    ref_filename: Optional[str] = None
    ref_anchor_x: Optional[str] = None
    ref_anchor_y: Optional[str] = None
    offset_x: float = 0.0
    offset_y: float = 0.0

class CenterParams(BaseModel):
    input_filename: str
    output_filename: str
    target_x: float = 0.0
    target_y: float = 0.0
    ref_filename: Optional[str] = None
    offset_x: float = 0.0
    offset_y: float = 0.0

@app.post("/create/dogbones")
async def create_dogbones(params: DogbonesParams):
    count = logic.add_dogbones(
        os.path.join(WORKSPACE, params.output_filename),
        os.path.join(WORKSPACE, params.input_filename),
        params.bit_diameter, params.corner_type, params.layer
    )
    if count == 0:
        return {"status": "ok", "message": "No concave corners found — dogbones not needed for this profile", "circles_added": 0}
    return {"status": "success", "circles_added": count,
            "path": os.path.join(WORKSPACE, params.output_filename)}

@app.post("/create/align")
async def create_align(params: AlignParams):
    try:
        success = logic.align_dxf(
            os.path.join(WORKSPACE, params.output_filename),
            os.path.join(WORKSPACE, params.input_filename),
            params.anchor_x, params.anchor_y,
            params.target_x, params.target_y,
            os.path.join(WORKSPACE, params.ref_filename) if params.ref_filename else None,
            params.ref_anchor_x, params.ref_anchor_y,
            params.offset_x, params.offset_y
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not success:
        raise HTTPException(status_code=500, detail="Alignment failed")
    return {"status": "success", "path": os.path.join(WORKSPACE, params.output_filename)}

@app.post("/create/center")
async def create_center(params: CenterParams):
    try:
        success = logic.center_dxf(
            os.path.join(WORKSPACE, params.output_filename),
            os.path.join(WORKSPACE, params.input_filename),
            params.target_x,
            params.target_y,
            os.path.join(WORKSPACE, params.ref_filename) if params.ref_filename else None,
            params.offset_x,
            params.offset_y,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not success:
        raise HTTPException(status_code=500, detail="Center operation failed")
    return {"status": "success", "path": os.path.join(WORKSPACE, params.output_filename)}

@app.post("/create/text")
async def create_text(params: TextParams):
    # Validate font upfront — avoids slow failure deep in rendering
    if params.font_name:
        ext = os.path.splitext(params.font_name)[1].lower()
        if ext in ('.ttf', '.otf', '.shx'):
            font_path = os.path.join(FONTS_DIR, params.font_name)
            if not os.path.exists(font_path):
                available = sorted(f for f in os.listdir(FONTS_DIR) if f.lower().endswith(('.ttf', '.otf', '.shx'))) if os.path.isdir(FONTS_DIR) else []
                raise HTTPException(
                    status_code=422,
                    detail=f"Font '{params.font_name}' not found. Available: {available or ['none — use catalogue_fonts to check']}"
                )
    path = os.path.join(WORKSPACE, params.filename)
    try:
        success = logic.generate_cad_text(
            path, params.text, params.height, params.x, params.y,
            params.font_name, params.font_type, params.rotation, params.alignment,
            params.layer
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=422, detail=str(e))
    if not success:
        raise HTTPException(status_code=500, detail="Failed to generate DXF")
    return {"status": "success", "path": path}


@app.get("/preview/{filename}")
async def preview_dxf(filename: str):
    """Render a DXF file to PNG and return it as an image."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import ezdxf
    from ezdxf.addons.drawing import RenderContext, Frontend
    from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

    dxf_path = os.path.join(WORKSPACE, filename)
    if not os.path.exists(dxf_path):
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")

    png_name = filename.rsplit(".", 1)[0] + ".png"
    png_path = os.path.join(WORKSPACE, png_name)

    try:
        doc = ezdxf.readfile(dxf_path)
        msp = doc.modelspace()
        fig = plt.figure(figsize=(10, 10), facecolor="white")
        ax = fig.add_axes([0, 0, 1, 1])
        ctx = RenderContext(doc)
        backend = MatplotlibBackend(ax)
        Frontend(ctx, backend).draw_layout(msp, finalize=True)
        fig.savefig(png_path, dpi=150, bbox_inches="tight", facecolor="white")
        plt.close(fig)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Render failed: {e}")

    return FileResponse(png_path, media_type="image/png", filename=png_name)


@app.get("/files/{filename}")
async def serve_workspace_file(filename: str):
    """Serve any file from the workspace (DXF, PNG, G-code, etc.)."""
    import mimetypes
    path = os.path.join(WORKSPACE, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")
    mime, _ = mimetypes.guess_type(filename)
    mime = mime or "application/octet-stream"
    return FileResponse(path, media_type=mime, filename=filename)
