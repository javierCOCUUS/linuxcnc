import ezdxf
import os
import math
import logging
from ezdxf.enums import TextEntityAlignment
from shapely.geometry import Polygon, MultiPolygon, LineString, MultiLineString, GeometryCollection, Point
from shapely.ops import unary_union, polygonize, linemerge
import rectpack


logger = logging.getLogger(__name__)

def generate_parametric_circle(nombre_archivo, radius_mm, center=(0,0), layer="PERFIL"):
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    msp.add_circle(center=center, radius=radius_mm,
                   dxfattribs={'layer': layer, 'color': 1 if layer == "PERFIL" else 2})
    destino = os.path.dirname(nombre_archivo)
    if destino and not os.path.exists(destino): os.makedirs(destino, exist_ok=True)
    doc.saveas(nombre_archivo)
    return True

def generate_parametric_rectangle(nombre_archivo, width_mm, height_mm, 
                                 r_br=0.0, r_tr=0.0, r_tl=0.0, r_bl=0.0, 
                                 c_br=0.0, c_tr=0.0, c_tl=0.0, c_bl=0.0,
                                 layer="PERFIL"):
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    w, h = width_mm, height_mm
    A = {'layer': layer, 'color': 1}

    # Rectangle with no corner modifications → single closed LWPOLYLINE
    # This makes it directly compatible with dxf_fillet and dxf_chamfer
    has_corners = any(v > 0.001 for v in [r_br, r_tr, r_tl, r_bl, c_br, c_tr, c_tl, c_bl])
    if not has_corners:
        msp.add_lwpolyline(
            [(0, 0), (w, 0), (w, h), (0, h)],
            dxfattribs={**A, 'closed': True}
        )
        doc.saveas(nombre_archivo)
        return True

    def add_line(p1, p2): msp.add_line(start=p1, end=p2, dxfattribs=A)
    def add_arc(cx, cy, r, a_start, a_end):
        if r > 0.001: msp.add_arc(center=(cx, cy), radius=r, start_angle=a_start, end_angle=a_end, dxfattribs=A)

    p_bl_start = (c_bl if c_bl > 0 else r_bl, 0)
    p_br_end = (w - (c_br if c_br > 0 else r_br), 0)
    add_line(p_bl_start, p_br_end)
    if c_br > 0: add_line((w - c_br, 0), (w, c_br))
    else: add_arc(w - r_br, r_br, r_br, 270, 360)
    p_br_up = (w, c_br if c_br > 0 else r_br)
    p_tr_down = (w, h - (c_tr if c_tr > 0 else r_tr))
    add_line(p_br_up, p_tr_down)
    if c_tr > 0: add_line((w, h - c_tr), (w - c_tr, h))
    else: add_arc(w - r_tr, h - r_tr, r_tr, 0, 90)
    p_tr_left = (w - (c_tr if c_tr > 0 else r_tr), h)
    p_tl_right = (c_tl if c_tl > 0 else r_tl, h)
    add_line(p_tr_left, p_tl_right)
    if c_tl > 0: add_line((c_tl, h), (0, h - c_tl))
    else: add_arc(r_tl, h - r_tl, r_tl, 90, 180)
    p_tl_down = (0, h - (c_tl if c_tl > 0 else r_tl))
    p_bl_up = (0, c_bl if c_bl > 0 else r_bl)
    add_line(p_tl_down, p_bl_up)
    if c_bl > 0: add_line((0, c_bl), (c_bl, 0))
    else: add_arc(r_bl, r_bl, r_bl, 180, 270)
    doc.saveas(nombre_archivo)
    return True

def perform_nesting(nombre_archivo_salida, lista_archivos, sheet_w, sheet_h, padding=5.0, label_pieces=False):
    """Anida múltiples piezas en un tablero usando rectpack."""
    packer = rectpack.newPacker(rotation=True)
    packer.add_bin(sheet_w, sheet_h)
    
    piece_data = []
    for idx, fpath in enumerate(lista_archivos):
        info = get_dxf_info(fpath)
        if info:
            # Añadimos padding al tamaño para seguridad
            w = info["size"]["width"] + padding * 2
            h = info["size"]["height"] + padding * 2
            packer.add_rect(w, h, idx)
            piece_data.append({"path": fpath, "info": info})
            
    packer.pack()
    
    doc_salida = ezdxf.new('R2010')
    msp_salida = doc_salida.modelspace()
    
    # Dibujar borde del tablero
    msp_salida.add_lwpolyline([(0,0), (sheet_w,0), (sheet_w,sheet_h), (0,sheet_h), (0,0)], dxfattribs={'layer': 'TABLERO', 'color': 8})

    for rect in packer[0]:
        idx = rect.rid
        data = piece_data[idx]
        # rectpack devuelve x, y de la esquina inferior izquierda
        # Pero nuestras piezas pueden no estar centradas en 0,0
        # Offset real = rect.x + padding - bbox.min_x
        off_x = rect.x + padding - data["info"]["bbox"]["min_x"]
        off_y = rect.y + padding - data["info"]["bbox"]["min_y"]
        
        # Importar entidades
        doc_in = ezdxf.readfile(data["path"])
        for entity in doc_in.modelspace():
            new_ent = entity.copy()
            if rect.width < rect.height != data["info"]["size"]["width"] < data["info"]["size"]["height"]:
                # Rotación si rectpack rotó la pieza
                new_ent.rotate_z(math.radians(90))
                # Ajustar offset tras rotación... (simplificado)
                pass 
            new_ent.translate(off_x, off_y, 0)
            msp_salida.add_entity(new_ent)
            
        if label_pieces:
            # Etiquetar en el centro
            cx = rect.x + rect.width / 2
            cy = rect.y + rect.height / 2
            label_text = os.path.basename(data["path"]).replace(".dxf", "")
            generate_cad_text_internal(msp_salida, label_text, 5.0, cx, cy, alignment='center', layer="ETIQUETAS")

    doc_salida.saveas(nombre_archivo_salida)
    return True

def _generate_text_vectorized(nombre_archivo, text, height_mm, x, y, font_name, rotation_deg, alignment, layer):
    """Convert text to DXF polylines using matplotlib font rendering (TTF/OTF only)."""
    import matplotlib
    matplotlib.use('Agg')
    from matplotlib.textpath import TextPath
    from matplotlib.font_manager import FontProperties

    fonts_dir = os.environ.get('FONTS_DIR', '/fonts')
    fp = FontProperties()
    if font_name:
        ext = os.path.splitext(font_name)[1].lower()
        if ext in ('.ttf', '.otf'):
            font_path = os.path.join(fonts_dir, font_name)
            if not os.path.exists(font_path):
                available = sorted(f for f in os.listdir(fonts_dir) if f.lower().endswith(('.ttf', '.otf', '.shx'))) if os.path.isdir(fonts_dir) else []
                raise FileNotFoundError(
                    f"Font '{font_name}' not found in {fonts_dir}. "
                    f"Available: {available or ['none — upload a font to /fonts first']}"
                )
            fp = FontProperties(fname=font_path)

    tp = TextPath((0, 0), text, size=height_mm, prop=fp)
    polys = tp.to_polygons()  # flattens bezier curves → list of (N,2) arrays
    if not polys:
        return False

    bbox = tp.get_extents()
    text_w = bbox.width if bbox.width > 0 else 0
    dx_align = -text_w / 2 if alignment == 'center' else (-text_w if alignment == 'right' else 0)

    cos_r = math.cos(math.radians(rotation_deg))
    sin_r = math.sin(math.radians(rotation_deg))

    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    for poly in polys:
        pts = []
        for px, py in poly:
            px += dx_align
            rx = px * cos_r - py * sin_r + x
            ry = px * sin_r + py * cos_r + y
            pts.append((rx, ry))
        if len(pts) >= 2:
            msp.add_lwpolyline(pts, dxfattribs={'layer': layer, 'color': 1, 'closed': True})
    doc.saveas(nombre_archivo)
    return True


def generate_cad_text_internal(msp, text, height_mm, x, y, alignment='left', layer="ETIQUETAS", font_name=None):
    """Versión interna para añadir texto a un modelspace existente."""
    dxfattribs = {'layer': layer, 'color': 3, 'height': height_mm}
    if font_name:
        doc = msp.doc
        style_name = os.path.splitext(font_name)[0].upper()
        fonts_dir = os.environ.get('FONTS_DIR', '/fonts')
        font_path = os.path.join(fonts_dir, font_name) if not os.path.isabs(font_name) else font_name
        if style_name not in doc.styles:
            doc.styles.new(style_name, dxfattribs={'font': font_path})
        dxfattribs['style'] = style_name
    msp.add_text(text, dxfattribs=dxfattribs).set_placement((x, y), align=TextEntityAlignment.CENTER)


def generate_cad_text(nombre_archivo, text, height_mm, pos_x_mm=0.0, pos_y_mm=0.0,
                       font_name=None, font_type='outline', rotation_degrees=0.0,
                       alignment='left', layer="GRABADO"):
    """Generate text as vector polylines (TTF/OTF) or DXF TEXT entity (SHX/fallback)."""
    # Attempt vectorized rendering for TTF/OTF — real geometry for CAM/boolean/preview
    if font_name is None or os.path.splitext(font_name)[1].lower() in ('.ttf', '.otf'):
        try:
            ok = _generate_text_vectorized(
                nombre_archivo, text, height_mm, pos_x_mm, pos_y_mm,
                font_name, rotation_degrees, alignment, layer
            )
            if ok:
                return True
        except FileNotFoundError:
            raise  # font not found — propagate to caller as 422
        except Exception as exc:
            logger.warning("Vectorized text rendering failed, falling back to DXF TEXT", exc_info=exc)
    # Fallback: DXF TEXT entity (SHX or no font — viewer-dependent rendering)
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    generate_cad_text_internal(msp, text, height_mm, pos_x_mm, pos_y_mm, alignment, layer, font_name=font_name)
    doc.saveas(nombre_archivo)
    return True


def get_dxf_info(filepath):
    if not os.path.exists(filepath): return None
    doc = ezdxf.readfile(filepath)
    msp = doc.modelspace()
    from ezdxf import path as ezpath
    all_points = []
    for entity in msp:
        try:
            p = ezpath.make_path(entity)
            for v in p.flattening(1.0): all_points.append((v.x, v.y))
        except Exception as exc:
            logger.warning("Skipping DXF entity during bounds analysis: %s", entity.dxftype(), exc_info=exc)
    if not all_points: return None
    xs, ys = [p[0] for p in all_points], [p[1] for p in all_points]
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
    return {
        "bbox": {"min_x": min_x, "max_x": max_x, "min_y": min_y, "max_y": max_y},
        "center": {"x": (min_x + max_x) / 2, "y": (min_y + max_y) / 2},
        "size": {"width": max_x - min_x, "height": max_y - min_y}
    }


def _leer_shape(filepath, dx=0.0, dy=0.0, arc_tolerance=0.1):
    from ezdxf import path as ezpath
    doc = ezdxf.readfile(filepath)
    msp = doc.modelspace()
    closed_polys, open_paths = [], []
    for entity in msp:
        try:
            p = ezpath.make_path(entity)
            pts = [(v.x + dx, v.y + dy) for v in p.flattening(arc_tolerance)]
            if len(pts) < 2: continue
            is_closed = False
            if entity.dxftype() == 'LWPOLYLINE': is_closed = entity.closed
            elif entity.dxftype() in ('CIRCLE', 'ELLIPSE'): is_closed = True
            if is_closed or (pts[0] == pts[-1]): closed_polys.append(Polygon(pts))
            else: open_paths.append(LineString(pts))
        except Exception as exc:
            logger.warning("Skipping DXF entity during shape extraction: %s", entity.dxftype(), exc_info=exc)
            continue
    if not closed_polys and not open_paths: return None
    return unary_union(closed_polys + open_paths)

def boolean_dxf_operation(nombre_archivo_salida, archivo_a, archivo_b, operacion='union', offset_x_b=0.0, offset_y_b=0.0, arc_tolerance=0.1):
    shape_a = _leer_shape(archivo_a, arc_tolerance=arc_tolerance)
    shape_b = _leer_shape(archivo_b, offset_x_b, offset_y_b, arc_tolerance=arc_tolerance)
    if shape_a is None or shape_b is None: return False
    if operacion == 'union': res = shape_a.union(shape_b)
    elif operacion == 'difference': res = shape_a.difference(shape_b)
    elif operacion == 'intersection': res = shape_a.intersection(shape_b)
    else: return False
    doc_salida = ezdxf.new('R2010')
    msp_salida = doc_salida.modelspace()
    def _exp(geom):
        if geom is None or geom.is_empty: return
        t = geom.geom_type
        if t == 'Polygon':
            msp_salida.add_lwpolyline(list(geom.exterior.coords), dxfattribs={'layer': 'PERFIL', 'color': 1})
            for i in geom.interiors: msp_salida.add_lwpolyline(list(i.coords), dxfattribs={'layer': 'AGUJEROS', 'color': 2})
        elif t in ('MultiPolygon', 'GeometryCollection'):
            for sub in geom.geoms: _exp(sub)
        elif t in ('LineString', 'MultiLineString'):
            for ls in ([geom] if t == 'LineString' else geom.geoms):
                msp_salida.add_lwpolyline(list(ls.coords), dxfattribs={'layer': 'PERFIL', 'color': 1})
    _exp(res)
    doc_salida.saveas(nombre_archivo_salida)
    return True


def generate_polyline(nombre_archivo, points, closed=False, layer="PERFIL"):
    """Genera una polilínea arbitraria a partir de una lista de puntos [[x,y],...]."""
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    msp.add_lwpolyline(points, dxfattribs={'layer': layer, 'color': 1, 'closed': closed})
    doc.saveas(nombre_archivo)
    return True


def generate_spline(nombre_archivo, points, closed=False, layer="PERFIL"):
    """Genera una spline suave a partir de puntos de control [[x,y],...]."""
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    pts3d = [(p[0], p[1], 0) for p in points]
    spline = msp.add_spline(pts3d, dxfattribs={'layer': layer, 'color': 1})
    if closed:
        spline.closed = True
    doc.saveas(nombre_archivo)
    return True


def generate_arc(nombre_archivo, center_x, center_y, radius, start_angle, end_angle, layer="PERFIL"):
    """Genera un arco definido por centro, radio y ángulos de inicio/fin en grados."""
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    msp.add_arc(
        center=(center_x, center_y),
        radius=radius,
        start_angle=start_angle,
        end_angle=end_angle,
        dxfattribs={'layer': layer, 'color': 1}
    )
    doc.saveas(nombre_archivo)
    return True


def offset_dxf(nombre_archivo_entrada, nombre_archivo_salida, distance, layer="PERFIL"):
    """Genera el offset de todos los contornos de un DXF a una distancia dada."""
    shape = _leer_shape(nombre_archivo_entrada)
    if shape is None:
        return False
    try:
        offsetted = shape.buffer(distance, join_style=2)  # 2=mitre
    except Exception as exc:
        logger.warning("Offset operation failed for '%s'", nombre_archivo_entrada, exc_info=exc)
        return False
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    def _exp(geom):
        if geom is None or geom.is_empty:
            return
        t = geom.geom_type
        if t == 'Polygon':
            msp.add_lwpolyline(list(geom.exterior.coords), dxfattribs={'layer': layer, 'color': 1})
            for i in geom.interiors:
                msp.add_lwpolyline(list(i.coords), dxfattribs={'layer': 'AGUJEROS', 'color': 2})
        elif t in ('MultiPolygon', 'GeometryCollection'):
            for sub in geom.geoms:
                _exp(sub)
        elif t in ('LineString', 'MultiLineString'):
            for ls in ([geom] if t == 'LineString' else geom.geoms):
                msp.add_lwpolyline(list(ls.coords), dxfattribs={'layer': layer, 'color': 1})
    _exp(offsetted)
    doc.saveas(nombre_archivo_salida)
    return True


def transform_dxf(nombre_archivo_entrada, nombre_archivo_salida,
                   translate_x=0.0, translate_y=0.0,
                   rotate_deg=0.0, scale=1.0, layer="PERFIL"):
    """Aplica traslación, rotación y escala a todas las entidades de un DXF."""
    shape = _leer_shape(nombre_archivo_entrada)
    if shape is None:
        return False
    from shapely import affinity
    if scale != 1.0:
        shape = affinity.scale(shape, xfact=scale, yfact=scale, origin=(0, 0))
    if rotate_deg != 0.0:
        shape = affinity.rotate(shape, rotate_deg, origin=(0, 0))
    if translate_x != 0.0 or translate_y != 0.0:
        shape = affinity.translate(shape, xoff=translate_x, yoff=translate_y)
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    def _exp(geom):
        if geom is None or geom.is_empty:
            return
        t = geom.geom_type
        if t == 'Polygon':
            msp.add_lwpolyline(list(geom.exterior.coords), dxfattribs={'layer': layer, 'color': 1})
            for i in geom.interiors:
                msp.add_lwpolyline(list(i.coords), dxfattribs={'layer': 'AGUJEROS', 'color': 2})
        elif t in ('MultiPolygon', 'GeometryCollection'):
            for sub in geom.geoms:
                _exp(sub)
        elif t in ('LineString', 'MultiLineString'):
            for ls in ([geom] if t == 'LineString' else geom.geoms):
                msp.add_lwpolyline(list(ls.coords), dxfattribs={'layer': layer, 'color': 1})
    _exp(shape)
    doc.saveas(nombre_archivo_salida)
    return True


def merge_dxf(nombre_archivo_salida, archivos_entrada):
    """Fusiona múltiples DXF en uno solo copiando todas sus entidades."""
    doc_out = ezdxf.new('R2010')
    msp_out = doc_out.modelspace()
    for fpath in archivos_entrada:
        if not os.path.exists(fpath):
            continue
        doc_in = ezdxf.readfile(fpath)
        msp_in = doc_in.modelspace()
        for entity in msp_in:
            try:
                msp_out.add_entity(entity.copy())
            except Exception as exc:
                logger.warning("Skipping entity during merge from '%s': %s", fpath, entity.dxftype(), exc_info=exc)
    doc_out.saveas(nombre_archivo_salida)
    return True


def fillet_dxf(nombre_archivo_entrada, nombre_archivo_salida, radius, corner_type="round", layer="PERFIL"):
    """Aplica redondeo (fillet) o chaflán (chamfer) a todas las esquinas de un DXF.

    corner_type="round"   → arco tangente en cada esquina (radio = radius mm)
    corner_type="chamfer" → corte plano a 45 ° en cada esquina (distancia = radius mm)

    Algoritmo: erosión morfológica (buffer -r) seguida de dilatación (buffer +r).
    Funciona con LWPOLYLINE cerrada, polígonos y cualquier contorno cerrado.
    """
    shape = _leer_shape(nombre_archivo_entrada)
    if shape is None:
        return False
    try:
        if corner_type == "chamfer":
            # join_style=3 → bevel: crea corte plano en cada esquina
            result = shape.buffer(-radius, join_style=3).buffer(radius, join_style=3)
        else:
            # join_style=1 → round: crea arco en cada esquina
            result = shape.buffer(-radius, join_style=1).buffer(radius, join_style=1)
    except Exception as exc:
        logger.warning("Fillet operation failed for '%s'", nombre_archivo_entrada, exc_info=exc)
        return False
    if result is None or result.is_empty:
        return False
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    def _exp(geom):
        if geom is None or geom.is_empty:
            return
        t = geom.geom_type
        if t == 'Polygon':
            msp.add_lwpolyline(list(geom.exterior.coords), dxfattribs={'layer': layer, 'color': 1})
            for interior in geom.interiors:
                msp.add_lwpolyline(list(interior.coords), dxfattribs={'layer': 'AGUJEROS', 'color': 2})
        elif t in ('MultiPolygon', 'GeometryCollection'):
            for sub in geom.geoms:
                _exp(sub)
        elif t in ('LineString', 'MultiLineString'):
            for ls in ([geom] if t == 'LineString' else geom.geoms):
                msp.add_lwpolyline(list(ls.coords), dxfattribs={'layer': layer, 'color': 1})
    _exp(result)
    doc.saveas(nombre_archivo_salida)
    return True


def chamfer_dxf(nombre_archivo_entrada, nombre_archivo_salida, distance, layer="PERFIL"):
    """Aplica chaflán plano a 45° (bevel) a todas las esquinas de un DXF.

    El parámetro `distance` es la longitud del corte en mm medida desde el vértice
    (equivalente al parámetro C en G-code CAD estándar).
    Internamente usa erosión + dilatación con join_style=3 (bevel de Shapely).
    """
    return fillet_dxf(nombre_archivo_entrada, nombre_archivo_salida,
                      distance, corner_type="chamfer", layer=layer)


def array_dxf(nombre_archivo_entrada, nombre_archivo_salida,
               cols, rows, spacing_x, spacing_y, layer="PERFIL"):
    """Genera un array rectangular (cols x rows) de un DXF con el espaciado dado."""
    shape = _leer_shape(nombre_archivo_entrada)
    if shape is None:
        return False
    from shapely import affinity
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    def _add_shape(s):
        if s is None or s.is_empty:
            return
        t = s.geom_type
        if t == 'Polygon':
            msp.add_lwpolyline(list(s.exterior.coords), dxfattribs={'layer': layer, 'color': 1})
            for i in s.interiors:
                msp.add_lwpolyline(list(i.coords), dxfattribs={'layer': 'AGUJEROS', 'color': 2})
        elif t in ('MultiPolygon', 'GeometryCollection'):
            for sub in s.geoms:
                _add_shape(sub)
        elif t in ('LineString', 'MultiLineString'):
            for ls in ([s] if t == 'LineString' else s.geoms):
                msp.add_lwpolyline(list(ls.coords), dxfattribs={'layer': layer, 'color': 1})
    for row in range(rows):
        for col in range(cols):
            translated = affinity.translate(shape, xoff=col * spacing_x, yoff=row * spacing_y)
            _add_shape(translated)
    doc.saveas(nombre_archivo_salida)
    return True


def generate_finger_joint(output_filename, panel_width, panel_height,
                           thickness, finger_width=None, side='a',
                           edge='bottom', layer='PERFIL'):
    """Generate a rectangular panel with a finger joint on one edge.

    panel_width × panel_height: nominal bounding box of the panel.
    thickness: finger depth = material thickness of the mating panel.
    finger_width: width of each finger segment (default = thickness).
    side: 'a' = starts with finger protrusion; 'b' = complement (starts with gap).
    edge: 'bottom' | 'top' | 'left' | 'right' — which edge gets the joint.
    Protrusions extend OUTWARD past the nominal bounding box by `thickness`.
    """
    if finger_width is None:
        finger_width = thickness
    joint_len = panel_width if edge in ('bottom', 'top') else panel_height
    n = max(1, round(joint_len / finger_width))
    if n % 2 == 0:
        n += 1  # keep odd for symmetric corners (same feature at both ends)
    fw = joint_len / n
    is_f = lambda i: (i % 2 == 0) if side == 'a' else (i % 2 == 1)

    def _dedup_append(pts, pt):
        if not pts or pts[-1] != pt:
            pts.append(pt)

    pts = []

    if edge == 'bottom':
        # Clockwise: bottom (with joint, protrusions DOWN y<0) → right → top → left
        for i in range(n):
            x0, x1 = i * fw, (i + 1) * fw
            if is_f(i):
                _dedup_append(pts, (x0, 0.0))
                pts += [(x0, -thickness), (x1, -thickness), (x1, 0.0)]
            else:
                _dedup_append(pts, (x0, 0.0))
                _dedup_append(pts, (x1, 0.0))
        pts += [(panel_width, panel_height), (0.0, panel_height)]

    elif edge == 'top':
        # Clockwise: bottom → right → top (with joint, protrusions UP y>panel_height) → left
        pts = [(0.0, 0.0), (panel_width, 0.0), (panel_width, panel_height)]
        for i in range(n - 1, -1, -1):
            x0, x1 = i * fw, (i + 1) * fw
            if is_f(i):
                _dedup_append(pts, (x1, panel_height))
                pts += [(x1, panel_height + thickness), (x0, panel_height + thickness), (x0, panel_height)]
            else:
                _dedup_append(pts, (x1, panel_height))
                _dedup_append(pts, (x0, panel_height))

    elif edge == 'right':
        # Clockwise: bottom → right (with joint, protrusions RIGHT x>panel_width) → top → left
        pts = [(0.0, 0.0), (panel_width, 0.0)]
        for i in range(n):
            y0, y1 = i * fw, (i + 1) * fw
            if is_f(i):
                _dedup_append(pts, (panel_width, y0))
                pts += [(panel_width + thickness, y0), (panel_width + thickness, y1), (panel_width, y1)]
            else:
                _dedup_append(pts, (panel_width, y0))
                _dedup_append(pts, (panel_width, y1))
        pts.append((0.0, panel_height))

    elif edge == 'left':
        # Clockwise: bottom → right → top → left (with joint, protrusions LEFT x<0)
        pts = [(0.0, 0.0), (panel_width, 0.0), (panel_width, panel_height)]
        for i in range(n - 1, -1, -1):
            y0, y1 = i * fw, (i + 1) * fw
            if is_f(i):
                _dedup_append(pts, (0.0, y1))
                pts += [(-thickness, y1), (-thickness, y0), (0.0, y0)]
            else:
                _dedup_append(pts, (0.0, y1))
                _dedup_append(pts, (0.0, y0))
    else:
        return False

    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    msp.add_lwpolyline(pts, dxfattribs={'layer': layer, 'color': 1, 'closed': True})
    doc.saveas(output_filename)
    return True


def generate_box(output_filename, box_width, box_height, box_depth,
                 thickness, finger_width=None, include_bottom=True, layer='PERFIL'):
    """Generate all panels of a rectangular open-top box with finger joints.

    Box panels (all in one DXF, arranged for flat cutting):
      Front / Back : box_width  × box_height, 'a' joints on left + right edges
      Left  / Right: box_depth  × box_height, 'b' joints on left + right edges
      Bottom (opt) : box_width  × box_depth,  plain rectangle (fits inside walls)

    Outer box dimensions when assembled ≈ box_width × box_depth × box_height
    (corner finger protrusions add ±thickness at each corner, visible on outside).
    """
    if finger_width is None:
        finger_width = thickness
    W, H, D, T = box_width, box_height, box_depth, thickness

    # Finger count along H (same for all four corner edges, so joints interlock)
    n = max(1, round(H / finger_width))
    if n % 2 == 0:
        n += 1
    fw = H / n

    def _dedup_append(pts, pt):
        if not pts or pts[-1] != pt:
            pts.append(pt)

    def _make_panel_lr(width, is_a):
        """Panel width × H with finger joints on left AND right edges."""
        is_f = lambda i: (i % 2 == 0) if is_a else (i % 2 == 1)
        pts = [(0.0, 0.0), (width, 0.0)]
        # Right edge: bottom → top, protrusions RIGHT (+x)
        for i in range(n):
            y0, y1 = i * fw, (i + 1) * fw
            if is_f(i):
                _dedup_append(pts, (width, y0))
                pts += [(width + T, y0), (width + T, y1), (width, y1)]
            else:
                _dedup_append(pts, (width, y0))
                _dedup_append(pts, (width, y1))
        pts.append((0.0, H))
        # Left edge: top → bottom, protrusions LEFT (-x)
        for i in range(n - 1, -1, -1):
            y0, y1 = i * fw, (i + 1) * fw
            if is_f(i):
                _dedup_append(pts, (0.0, y1))
                pts += [(-T, y1), (-T, y0), (0.0, y0)]
            else:
                _dedup_append(pts, (0.0, y1))
                _dedup_append(pts, (0.0, y0))
        return pts

    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    A = {'layer': layer, 'color': 1}
    gap = max(20.0, T * 3)  # spacing between panels in the DXF layout

    def place(pts, ox, oy):
        msp.add_lwpolyline(
            [(x + ox, y + oy) for x, y in pts],
            dxfattribs={**A, 'closed': True}
        )

    fp = _make_panel_lr(W, is_a=True)   # Front / Back ('a' side)
    lp = _make_panel_lr(D, is_a=False)  # Left / Right ('b' side, complement)

    # Horizontal layout: Front | Left | Back | Right
    # Each panel's bounding box extends ±T on the jointed sides
    fp_ox = T                       # leave T space for left-edge protrusions
    lp_ox = fp_ox + W + T + gap     # after front panel right protrusion + gap
    bp_ox = lp_ox + D + T + gap     # after left panel right protrusion + gap
    rp_ox = bp_ox + W + T + gap     # after back panel right protrusion + gap

    place(fp, fp_ox, 0.0)           # Front
    place(lp, lp_ox, 0.0)           # Left
    place(fp, bp_ox, 0.0)           # Back (same geometry as front)
    place(lp, rp_ox, 0.0)           # Right (same geometry as left)

    if include_bottom:
        # Bottom sits flush inside the four walls — plain rectangle, no joints
        bottom_pts = [(0.0, 0.0), (W, 0.0), (W, D), (0.0, D)]
        place(bottom_pts, fp_ox, -(D + gap))

    doc.saveas(output_filename)
    return True


def add_dogbones(output_filename, input_filename, bit_diameter, corner_type='round', layer='PERFIL'):
    """Add dogbone cutouts at concave (interior) corners of LWPOLYLINE profiles.

    At each concave corner, a circle of radius bit_diameter/2 is placed so that
    a round end mill can fully cut the corner, allowing mating pieces to fit flush.

    bit_diameter : diameter of the end mill in mm.
    corner_type  : 'round' (classic dogbone circle) or 'tbone' (T-bone: circle
                   offset along one edge, easier to cut but visible on the outside).
    """
    bit_r = bit_diameter / 2.0

    doc = ezdxf.readfile(input_filename)
    msp = doc.modelspace()
    A = {'layer': layer, 'color': 7}
    circles_added = 0

    for pline in msp.query("LWPOLYLINE"):
        pts = [(p[0], p[1]) for p in pline.get_points()]
        n = len(pts)
        if n < 3:
            continue
        closed = bool(pline.dxf.flags & 1) or (
            abs(pts[0][0] - pts[-1][0]) < 1e-6 and abs(pts[0][1] - pts[-1][1]) < 1e-6
        )
        if not closed:
            continue
        # Remove duplicate closing vertex if present
        if abs(pts[0][0] - pts[-1][0]) < 1e-6 and abs(pts[0][1] - pts[-1][1]) < 1e-6:
            pts = pts[:-1]
            n -= 1

        # Signed area (Shoelace) to determine winding
        area = sum(
            pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1]
            for i in range(n)
        ) / 2.0
        ccw = area > 0

        for i in range(n):
            prev = pts[(i - 1) % n]
            curr = pts[i]
            nxt  = pts[(i + 1) % n]

            v1 = (prev[0] - curr[0], prev[1] - curr[1])
            v2 = (nxt[0]  - curr[0], nxt[1]  - curr[1])
            l1 = math.hypot(*v1)
            l2 = math.hypot(*v2)
            if l1 < 1e-9 or l2 < 1e-9:
                continue

            d1 = (v1[0] / l1, v1[1] / l1)
            d2 = (v2[0] / l2, v2[1] / l2)

            in_vec  = (curr[0] - prev[0], curr[1] - prev[1])
            out_vec = (nxt[0]  - curr[0], nxt[1]  - curr[1])
            cross = in_vec[0] * out_vec[1] - in_vec[1] * out_vec[0]

            is_concave = (cross < 0) if ccw else (cross > 0)
            if not is_concave:
                continue

            bx, by = d1[0] + d2[0], d1[1] + d2[1]
            bl = math.hypot(bx, by)
            if bl < 1e-9:
                continue
            bx, by = bx / bl, by / bl

            dot = max(-1.0, min(1.0, d1[0] * d2[0] + d1[1] * d2[1]))
            half_sin = math.sqrt((1.0 - dot) / 2.0)
            dist = bit_r / half_sin if half_sin > 1e-6 else bit_r * math.sqrt(2)

            if corner_type == 'tbone':
                side = d1 if l1 >= l2 else d2
                cx = curr[0] + side[0] * bit_r
                cy = curr[1] + side[1] * bit_r
            else:
                cx = curr[0] + bx * dist
                cy = curr[1] + by * dist

            msp.add_circle(center=(cx, cy), radius=bit_r, dxfattribs=A)
            circles_added += 1

    doc.saveas(output_filename)
    return circles_added


def align_dxf(output_filename, input_filename,
              anchor_x=None, anchor_y=None,
              target_x=None, target_y=None,
              ref_filename=None,
              ref_anchor_x=None, ref_anchor_y=None,
              offset_x=0.0, offset_y=0.0):
    """Translate a DXF so that a chosen anchor point lands on a target position.

    anchor_x / anchor_y : 'left'|'center'|'right'  /  'bottom'|'center'|'top'
    target_x / target_y : absolute coordinates for the anchor.
    ref_filename        : use the bounding box of this file to compute target.
    ref_anchor_x/y      : which feature of ref to target.
    offset_x / offset_y : additional offset after alignment.
    """
    import shutil

    def _bbox(fname):
        d = ezdxf.readfile(fname)
        xs, ys = [], []
        for e in d.modelspace():
            t = e.dxftype()
            try:
                if t == 'LINE':
                    xs += [e.dxf.start.x, e.dxf.end.x]
                    ys += [e.dxf.start.y, e.dxf.end.y]
                elif t in ('CIRCLE', 'ARC'):
                    xs += [e.dxf.center.x - e.dxf.radius, e.dxf.center.x + e.dxf.radius]
                    ys += [e.dxf.center.y - e.dxf.radius, e.dxf.center.y + e.dxf.radius]
                elif t in ('LWPOLYLINE', 'POLYLINE'):
                    for p in e.get_points():
                        xs.append(p[0]); ys.append(p[1])
                elif t == 'SPLINE':
                    for cp in e.control_points:
                        xs.append(cp[0]); ys.append(cp[1])
            except Exception as exc:
                logger.warning("Skipping entity during bbox calculation for '%s': %s", fname, t, exc_info=exc)
        if not xs:
            return 0.0, 0.0, 0.0, 0.0
        return min(xs), min(ys), max(xs), max(ys)

    def _pick(val, lo, hi, name):
        m = {'left': lo, 'bottom': lo, 'right': hi, 'top': hi, 'center': (lo + hi) / 2.0}
        v = m.get(str(val).lower())
        if v is None:
            raise ValueError(f"Unknown anchor '{val}' for {name}. Use left/center/right or bottom/center/top.")
        return v

    x0, y0, x1, y1 = _bbox(input_filename)
    ax = _pick(anchor_x, x0, x1, 'anchor_x') if anchor_x else None
    ay = _pick(anchor_y, y0, y1, 'anchor_y') if anchor_y else None

    tx, ty = target_x, target_y
    if ref_filename:
        rx0, ry0, rx1, ry1 = _bbox(ref_filename)
        if ref_anchor_x and tx is None:
            tx = _pick(ref_anchor_x, rx0, rx1, 'ref_anchor_x')
        if ref_anchor_y and ty is None:
            ty = _pick(ref_anchor_y, ry0, ry1, 'ref_anchor_y')

    dx = (tx - ax + offset_x) if (tx is not None and ax is not None) else offset_x
    dy = (ty - ay + offset_y) if (ty is not None and ay is not None) else offset_y

    if abs(dx) < 1e-9 and abs(dy) < 1e-9:
        shutil.copy2(input_filename, output_filename)
        return True

    doc = ezdxf.readfile(input_filename)
    msp = doc.modelspace()
    for e in msp:
        t = e.dxftype()
        try:
            if t == 'LINE':
                e.dxf.start = (e.dxf.start.x + dx, e.dxf.start.y + dy, e.dxf.start.z)
                e.dxf.end   = (e.dxf.end.x   + dx, e.dxf.end.y   + dy, e.dxf.end.z)
            elif t in ('CIRCLE', 'ARC'):
                c = e.dxf.center
                e.dxf.center = (c.x + dx, c.y + dy, c.z)
            elif t == 'LWPOLYLINE':
                pts = [(p[0] + dx, p[1] + dy) + tuple(p[2:]) for p in e.get_points()]
                e.set_points(pts)
            elif t == 'POLYLINE':
                for v in e.vertices:
                    p = v.dxf.location
                    v.dxf.location = (p.x + dx, p.y + dy, p.z)
            elif t == 'SPLINE':
                e.control_points = [(p[0] + dx, p[1] + dy, p[2] if len(p) > 2 else 0) for p in e.control_points]
            elif t in ('INSERT', 'TEXT', 'MTEXT'):
                p = e.dxf.insert
                e.dxf.insert = (p.x + dx, p.y + dy, p.z)
        except Exception as exc:
            logger.warning("Skipping entity during alignment for '%s': %s", input_filename, t, exc_info=exc)

    doc.saveas(output_filename)
    return True


def center_dxf(output_filename, input_filename,
               target_x=0.0, target_y=0.0,
               ref_filename=None,
               offset_x=0.0, offset_y=0.0):
    """Center a DXF on absolute coordinates or inside another DXF bounds.

    If ref_filename is provided, the input DXF center is aligned to the
    center of the reference DXF and target_x/target_y act as extra offsets.
    Otherwise the input DXF center is aligned to target_x/target_y.
    """
    return align_dxf(
        output_filename,
        input_filename,
        anchor_x='center',
        anchor_y='center',
        target_x=target_x if ref_filename is None else None,
        target_y=target_y if ref_filename is None else None,
        ref_filename=ref_filename,
        ref_anchor_x='center' if ref_filename else None,
        ref_anchor_y='center' if ref_filename else None,
        offset_x=offset_x,
        offset_y=offset_y,
    )
