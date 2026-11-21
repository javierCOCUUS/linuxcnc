"""
Unit tests for the E-stop / power command helpers.

Run with:  cd linuxcnc-bridge && python -m pytest tests/test_motion_commands.py -v
"""
import sys
import types
import unittest
from unittest.mock import MagicMock


def _stub_module(name: str, **attrs):
    m = types.ModuleType(name)
    for k, v in attrs.items():
        setattr(m, k, v)
    sys.modules[name] = m
    return m


def _load_bridge_module():
    """Import main.py with heavy dependencies stubbed out."""
    fake_socks = _stub_module("socks", socksocket=MagicMock, SOCKS5=2)
    fake_socks.set_default_proxy = MagicMock()

    class FakeHTTPException(Exception):
        def __init__(self, status_code=500, detail=""):
            super().__init__(detail)
            self.status_code = status_code
            self.detail = detail

    _stub_module("fastapi", FastAPI=MagicMock(return_value=MagicMock()), HTTPException=FakeHTTPException)

    class _BaseModel:
        def __init__(self, **kw):
            for k, v in kw.items():
                setattr(self, k, v)
    _stub_module("pydantic", BaseModel=_BaseModel)

    import importlib.util, pathlib
    spec = importlib.util.spec_from_file_location(
        "bridge_main_motion",
        pathlib.Path(__file__).parent.parent / "main.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class MotionCommandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bridge = _load_bridge_module()

    def test_estop_commands(self):
        self.assertEqual(self.bridge._estop_command(True), "estop on")
        self.assertEqual(self.bridge._estop_command(False), "estop off")

    def test_power_commands(self):
        self.assertEqual(self.bridge._power_command(True), "machine on")
        self.assertEqual(self.bridge._power_command(False), "machine off")

    def test_apply_set_sends_the_subcommand(self):
        client = MagicMock()
        self.bridge._apply_set(client, "estop off")
        client.set.assert_called_once_with("estop off")

    def test_apply_set_turns_a_rejection_into_409(self):
        client = MagicMock()
        client.set.side_effect = self.bridge.LinuxCNCUnavailable("rejected: SET NAK")
        with self.assertRaises(Exception) as ctx:
            self.bridge._apply_set(client, "machine on")
        self.assertEqual(ctx.exception.status_code, 409)
        self.assertIn("rejected", ctx.exception.detail)


if __name__ == "__main__":
    unittest.main()
