"""Software-only tests; the Seeed hardware boundary is mocked."""
import contextlib
import importlib.util
import io
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SCRIPT = Path(__file__).parents[2] / "src/naturematch/tools/hardware/read_temperature_humidity.py"
spec = importlib.util.spec_from_file_location("sensor_tool", SCRIPT)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


class SensorToolTests(unittest.TestCase):
    def run_tool(self, readings, extra=()):
        attempts = iter(readings)
        sensor = SimpleNamespace(_read=lambda: next(attempts))
        driver = SimpleNamespace(DHT=lambda model, pin: sensor)
        output = io.StringIO()
        with patch.dict("sys.modules", {"seeed_dht": driver}), \
                patch("time.sleep"), contextlib.redirect_stdout(output):
            code = tool.main(["--model", "11", "--pin", "16", "--samples",
                              str(len(readings)), *extra])
        return code, [json.loads(line) for line in output.getvalue().splitlines()]

    def test_reports_units_station_time_and_real_zero(self):
        code, rows = self.run_tool([(55, 0)])
        self.assertEqual(code, 0)
        self.assertEqual(rows[0]["temperature"], {"value": 0, "unit": "C"})
        self.assertEqual(rows[0]["humidity"], {"value": 55, "unit": "%"})
        self.assertEqual(rows[0]["station_id"], "sensor-test")
        self.assertTrue(rows[0]["ts"].endswith("+00:00"))
        self.assertEqual(rows[0]["quality"], "experimental")

    def test_failed_read_does_not_repeat_last_value_and_continues(self):
        code, rows = self.run_tool([(55, 21), (None, "checksum error!"), (56, 22)])
        self.assertEqual(code, 1)
        self.assertEqual(rows[1]["quality"], "missing")
        self.assertIsNone(rows[1]["temperature"]["value"])
        self.assertIsNone(rows[1]["humidity"]["value"])
        self.assertEqual(rows[2]["temperature"]["value"], 22)

    def test_rejects_nonfinite_or_out_of_range_values(self):
        for reading in [(101, 20), (50, float("nan")), (50, -1)]:
            with self.subTest(reading=reading):
                code, rows = self.run_tool([reading])
                self.assertEqual(code, 1)
                self.assertEqual(rows[0]["quality"], "invalid")
                self.assertIsNone(rows[0]["temperature"]["value"])

    def test_rejects_fast_polling_before_loading_hardware(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            tool.main(["--model", "11", "--pin", "16", "--interval", "0.1"])
        self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
