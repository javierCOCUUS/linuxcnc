import argparse
import os
import re
import time
from dataclasses import dataclass

import pyvista as pv


@dataclass
class EstadoMaquina:
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
    spindle_activo: int = 1
    modo_absoluto: bool = True
    wcs: int = 1  # G54=1, G55=2, G56=3
    motion_mode: str = "G0"  # G0/G1/G2/G3 modal


class SimuladorCNC:
    def __init__(self, archivo_gcode: str, carpeta_trabajo: str, origen_maquina=(0.0, 0.0, 0.0)):
        self.carpeta_trabajo = carpeta_trabajo
        self.archivo_gcode = archivo_gcode
        self.origen_maquina = {
            "X": float(origen_maquina[0]),
            "Y": float(origen_maquina[1]),
            "Z": float(origen_maquina[2]),
        }

        self.is_playing = False
        self.current_line = 0
        self.lineas_gcode = []
        self.play_lines_per_tick = 5.0

        # Parametros de maquina 3 spindles
        self.offsets_x = {1: 0.0, 2: -163.9, 3: -329.9}
        self.carrera_z_neumatica = -100.0

        self.estado = EstadoMaquina()
        self.pos_fisica = {"X": 0.0, "Y": 0.0, "Z": 0.0}

        self._regex_tokens = re.compile(r"([A-Z][-+]?\d*\.?\d*)")
        self._trail_points = []
        self._segment_history = []
        self.max_trail_points = 5000
        self.redraw_interval_lines = 25
        self._lines_since_redraw = 0
        self.z_visual_offset = 0.0
        self.trace_bias = {}

        self.cargar_gcode()
        self.cargar_mallas()
        self.configurar_entorno_3d()
        self._ir_a_linea(0)

    def cargar_gcode(self) -> None:
        path = os.path.join(self.carpeta_trabajo, self.archivo_gcode)
        if not os.path.exists(path):
            raise FileNotFoundError(f"No existe el archivo G-code: {path}")

        lineas = []
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            for raw in f:
                l = raw.strip().upper()
                if not l:
                    continue
                if l.startswith("(") or l.startswith(";"):
                    continue
                lineas.append(l)

        self.lineas_gcode = lineas
        print(f"G-code cargado: {self.archivo_gcode} ({len(self.lineas_gcode)} lineas)")

    def _leer_stl(self, nombre: str):
        path = os.path.join(self.carpeta_trabajo, nombre)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Falta STL requerido: {path}")
        return pv.read(path)

    def cargar_mallas(self) -> None:
        self.mallas = {
            "base": self._leer_stl("base.stl"),
            "portico_y": self._leer_stl("portico_y.stl"),
            "portico_x": self._leer_stl("portico_x.stl"),
            "portico_z": self._leer_stl("portico_z.stl"),
            "spindle_1": self._leer_stl("spindle_1.stl"),
            "spindle_2": self._leer_stl("spindle_2.stl"),
            "spindle_3": self._leer_stl("spindle_3.stl"),
        }
        # Referencia de punta por malla: centro XY y Z minimo.
        self.spindle_tip_ref = {}
        for k in ("spindle_1", "spindle_2", "spindle_3"):
            b = self.mallas[k].bounds
            self.spindle_tip_ref[k] = {
                "x": 0.5 * (b[0] + b[1]),
                "y": 0.5 * (b[2] + b[3]),
                "z": b[4],
            }

    def configurar_entorno_3d(self) -> None:
        self.plotter = pv.Plotter(window_size=(1400, 900))
        self.actores = {}
        self.actor_pos_base = {}
        self.actores["base"] = self.plotter.add_mesh(self.mallas["base"], color="lightgray", opacity=0.7)
        self.actores["portico_y"] = self.plotter.add_mesh(self.mallas["portico_y"], color="#2c3e50")
        self.actores["portico_x"] = self.plotter.add_mesh(self.mallas["portico_x"], color="#e74c3c")
        self.actores["portico_z"] = self.plotter.add_mesh(self.mallas["portico_z"], color="#27ae60")
        self.actores["spindle_1"] = self.plotter.add_mesh(self.mallas["spindle_1"], color="#f1c40f")
        self.actores["spindle_2"] = self.plotter.add_mesh(self.mallas["spindle_2"], color="#e67e22")
        self.actores["spindle_3"] = self.plotter.add_mesh(self.mallas["spindle_3"], color="#d35400")
        self.actores["marker"] = self.plotter.add_mesh(pv.Sphere(radius=6.0), color="magenta", opacity=0.9)
        self.actores["trail"] = None

        # Guarda posicion original de cada actor para mover en delta.
        for k, a in self.actores.items():
            if a is None:
                continue
            self.actor_pos_base[k] = a.GetPosition()
        for sp in (1, 2, 3):
            key = f"spindle_{sp}"
            bx, by, bz = self.actor_pos_base[key]
            tip = self.spindle_tip_ref[key]
            self.trace_bias[sp] = (bx + tip["x"], by + tip["y"], bz + tip["z"])

        self._set_estado_txt("PAUSADO", "red")
        self.plotter.add_text(
            "ESPACIO/P: play-pausa | N: +1 | B: -1 | R: rebobinar | I: ir a linea",
            position="lower_left",
            color="white",
            font_size=10,
        )
        self.plotter.add_text("G-Code: --", position="upper_right", color="yellow", font_size=12, name="txt_gcode")
        self.plotter.add_text("Linea: 0", position=(10, 70), color="cyan", font_size=12, name="txt_linea")
        self.plotter.add_text("XYZ fisica: 0,0,0", position=(10, 100), color="white", font_size=11, name="txt_xyz")
        self.plotter.add_text(
            f"Origen maquina: X{self.origen_maquina['X']:.2f} Y{self.origen_maquina['Y']:.2f} Z{self.origen_maquina['Z']:.2f}",
            position=(10, 160),
            color="white",
            font_size=10,
            name="txt_origen",
        )
        self.plotter.add_text("Preview planta desactivado para maximo rendimiento", position=(10, 130), color="gray", font_size=9, name="txt_plan_legend")
        # Ligero offset visual para que la traza no haga z-fighting con superficies.
        self.z_visual_offset = 0.5
        self.plotter.view_isometric()
        self.plotter.add_axes()
        self.plotter.reset_camera()

        self.plotter.add_key_event("space", self.toggle_play)
        self.plotter.add_key_event("p", self.toggle_play)
        self.plotter.add_key_event("r", self.rebobinar)
        self.plotter.add_key_event("n", self.step_forward)
        self.plotter.add_key_event("b", self.step_backward)
        self.plotter.add_key_event("i", self.ir_a_linea_prompt)

        self.plotter.add_slider_widget(
            callback=self._slider_velocidad,
            rng=[1.0, 200.0],
            value=self.play_lines_per_tick,
            title="Velocidad (lineas/tick)",
            pointa=(0.02, 0.12),
            pointb=(0.28, 0.12),
            style="modern",
        )

        self.plotter.add_slider_widget(
            callback=self._slider_linea,
            rng=[0, max(0, len(self.lineas_gcode) - 1)],
            value=0,
            title="Linea",
            pointa=(0.02, 0.06),
            pointb=(0.28, 0.06),
            style="modern",
        )

    def _set_estado_txt(self, estado: str, color: str) -> None:
        self.plotter.add_text(f"ESTADO: {estado}", position="upper_left", color=color, font_size=14, name="txt_estado")

    def _slider_velocidad(self, value: float) -> None:
        self.play_lines_per_tick = float(value)

    def _slider_linea(self, value: float) -> None:
        if self.is_playing:
            return
        idx = int(round(value))
        self._ir_a_linea(idx)

    def actualizar_posiciones_3d(self) -> None:
        x = self.pos_fisica["X"]
        y = self.pos_fisica["Y"]
        z = self.pos_fisica["Z"]

        bx, by, bz = self.actor_pos_base["portico_y"]
        self.actores["portico_y"].SetPosition(bx + 0, by + y, bz + 0)
        bx, by, bz = self.actor_pos_base["portico_x"]
        self.actores["portico_x"].SetPosition(bx + x, by + y, bz + 0)
        bx, by, bz = self.actor_pos_base["portico_z"]
        self.actores["portico_z"].SetPosition(bx + x, by + y, bz + z)

        z1 = z + (self.carrera_z_neumatica if self.estado.spindle_activo == 1 else 0.0)
        z2 = z + (self.carrera_z_neumatica if self.estado.spindle_activo == 2 else 0.0)
        z3 = z + (self.carrera_z_neumatica if self.estado.spindle_activo == 3 else 0.0)

        # Posicionamiento base (el que funcionaba para la maquina visual).
        bx, by, bz = self.actor_pos_base["spindle_1"]
        self.actores["spindle_1"].SetPosition(bx + x, by + y, bz + z1)
        bx, by, bz = self.actor_pos_base["spindle_2"]
        self.actores["spindle_2"].SetPosition(bx + x, by + y, bz + z2)
        bx, by, bz = self.actor_pos_base["spindle_3"]
        self.actores["spindle_3"].SetPosition(bx + x, by + y, bz + z3)

        # Marcador de referencia para verificar movimiento aunque los STL esten mal orientados.
        bx, by, bz = self.actor_pos_base["marker"]
        self.actores["marker"].SetPosition(bx + x, by + y, bz + z + 20.0)

    def _actualizar_textos(self, linea: str) -> None:
        self.plotter.add_text(f"G-Code: {linea}", position="upper_right", color="yellow", font_size=12, name="txt_gcode")
        self.plotter.add_text(
            f"Linea: {self.current_line}/{max(0, len(self.lineas_gcode)-1)} | T{self.estado.spindle_activo} | G5{3 + self.estado.wcs}",
            position=(10, 70),
            color="cyan",
            font_size=12,
            name="txt_linea",
        )
        self.plotter.add_text(
            f"XYZ fisica: {self.pos_fisica['X']:.2f}, {self.pos_fisica['Y']:.2f}, {self.pos_fisica['Z']:.2f}",
            position=(10, 100),
            color="white",
            font_size=11,
            name="txt_xyz",
        )

    def toggle_play(self) -> None:
        self.is_playing = not self.is_playing
        if self.is_playing:
            self._set_estado_txt("EJECUTANDO", "green")
        else:
            self._set_estado_txt("PAUSADO", "red")

    def rebobinar(self) -> None:
        self.is_playing = False
        self._ir_a_linea(0)
        self._set_estado_txt("REBOBINADO (PAUSADO)", "red")

    def ir_a_linea_prompt(self) -> None:
        self.is_playing = False
        try:
            target = input(f"Ir a linea [0..{max(0, len(self.lineas_gcode)-1)}]: ").strip()
            if not target:
                return
            idx = int(target)
            self._ir_a_linea(idx)
            self._set_estado_txt("PAUSADO", "red")
        except Exception as exc:
            print(f"Entrada invalida: {exc}")

    def step_forward(self) -> None:
        self.is_playing = False
        self._ejecutar_linea_actual(avanzar=True, render=True)

    def step_backward(self) -> None:
        self.is_playing = False
        idx = max(0, self.current_line - 1)
        self._ir_a_linea(idx)

    def _reset_estado(self) -> None:
        self.current_line = 0
        self.estado = EstadoMaquina()
        px, py, pz = self._logical_to_physical(0.0, 0.0, 0.0, self.estado.spindle_activo)
        self.pos_fisica = {"X": px, "Y": py, "Z": pz}
        self._lines_since_redraw = 0
        self._segment_history = []
        tx, ty, tz = self._trace_point_from_machine(px, py, pz, self.estado.spindle_activo)
        self._trail_points = [(tx, ty, tz)]
        if self.actores.get("trail") is not None:
            try:
                self.plotter.remove_actor(self.actores["trail"])
            except Exception:
                pass
            self.actores["trail"] = None

    def _ir_a_linea(self, idx: int) -> None:
        idx = max(0, min(idx, max(0, len(self.lineas_gcode))))
        self._reset_estado()
        for _ in range(idx):
            self._ejecutar_linea_actual(avanzar=True, render=False)

        self.current_line = idx
        preview = self.lineas_gcode[self.current_line] if self.current_line < len(self.lineas_gcode) else "--"
        self._actualizar_textos(preview)
        self._redraw_trail()
        self.actualizar_posiciones_3d()
        self.plotter.render()

    def _parse_tokens(self, linea: str) -> dict:
        out = {}
        for tok in self._regex_tokens.findall(linea):
            k = tok[0]
            try:
                out[k] = float(tok[1:])
            except ValueError:
                continue
        return out

    def _actualizar_traza(self, x: float, y: float, z: float) -> None:
        tx, ty, tz = self._trace_point_from_machine(x, y, z, self.estado.spindle_activo)
        self._trail_points.append((tx, ty, tz))
        self._lines_since_redraw += 1
        if len(self._trail_points) > self.max_trail_points:
            self._trail_points = self._trail_points[-self.max_trail_points:]

    def _redraw_trail(self) -> None:
        if len(self._trail_points) < 2:
            return
        if self.actores.get("trail") is not None:
            try:
                self.plotter.remove_actor(self.actores["trail"])
            except Exception:
                pass
        poly = pv.lines_from_points(self._trail_points)
        self.actores["trail"] = self.plotter.add_mesh(poly, color="cyan", line_width=2)

    def _current_phys_tuple(self):
        return (self.pos_fisica["X"], self.pos_fisica["Y"], self.pos_fisica["Z"])

    def _trace_point_from_machine(self, x: float, y: float, z: float, spindle: int):
        bx, by, bz = self.trace_bias.get(spindle, (0.0, 0.0, 0.0))
        drop = self.carrera_z_neumatica if spindle == self.estado.spindle_activo else 0.0
        return (x + bx, y + by, z + bz + drop + self.z_visual_offset)

    def _logical_to_physical(self, x: float, y: float, z: float, spindle: int):
        return (
            self.origen_maquina["X"] + x + self.offsets_x[spindle],
            self.origen_maquina["Y"] + y,
            self.origen_maquina["Z"] + z,
        )

    def _append_history_segment(self, line_idx: int, p0, p1, is_cut: bool) -> None:
        if p0 == p1:
            return
        self._segment_history.append((line_idx, p0, p1, is_cut))

    def _update_plan_preview(self) -> None:
        return

    def _predict_next_segments(self, count: int):
        # Simulacion ligera desde estado actual para mostrar proximas lineas con movimiento.
        state = EstadoMaquina(
            x=self.estado.x,
            y=self.estado.y,
            z=self.estado.z,
            spindle_activo=self.estado.spindle_activo,
            modo_absoluto=self.estado.modo_absoluto,
            wcs=self.estado.wcs,
            motion_mode=self.estado.motion_mode,
        )
        out = []
        idx = self.current_line

        def phys_x(x, spindle):
            return x + self.offsets_x[spindle]

        while idx < len(self.lineas_gcode) and len(out) < count:
            line = self.lineas_gcode[idx]
            toks = self._parse_tokens(line)

            if "G00" in line or "G0" in line:
                state.motion_mode = "G0"
            elif "G01" in line or "G1" in line:
                state.motion_mode = "G1"
            elif "G02" in line or "G2" in line:
                state.motion_mode = "G2"
            elif "G03" in line or "G3" in line:
                state.motion_mode = "G3"

            if "G90" in line and "G91.1" not in line:
                state.modo_absoluto = True
            if "G91" in line and "G91.1" not in line:
                state.modo_absoluto = False
            if "M6" in line or "M06" in line:
                t = int(toks.get("T", state.spindle_activo))
                if t in (1, 2, 3):
                    state.spindle_activo = t

            has_move = any(k in toks for k in ("X", "Y", "Z", "I", "J"))
            if has_move:
                x0, y0, z0 = state.x, state.y, state.z
                x1, y1, z1 = x0, y0, z0

                if state.motion_mode in ("G0", "G1"):
                    if state.modo_absoluto:
                        x1 = toks.get("X", x0)
                        y1 = toks.get("Y", y0)
                        z1 = toks.get("Z", z0)
                    else:
                        x1 = x0 + toks.get("X", 0.0)
                        y1 = y0 + toks.get("Y", 0.0)
                        z1 = z0 + toks.get("Z", 0.0)
                else:
                    # Para preview de arco, usamos endpoint de la linea.
                    if state.modo_absoluto:
                        x1 = toks.get("X", x0)
                        y1 = toks.get("Y", y0)
                        z1 = toks.get("Z", z0)
                    else:
                        x1 = x0 + toks.get("X", 0.0)
                        y1 = y0 + toks.get("Y", 0.0)
                        z1 = z0 + toks.get("Z", 0.0)

                p0 = (phys_x(x0, state.spindle_activo), y0, z0)
                p1 = (phys_x(x1, state.spindle_activo), y1, z1)
                is_cut = state.motion_mode in ("G1", "G2", "G3")
                if p0 != p1:
                    out.append((idx, p0, p1, is_cut))

                state.x, state.y, state.z = x1, y1, z1
            idx += 1

        return out

    def _apply_motion(self, tokens: dict) -> None:
        nx, ny, nz = self.estado.x, self.estado.y, self.estado.z
        if self.estado.modo_absoluto:
            if "X" in tokens:
                nx = tokens["X"]
            if "Y" in tokens:
                ny = tokens["Y"]
            if "Z" in tokens:
                nz = tokens["Z"]
        else:
            if "X" in tokens:
                nx += tokens["X"]
            if "Y" in tokens:
                ny += tokens["Y"]
            if "Z" in tokens:
                nz += tokens["Z"]

        self.estado.x, self.estado.y, self.estado.z = nx, ny, nz
        px, py, pz = self._logical_to_physical(nx, ny, nz, self.estado.spindle_activo)
        self.pos_fisica["X"] = px
        self.pos_fisica["Y"] = py
        self.pos_fisica["Z"] = pz
        self._actualizar_traza(self.pos_fisica["X"], self.pos_fisica["Y"], self.pos_fisica["Z"])

    def _apply_arc(self, tokens: dict, clockwise: bool) -> None:
        # Simulacion de arco en XY usando I/J relativos al punto actual.
        x0, y0, z0 = self.estado.x, self.estado.y, self.estado.z
        x1 = tokens.get("X", x0) if self.estado.modo_absoluto else x0 + tokens.get("X", 0.0)
        y1 = tokens.get("Y", y0) if self.estado.modo_absoluto else y0 + tokens.get("Y", 0.0)
        z1 = tokens.get("Z", z0) if self.estado.modo_absoluto else z0 + tokens.get("Z", 0.0)

        if "I" not in tokens and "J" not in tokens:
            # Sin centro de arco, caer a lineal.
            self._apply_motion({"X": x1, "Y": y1, "Z": z1})
            return

        cx = x0 + tokens.get("I", 0.0)
        cy = y0 + tokens.get("J", 0.0)
        r = ((x0 - cx) ** 2 + (y0 - cy) ** 2) ** 0.5
        if r <= 1e-9:
            self._apply_motion({"X": x1, "Y": y1, "Z": z1})
            return

        import math

        a0 = math.atan2(y0 - cy, x0 - cx)
        a1 = math.atan2(y1 - cy, x1 - cx)
        da = a1 - a0
        if clockwise and da > 0:
            da -= 2 * math.pi
        if (not clockwise) and da < 0:
            da += 2 * math.pi

        segs = max(8, int(abs(da) * 180 / math.pi / 6))  # aprox 6 grados por segmento
        for i in range(1, segs + 1):
            t = i / segs
            a = a0 + da * t
            xi = cx + r * math.cos(a)
            yi = cy + r * math.sin(a)
            zi = z0 + (z1 - z0) * t

            self.estado.x, self.estado.y, self.estado.z = xi, yi, zi
            px, py, pz = self._logical_to_physical(xi, yi, zi, self.estado.spindle_activo)
            self.pos_fisica["X"] = px
            self.pos_fisica["Y"] = py
            self.pos_fisica["Z"] = pz
            self._actualizar_traza(self.pos_fisica["X"], self.pos_fisica["Y"], self.pos_fisica["Z"])

    def _ejecutar_linea_actual(self, avanzar: bool = True, render: bool = True) -> None:
        if self.current_line >= len(self.lineas_gcode):
            return

        linea = self.lineas_gcode[self.current_line]
        tokens = self._parse_tokens(linea)

        # Modal motion mode (persistente entre lineas).
        if "G00" in linea or "G0" in linea:
            self.estado.motion_mode = "G0"
        elif "G01" in linea or "G1" in linea:
            self.estado.motion_mode = "G1"
        elif "G02" in linea or "G2" in linea:
            self.estado.motion_mode = "G2"
        elif "G03" in linea or "G3" in linea:
            self.estado.motion_mode = "G3"

        if "G54" in linea:
            self.estado.wcs = 1
        elif "G55" in linea:
            self.estado.wcs = 2
        elif "G56" in linea:
            self.estado.wcs = 3

        if "G90" in linea and "G91.1" not in linea:
            self.estado.modo_absoluto = True
        if "G91" in linea and "G91.1" not in linea:
            self.estado.modo_absoluto = False

        if "M6" in linea or "M06" in linea:
            t = int(tokens.get("T", self.estado.spindle_activo))
            if t in (1, 2, 3):
                self.estado.spindle_activo = t

        p0 = self._current_phys_tuple()
        if any(k in tokens for k in ("X", "Y", "Z", "I", "J")):
            if self.estado.motion_mode in ("G0", "G1"):
                self._apply_motion(tokens)
            elif self.estado.motion_mode == "G2":
                self._apply_arc(tokens, clockwise=True)
            elif self.estado.motion_mode == "G3":
                self._apply_arc(tokens, clockwise=False)
        p1 = self._current_phys_tuple()
        self._append_history_segment(self.current_line, p0, p1, self.estado.motion_mode in ("G1", "G2", "G3"))

        if avanzar:
            self.current_line += 1

        self._actualizar_textos(linea)
        if render or self._lines_since_redraw >= self.redraw_interval_lines:
            self._redraw_trail()
            self._lines_since_redraw = 0
        self.actualizar_posiciones_3d()
        if render:
            self.plotter.render()

    def update_step(self, *args) -> None:
        try:
            if self.current_line >= len(self.lineas_gcode):
                self.is_playing = False
                self._set_estado_txt("FIN DEL PROGRAMA", "gray")
                return

            if not self.is_playing:
                return

            steps = max(1, int(round(self.play_lines_per_tick)))
            for _ in range(steps):
                if self.current_line >= len(self.lineas_gcode):
                    break
                self._ejecutar_linea_actual(avanzar=True, render=False)
            if self._lines_since_redraw > 0:
                self._redraw_trail()
                self._lines_since_redraw = 0
            self.plotter.render()
        except Exception as exc:
            print(f"Error en la simulacion: {exc}")
            self.is_playing = False
            self._set_estado_txt("ERROR", "orange")

    def iniciar(self) -> None:
        self.plotter.show(title=f"Simulador CNC 3 Spindles - {self.archivo_gcode}", auto_close=False, interactive_update=True)
        # Bucle de actualizacion estable en PyVista 0.47.x
        while not self.plotter._closed:
            self.update_step()
            self.plotter.update()
            time.sleep(0.02)


def seleccionar_gcode(carpeta: str) -> str:
    candidatos = []
    for name in sorted(os.listdir(carpeta)):
        low = name.lower()
        if low.endswith(".gcode") or low.endswith(".tap") or low.endswith(".ngc"):
            candidatos.append(name)

    if not candidatos:
        raise RuntimeError("No se encontraron archivos .gcode/.tap/.ngc en la carpeta del simulador.")

    print("Archivos G-code disponibles:")
    for i, name in enumerate(candidatos, start=1):
        print(f"  {i}. {name}")

    raw = input(f"Selecciona archivo [1-{len(candidatos)}] (Enter=1): ").strip()
    if not raw:
        return candidatos[0]

    idx = int(raw)
    if idx < 1 or idx > len(candidatos):
        raise ValueError("Indice fuera de rango.")
    return candidatos[idx - 1]


def pedir_origen(origen_default=(0.0, 0.0, 0.0)):
    dx, dy, dz = origen_default
    raw = input(
        f"Origen pieza en coordenadas maquina X,Y,Z "
        f"[Enter={dx:.3f},{dy:.3f},{dz:.3f}]: "
    ).strip()
    if not raw:
        return origen_default
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) != 3:
        raise ValueError("Formato invalido. Usa X,Y,Z por ejemplo: 100,200,0")
    return (float(parts[0]), float(parts[1]), float(parts[2]))


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulador CNC 3 spindles en PyVista")
    parser.add_argument("--gcode", help="Archivo G-code dentro de la carpeta del simulador")
    parser.add_argument("--origin-x", type=float, help="Origen maquina X para el cero de pieza")
    parser.add_argument("--origin-y", type=float, help="Origen maquina Y para el cero de pieza")
    parser.add_argument("--origin-z", type=float, help="Origen maquina Z para el cero de pieza")
    args = parser.parse_args()

    carpeta = os.path.dirname(os.path.abspath(__file__))
    gcode = args.gcode if args.gcode else seleccionar_gcode(carpeta)
    if args.origin_x is None or args.origin_y is None or args.origin_z is None:
        origen = pedir_origen((0.0, 0.0, 0.0))
    else:
        origen = (args.origin_x, args.origin_y, args.origin_z)

    sim = SimuladorCNC(archivo_gcode=gcode, carpeta_trabajo=carpeta, origen_maquina=origen)
    sim.iniciar()


if __name__ == "__main__":
    main()
