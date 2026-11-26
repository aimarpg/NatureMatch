"""Software-only diagnostic checks; ultrasonic hardware is mocked."""
import contextlib
import importlib.util
import io
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SCRIPT = Path(__file__).parents[2] / "src/naturematch/tools/hardware/read_ultrasonic.py"


class UltrasonicToolTests(unittest.TestCase):
    def load_tool(self):
        self.assertTrue(SCRIPT.exists(), "Ultrasonic diagnostic script is missing")
        spec = importlib.util.spec_from_file_location("ultrasonic_tool", SCRIPT)
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        return tool

    def run_tool(self, readings, extra=(), init_error=None):
        tool = self.load_tool()
        values = iter(readings)

        def read_distance():
            print("driver diagnostic")
            value = next(values)
            if isinstance(value, BaseException):
                raise value
            return value

        def ranger(pin):
            if init_error is not None:
                raise init_error
            if pin != 5:
                raise AssertionError("Expected BCM 5")
            return SimpleNamespace(_get_distance=read_distance)

        output, errors = io.StringIO(), io.StringIO()
        driver = SimpleNamespace(GroveUltrasonicRanger=ranger)
        with patch.dict("sys.modules", {
            "grove": SimpleNamespace(), "grove.grove_ultrasonic_ranger": driver,
        }), patch("time.sleep"), contextlib.redirect_stdout(output), \
                contextlib.redirect_stderr(errors):
            code = tool.main(["--pin", "5", "--samples", str(max(1, len(readings))), *extra])
        return code, [json.loads(line) for line in output.getvalue().splitlines()]

    def test_distance_records_have_identity_time_unit_and_experimental_quality(self):
        code, rows = self.run_tool([2, 42.5, 350], ["--station-id", "entrance-a"])
        self.assertEqual(code, 0)
        self.assertEqual([r["distance"]["value"] for r in rows], [2, 42.5, 350])
        for row in rows:
            self.assertEqual(row["distance"]["unit"], "cm")
            self.assertEqual(row["quality"], "experimental")
            self.assertEqual(row["station_id"], "entrance-a")
            self.assertEqual(row["pin_bcm"], 5)
            self.assertTrue(row["ts"].endswith("+00:00"))

    def test_no_echo_and_read_errors_do_not_reuse_previous_values(self):
        code, rows = self.run_tool([25, None, OSError("GPIO failed"), SystemExit(2), 30])
        self.assertEqual(code, 1)
        for row in rows[1:4]:
            self.assertEqual(row["quality"], "missing")
            self.assertIsNone(row["distance"]["value"])
            self.assertIn("error", row)
        self.assertEqual(rows[-1]["distance"]["value"], 30)

    def test_invalid_distances_are_null(self):
        for value in [0, -1, 1.9, 351, float("nan"), float("inf"), "bad", True]:
            with self.subTest(value=value):
                code, rows = self.run_tool([value])
                self.assertEqual(code, 1)
                self.assertEqual(rows[0]["quality"], "invalid")
                self.assertIsNone(rows[0]["distance"]["value"])

    def test_invalid_arguments_and_help_need_no_driver(self):
        tool = self.load_tool()
        for args in [[], ["--pin", "-1"], ["--pin", "28"],
                     ["--pin", "5", "--samples", "0"],
                     ["--pin", "5", "--interval", "nan"],
                     ["--pin", "5", "--interval", "0"],
                     ["--pin", "5", "--station-id", "  "]]:
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    tool.main(args)
                self.assertEqual(error.exception.code, 2)
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as error:
            tool.main(["--help"])
        self.assertEqual(error.exception.code, 0)

    def test_initialization_failure_emits_no_measurements(self):
        code, rows = self.run_tool([], init_error=OSError("GPIO unavailable"))
        self.assertEqual(code, 1)
        self.assertEqual(rows, [])

    def test_ctrl_c_returns_130(self):
        code, rows = self.run_tool([KeyboardInterrupt()])
        self.assertEqual(code, 130)
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
