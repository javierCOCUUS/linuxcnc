from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List
import json as _json
import logging
import os
import re
import socket
import socks
import threading
import time
import urllib.error
import urllib.request

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
_log = logging.getLogger("linuxcnc-bridge")

app = FastAPI(title="linuxcnc-bridge")


def _env_int(name: str, default: int) -> int:
    value = (os.environ.get(name, "") or "").strip()
    return int(value) if value else default


def _env_float(name: str, default: float) -> float:
    value = (os.environ.get(name, "") or "").strip()
    return float(value) if value else default

# --- CONFIGURATION ---
NC_FILES_DIR = os.environ.get("GCODE_DIR", "/gcode")
CONFIG_DIR = "/machine/config"
MACROS_DIR = "/machine/macros"
BRIDGE_BACKEND = os.environ.get("BRIDGE_BACKEND", "stub").strip().lower()
LINUXCNCRSH_HOST = os.environ.get("LINUXCNCRSH_HOST", "").strip()
LINUXCNCRSH_PORT = _env_int("LINUXCNCRSH_PORT", 5007)
LINUXCNCRSH_CONNECT_PASSWORD = os.environ.get("LINUXCNCRSH_CONNECT_PASSWORD", "EMC")
LINUXCNCRSH_ENABLE_PASSWORD = os.environ.get("LINUXCNCRSH_ENABLE_PASSWORD", "EMCTOO")
LINUXCNCRSH_CLIENT_NAME = os.environ.get("LINUXCNCRSH_CLIENT_NAME", "mcp-cnc-bridge")
LINUXCNCRSH_TIMEOUT = _env_float("LINUXCNCRSH_TIMEOUT", 2.0)
LINUXCNCRSH_SOCKS5_PROXY_HOST = os.environ.get("LINUXCNCRSH_SOCKS5_PROXY_HOST", "").strip()
LINUXCNCRSH_SOCKS5_PROXY_PORT = _env_int("LINUXCNCRSH_SOCKS5_PROXY_PORT", 1080)
LINUXCNC_REMOTE_GCODE_DIR = os.environ.get("LINUXCNC_REMOTE_GCODE_DIR", "").strip()
HAL_BRIDGE_PORT = _env_int("HAL_BRIDGE_PORT", 8010)
AXIS_LETTERS = "XYZABCUVW"
FLOAT_RE = re.compile(r"[-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?")

# --- LINUXCNCRSH CONCURRENCY STATE ---
_cncrsh_lock = threading.Lock()   # one TCP connection to :5007 at a time
_cncrsh_fail_count: int = 0
_cncrsh_last_good: dict = {}
_cncrsh_last_good_ts: float = 0.0
_cncrsh_backoff_until: float = 0.0
_CNCRSH_STALE_TTL = 5.0           # serve last-good status for up to 5s on transient failure
_CNCRSH_BACKOFF_S = 3.0           # seconds to wait after any connection failure

# Ensure directories exist
for d in [NC_FILES_DIR, CONFIG_DIR, MACROS_DIR]:
    os.makedirs(d, exist_ok=True)

# --- MODELS ---

class CommandBase(BaseModel):
    confirm: bool = False

class JogParams(CommandBase):
    axis: str
    distance: float
    speed: float = 600

class GCodeParams(CommandBase):
    command: Optional[str] = None
    gcode: Optional[str] = None  # alias for command; command takes priority if both are set

class SpindleParams(CommandBase):
    speed: int = 0
    direction: str = "CW"
    spindle_speed: Optional[int] = None  # alias for speed; takes priority if set
    state: Optional[str] = None          # alias for direction; takes priority if set

class MacroParams(BaseModel):
    name: str
    content: str


class LinuxCNCUnavailable(RuntimeError):
    pass


def _linuxcncrsh_socket() -> socket.socket:
    if LINUXCNCRSH_SOCKS5_PROXY_HOST:
        proxy_socket = socks.socksocket()
        proxy_socket.set_proxy(
            socks.SOCKS5,
            LINUXCNCRSH_SOCKS5_PROXY_HOST,
            LINUXCNCRSH_SOCKS5_PROXY_PORT,
        )
        proxy_socket.settimeout(LINUXCNCRSH_TIMEOUT)
        proxy_socket.connect((LINUXCNCRSH_HOST, LINUXCNCRSH_PORT))
        return proxy_socket
    return socket.create_connection((LINUXCNCRSH_HOST, LINUXCNCRSH_PORT), timeout=LINUXCNCRSH_TIMEOUT)


class LinuxCNCRshClient:
    def __init__(self):
        if not LINUXCNCRSH_HOST:
            raise LinuxCNCUnavailable("LINUXCNCRSH_HOST is not configured")
        self._socket = _linuxcncrsh_socket()
        self._socket.settimeout(LINUXCNCRSH_TIMEOUT)
        try:
            self._handshake()
        except Exception:
            self._socket.close()
            raise

    def __enter__(self) -> "LinuxCNCRshClient":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def close(self) -> None:
        try:
            self._socket.close()
        except OSError:
            pass

    def _read_lines(self) -> List[str]:
        buf = b""
        while True:
            try:
                data = self._socket.recv(4096)
            except socket.timeout:
                break
            if not data:
                break
            buf += data
            if b"\n" in buf:
                break
        text = buf.decode("utf-8", errors="replace")
        return [line.strip() for line in text.replace("\r", "\n").split("\n") if line.strip()]

    def _send(self, command: str) -> List[str]:
        self._socket.sendall((command + "\n").encode("utf-8"))
        return self._read_lines()

    def _handshake(self):
        lines = self._send(f"hello {LINUXCNCRSH_CONNECT_PASSWORD} {LINUXCNCRSH_CLIENT_NAME} 1.0")
        if not any("HELLO ACK" in line.upper() for line in lines):
            raise LinuxCNCUnavailable(f"linuxcncrsh handshake failed: {' | '.join(lines) or 'no response'}")
        self._send("set echo off")
        self._send("set verbose on")
        self._send("set set_wait done")
        self._send("set update auto")

    def enable(self):
        lines = self._send(f"set enable {LINUXCNCRSH_ENABLE_PASSWORD}")
        if any("NAK" in line.upper() for line in lines):
            raise LinuxCNCUnavailable(f"linuxcncrsh enable failed: {' | '.join(lines)}")

    def get(self, subcommand: str) -> str:
        lines = self._send(f"get {subcommand}")
        return _extract_payload(lines, "GET")

    def set(self, subcommand: str):
        lines = self._send(f"set {subcommand}")
        if any("NAK" in line.upper() for line in lines):
            raise LinuxCNCUnavailable(f"linuxcncrsh rejected command '{subcommand}': {' | '.join(lines)}")


def _check_machine_ready(client: "LinuxCNCRshClient") -> None:
    estop = _first_word(client.get("estop"))
    machine = _first_word(client.get("machine"))
    if estop == "on":
        raise HTTPException(status_code=409, detail="LinuxCNC is in E-stop")
    if machine != "on":
        raise HTTPException(status_code=409, detail="LinuxCNC machine power is off")


def _extract_payload(lines: List[str], prefix: str) -> str:
    if not lines:
        return ""
    filtered = [line for line in lines if not line.lower().startswith(("hello ", "set ", "get "))]
    target = filtered[-1] if filtered else lines[-1]
    upper_prefix = prefix.upper()
    upper_target = target.upper()
    if upper_prefix == "GET":
        parts = target.split(None, 1)
        return parts[1].strip() if len(parts) > 1 else ""
    marker = f"{upper_prefix} "
    ack_marker = " ACK"
    if upper_target.startswith(marker):
        without_prefix = target[len(marker):]
        ack_index = without_prefix.upper().find(ack_marker)
        if ack_index >= 0:
            return without_prefix[ack_index + len(ack_marker):].strip()
    return target.strip()


def _float_tokens(text: str) -> List[float]:
    return [float(match) for match in FLOAT_RE.findall(text)]


def _first_word(text: str) -> str:
    return text.strip().split()[0].lower() if text.strip() else ""


def _axis_letter(axis: str) -> str:
    axis_name = (axis or "").strip().upper()
    if axis_name not in AXIS_LETTERS:
        raise HTTPException(status_code=422, detail=f"Unsupported axis '{axis}'. Use one of {', '.join(AXIS_LETTERS)}")
    return axis_name


def _resolved_gcode(params: GCodeParams) -> str:
    command = (params.command or params.gcode or "").strip()
    if not command:
        raise HTTPException(status_code=422, detail="Missing G-code command")
    return command


def _resolved_spindle(params: SpindleParams) -> tuple[int, str]:
    speed = params.spindle_speed if params.spindle_speed is not None else params.speed
    state = (params.state or params.direction or "CW").strip().lower()
    return speed, state


def _state_from_status(estop: str, machine: str, program_status: str, mode: str) -> str:
    if estop == "on":
        return "ESTOP"
    if machine == "off":
        return "OFF"
    if program_status == "running":
        return "RUNNING"
    if program_status == "paused":
        return "PAUSED"
    if mode == "mdi":
        return "MDI"
    return "IDLE"


def _remote_file_path(filename: str) -> str:
    local_path = os.path.abspath(os.path.join(NC_FILES_DIR, filename))
    if not local_path.startswith(os.path.abspath(NC_FILES_DIR) + os.sep) and local_path != os.path.abspath(NC_FILES_DIR):
        raise HTTPException(status_code=422, detail="Invalid filename")
    if not os.path.isfile(local_path):
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")
    if not LINUXCNC_REMOTE_GCODE_DIR:
        raise HTTPException(
            status_code=409,
            detail="LINUXCNC_REMOTE_GCODE_DIR is not configured; cannot open files on the remote LinuxCNC host"
        )
    remote_gcode_dir = LINUXCNC_REMOTE_GCODE_DIR.rstrip("/\\")
    return f"{remote_gcode_dir}/{os.path.basename(filename)}"


def _stub_status():
    return {
        "position": {"x": 0.0, "y": 0.0, "z": 10.0},
        "state": "IDLE",
        "homed": ["X", "Y", "Z"],
        "spindle": {"on": False, "speed": 0, "direction": "off"},
        "feed_rate": 100.0,
        "active_gcode": "G54 G17 G90",
        "system": {"backend": "stub", "cpu": "arm64", "temp": 45.2}
    }


def _linuxcncrsh_status():
    if time.time() < _cncrsh_backoff_until:
        remaining = _cncrsh_backoff_until - time.time()
        raise LinuxCNCUnavailable(f"connection backoff active ({remaining:.1f}s remaining)")
    with _cncrsh_lock:
        t0 = time.time()
        client = LinuxCNCRshClient()
        try:
            positions = _float_tokens(client.get("abs_act_pos"))
            homed_words = client.get("joint_homed").lower().split()
            estop = _first_word(client.get("estop"))
            machine = _first_word(client.get("machine"))
            mode = _first_word(client.get("mode"))
            program_status = _first_word(client.get("program_status"))
            spindle_state = _first_word(client.get("spindle"))
            active_codes = client.get("program_codes")
            feed_override = _float_tokens(client.get("feed_override"))
            homed = [
                AXIS_LETTERS[index]
                for index, word in enumerate(homed_words)
                if word in {"homed", "yes", "on", "1"} and index < len(AXIS_LETTERS)
            ]
            spindle_on = spindle_state not in {"off", ""}
            return {
                "position": {
                    "x": positions[0] if len(positions) > 0 else 0.0,
                    "y": positions[1] if len(positions) > 1 else 0.0,
                    "z": positions[2] if len(positions) > 2 else 0.0,
                },
                "state": _state_from_status(estop, machine, program_status, mode),
                "homed": homed,
                "spindle": {
                    "on": spindle_on,
                    "speed": 0,
                    "direction": spindle_state or "off",
                },
                "feed_rate": feed_override[0] if feed_override else 100.0,
                "active_gcode": active_codes,
                "system": {
                    "backend": "linuxcncrsh",
                    "target": f"{LINUXCNCRSH_HOST}:{LINUXCNCRSH_PORT}",
                    "proxy": f"socks5://{LINUXCNCRSH_SOCKS5_PROXY_HOST}:{LINUXCNCRSH_SOCKS5_PROXY_PORT}" if LINUXCNCRSH_SOCKS5_PROXY_HOST else None,
                    "mode": mode,
                    "machine": machine,
                    "estop": estop,
                    "program_status": program_status,
                }
            }
        finally:
            client.close()
            elapsed = time.time() - t0
            if elapsed > 1.5:
                _log.warning("[linuxcncrsh_status] slow: %.2fs", elapsed)
            else:
                _log.debug("[linuxcncrsh_status] %.2fs", elapsed)


def _status_payload():
    global _cncrsh_fail_count, _cncrsh_last_good, _cncrsh_last_good_ts, _cncrsh_backoff_until
    if BRIDGE_BACKEND == "stub":
        return _stub_status()
    if BRIDGE_BACKEND == "linuxcncrsh":
        try:
            result = _linuxcncrsh_status()
            _cncrsh_fail_count = 0
            _cncrsh_last_good = result
            _cncrsh_last_good_ts = time.time()
            return result
        except (OSError, LinuxCNCUnavailable, ValueError) as exc:
            _cncrsh_fail_count += 1
            if isinstance(exc, OSError):
                _cncrsh_backoff_until = time.time() + _CNCRSH_BACKOFF_S
                _log.warning("[linuxcncrsh_status] failure %d (backoff %.0fs): %s",
                             _cncrsh_fail_count, _CNCRSH_BACKOFF_S, exc)
            else:
                _log.warning("[linuxcncrsh_status] failure %d: %s", _cncrsh_fail_count, exc)
            if (_cncrsh_fail_count < 2 and _cncrsh_last_good
                    and (time.time() - _cncrsh_last_good_ts) < _CNCRSH_STALE_TTL):
                _log.info("[linuxcncrsh_status] returning last-good status (transient failure)")
                return _cncrsh_last_good
            return {
                "position": {"x": 0.0, "y": 0.0, "z": 0.0},
                "state": "UNAVAILABLE",
                "homed": [],
                "spindle": {"on": False, "speed": 0, "direction": "off"},
                "feed_rate": 0.0,
                "active_gcode": "",
                "system": {
                    "backend": "linuxcncrsh",
                    "target": f"{LINUXCNCRSH_HOST}:{LINUXCNCRSH_PORT}" if LINUXCNCRSH_HOST else "unconfigured",
                    "proxy": f"socks5://{LINUXCNCRSH_SOCKS5_PROXY_HOST}:{LINUXCNCRSH_SOCKS5_PROXY_PORT}" if LINUXCNCRSH_SOCKS5_PROXY_HOST else None,
                    "error": str(exc),
                }
            }
    raise HTTPException(status_code=500, detail=f"Unsupported BRIDGE_BACKEND '{BRIDGE_BACKEND}'")


def _require_live_linuxcnc() -> "LinuxCNCRshClient":
    if BRIDGE_BACKEND != "linuxcncrsh":
        raise HTTPException(status_code=409, detail=f"Motion commands require BRIDGE_BACKEND=linuxcncrsh, current backend is '{BRIDGE_BACKEND}'")
    try:
        client = LinuxCNCRshClient()
    except (OSError, LinuxCNCUnavailable) as exc:
        raise HTTPException(status_code=503, detail=f"LinuxCNC connection failed: {exc}") from exc
    try:
        _check_machine_ready(client)
        client.enable()
        return client
    except Exception:
        client.close()
        raise

# --- SAFETY SYSTEM DECORATOR ---
def check_safety(level: str, confirm: bool):
    if level in ["CAUTION", "DANGEROUS", "CRITICAL"] and not confirm:
        raise HTTPException(
            status_code=403, 
            detail=f"This operation is {level}. Please set 'confirm: true' to execute."
        )

# --- ENDPOINTS ---

# 1. STATUS (SAFE)
@app.get("/status")
async def get_machine_status():
    return _status_payload()

# 2. MOTION (CAUTION)
@app.post("/motion/jog")
async def jog(params: JogParams):
    check_safety("CAUTION", params.confirm)
    axis = _axis_letter(params.axis)
    if BRIDGE_BACKEND == "stub":
        return {"status": "moving", "axis": axis, "dist": params.distance, "backend": "stub"}

    client = _require_live_linuxcnc()
    try:
        signed_speed = abs(params.speed) if params.distance >= 0 else -abs(params.speed)
        client.set("mode manual")
        client.set("teleop_enable on")
        client.set(f"jog_incr {axis} {signed_speed} {abs(params.distance)}")
        return {"status": "moving", "axis": axis, "dist": params.distance, "speed": signed_speed, "backend": "linuxcncrsh"}
    finally:
        client.close()

@app.post("/motion/home")
async def home_axes(params: CommandBase):
    check_safety("CAUTION", params.confirm)
    if BRIDGE_BACKEND == "stub":
        return {"status": "homing_initiated", "backend": "stub"}

    client = _require_live_linuxcnc()
    try:
        client.set("mode manual")
        client.set("home -1")
        return {"status": "homing_initiated", "backend": "linuxcncrsh"}
    finally:
        client.close()

# 3. G-CODE (DANGEROUS)
@app.post("/gcode/send")
async def send_gcode(params: GCodeParams):
    check_safety("DANGEROUS", params.confirm)
    command = _resolved_gcode(params)
    if BRIDGE_BACKEND == "stub":
        return {"status": "executed", "command": command, "backend": "stub"}

    client = _require_live_linuxcnc()
    try:
        client.set("mode mdi")
        client.set(f"mdi {command}")
        return {"status": "executed", "command": command, "backend": "linuxcncrsh"}
    finally:
        client.close()

@app.post("/gcode/spindle")
async def spindle_control(params: SpindleParams):
    check_safety("DANGEROUS", params.confirm)
    speed, state = _resolved_spindle(params)
    if state in {"off", "stop", "m5"}:
        command = "M5"
    elif state in {"reverse", "ccw", "m4"}:
        command = f"M4 S{max(speed, 0)}"
    else:
        command = f"M3 S{max(speed, 0)}"

    if BRIDGE_BACKEND == "stub":
        return {"status": "spindle_updated", "command": command, "backend": "stub"}

    client = _require_live_linuxcnc()
    try:
        client.set("mode mdi")
        client.set(f"mdi {command}")
        return {"status": "spindle_updated", "command": command, "backend": "linuxcncrsh"}
    finally:
        client.close()

# 4. SD CARD (FILES)
@app.get("/files")
async def list_files():
    files = os.listdir(NC_FILES_DIR)
    return {"files": files}

@app.post("/files/run")
async def run_file(filename: str, params: CommandBase):
    check_safety("DANGEROUS", params.confirm)
    if BRIDGE_BACKEND == "stub":
        return {"status": "program_started", "file": filename, "backend": "stub"}

    remote_path = _remote_file_path(filename)
    client = _require_live_linuxcnc()
    try:
        client.set("mode auto")
        client.set(f"open {remote_path}")
        client.set("run")
        return {"status": "program_started", "file": filename, "remote_path": remote_path, "backend": "linuxcncrsh"}
    finally:
        client.close()

# 5. MACROS
@app.post("/macros/save")
async def save_macro(params: MacroParams):
    path = os.path.join(MACROS_DIR, f"{params.name}.ngc")
    with open(path, "w") as f:
        f.write(params.content)
    return {"status": "macro_saved", "name": params.name}

@app.get("/macros")
async def list_macros():
    return {"macros": os.listdir(MACROS_DIR)}

# 6. CONFIG (CRITICAL)
@app.post("/config/restore")
async def restore_config(backup_name: str, params: CommandBase):
    check_safety("CRITICAL", params.confirm)
    return {"status": "config_restored", "backup": backup_name}

# --- HEALTH CHECKS ---

def _check_linuxcncrsh() -> dict:
    """Derives linuxcncrsh health from /status polling state — opens no new sockets."""
    if not LINUXCNCRSH_HOST:
        return {"status": "unconfigured", "latency_ms": 0}
    now = time.time()
    if now < _cncrsh_backoff_until:
        return {"status": "down", "latency_ms": 0,
                "error": f"backoff ({_cncrsh_backoff_until - now:.1f}s remaining)"}
    if _cncrsh_fail_count >= 2:
        return {"status": "down", "latency_ms": 0,
                "error": f"{_cncrsh_fail_count} consecutive failures"}
    if _cncrsh_last_good and (now - _cncrsh_last_good_ts) < 10.0:
        return {"status": "ok", "latency_ms": 0}
    return {"status": "down", "latency_ms": 0, "error": "no recent status data"}


def _check_hal_bridge() -> dict:
    """GET http://<host>:HAL_BRIDGE_PORT/ — verify service=hal-bridge, status=online."""
    t0 = time.time()
    if not LINUXCNCRSH_HOST:
        return {"status": "unconfigured", "latency_ms": 0}
    url = f"http://{LINUXCNCRSH_HOST}:{HAL_BRIDGE_PORT}/"
    try:
        with urllib.request.urlopen(url, timeout=3) as resp:
            body = _json.loads(resp.read())
        elapsed = round((time.time() - t0) * 1000)
        if body.get("service") == "hal-bridge" and body.get("status") == "online":
            return {"status": "ok", "latency_ms": elapsed}
        return {"status": "down", "latency_ms": elapsed, "error": f"unexpected response: {body}"}
    except Exception as exc:
        return {"status": "down", "latency_ms": round((time.time() - t0) * 1000), "error": str(exc)}


def _check_mesa_pins() -> dict:
    """GET /hal/pins?filter=hm2 — verify status=ok and count > 0."""
    t0 = time.time()
    if not LINUXCNCRSH_HOST:
        return {"status": "unconfigured", "latency_ms": 0}
    url = f"http://{LINUXCNCRSH_HOST}:{HAL_BRIDGE_PORT}/hal/pins?filter=hm2"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            body = _json.loads(resp.read())
        elapsed = round((time.time() - t0) * 1000)
        count = body.get("count", 0)
        if body.get("status") == "ok" and count > 0:
            return {"status": "ok", "latency_ms": elapsed, "count": count}
        return {"status": "down", "latency_ms": elapsed, "count": count, "error": "no hm2 pins found"}
    except Exception as exc:
        return {"status": "down", "latency_ms": round((time.time() - t0) * 1000), "error": str(exc)}


@app.get("/health")
def get_health():
    """Infrastructure health — read-only, no machine control, no side effects."""
    if BRIDGE_BACKEND == "stub":
        stub = {"status": "stub", "latency_ms": 0}
        return {"backend": "stub", "status": "stub",
                "linuxcncrsh": stub, "hal_bridge": stub, "mesa_pins": stub}

    cncrsh = _check_linuxcncrsh()
    hal    = _check_hal_bridge()
    mesa   = _check_mesa_pins()
    overall = "ok" if all(r["status"] == "ok" for r in [cncrsh, hal, mesa]) else "degraded"
    return {
        "backend": BRIDGE_BACKEND,
        "status": overall,
        "linuxcncrsh": cncrsh,
        "hal_bridge": hal,
        "mesa_pins": mesa,
    }


@app.get("/")
async def root():
    return {
        "service": "linuxcnc-bridge",
        "mode": BRIDGE_BACKEND,
        "status": "online",
        "target": f"{LINUXCNCRSH_HOST}:{LINUXCNCRSH_PORT}" if LINUXCNCRSH_HOST else None,
        "proxy": f"socks5://{LINUXCNCRSH_SOCKS5_PROXY_HOST}:{LINUXCNCRSH_SOCKS5_PROXY_PORT}" if LINUXCNCRSH_SOCKS5_PROXY_HOST else None,
    }
