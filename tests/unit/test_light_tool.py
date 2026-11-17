"""Software-only checks; Grove ADC hardware is mocked."""
import contextlib
import importlib.util
import io
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SCRIPT = Path(__file__).parents[2] / "src/naturematch/tools/hardware/read_light.py"


class LightToolTests(unittest.TestCase):
    def run_tool(self, readings, extra=()):
        self.assertTrue(SCRIPT.exists(), "Light diagnostic script is missing")
        spec = importlib.util.spec_from_file_location("light_tool", SCRIPT)
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        values = iter(readings)

        def read_raw(channel):
            if channel != 2:
                raise AssertionError("Expected A2")
            value = next(values)
            if isinstance(value, BaseException):
                print("driver diagnostic")
                raise value
            return value

        output = io.StringIO()
        errors = io.StringIO()
        driver = SimpleNamespace(ADC=lambda: SimpleNamespace(read_raw=read_raw))
        with patch.dict("sys.modules", {"grove": SimpleNamespace(), "grove.adc": driver}), \
                patch("time.sleep"), contextlib.redirect_stdout(output), \
                contextlib.redirect_stderr(errors):
            code = tool.main(["--samples", str(len(readings)), *extra])
        return code, [json.loads(line) for line in output.getvalue().splitlines()]

    def test_zero_and_full_scale_are_experimental_not_missing(self):
        code, rows = self.run_tool([0, 4095])
        self.assertEqual(code, 0)
        self.assertEqual([r["light"]["value"] for r in rows], [0, 4095])
        self.assertEqual(rows[0]["light"]["unit"], "ADC counts")
        self.assertEqual(rows[0]["quality"], "experimental")
        self.assertEqual(rows[0]["station_id"], "sensor-test")
        self.assertTrue(rows[0]["ts"].endswith("+00:00"))

    def test_failures_never_reuse_values_and_sampling_continues(self):
        code, rows = self.run_tool([100, OSError("bus failed"), SystemExit(2), None, 200])
        self.assertEqual(code, 1)
        for row in rows[1:4]:
            self.assertEqual(row["quality"], "missing")
            self.assertIsNone(row["light"]["value"])
            self.assertIn("error", row)
        self.assertEqual(rows[-1]["light"]["value"], 200)

    def test_invalid_values_are_not_emitted(self):
        for value in [-1, 4096, float("nan"), float("inf"), "bad", True]:
            with self.subTest(value=value):
                code, rows = self.run_tool([value])
                self.assertEqual(code, 1)
                self.assertEqual(rows[0]["quality"], "invalid")
                self.assertIsNone(rows[0]["light"]["value"])

    def test_invalid_arguments_exit_before_hardware_initialization(self):
        spec = importlib.util.spec_from_file_location("light_tool", SCRIPT)
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        for args in (["--channel", "8"], ["--channel", "-1"],
                     ["--samples", "0"], ["--interval", "nan"],
                     ["--interval", "0"], ["--station-id", "  "]):
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    tool.main(args)
                self.assertEqual(error.exception.code, 2)

    def test_initialization_failure_returns_one_without_json(self):
        spec = importlib.util.spec_from_file_location("light_tool", SCRIPT)
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)

        def broken_adc():
            print("driver diagnostic")
            raise SystemExit(2)

        output = io.StringIO()
        driver = SimpleNamespace(ADC=broken_adc)
        with patch.dict("sys.modules", {"grove": SimpleNamespace(), "grove.adc": driver}), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(tool.main([]), 1)
        self.assertEqual(output.getvalue(), "")

    def test_interruption_returns_130(self):
        code, rows = self.run_tool([KeyboardInterrupt()])
        self.assertEqual(code, 130)
        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
