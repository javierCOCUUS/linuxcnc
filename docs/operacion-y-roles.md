# Pantalla Operación, roles y variables nuevas

## Dos tokens

El orquestador (`mcp`) distingue dos roles según el token que reciba:

| Token | Variable | Qué puede hacer |
|---|---|---|
| Máquina | `PLUGIN_API_TOKEN` | Todo. Es el que se configura en la app del PC de la máquina. |
| Operador | `PLUGIN_OPERATOR_TOKEN` (opcional) | Ver, parar (E-stop, pausa, stop) y cambiar los overrides de avance y husillo. |

El operador recibe **403** en todo lo que mueve la máquina o cambia su configuración: jog, power,
home, MDI, husillo, salir de E-stop, abrir/ejecutar/reanudar/paso/rewind de un programa, ir a park,
ir a cero y poner a cero un eje.

Sin `PLUGIN_OPERATOR_TOKEN` no cambia nada: el token único puede hacerlo todo. `GET /whoami` dice
qué rol tiene el token; la app lo usa para desactivar lo que el servidor rechazaría y muestra
«MODO OPERADOR» en la cabecera. Mientras no sabe el rol, trata al cliente como operador.

Para usarlo, en el servidor: añade `PLUGIN_OPERATOR_TOKEN=<otro token largo>` y recrea el
orquestador; en el portátil pon ese token en Ajustes.

## Variables del bridge

| Variable | Por defecto | Para qué |
|---|---|---|
| `Z_SAFE_G53` | sin valor | Cota Z de máquina (G53) a la que se sube antes de ir a park o a cero. |
| `PARK_X_G53`, `PARK_Y_G53` | sin valor | Posición X/Y de máquina de «IR A PARK». |
| `LINUXCNCRSH_QUERY_SPINDLE` | `false` | Consultar `get spindle` en el sondeo. **Tumba `linuxcncrsh`**; no activar. |

`Z_SAFE_G53`, `PARK_X_G53` y `PARK_Y_G53` **no tienen valor por defecto a propósito**: un valor
equivocado podría llevar un eje contra su final de carrera. «IR A PARK» y «GO TO ZERO» se niegan
a ejecutarse (409) hasta que estén configuradas. Las cotas de Mach3 no valen tal cual: son de otro
sistema de coordenadas.

## Qué falta (pantalla Operación)

- Mandriles T1–T3, nuevos ceros, altura de herramienta y «desde línea»: dependen de las macros de
  Mach3 (`legacy_macros/`) y de decidir cómo se traducen.
- Salidas de aspiración y vacío: hace falta el `salidas.txt` de `cncelephant`.
- Posición de trabajo (coordenadas relativas), línea actual y progreso: requieren consultas nuevas
  (`get rel_act_pos`, `get program_line`). **No se han añadido al sondeo** porque `get spindle`
  demostró que una consulta puede tumbar `linuxcncrsh`. Probar cada una por separado antes.
- Jog continuo con latido (parar si la app deja de confirmar).
- Registro de trabajos y avisos.

## Comprobar una consulta `get` nueva antes de activarla

En el PC de LinuxCNC, una conexión por consulta, esperando a que systemd relance el servidor si cae:

```bash
python3 - <<'PY'
import re, socket, time
pw = re.search(r"--connectpw (\S+)", open("/home/linuxcnc/linuxcncrsh.service").read()).group(1)
def probe(cmd):
    s = socket.create_connection(("127.0.0.1", 5007), 3); s.settimeout(0.6)
    def talk(c, w=0.4):
        s.sendall((c + "\n").encode()); time.sleep(w); out = b""
        try:
            while True:
                d = s.recv(4096)
                if not d: return "CONEXION CERRADA (el servidor se cayo)"
                out += d
        except socket.timeout: pass
        return out.decode(errors="replace").strip().replace("\r\n", " | ")
    talk(f"hello {pw} diag 1.0")
    for h in ("set echo off", "set verbose on", "set set_wait done", "set update auto"): talk(h, 0.2)
    return talk(f"get {cmd}")
for cmd in ["rel_act_pos", "program_line", "spindle_override", "joint_limit", "tool"]:
    print(f"get {cmd:18s} -> {probe(cmd)}", flush=True); time.sleep(8)
PY
```
