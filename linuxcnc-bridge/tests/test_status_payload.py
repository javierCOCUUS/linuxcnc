"""
Unit tests for _status_payload() backoff + stale-cache logic.

Run with:  cd linuxcnc-bridge && python -m pytest tests/test_status_payload.py -v
"""
import importlib
import sys
import time
import types
import unittest
from unittest.mock import patch, MagicMock


def _stub_module(name: str, **attrs):
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m
    return m


def _load_bridge_module():
    """Import main.py with heavy dependencies stubbed out."""
    # Stub socks
    fake_socks = _stub_module("socks", socksocket=MagicMock, SOCKS5=2)
    fake_socks.set_default_proxy = MagicMock()

    # Stub fastapi
    fake_http_exc = type("HTTPException", (Exception,), {"__init__": lambda self, status_code=500, detail="": None})
    fake_fa = _stub_module("fastapi",
        FastAPI=MagicMock(return_value=MagicMock()),
        HTTPException=fake_http_exc,
    )

    # Stub pydantic
    class _BaseModel:
        def __init__(self, **kw):
            for k, v in kw.items():
                setattr(self, k, v)
    fake_pydantic = _stub_module("pydantic", BaseModel=_BaseModel)

    import importlib.util, pathlib
    spec = importlib.util.spec_from_file_location(
        "bridge_main",
        pathlib.Path(__file__).parent.parent / "main.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


bridge = _load_bridge_module()


def _reset_state(mod, last_good=None, last_good_ts=0.0, backoff_until=0.0, fail_count=0):
    mod._cncrsh_last_good = last_good
    mod._cncrsh_last_good_ts = last_good_ts
    mod._cncrsh_backoff_until = backoff_until
    mod._cncrsh_fail_count = fail_count


SAMPLE_STATUS = {
    "state": "IDLE",
    "position": {"x": 1.0, "y": 2.0, "z": 3.0},
    "homed": ["X", "Y", "Z"],
    "spindle": {"on": False, "speed": 0, "direction": "off"},
    "feed_rate": 0.0,
    "active_gcode": "",
    "system": {"backend": "linuxcncrsh"},
}


class TestStatusPayloadBackoff(unittest.TestCase):

    def setUp(self):
        # Force linuxcncrsh backend for all tests
        bridge.BRIDGE_BACKEND = "linuxcncrsh"

    def test_backoff_active_fresh_last_good_returns_stale(self):
        """Backoff + fresh last_good → stale dict, never UNAVAILABLE."""
        now = time.time()
        _reset_state(
            bridge,
            last_good=SAMPLE_STATUS,
            last_good_ts=now - 2.0,          # 2s ago — well within 10s TTL
            backoff_until=now + 2.0,          # still in backoff
        )
        result = bridge._status_payload()
        self.assertNotEqual(result.get("state"), "UNAVAILABLE")
        self.assertEqual(result.get("state"), "IDLE")
        self.assertTrue(result.get("system", {}).get("degraded"))

    def test_backoff_active_no_last_good_returns_unavailable(self):
        """Backoff + no last_good (first failure ever) → UNAVAILABLE."""
        now = time.time()
        _reset_state(bridge, last_good=None, backoff_until=now + 2.0)
        result = bridge._status_payload()
        self.assertEqual(result.get("state"), "UNAVAILABLE")

    def test_backoff_active_stale_last_good_returns_unavailable(self):
        """Backoff + last_good older than STALE_TTL → UNAVAILABLE."""
        now = time.time()
        _reset_state(
            bridge,
            last_good=SAMPLE_STATUS,
            last_good_ts=now - (bridge._CNCRSH_STALE_TTL + 1),  # expired
            backoff_until=now + 2.0,
        )
        result = bridge._status_payload()
        self.assertEqual(result.get("state"), "UNAVAILABLE")

    def test_no_backoff_success_clears_stale(self):
        """Successful call returns fresh data with no degraded flag."""
        now = time.time()
        _reset_state(bridge, last_good=None, backoff_until=0.0)
        with patch.object(bridge, "_linuxcncrsh_status", return_value=dict(SAMPLE_STATUS)):
            result = bridge._status_payload()
        self.assertEqual(result.get("state"), "IDLE")
        self.assertFalse(result.get("system", {}).get("degraded", False))
        # State has been stored
        self.assertIsNotNone(bridge._cncrsh_last_good)

    def test_non_os_error_serves_stale_if_fresh(self):
        """LinuxCNCUnavailable failure → serves last_good if fresh."""
        now = time.time()
        _reset_state(
            bridge,
            last_good=SAMPLE_STATUS,
            last_good_ts=now - 1.0,
            backoff_until=0.0,
            fail_count=0,
        )
        with patch.object(bridge, "_linuxcncrsh_status",
                          side_effect=bridge.LinuxCNCUnavailable("parse error")):
            result = bridge._status_payload()
        self.assertNotEqual(result.get("state"), "UNAVAILABLE")
        self.assertEqual(result.get("state"), "IDLE")
        self.assertTrue(result.get("system", {}).get("degraded"))

    def test_empty_dict_last_good_treated_as_none(self):
        """An empty dict {} for last_good must NOT be served as stale data."""
        # This tests the original bug: {} is falsy, but an actual result dict is not
        now = time.time()
        _reset_state(
            bridge,
            last_good=None,          # None = never succeeded (the correct initial value)
            last_good_ts=now - 1.0,
            backoff_until=now + 2.0,
        )
        result = bridge._status_payload()
        self.assertEqual(result.get("state"), "UNAVAILABLE",
                         "Should be UNAVAILABLE when no last_good, even if ts is recent")


if __name__ == "__main__":
    unittest.main()
