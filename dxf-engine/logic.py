import ezdxf
import os
import math
from ezdxf.enums import TextEntityAlignment
from shapely.geometry import Polygon, MultiPolygon, LineString, MultiLineString, GeometryCollection, Point
from shapely.ops import unary_union, polygonize, linemerge
import rectpack

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

def generate_cad_text_internal(msp, text, height_mm, x, y, alignment='left', layer="ETIQUETAS", font_name=None):
    """Versión interna para añadir texto a un modelspace existente."""
    import os
    dxfattribs = {'layer': layer, 'color': 3, 'height': height_mm}
    if font_name:
        # Register the text style with the font
        doc = msp.doc
        style_name = os.path.splitext(font_name)[0].upper()
        fonts_dir = os.environ.get('FONTS_DIR', '/fonts')
        font_path = os.path.join(fonts_dir, font_name) if not os.path.isabs(font_name) else font_name
        if style_name not in doc.styles:
            doc.styles.new(style_name, dxfattribs={'font': font_path})
        dxfattribs['style'] = style_name
    msp.add_text(text, dxfattribs=dxfattribs).set_placement((x, y), align=TextEntityAlignment.CENTER)

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
        except: pass
    if not all_points: return None
    xs, ys = [p[0] for p in all_points], [p[1] for p in all_points]
    min_x, max_x, min_y, max_y = min(xs), max(xs), min(ys), max(ys)
    return {
        "bbox": {"min_x": min_x, "max_x": max_x, "min_y": min_y, "max_y": max_y},
        "center": {"x": (min_x + max_x) / 2, "y": (min_y + max_y) / 2},
        "size": {"width": max_x - min_x, "height": max_y - min_y}
    }

def _leer_shape(filepath, dx=0.0, dy=0.0):
    from ezdxf import path as ezpath
    doc = ezdxf.readfile(filepath)
    msp = doc.modelspace()
    closed_polys, open_paths = [], []
    for entity in msp:
        try:
            p = ezpath.make_path(entity)
            pts = [(v.x + dx, v.y + dy) for v in p.flattening(0.5)]
            if len(pts) < 2: continue
            is_closed = False
            if entity.dxftype() == 'LWPOLYLINE': is_closed = entity.closed
            elif entity.dxftype() in ('CIRCLE', 'ELLIPSE'): is_closed = True
            if is_closed or (pts[0] == pts[-1]): closed_polys.append(Polygon(pts))
            else: open_paths.append(LineString(pts))
        except: continue
    if not closed_polys and not open_paths: return None
    return unary_union(closed_polys + open_paths)

def generate_cad_text(nombre_archivo, text, height_mm, pos_x_mm=0.0, pos_y_mm=0.0,
                       font_name=None, font_type='outline', rotation_degrees=0.0,
                       alignment='left', layer="GRABADO"):
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    generate_cad_text_internal(msp, text, height_mm, pos_x_mm, pos_y_mm, alignment, layer, font_name=font_name)
    doc.saveas(nombre_archivo)
    return True

def boolean_dxf_operation(nombre_archivo_salida, archivo_a, archivo_b, operacion='union', offset_x_b=0.0, offset_y_b=0.0):
    shape_a, shape_b = _leer_shape(archivo_a), _leer_shape(archivo_b, offset_x_b, offset_y_b)
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
    except Exception:
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
            except Exception:
                pass
    doc_out.saveas(nombre_archivo_salida)
    return True


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
