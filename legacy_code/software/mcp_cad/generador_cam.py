import ezdxf
from shapely.geometry import Polygon, Point, LinearRing
import os
import json
import math
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
TOOLS_PATH = BASE_DIR / "herramientas.json"

class GeneradorCAM:
    def __init__(self, dxf_file, tool_id=None, safe_z=5.0):
        self.dxf_file = dxf_file
        self.safe_z = safe_z
        self.doc = ezdxf.readfile(dxf_file)
        self.msp = self.doc.modelspace()
        self.gcode = []
        
        # Valores por defecto de herramienta
        self.tool_radius = 1.5
        self.feed_xy = 800
        self.feed_z = 300
        self.step_z = 1.0
        self.rpm = 12000
        
        if tool_id:
            self._cargar_herramienta(tool_id)

    def _cargar_herramienta(self, tool_id):
        if not TOOLS_PATH.exists():
            print("No se encontr├│ herramientas.json")
            return
            
        with TOOLS_PATH.open('r', encoding='utf-8-sig') as f:
            datos = json.load(f)
            
        herramientas = datos.get("tools", [])
        for tool in herramientas:
            if tool_id == tool.get("id") or tool_id.lower() in tool.get("display_name", "").lower():
                self.tool_radius = tool.get("diameter_mm", 3) / 2.0
                self.feed_xy = tool.get("feed_recommend_mm_per_min", 800)
                self.feed_z = tool.get("plunge_recommend_mm_per_min", 300)
                self.rpm = tool.get("rpm_recommend", 12000)
                self.step_z = tool.get("stepdown_mm", 1.0)
                print(f"Herramienta: {tool.get('display_name')} (R: {self.tool_radius}mm)")
                return
        print(f"Herramienta '{tool_id}' no encontrada. Usando config por defecto.")

    def inicializar_gcode(self):
        self.gcode.append("(Generado por Agente Aut├│nomo CAM IA)")
        self.gcode.append("G21 (Modo Metrico)")
        self.gcode.append("G90 (Modo Absoluto)")
        self.gcode.append(f"G0 Z{self.safe_z} F{self.feed_z}")
        self.gcode.append(f"M3 S{self.rpm} (Encender Husillo)")
        self.gcode.append("")
        
    def finalizar_gcode(self):
        self.gcode.append(f"G0 Z{self.safe_z}")
        self.gcode.append("M5 (Apagar Husillo)")
        self.gcode.append("M30 (Fin del programa)")

    def _extraer_poligonos(self):
        """
        Extrae entidades del DXF y detecta matem├íticamente la anidaci├│n.
        Soporta: LWPOLYLINE, CIRCLE, y cadenas de LINE+ARC reconstruidas via polygonize.
        """
        from ezdxf import path as ezpath
        from shapely.ops import polygonize, linemerge
        from shapely.geometry import LineString

        raw_polys = []
        line_segments = []

        # 1. LWPOLYLINE cerradas (texto, booleanas, merge)
        for pline in self.msp.query("LWPOLYLINE"):
            pts = [(p[0], p[1]) for p in pline.get_points()]
            if len(pts) >= 3:
                raw_polys.append(Polygon(pts))

        # 2. CIRCLE nativas ÔåÆ pol├¡gono aproximado para Shapely
        for circle in self.msp.query("CIRCLE"):
            r  = circle.dxf.radius
            cx = circle.dxf.center.x
            cy = circle.dxf.center.y
            pts = [(cx + r * math.cos(math.radians(d)),
                    cy + r * math.sin(math.radians(d))) for d in range(0, 360, 5)]
            raw_polys.append(Polygon(pts))

        # 3. LINE + ARC sueltos ÔåÆ reconstruir pol├¡gonos cerrados via polygonize
        for entity in self.msp.query("LINE ARC"):
            try:
                p = ezpath.make_path(entity)
                pts_path = [(v.x, v.y) for v in p.flattening(0.5)]
                if len(pts_path) >= 2:
                    line_segments.append(LineString(pts_path))
            except Exception:
                pass

        if line_segments:
            reconstructed = list(polygonize(linemerge(line_segments)))
            raw_polys.extend(reconstructed)

        if not raw_polys:
            return []

        # Ordenar por ├írea descendente para procesar primero los contenedores padre
        raw_polys.sort(key=lambda p: p.area, reverse=True)

        nodos = []
        for poly in raw_polys:
            padre_directo = None
            for nodo in reversed(nodos):
                if nodo['poly'].contains(poly) or nodo['poly'].buffer(0.001).contains(poly):
                    padre_directo = nodo
                    break
            if padre_directo is None:
                nodos.append({'poly': poly, 'holes': [], 'is_hole': False})
            else:
                es_agujero = not padre_directo['is_hole']
                nodos.append({'poly': poly, 'holes': [], 'is_hole': es_agujero})
                if es_agujero:
                    padre_directo['holes'].append(poly.exterior)

        final_polygons = []
        for nodo in nodos:
            if not nodo['is_hole']:
                final_polygons.append(Polygon(nodo['poly'].exterior, nodo['holes']))

        return final_polygons

    def procesar_operacion_avanzada(self, config):
        """
        Ejecuta la operaci├│n basada en el diccionario config.
        """
        operacion = config.get("operation", "profile_outside")
        depth = -abs(config.get("cut_depth_mm", 5.0))
        pass_depth = config.get("pass_depth_mm", self.step_z)
        if pass_depth <= 0: pass_depth = self.step_z
        
        # Opciones TABS
        tabs_enabled = config.get("tabs_enabled", False)
        tab_width = config.get("tab_width_mm", 5.0)
        tab_height = config.get("tab_height_mm", 2.0)
        tab_count = config.get("tab_count", 4)
        mat_thickness = config.get("material_thickness_mm", 5.0) # Usado para saber cuando levantar
        
        # Punto Inicio
        start_x = config.get("start_x_mm", None)
        start_y = config.get("start_y_mm", None)

        self.gcode.append(f"( --- OPERACION: {operacion.upper()} --- )")
        self.gcode.append(f"(Profundidad Total: {depth:.2f}mm, Pasada: {pass_depth:.2f}mm)")
        
        poligonos = self._extraer_poligonos()
        if not poligonos:
            self.gcode.append("( ERROR: No se encontraron geometrias cerradas continuas )")
            return

        for poly in poligonos:
            if operacion == "pocket":
                self._generar_pocket(poly, depth, pass_depth)
            elif operacion == "profile_outside":
                self._generar_perfil(poly, depth, pass_depth, self.tool_radius + 0.1, 
                                     tabs_enabled, tab_width, tab_height, tab_count, mat_thickness, start_x, start_y)
            elif operacion == "profile_inside":
                self._generar_perfil(poly, depth, pass_depth, -(self.tool_radius + 0.1), 
                                     tabs_enabled, tab_width, tab_height, tab_count, mat_thickness, start_x, start_y)

    def _generar_pocket(self, poly, depth, pass_depth):
        step_lateral = self.tool_radius
        paths_2d = []
        offset = -self.tool_radius 
        while True:
            ring = poly.buffer(offset, join_style=2)
            if ring.is_empty: break
            if ring.geom_type == 'Polygon':
                paths_2d.append(list(ring.exterior.coords))
            elif ring.geom_type == 'MultiPolygon':
                for p in ring.geoms: paths_2d.append(list(p.exterior.coords))
            offset -= step_lateral
            
        paths_2d = paths_2d[::-1] # Desde el centro hacia afuera
        
        z = 0.0
        while z > depth:
            z = max(z - pass_depth, depth)
            self.gcode.append(f"(Pasada de vaciado Z: {z:.3f})")
            for path in paths_2d:
                if not path: continue
                px, py = path[0]
                self.gcode.append(f"G0 Z{self.safe_z}")
                self.gcode.append(f"G0 X{px:.3f} Y{py:.3f}")
                self.gcode.append(f"G1 Z{z:.3f} F{self.feed_z}")
                for pt in path[1:]:
                    self.gcode.append(f"G1 X{pt[0]:.3f} Y{pt[1]:.3f} F{self.feed_xy}")
            self.gcode.append(f"G0 Z{self.safe_z}")
        self.gcode.append("")

    def _generar_perfil(self, poly, depth, pass_depth, buffer_offset, 
                        tabs_enabled, tab_width, tab_height, tab_count, mat_thickness,
                        start_x, start_y):
        
        ring_poly = poly.buffer(buffer_offset, join_style=2)
        if ring_poly.is_empty: return
        
        if ring_poly.geom_type == 'Polygon':
            ring = ring_poly.exterior
        elif ring_poly.geom_type == 'MultiPolygon':
            # Toma el contorno mas largo
            ring = max(ring_poly.geoms, key=lambda p: p.exterior.length).exterior
        else:
            ring = LinearRing(list(ring_poly.coords))
            
        perimeter = ring.length
        
        # Muestreo denso para tener precision matematica en los Tabs
        resolution = 0.5 # mm
        num_points = max(int(perimeter / resolution), 4)
        sampled_points = [ring.interpolate(i * perimeter / num_points) for i in range(num_points)]
        
        # Rotar array para empezar en Start_X, Start_Y
        if start_x is not None and start_y is not None:
            pt_start = Point(start_x, start_y)
            closest_idx = min(range(num_points), key=lambda i: sampled_points[i].distance(pt_start))
            sampled_points = sampled_points[closest_idx:] + sampled_points[:closest_idx]
            
        # Posiciones de Tabs a lo largo del perimetro
        tab_spacing = perimeter / tab_count if tab_count > 0 else 999999
        tab_positions = [i * tab_spacing for i in range(tab_count)]
        
        z = 0.0
        while z > depth:
            z = max(z - pass_depth, depth)
            self.gcode.append(f"(Pasada de perfilado Z: {z:.3f})")
            
            # Penetraci├│n Inicial
            pt0 = sampled_points[0]
            self.gcode.append(f"G0 X{pt0.x:.3f} Y{pt0.y:.3f}")
            self.gcode.append(f"G1 Z{z:.3f} F{self.feed_z}")
            
            current_dist = 0.0
            last_z_sent = z
            
            for i in range(1, len(sampled_points)):
                pt = sampled_points[i]
                pt_prev = sampled_points[i-1]
                dist_step = math.hypot(pt.x - pt_prev.x, pt.y - pt_prev.y)
                current_dist += dist_step
                
                # Check Tabs
                z_target = z
                if tabs_enabled and z < -mat_thickness + tab_height + 0.01:
                    # Is inside tab?
                    in_tab = False
                    for t_pos in tab_positions:
                        # Consideracion de anillos circulares
                        dist_to_tab = min(abs(current_dist - t_pos), abs(current_dist - (t_pos + perimeter)), abs(current_dist - (t_pos - perimeter)))
                        if dist_to_tab < tab_width / 2.0:
                            in_tab = True
                            break
                            
                    if in_tab:
                        z_target = -mat_thickness + tab_height
                
                # Gcode emission
                if abs(z_target - last_z_sent) > 0.001:
                    self.gcode.append(f"G1 Z{z_target:.3f} F{self.feed_z}")
                    last_z_sent = z_target
                
                self.gcode.append(f"G1 X{pt.x:.3f} Y{pt.y:.3f} F{self.feed_xy}")

            # Cerrar bucle
            self.gcode.append(f"G1 X{pt0.x:.3f} Y{pt0.y:.3f} F{self.feed_xy}")
            self.gcode.append(f"G0 Z{self.safe_z}")
        self.gcode.append("")

    def exportar(self, salida_nc):
        with open(salida_nc, 'w') as f:
            f.write("\n".join(self.gcode))
        print(f"G-Code generado con exito: {salida_nc}")

if __name__ == "__main__":
    import sys
    dxf_origen = sys.argv[1] if len(sys.argv) > 1 else str(BASE_DIR / "outputs" / "letra_A_300mm_90deg.dxf")
    nc_destino = sys.argv[2] if len(sys.argv) > 2 else str(BASE_DIR / "outputs" / "letra_A_test2.nc")
    
    if os.path.exists(dxf_origen):
        print(f"Iniciando CAM para: {dxf_origen}")
        cam = GeneradorCAM(dxf_origen, tool_id="End Mills 3mm")
        cam.inicializar_gcode()
        cam.procesar_operacion_avanzada({
            "operation": "profile_outside",
            "cut_depth_mm": 5.0,
            "pass_depth_mm": 2.0,
            "tabs_enabled": True,
            "tab_count": 4,
            "start_x_mm": 0.0,
            "start_y_mm": 0.0
        })
        cam.finalizar_gcode()
        cam.exportar(nc_destino)
    else:
        print(f"No existe: {dxf_origen}")
