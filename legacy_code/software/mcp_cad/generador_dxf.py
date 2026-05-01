import ezdxf
import os
import math
from ezdxf.enums import TextEntityAlignment
from shapely.geometry import Polygon
from shapely.ops import unary_union

def generate_parametric_circle(nombre_archivo, radius_mm):
    """
    Dibuja un c├¡rculo usando la entidad nativa CIRCLE de DXF.
    El CAM extrae su geometr├¡a v├¡a aproximaci├│n angular de alta precisi├│n.
    """
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    msp.add_circle(center=(0, 0), radius=radius_mm,
                   dxfattribs={'layer': 'PERFIL', 'color': 1})
    destino = os.path.dirname(nombre_archivo)
    if destino and not os.path.exists(destino):
        os.makedirs(destino, exist_ok=True)
    doc.saveas(nombre_archivo)
    return True

def generate_parametric_rectangle(nombre_archivo, width_mm, height_mm, r_br=0.0, r_tr=0.0, r_tl=0.0, r_bl=0.0):
    """
    Dibuja un rect├íngulo usando entidades nativas LINE y ARC.
    Los lados rectos son LINE, las esquinas redondeadas son ARC.
    El extractor CAM reconstruye el pol├¡gono cerrado via shapely.polygonize.
    """
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    w, h = width_mm, height_mm
    A = {'layer': 'PERFIL', 'color': 1}

    def add_line(p1, p2):
        msp.add_line(start=p1, end=p2, dxfattribs=A)

    def add_arc(cx, cy, r, a_start, a_end):
        if r > 0.001:
            msp.add_arc(center=(cx, cy), radius=r,
                        start_angle=a_start, end_angle=a_end, dxfattribs=A)

    # Punto de arranque de cada segmento (sentido antihorario, convenci├│n CAD)
    # Bottom edge: de (r_bl, 0) -> (w-r_br, 0)
    add_line((r_bl, 0), (w - r_br, 0))
    # Bottom-right arc: 270┬░ -> 360┬░
    add_arc(w - r_br, r_br, r_br, 270, 360)
    # Right edge: de (w, r_br) -> (w, h-r_tr)
    add_line((w, r_br), (w, h - r_tr))
    # Top-right arc: 0┬░ -> 90┬░
    add_arc(w - r_tr, h - r_tr, r_tr, 0, 90)
    # Top edge: de (w-r_tr, h) -> (r_tl, h)
    add_line((w - r_tr, h), (r_tl, h))
    # Top-left arc: 90┬░ -> 180┬░
    add_arc(r_tl, h - r_tl, r_tl, 90, 180)
    # Left edge: de (0, h-r_tl) -> (0, r_bl)
    add_line((0, h - r_tl), (0, r_bl))
    # Bottom-left arc: 180┬░ -> 270┬░
    add_arc(r_bl, r_bl, r_bl, 180, 270)

    destino = os.path.dirname(nombre_archivo)
    if destino and not os.path.exists(destino):
        os.makedirs(destino, exist_ok=True)
    doc.saveas(nombre_archivo)
    return True

def generate_parametric_concentric_circles(nombre_archivo, outer_radius, inner_radius):
    """
    Dibuja dos c├¡rculos conc├®ntricos con entidades nativas CIRCLE.
    """
    doc = ezdxf.new('R2010')
    msp = doc.modelspace()
    msp.add_circle(center=(0, 0), radius=outer_radius,
                   dxfattribs={'layer': 'PERFIL', 'color': 1})
    msp.add_circle(center=(0, 0), radius=inner_radius,
                   dxfattribs={'layer': 'AGUJEROS', 'color': 2})
    destino = os.path.dirname(nombre_archivo)
    if destino and not os.path.exists(destino):
        os.makedirs(destino, exist_ok=True)
    doc.saveas(nombre_archivo)
    return True

def merge_dxf_assembly(nombre_archivo_salida, lista_archivos_entrada, offsets_x, offsets_y):
    """
    Carga geometr├¡as en bruto (LWPOLYLINE) desde varios .dxf y los
    ensambla en un mismo lienzo vector aplicando offsets (x, y) relativas
    a cada pieza para fabricar ensamblajes complejos.
    """
    doc_salida = ezdxf.new('R2010')
    msp_salida = doc_salida.modelspace()
    
    for idx, fpath in enumerate(lista_archivos_entrada):
        if not os.path.exists(fpath): 
            continue
            
        d_in = ezdxf.readfile(fpath)
        m_in = d_in.modelspace()
        
        dx = offsets_x[idx] if idx < len(offsets_x) else 0.0
        dy = offsets_y[idx] if idx < len(offsets_y) else 0.0
        
        # Copiar y transladar todas las entidades geom├®tricas (CIRCLE, ARC, LINE, LWPOLYLINE)
        for entity in m_in.query('LWPOLYLINE'):
            pts = [(p[0] + dx, p[1] + dy) for p in entity.get_points()]
            layer_name = entity.dxf.layer if entity.dxf.hasattr('layer') else 'PERFIL'
            color_val  = entity.dxf.color  if entity.dxf.hasattr('color')  else 1
            msp_salida.add_lwpolyline(pts, dxfattribs={'layer': layer_name, 'color': color_val})

        for entity in m_in.query('CIRCLE'):
            cx = entity.dxf.center.x + dx
            cy = entity.dxf.center.y + dy
            layer_name = entity.dxf.layer if entity.dxf.hasattr('layer') else 'PERFIL'
            color_val  = entity.dxf.color  if entity.dxf.hasattr('color')  else 1
            msp_salida.add_circle(center=(cx, cy), radius=entity.dxf.radius,
                                  dxfattribs={'layer': layer_name, 'color': color_val})

        for entity in m_in.query('ARC'):
            cx = entity.dxf.center.x + dx
            cy = entity.dxf.center.y + dy
            layer_name = entity.dxf.layer if entity.dxf.hasattr('layer') else 'PERFIL'
            color_val  = entity.dxf.color  if entity.dxf.hasattr('color')  else 1
            msp_salida.add_arc(center=(cx, cy), radius=entity.dxf.radius,
                               start_angle=entity.dxf.start_angle,
                               end_angle=entity.dxf.end_angle,
                               dxfattribs={'layer': layer_name, 'color': color_val})

        for entity in m_in.query('LINE'):
            sx = entity.dxf.start.x + dx; sy = entity.dxf.start.y + dy
            ex = entity.dxf.end.x   + dx; ey = entity.dxf.end.y   + dy
            layer_name = entity.dxf.layer if entity.dxf.hasattr('layer') else 'PERFIL'
            color_val  = entity.dxf.color  if entity.dxf.hasattr('color')  else 1
            msp_salida.add_line(start=(sx, sy), end=(ex, ey),
                                dxfattribs={'layer': layer_name, 'color': color_val})
            
    if not os.path.exists(os.path.dirname(nombre_archivo_salida)):
        os.makedirs(os.path.dirname(nombre_archivo_salida), exist_ok=True)
    doc_salida.saveas(nombre_archivo_salida)
    return True

def boolean_dxf_operation(nombre_archivo_salida, archivo_a, archivo_b, operacion='union', offset_x_b=0.0, offset_y_b=0.0):
    """
    Aplica una operaci├│n booleana Shapely entre dos archivos DXF y exporta el
    resultado como un nuevo archivo DXF con soporte completo de agujeros interiores.
    
    operacion: 'union' | 'difference' | 'intersection'
    offset_x_b / offset_y_b: traslaci├│n aplicada a B antes de la operaci├│n.
    """
    def _leer_shape(filepath, dx=0.0, dy=0.0):
        """Lee cualquier entidad DXF (CIRCLE, ARC, LINE, LWPOLYLINE) y devuelve un Shape Shapely."""
        from ezdxf import path as ezpath
        from shapely.ops import polygonize, linemerge
        from shapely.geometry import LineString

        doc = ezdxf.readfile(filepath)
        msp = doc.modelspace()
        raw_polys  = []
        segments   = []

        # LWPOLYLINE cerradas
        for pline in msp.query('LWPOLYLINE'):
            pts = [(p[0] + dx, p[1] + dy) for p in pline.get_points()]
            if len(pts) >= 3:
                raw_polys.append(Polygon(pts))

        # CIRCLE nativas
        for circle in msp.query('CIRCLE'):
            r  = circle.dxf.radius
            cx = circle.dxf.center.x + dx
            cy = circle.dxf.center.y + dy
            pts = [(cx + r * math.cos(math.radians(d)),
                    cy + r * math.sin(math.radians(d))) for d in range(0, 360, 5)]
            raw_polys.append(Polygon(pts))

        # LINE + ARC ÔåÆ reconstruir pol├¡gonos cerrados
        for entity in msp.query('LINE ARC'):
            try:
                p = ezpath.make_path(entity)
                pts_path = [(v.x + dx, v.y + dy) for v in p.flattening(0.5)]
                if len(pts_path) >= 2:
                    segments.append(LineString(pts_path))
            except Exception:
                pass

        if segments:
            raw_polys.extend(polygonize(linemerge(segments)))

        if not raw_polys:
            return None
        return unary_union(raw_polys)

    shape_a = _leer_shape(archivo_a)
    shape_b = _leer_shape(archivo_b, offset_x_b, offset_y_b)

    if shape_a is None or shape_b is None:
        return False

    if operacion == 'union':
        resultado = shape_a.union(shape_b)
    elif operacion == 'difference':
        resultado = shape_a.difference(shape_b)
    elif operacion == 'intersection':
        resultado = shape_a.intersection(shape_b)
    else:
        return False

    doc_salida = ezdxf.new('R2010')
    msp_salida = doc_salida.modelspace()

    def _exportar_geometria(geom):
        if geom is None or geom.is_empty:
            return
        gtype = geom.geom_type
        if gtype == 'Polygon':
            # Contorno exterior
            msp_salida.add_lwpolyline(
                list(geom.exterior.coords),
                dxfattribs={'layer': 'PERFIL', 'color': 1}
            )
            # Agujeros interiores (ej: difference, o islas)
            for interior in geom.interiors:
                msp_salida.add_lwpolyline(
                    list(interior.coords),
                    dxfattribs={'layer': 'AGUJEROS', 'color': 2}
                )
        elif gtype in ('MultiPolygon', 'GeometryCollection'):
            for sub in geom.geoms:
                _exportar_geometria(sub)

    _exportar_geometria(resultado)

    destino_dir = os.path.dirname(nombre_archivo_salida)
    if destino_dir and not os.path.exists(destino_dir):
        os.makedirs(destino_dir, exist_ok=True)
    doc_salida.saveas(nombre_archivo_salida)
    return True

def generate_cad_text(nombre_archivo, text, height_mm, pos_x_mm=0.0, pos_y_mm=0.0,
                       font_type='outline', rotation_degrees=0.0,
                       alignment='left', letter_spacing_mm=0.0):
    """
    Genera texto vectorial en DXF.
    
    font_type='outline' : Contornos cerrados TTF v├¡a matplotlib (pocket / profile)
    font_type='single_line': Entidad TEXT ezdxf con fuente SIMPLEX (grabado V-bit)
    
    alignment: 'left' | 'center' | 'right'
    """
    if not text or height_mm <= 0:
        return False

    doc = ezdxf.new('R2010')
    msp = doc.modelspace()

    if font_type == 'single_line':
        # ÔöÇÔöÇ Fuente stroke SIMPLEX (ideal para grabado V-bit) ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
        # ezdxf TEXT con estilo SIMPLEX genera trazos ├║nicos sin relleno
        doc.styles.add('SIMPLEX', font='simplex.shx')
        text_entity = msp.add_text(
            text,
            dxfattribs={
                'layer': 'TEXTO',
                'color': 1,
                'height': height_mm,
                'style': 'SIMPLEX',
                'rotation': rotation_degrees,
            }
        )
        # Alineaci├│n horizontal
        halign_map = {'left': 0, 'center': 4, 'right': 2}
        halign = halign_map.get(alignment, 0)
        if halign == 0:
            text_entity.dxf.insert = (pos_x_mm, pos_y_mm)
        else:
            align_map = {
                4: TextEntityAlignment.MIDDLE_CENTER,
                2: TextEntityAlignment.MIDDLE_RIGHT,
            }
            text_entity.set_placement(
                (pos_x_mm, pos_y_mm), align=align_map.get(halign, TextEntityAlignment.LEFT)
            )

    else:
        # ÔöÇÔöÇ Contornos cerrados TTF via matplotlib TextPath ÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇÔöÇ
        try:
            import numpy as np
            from matplotlib.textpath import TextPath
            from matplotlib.font_manager import FontProperties

            fp = FontProperties(family='DejaVu Sans')

            # Renderizar a tama├▒o 1.0 y escalar manualmente para precisi├│n
            tp = TextPath((0, 0), text, size=1.0, prop=fp)
            polygons = tp.to_polygons()

            if not polygons:
                return False

            # Factor de escala: cap-height de DejaVu Sans size=1.0 Ôëê 0.716
            CAP_H = 0.716
            scale = height_mm / CAP_H

            # Calcular ancho total para alineaci├│n
            all_x = np.concatenate([p[:, 0] for p in polygons])
            total_width = (all_x.max() - all_x.min()) * scale

            if alignment == 'center':
                x_offset = pos_x_mm - total_width / 2.0
            elif alignment == 'right':
                x_offset = pos_x_mm - total_width
            else:
                x_offset = pos_x_mm
            y_offset = pos_y_mm

            # Pre-calcular rotaci├│n
            cos_r = math.cos(math.radians(rotation_degrees))
            sin_r = math.sin(math.radians(rotation_degrees))

            def _transform(x, y):
                sx = x * scale + x_offset
                sy = y * scale + y_offset
                if rotation_degrees != 0.0:
                    dx, dy = sx - pos_x_mm, sy - pos_y_mm
                    sx = pos_x_mm + dx * cos_r - dy * sin_r
                    sy = pos_y_mm + dx * sin_r + dy * cos_r
                return (sx, sy)

            for poly in polygons:
                if len(poly) < 3:
                    continue
                pts = [_transform(v[0], v[1]) for v in poly]
                # Cerrar contorno si no lo est├í
                if pts[0] != pts[-1]:
                    pts.append(pts[0])
                msp.add_lwpolyline(pts, dxfattribs={'layer': 'TEXTO', 'color': 1})

        except ImportError:
            return False

    destino_dir = os.path.dirname(nombre_archivo)
    if destino_dir and not os.path.exists(destino_dir):
        os.makedirs(destino_dir, exist_ok=True)
    doc.saveas(nombre_archivo)
    return True
