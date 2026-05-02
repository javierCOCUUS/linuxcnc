import importlib
import json
import sys
import unittest
from pathlib import Path
from shapely.geometry import LineString, Polygon
from unittest import mock


CAM_ENGINE_DIR = Path(__file__).resolve().parents[1]
if str(CAM_ENGINE_DIR) not in sys.path:
    sys.path.insert(0, str(CAM_ENGINE_DIR))


class CamLogicHardeningTests(unittest.TestCase):
    def setUp(self):
        sys.modules.pop("logic", None)
        self.logic = importlib.import_module("logic")

    def tearDown(self):
        sys.modules.pop("logic", None)

    def test_extraer_poligonos_logs_and_skips_bad_path_entities(self):
        bad_entity = mock.Mock()
        good_entity = mock.Mock()
        line_entity = mock.Mock()
        line_entity.dxf.start.x = 0.0
        line_entity.dxf.start.y = 0.0
        line_entity.dxf.end.x = 5.0
        line_entity.dxf.end.y = 0.0

        line_string = LineString([(0.0, 0.0), (5.0, 0.0), (5.0, 5.0), (0.0, 0.0)])
        polygonized = [Polygon([(0.0, 0.0), (5.0, 0.0), (5.0, 5.0), (0.0, 0.0)])]

        cam = object.__new__(self.logic.GeneradorCAM)
        cam.msp = mock.Mock()
        cam.msp.query.side_effect = [[], [], [bad_entity, good_entity]]

        good_path = mock.Mock()
        good_path.flattening.return_value = [mock.Mock(x=0.0, y=0.0), mock.Mock(x=5.0, y=0.0), mock.Mock(x=5.0, y=5.0)]

        with mock.patch("ezdxf.path.make_path", side_effect=[RuntimeError("bad path"), good_path]):
            with mock.patch("shapely.ops.linemerge", return_value=line_string):
                with mock.patch("shapely.ops.polygonize", return_value=polygonized):
                    with mock.patch.object(self.logic.logger, "warning") as warning:
                        polys = cam._extraer_poligonos()

        self.assertEqual(len(polys), 1)
        warning.assert_called_once()

    def test_generar_engrave_logs_and_skips_bad_curve_entities(self):
        line_entity = mock.Mock()
        line_entity.dxf.start.x = 0.0
        line_entity.dxf.start.y = 0.0
        line_entity.dxf.end.x = 10.0
        line_entity.dxf.end.y = 0.0
        bad_curve = mock.Mock()
        good_curve = mock.Mock()

        cam = object.__new__(self.logic.GeneradorCAM)
        cam.feed_z = 300.0
        cam.feed_xy = 800.0
        cam.safe_z = 5.0
        cam.msp = mock.Mock()
        cam.msp.query.side_effect = [[line_entity], [], [bad_curve, good_curve]]
        cam._emit_move = mock.Mock()

        good_path = mock.Mock()
        good_path.flattening.return_value = [mock.Mock(x=0.0, y=0.0), mock.Mock(x=5.0, y=5.0)]

        with mock.patch("ezdxf.path.make_path", side_effect=[RuntimeError("bad curve"), good_path]):
            with mock.patch.object(self.logic.logger, "warning") as warning:
                cam.generar_engrave(-0.5)

        self.assertGreaterEqual(cam._emit_move.call_count, 6)
        warning.assert_called_once()

    def test_cargar_herramienta_logs_and_skips_malformed_matching_entry(self):
        cam = object.__new__(self.logic.GeneradorCAM)
        cam.tool_radius = 1.5
        cam.tool_number = 1
        cam.feed_xy = 800
        cam.feed_z = 300
        cam.rpm = 12000
        cam.step_z = 1.0

        malformed_tool = {
            "id": "t1",
            "display_name": "T1",
            "diameter_mm": "bad",
        }
        valid_tool = {
            "id": "t1",
            "display_name": "T1",
            "diameter_mm": 6,
            "tool_number": 7,
            "feed_recommend_mm_per_min": 900,
            "plunge_recommend_mm_per_min": 250,
            "rpm_recommend": 10000,
            "stepdown_mm": 1.5,
        }

        tools_path = mock.Mock()
        tools_path.exists.return_value = True
        tools_path.open = mock.mock_open(read_data="{}")

        with mock.patch.object(self.logic, "TOOLS_PATH", tools_path):
            with mock.patch.object(self.logic.json, "load", return_value={"tools": [malformed_tool, valid_tool]}):
                with mock.patch.object(self.logic.logger, "warning") as warning:
                    cam._cargar_herramienta("T1")

        self.assertEqual(cam.tool_radius, 3.0)
        self.assertEqual(cam.tool_number, 7)
        self.assertEqual(cam.feed_xy, 900.0)
        warning.assert_called_once()

    def test_cargar_material_logs_and_skips_malformed_matching_entry(self):
        cam = object.__new__(self.logic.GeneradorCAM)
        cam.feed_xy = 800.0
        cam.feed_z = 300.0
        cam.step_z = 1.0
        cam.mat_feed_mult = 1.0
        cam.mat_step_mult = 1.0

        malformed_material = {
            "id": "wood",
            "name": "Wood",
            "feed_multiplier": "bad",
        }
        valid_material = {
            "id": "wood",
            "name": "Wood",
            "feed_multiplier": 1.2,
            "stepdown_multiplier": 0.8,
        }

        materials_path = mock.Mock()
        materials_path.exists.return_value = True
        materials_path.open = mock.mock_open(read_data="{}")

        with mock.patch.object(self.logic, "MATERIALS_PATH", materials_path):
            with mock.patch.object(self.logic.json, "load", return_value={"materials": [malformed_material, valid_material]}):
                with mock.patch.object(self.logic.logger, "warning") as warning:
                    cam._cargar_material("wood")

        self.assertEqual(cam.feed_xy, 960.0)
        self.assertEqual(cam.feed_z, 360.0)
        self.assertEqual(cam.step_z, 0.8)
        warning.assert_called_once()

    def test_cargar_herramienta_logs_and_ignores_invalid_json_catalog(self):
        cam = object.__new__(self.logic.GeneradorCAM)
        cam.tool_radius = 1.5

        tools_path = mock.Mock()
        tools_path.exists.return_value = True
        tools_path.open = mock.mock_open(read_data="{")

        with mock.patch.object(self.logic, "TOOLS_PATH", tools_path):
            with mock.patch.object(self.logic.logger, "warning") as warning:
                with self.assertRaises(self.logic.CatalogUnavailableError):
                    cam._cargar_herramienta("T1")

        self.assertEqual(cam.tool_radius, 1.5)
        warning.assert_called_once()

    def test_cargar_material_logs_and_raises_for_invalid_catalog_root(self):
        cam = object.__new__(self.logic.GeneradorCAM)
        cam.feed_xy = 800.0
        cam.feed_z = 300.0
        cam.step_z = 1.0

        materials_path = mock.Mock()
        materials_path.exists.return_value = True
        materials_path.open = mock.mock_open(read_data="[]")

        with mock.patch.object(self.logic, "MATERIALS_PATH", materials_path):
            with mock.patch.object(self.logic.logger, "warning") as warning:
                with self.assertRaises(self.logic.CatalogUnavailableError):
                    cam._cargar_material("wood")

        self.assertEqual(cam.feed_xy, 800.0)
        self.assertEqual(cam.feed_z, 300.0)
        self.assertEqual(cam.step_z, 1.0)
        warning.assert_called_once()

    def test_cargar_herramienta_raises_when_requested_tool_is_missing(self):
        cam = object.__new__(self.logic.GeneradorCAM)

        tools_path = mock.Mock()
        tools_path.exists.return_value = True
        tools_path.open = mock.mock_open(read_data="{}")

        with mock.patch.object(self.logic, "TOOLS_PATH", tools_path):
            with mock.patch.object(self.logic.json, "load", return_value={"tools": []}):
                with self.assertRaises(self.logic.CatalogLookupError):
                    cam._cargar_herramienta("T99")

    def test_cargar_material_raises_when_requested_material_is_missing(self):
        cam = object.__new__(self.logic.GeneradorCAM)

        materials_path = mock.Mock()
        materials_path.exists.return_value = True
        materials_path.open = mock.mock_open(read_data="{}")

        with mock.patch.object(self.logic, "MATERIALS_PATH", materials_path):
            with mock.patch.object(self.logic.json, "load", return_value={"materials": []}):
                with self.assertRaises(self.logic.CatalogLookupError):
                    cam._cargar_material("steel")


if __name__ == "__main__":
    unittest.main()