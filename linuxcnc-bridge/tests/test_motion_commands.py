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


class OverrideAndPositionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bridge = _load_bridge_module()

    def test_override_commands(self):
        self.assertEqual(self.bridge._override_command("feed", 100), "feed_override 100")
        self.assertEqual(self.bridge._override_command("spindle", 50), "spindle_override 50")
        self.assertEqual(self.bridge._override_command("feed", 0), "feed_override 0")
        self.assertEqual(self.bridge._override_command("feed", 200), "feed_override 200")

    def test_override_rejects_out_of_range_and_non_integers(self):
        for bad in (-1, 201, 1.5, "100", None, True):
            with self.assertRaises(ValueError, msg=repr(bad)):
                self.bridge._override_command("feed", bad)

    def test_override_rejects_an_unknown_kind(self):
        with self.assertRaises(ValueError):
            self.bridge._override_command("rapid", 100)

    def test_active_offset_reads_g54_to_g59(self):
        for n, code in enumerate(["G54", "G55", "G56", "G57", "G58", "G59"], start=1):
            self.assertEqual(self.bridge._active_offset(f"PROGRAM_CODES G80 G17 {code} G90"), n)

    def test_active_offset_defaults_to_one(self):
        self.assertEqual(self.bridge._active_offset("PROGRAM_CODES G80 G17 G90"), 1)
        self.assertEqual(self.bridge._active_offset(""), 1)
        self.assertEqual(self.bridge._active_offset(None), 1)

    def test_active_offset_reads_the_g59_sub_systems_as_p7_to_p9(self):
        # G59.1 is a different system and must not be read as G59 (P6)
        self.assertEqual(self.bridge._active_offset("G59.1 G90"), 7)
        self.assertEqual(self.bridge._active_offset("G17 G59.2"), 8)
        self.assertEqual(self.bridge._active_offset("G59.3"), 9)

    def test_active_offset_does_not_confuse_g54_with_longer_codes(self):
        self.assertEqual(self.bridge._active_offset("G540 G90"), 1)
        self.assertEqual(self.bridge._active_offset("G54.1 G90"), 1)

    def test_zero_command_targets_the_given_axis_and_offset(self):
        self.assertEqual(self.bridge._zero_command("x", 1), "G10 L20 P1 X0")
        self.assertEqual(self.bridge._zero_command("Z", 3), "G10 L20 P3 Z0")

    def test_zero_command_refuses_rotary_axes(self):
        with self.assertRaises(Exception) as ctx:
            self.bridge._zero_command("A", 1)
        self.assertEqual(ctx.exception.status_code, 422)

    def test_park_and_zero_refuse_to_run_without_safe_coordinates(self):
        b = self.bridge
        saved = (b.Z_SAFE_G53, b.PARK_X_G53, b.PARK_Y_G53)
        try:
            b.Z_SAFE_G53 = b.PARK_X_G53 = b.PARK_Y_G53 = None
            for fn in (b._park_commands, b._zero_position_commands):
                with self.assertRaises(Exception) as ctx:
                    fn()
                self.assertEqual(ctx.exception.status_code, 409)
        finally:
            b.Z_SAFE_G53, b.PARK_X_G53, b.PARK_Y_G53 = saved

    def test_park_needs_all_three_values(self):
        b = self.bridge
        saved = (b.Z_SAFE_G53, b.PARK_X_G53, b.PARK_Y_G53)
        try:
            b.Z_SAFE_G53, b.PARK_X_G53, b.PARK_Y_G53 = -5.0, 5.0, None
            with self.assertRaises(Exception):
                b._park_commands()
        finally:
            b.Z_SAFE_G53, b.PARK_X_G53, b.PARK_Y_G53 = saved

    def test_park_and_zero_commands_lift_z_first_in_machine_coordinates(self):
        b = self.bridge
        saved = (b.Z_SAFE_G53, b.PARK_X_G53, b.PARK_Y_G53)
        try:
            b.Z_SAFE_G53, b.PARK_X_G53, b.PARK_Y_G53 = -5.0, 5.0, 7.5
            self.assertEqual(b._park_commands(), ["G90 G53 G0 Z-5", "G53 G0 X5 Y7.5"])
            self.assertEqual(b._zero_position_commands(), ["G90 G53 G0 Z-5", "G90 G0 X0 Y0"])
        finally:
            b.Z_SAFE_G53, b.PARK_X_G53, b.PARK_Y_G53 = saved
