import asyncio
import importlib
import os
import sys
import unittest
from pathlib import Path
from unittest import mock

from pydantic import ValidationError


CAM_ENGINE_DIR = Path(__file__).resolve().parents[1]
if str(CAM_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(CAM_ENGINE_DIR))


class CamApiHardeningTests(unittest.TestCase):
    def setUp(self):
        self._old_workspace = os.environ.get("DXF_WORKSPACE")
        self._old_gcode_output = os.environ.get("GCODE_OUTPUT")
        os.environ["DXF_WORKSPACE"] = str(CAM_ENGINE_DIR / "workspace-test")
        os.environ["GCODE_OUTPUT"] = str(CAM_ENGINE_DIR / "gcode-test")
        sys.modules.pop("main", None)
        self.main = importlib.import_module("main")

    def tearDown(self):
        if self._old_workspace is None:
            os.environ.pop("DXF_WORKSPACE", None)
        else:
            os.environ["DXF_WORKSPACE"] = self._old_workspace
        if self._old_gcode_output is None:
            os.environ.pop("GCODE_OUTPUT", None)
        else:
            os.environ["GCODE_OUTPUT"] = self._old_gcode_output
        sys.modules.pop("main", None)

    def test_generate_cam_logs_unexpected_engine_failures(self):
        config = self.main.CAMConfig(dxf_filename="demo.dxf", output_filename="demo.nc", tool_id="T1")

        with mock.patch.object(self.main, "_build_cam", side_effect=RuntimeError("boom")):
            with mock.patch.object(self.main.logger, "exception") as log_exception:
                with self.assertRaises(self.main.HTTPException) as ctx:
                    asyncio.run(self.main.generate_cam(config))

        self.assertEqual(ctx.exception.status_code, 500)
        self.assertIn("CAM generation failed: boom", ctx.exception.detail)
        log_exception.assert_called_once()

    def test_workspace_path_accepts_regular_file(self):
        resolved = self.main._workspace_path("demo.dxf")
        self.assertTrue(resolved.endswith("demo.dxf"))
        self.assertTrue(resolved.startswith(self.main.WORKSPACE))

    def test_workspace_path_rejects_parent_traversal(self):
        with self.assertRaises(self.main.HTTPException) as ctx:
            self.main._workspace_path("..", "secret.dxf")
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("escapes workspace", ctx.exception.detail)

    def test_gcode_path_rejects_parent_traversal(self):
        with self.assertRaises(self.main.HTTPException) as ctx:
            self.main._gcode_path("..", "secret.nc")
        self.assertEqual(ctx.exception.status_code, 422)
        self.assertIn("escapes workspace", ctx.exception.detail)

    def test_drill_logs_unexpected_engine_failures(self):
        config = self.main.DrillConfig(dxf_filename="demo.dxf", output_filename="demo.nc", tool_id="T1")
        cam = mock.Mock()

        with mock.patch.object(self.main, "_build_cam", return_value=(cam, "demo.dxf")):
            with mock.patch.object(self.main, "_save_gcode", return_value="demo.nc"):
                cam.generar_drill.side_effect = RuntimeError("drill boom")
                with mock.patch.object(self.main.logger, "exception") as log_exception:
                    with self.assertRaises(self.main.HTTPException) as ctx:
                        asyncio.run(self.main.cam_drill(config))

        self.assertEqual(ctx.exception.status_code, 500)
        self.assertIn("CAM drill failed: drill boom", ctx.exception.detail)
        log_exception.assert_called_once()

    def test_readyz_returns_503_when_directories_are_missing(self):
        with mock.patch.object(self.main.os.path, "isdir", side_effect=[False, True]):
            response = asyncio.run(self.main.readyz())

        self.assertEqual(response.status_code, 503)
        self.assertIn(b'"status":"not-ready"', response.body)

    def test_readyz_returns_200_when_directories_are_ready(self):
        with mock.patch.object(self.main.os.path, "isdir", side_effect=[True, True]):
            response = asyncio.run(self.main.readyz())

        self.assertEqual(response.status_code, 200)
        self.assertIn(b'"status":"ready"', response.body)

    def test_profile_config_rejects_negative_pass_depth(self):
        with self.assertRaises(ValidationError):
            self.main.ProfileConfig(
                dxf_filename="demo.dxf",
                output_filename="demo.nc",
                tool_id="T1",
                pass_depth_mm=-1,
            )

    def test_profile_config_rejects_unknown_cut_side(self):
        with self.assertRaises(ValidationError):
            self.main.ProfileConfig(
                dxf_filename="demo.dxf",
                output_filename="demo.nc",
                tool_id="T1",
                cut_side="outer",
            )

    def test_cam_config_rejects_unknown_operation(self):
        with self.assertRaises(ValidationError):
            self.main.CAMConfig(
                dxf_filename="demo.dxf",
                output_filename="demo.nc",
                tool_id="T1",
                operation="engrave",
            )

    def test_profile_config_rejects_invalid_finish_feed_fraction(self):
        with self.assertRaises(ValidationError):
            self.main.ProfileConfig(
                dxf_filename="demo.dxf",
                output_filename="demo.nc",
                tool_id="T1",
                finish_pass_feed_pct=1.5,
            )

    def test_cam_config_rejects_non_positive_feed_override(self):
        with self.assertRaises(ValidationError):
            self.main.CAMConfig(
                dxf_filename="demo.dxf",
                output_filename="demo.nc",
                tool_id="T1",
                feed_rate_override=0,
            )

    def test_profile_config_rejects_negative_safe_z(self):
        with self.assertRaises(ValidationError):
            self.main.ProfileConfig(
                dxf_filename="demo.dxf",
                output_filename="demo.nc",
                tool_id="T1",
                safe_z_mm=-1,
            )

    def test_cam_config_rejects_non_positive_override_tool_number(self):
        with self.assertRaises(ValidationError):
            self.main.CAMConfig(
                dxf_filename="demo.dxf",
                output_filename="demo.nc",
                tool_id="T1",
                override_tool_number=0,
            )

    def test_build_cam_returns_422_when_requested_tool_is_missing(self):
        with mock.patch.object(self.main.os.path, "exists", return_value=True):
            with mock.patch.object(
                self.main.logic,
                "GeneradorCAM",
                side_effect=self.main.logic.CatalogLookupError("Tool not found: T99"),
            ):
                with self.assertRaises(self.main.HTTPException) as ctx:
                    self.main._build_cam("demo.dxf", "T99", None, None, None, None)

        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(ctx.exception.detail, "Tool not found: T99")

    def test_build_cam_returns_503_when_tool_catalog_is_unavailable(self):
        with mock.patch.object(self.main.os.path, "exists", return_value=True):
            with mock.patch.object(
                self.main.logic,
                "GeneradorCAM",
                side_effect=self.main.logic.CatalogUnavailableError("Tool catalog unavailable: /data/tools.json"),
            ):
                with self.assertRaises(self.main.HTTPException) as ctx:
                    self.main._build_cam("demo.dxf", "T1", None, None, None, None)

        self.assertEqual(ctx.exception.status_code, 503)
        self.assertEqual(ctx.exception.detail, "Tool catalog unavailable: /data/tools.json")

    def test_build_cam_returns_422_when_requested_material_is_missing(self):
        with mock.patch.object(self.main.os.path, "exists", return_value=True):
            with mock.patch.object(
                self.main.logic,
                "GeneradorCAM",
                side_effect=self.main.logic.CatalogLookupError("Material not found: steel"),
            ):
                with self.assertRaises(self.main.HTTPException) as ctx:
                    self.main._build_cam("demo.dxf", "T1", "steel", None, None, None)

        self.assertEqual(ctx.exception.status_code, 422)
        self.assertEqual(ctx.exception.detail, "Material not found: steel")

    def test_profile_config_rejects_negative_cut_depth(self):
        with self.assertRaises(ValidationError):
            self.main.ProfileConfig(
                dxf_filename="demo.dxf",
                output_filename="demo.nc",
                tool_id="T1",
                cut_depth_mm=-5,
            )

    def test_drill_config_rejects_non_positive_drill_depth(self):
        with self.assertRaises(ValidationError):
            self.main.DrillConfig(
                dxf_filename="demo.dxf",
                output_filename="demo.nc",
                tool_id="T1",
                drill_depth_mm=0,
            )

    def test_cam_config_rejects_negative_finish_pass_offset(self):
        with self.assertRaises(ValidationError):
            self.main.CAMConfig(
                dxf_filename="demo.dxf",
                output_filename="demo.nc",
                tool_id="T1",
                finish_pass_offset=-0.2,
            )

    def test_profile_config_rejects_negative_material_thickness(self):
        with self.assertRaises(ValidationError):
            self.main.ProfileConfig(
                dxf_filename="demo.dxf",
                output_filename="demo.nc",
                tool_id="T1",
                material_thickness_mm=-3,
            )


if __name__ == "__main__":
    unittest.main()