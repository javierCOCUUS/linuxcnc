import ezdxf
from shapely.geometry import Polygon, Point, LinearRing
import os
import json
import math
from pathlib import Path

# In the container, this will be mounted
TOOLS_PATH = Path("/data/tools.json")
MATERIALS_PATH = Path("/data/materials.json")

class GeneradorCAM:
    def __init__(self, dxf_file, tool_id=None, material_id=None, safe_z=5.0):
        self.dxf_file = dxf_file
        self.safe_z = safe_z
        self.doc = ezdxf.readfile(dxf_file)
        self.msp = self.doc.modelspace()
        self.gcode = []
        self.postprocessor = None
        
        # Valores por defecto de herramienta
        self.tool_radius = 1.5
        self.tool_number = 1
        self.feed_xy = 800
        self.feed_z = 300
        self.step_z = 1.0
        self.rpm = 12000
        
        # Multiplicadores de material
        self.mat_feed_mult = 1.0
        self.mat_step_mult = 1.0

        if tool_id:
            self._cargar_herramienta(tool_id)
        
        if material_id:
            self._cargar_material(material_id)

    def _cargar_herramienta(self, tool_id):
        if not TOOLS_PATH.exists(): return
        with TOOLS_PATH.open('r', encoding='utf-8-sig') as f:
            datos = json.load(f)
        herramientas = datos.get("tools", [])
        for tool in herramientas:
            if tool_id == tool.get("id") or tool_id.lower() in tool.get("display_name", "").lower():
                self.tool_radius = tool.get("diameter_mm", 3) / 2.0
                self.tool_number = tool.get("tool_number", 1)
                self.feed_xy = tool.get("feed_recommend_mm_per_min", 800)
                self.feed_z = tool.get("plunge_recommend_mm_per_min", 300)
                self.rpm = tool.get("rpm_recommend", 12000)
                self.step_z = tool.get("stepdown_mm", 1.0)
                return

    def _cargar_material(self, material_id):
        if not MATERIALS_PATH.exists(): return
        with MATERIALS_PATH.open('r', encoding='utf-8-sig') as f:
            datos = json.load(f)
        materiales = datos.get("materials", [])
        for mat in materiales:
            if material_id.lower() == mat.get("id").lower() or material_id.lower() == mat.get("name").lower():
                self.mat_feed_mult = mat.get("feed_multiplier", 1.0)
                self.mat_step_mult = mat.get("stepdown_multiplier", 1.0)
                # Aplicar multiplicadores
                self.feed_xy *= self.mat_feed_mult
                self.feed_z *= self.mat_feed_mult
                self.step_z *= self.mat_step_mult
                return

    def inicializar_gcode(self):
        if self.postprocessor:
            self.gcode.append(self.postprocessor.header(self.tool_number, self.rpm, z_home=self.safe_z))
        else:
            self.gcode.append(f"G21\nG90\nG0 Z{self.safe_z}\nM3 S{self.rpm}")
        
    def finalizar_gcode(self):
        if self.postprocessor:
            self.gcode.append(self.postprocessor.footer(z_home=self.safe_z))
        else:
            self.gcode.append(f"G0 Z{self.safe_z}\nM5\nM30")

    def _emit_move(self, x=None, y=None, z=None, feed=None, rapid=False):
        if self.postprocessor:
            if rapid: self.gcode.append(self.postprocessor.rapid_move(x, y, z))
            elif feed is not None: self.gcode.append(self.postprocessor.first_feed_move(x, y, z, feed))
            else: self.gcode.append(self.postprocessor.feed_move(x, y, z))
        else:
            cmd = "G0" if rapid else "G1"
            parts = [cmd]
            if x is not None: parts.append(f"X{x:.3f}")
            if y is not None: parts.append(f"Y{y:.3f}")
            if z is not None: parts.append(f"Z{z:.3f}")
            if feed is not None and not rapid: parts.append(f"F{feed:.1f}")
            self.gcode.append(" ".join(parts))

    def _extraer_poligonos(self):
        from ezdxf import path as ezpath
        from shapely.ops import polygonize, linemerge
        from shapely.geometry import LineString

        raw_polys = []
        line_segments = []

        for pline in self.msp.query("LWPOLYLINE"):
            pts = [(p[0], p[1]) for p in pline.get_points()]
            if len(pts) >= 3: raw_polys.append(Polygon(pts))

        for circle in self.msp.query("CIRCLE"):
            r, cx, cy = circle.dxf.radius, circle.dxf.center.x, circle.dxf.center.y
            pts = [(cx + r * math.cos(math.radians(d)), cy + r * math.sin(math.radians(d))) for d in range(0, 360, 5)]
            raw_polys.append(Polygon(pts))

        for entity in self.msp.query("LINE ARC SPLINE"):
            try:
                p = ezpath.make_path(entity)
                pts_path = [(v.x, v.y) for v in p.flattening(0.5)]
                if len(pts_path) >= 2: line_segments.append(LineString(pts_path))
            except: pass

        if line_segments:
            raw_polys.extend(list(polygonize(linemerge(line_segments))))

        if not raw_polys: return []
        raw_polys.sort(key=lambda p: p.area, reverse=True)

        nodos = []
        for poly in raw_polys:
            padre = None
            for nodo in reversed(nodos):
                if nodo['poly'].contains(poly):
                    padre = nodo
                    break
            if padre is None:
                nodos.append({'poly': poly, 'holes': [], 'is_hole': False})
            else:
                es_agujero = not padre['is_hole']
                nodos.append({'poly': poly, 'holes': [], 'is_hole': es_agujero})
                if es_agujero: padre['holes'].append(poly.exterior)

        return [Polygon(n['poly'].exterior, n['holes']) for n in nodos if not n['is_hole']]

    def procesar_operacion_avanzada(self, config):
        operacion = config.get("operation", "profile_outside")
        depth = -abs(config.get("cut_depth_mm", 5.0))
        pass_depth = config.get("pass_depth_mm", self.step_z)
        
        # Lead-in / Lead-out params
        leadin_type = config.get("leadin_type", "ramp") # "none", "ramp", "arc"
        leadin_len = config.get("leadin_length_mm", 10.0)

        self.gcode.append(f"( --- OP: {operacion.upper()} | MAT: {config.get('material_id','N/A')} --- )")
        
        poligonos = self._extraer_poligonos()
        poligonos = self._sort_paths_nearest_neighbor(poligonos)
        for poly in poligonos:
            if operacion == "pocket":
                self._generar_pocket(poly, depth, pass_depth)
            elif operacion == "profile_outside":
                self._generar_perfil(poly, depth, pass_depth, self.tool_radius + 0.1, config, leadin_type, leadin_len)
            elif operacion == "profile_inside":
                self._generar_perfil(poly, depth, pass_depth, -(self.tool_radius + 0.1), config, leadin_type, leadin_len)

    def _sort_paths_nearest_neighbor(self, polygons):
        """Sort polygons to minimise total G0 travel (nearest-neighbour heuristic)."""
        if len(polygons) <= 1:
            return polygons
        current = (0.0, 0.0)
        remaining = list(polygons)
        ordered = []
        while remaining:
            best_i, best_d = 0, float('inf')
            for i, poly in enumerate(remaining):
                coords = list(poly.exterior.coords)
                pt = coords[0]
                d = math.hypot(pt[0] - current[0], pt[1] - current[1])
                if d < best_d:
                    best_d, best_i = d, i
            chosen = remaining.pop(best_i)
            ordered.append(chosen)
            coords = list(chosen.exterior.coords)
            current = coords[-1]
        return ordered

    def _generar_perfil(self, poly, depth, pass_depth, buffer_offset, config, leadin_type, leadin_len):
        # G41/G42 cutter radius compensation mode
        cutter_comp = config.get("cutter_comp", "none")  # "none" | "left" (G41) | "right" (G42)
        use_comp = cutter_comp in ("left", "right")

        if use_comp:
            # With G41/G42 the controller compensates — don't pre-offset the path
            ring_poly = poly
            if ring_poly.geom_type == 'Polygon':
                ring = ring_poly.exterior
            else:
                ring = max(ring_poly.geoms, key=lambda p: p.exterior.length).exterior
        else:
            ring_poly = poly.buffer(buffer_offset, join_style=2)
            if ring_poly.is_empty: return
            ring = ring_poly.exterior if ring_poly.geom_type == 'Polygon' else max(ring_poly.geoms, key=lambda p: p.exterior.length).exterior

        perimeter = ring.length
        resolution = 0.5
        num_points = max(int(perimeter / resolution), 4)
        sampled = [ring.interpolate(i * perimeter / num_points) for i in range(num_points)]
        
        # Tabs logic
        tabs_enabled = config.get("tabs_enabled", False)
        tab_h, tab_w, tab_c = config.get("tab_height_mm", 2.0), config.get("tab_width_mm", 5.0), config.get("tab_count", 4)
        tab_pos = [i * (perimeter / tab_c) for i in range(tab_c)] if tab_c > 0 else []
        mat_thick = config.get("material_thickness_mm", 5.0)

        z = 0.0
        while z > depth:
            z_prev = z
            z = max(z - pass_depth, depth)
            self.gcode.append(f"(Pasada Z: {z:.3f})")

            pt0 = sampled[0]
            if use_comp:
                comp_code = "G41" if cutter_comp == "left" else "G42"
                self.gcode.append(f"{comp_code} D{self.tool_number}")

            if leadin_type == "ramp" and perimeter > leadin_len:
                ramp_steps = max(int(leadin_len / resolution), 2)
                self._emit_move(x=pt0.x, y=pt0.y, z=self.safe_z, rapid=True)
                self._emit_move(z=z_prev, feed=self.feed_z)
                for i in range(1, ramp_steps + 1):
                    p = sampled[i % num_points]
                    zi = z_prev + (z - z_prev) * (i / ramp_steps)
                    self._emit_move(x=p.x, y=p.y, z=zi, feed=self.feed_xy)
                start_idx = ramp_steps
            else:
                self._emit_move(x=pt0.x, y=pt0.y, rapid=True)
                self._emit_move(z=z, feed=self.feed_z)
                start_idx = 1

            current_dist = 0.0
            last_z_sent = z
            for i in range(start_idx, num_points):
                pt, prev = sampled[i], sampled[i-1]
                current_dist += math.hypot(pt.x - prev.x, pt.y - prev.y)

                z_target = z
                if tabs_enabled and z < -mat_thick + tab_h + 0.01:
                    for t_pos in tab_pos:
                        if min(abs(current_dist - t_pos), abs(current_dist - (t_pos + perimeter)), abs(current_dist - (t_pos - perimeter))) < tab_w / 2.0:
                            z_target = -mat_thick + tab_h
                            break

                if abs(z_target - last_z_sent) > 0.001:
                    self._emit_move(z=z_target, feed=self.feed_z)
                    last_z_sent = z_target
                self._emit_move(x=pt.x, y=pt.y, feed=self.feed_xy)

            self._emit_move(x=pt0.x, y=pt0.y, feed=self.feed_xy)
            if use_comp:
                self.gcode.append("G40")
            self._emit_move(z=self.safe_z, rapid=True)

    def _generar_pocket(self, poly, depth, pass_depth):
        # Simplificado para incluir material multipliers
        step_lat = self.tool_radius
        paths = []
        off = -self.tool_radius
        while True:
            r = poly.buffer(off, join_style=2)
            if r.is_empty: break
            if r.geom_type == 'Polygon': paths.append(list(r.exterior.coords))
            elif r.geom_type == 'MultiPolygon':
                for p in r.geoms: paths.append(list(p.exterior.coords))
            off -= step_lat
        paths = paths[::-1]
        z = 0.0
        while z > depth:
            z = max(z - pass_depth, depth)
            for path in paths:
                self._emit_move(x=path[0][0], y=path[0][1], rapid=True)
                self._emit_move(z=z, feed=self.feed_z)
                for pt in path[1:]: self._emit_move(x=pt[0], y=pt[1], feed=self.feed_xy)
            self._emit_move(z=self.safe_z, rapid=True)

    def _generar_pocket_adv(self, poly, depth, pass_depth, stepover_mm):
        """Pocket with configurable stepover (mm)."""
        step_lat = max(stepover_mm, self.tool_radius * 0.1)
        paths = []
        off = -self.tool_radius
        while True:
            r = poly.buffer(off, join_style=2)
            if r.is_empty: break
            geoms = [r] if r.geom_type == 'Polygon' else list(r.geoms)
            for g in geoms:
                paths.append(list(g.exterior.coords))
            off -= step_lat
        paths = paths[::-1]
        z = 0.0
        while z > depth:
            z = max(z - pass_depth, depth)
            self.gcode.append(f"(Pocket Z: {z:.3f})")
            for path in paths:
                self._emit_move(x=path[0][0], y=path[0][1], rapid=True)
                self._emit_move(z=z, feed=self.feed_z)
                for pt in path[1:]:
                    self._emit_move(x=pt[0], y=pt[1], feed=self.feed_xy)
            self._emit_move(z=self.safe_z, rapid=True)

    def generar_drill(self, drill_depth, peck_depth=2.0, dwell_ms=0):
        """Generate drill cycles for all circles in the DXF."""
        self._drill_hole_count = 0
        for circle in self.msp.query("CIRCLE"):
            cx, cy = circle.dxf.center.x, circle.dxf.center.y
            self.gcode.append(f"(Drill hole X{cx:.3f} Y{cy:.3f} D{circle.dxf.radius*2:.3f})")
            self._emit_move(x=cx, y=cy, rapid=True)
            self._emit_move(z=self.safe_z, rapid=True)
            if peck_depth and peck_depth > 0 and peck_depth < abs(drill_depth):
                # Peck drilling
                z = 0.0
                while z > drill_depth:
                    z = max(z - peck_depth, drill_depth)
                    self._emit_move(z=z, feed=self.feed_z)
                    if dwell_ms > 0:
                        self.gcode.append(f"G4 P{dwell_ms / 1000:.3f}")
                    self._emit_move(z=self.safe_z, rapid=True)
            else:
                # Single plunge
                self._emit_move(z=drill_depth, feed=self.feed_z)
                if dwell_ms > 0:
                    self.gcode.append(f"G4 P{dwell_ms / 1000:.3f}")
                self._emit_move(z=self.safe_z, rapid=True)
            self._drill_hole_count += 1

    def generar_engrave(self, cut_depth):
        """Single-pass engraving: follow every LINE, ARC, LWPOLYLINE, SPLINE at cut_depth."""
        from ezdxf import path as ezpath

        def _follow(pts):
            if len(pts) < 2:
                return
            self._emit_move(x=pts[0][0], y=pts[0][1], rapid=True)
            self._emit_move(z=cut_depth, feed=self.feed_z)
            for p in pts[1:]:
                self._emit_move(x=p[0], y=p[1], feed=self.feed_xy)
            self._emit_move(z=self.safe_z, rapid=True)

        for entity in self.msp.query("LINE"):
            sx, sy = entity.dxf.start.x, entity.dxf.start.y
            ex, ey = entity.dxf.end.x, entity.dxf.end.y
            _follow([(sx, sy), (ex, ey)])

        for entity in self.msp.query("LWPOLYLINE"):
            pts = [(p[0], p[1]) for p in entity.get_points()]
            _follow(pts)

        for entity in self.msp.query("ARC SPLINE"):
            try:
                p = ezpath.make_path(entity)
                pts = [(v.x, v.y) for v in p.flattening(0.1)]
                _follow(pts)
            except Exception:
                pass

    def exportar(self, salida_nc):
        with open(salida_nc, 'w') as f: f.write("\n".join(self.gcode))

if __name__ == "__main__":
    pass
