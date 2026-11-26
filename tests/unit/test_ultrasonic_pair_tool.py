"""Software-only checks; both Grove rangers are mocked."""
import contextlib
import importlib.util
import io
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SCRIPT = Path(__file__).parents[2] / "src/naturematch/tools/hardware/read_ultrasonic_pair.py"


class UltrasonicPairToolTests(unittest.TestCase):
    def load_tool(self):
        self.assertTrue(SCRIPT.exists(), "Paired ultrasonic script is missing")
        spec = importlib.util.spec_from_file_location("ultrasonic_pair_tool", SCRIPT)
        tool = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(tool)
        return tool

    def run_tool(self, values, extra=(), broken_pin=None):
        tool = self.load_tool()
        events = []
        readings = {pin: iter(sequence) for pin, sequence in values.items()}

        def ranger(pin):
            if pin == broken_pin:
                raise OSError("GPIO unavailable")

            def read():
                events.append(pin)
                print("driver diagnostic")
                value = next(readings[pin])
                if isinstance(value, BaseException):
                    raise value
                return value

            return SimpleNamespace(_get_distance=read)

        output = io.StringIO()
        with patch.dict("sys.modules", {
            "grove": SimpleNamespace(),
            "grove.grove_ultrasonic_ranger": SimpleNamespace(GroveUltrasonicRanger=ranger),
        }), patch("time.sleep", side_effect=lambda delay: events.append(("sleep", delay))), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            code = tool.main(["--samples", str(len(values[5])), *extra])
        return code, [json.loads(line) for line in output.getvalue().splitlines()], events

    def test_combines_both_sensors_and_spaces_every_trigger(self):
        code, rows, events = self.run_tool({5: [10, 20], 18: [30, 40]})
        self.assertEqual(code, 0)
        self.assertEqual(events, [5, ("sleep", 0.1), 18, ("sleep", 2.0),
                                  5, ("sleep", 0.1), 18])
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["station_id"], "sensor-test")
        for row, expected in zip(rows, [(10, 30), (20, 40)]):
            sensors = row["sensors"]
            self.assertEqual([s["pin_bcm"] for s in sensors], [5, 18])
            self.assertEqual([s["distance"]["value"] for s in sensors], list(expected))
            for sensor in sensors:
                self.assertEqual(sensor["quality"], "experimental")
                self.assertEqual(sensor["distance"]["unit"], "cm")
                self.assertTrue(sensor["ts"].endswith("+00:00"))

    def test_one_failed_sensor_does_not_discard_other_or_reuse_values(self):
        code, rows, _ = self.run_tool({5: [10, None, OSError("no echo")], 18: [20, 30, 40]})
        self.assertEqual(code, 1)
        self.assertEqual([r["sensors"][1]["distance"]["value"] for r in rows], [20, 30, 40])
        for row in rows[1:]:
            self.assertIsNone(row["sensors"][0]["distance"]["value"])
            self.assertEqual(row["sensors"][0]["quality"], "missing")

    def test_invalid_values_are_null(self):
        invalid = [0, 351, float("nan"), float("inf"), True, "bad"]
        code, rows, _ = self.run_tool({5: invalid, 18: [25] * len(invalid)})
        self.assertEqual(code, 1)
        for row in rows:
            self.assertIsNone(row["sensors"][0]["distance"]["value"])
            self.assertEqual(row["sensors"][0]["quality"], "invalid")

    def test_initialization_failure_and_interruption(self):
        code, rows, _ = self.run_tool({5: [10], 18: [20]}, broken_pin=18)
        self.assertEqual((code, rows), (1, []))
        code, rows, _ = self.run_tool({5: [KeyboardInterrupt()], 18: [20]})
        self.assertEqual((code, rows), (130, []))

    def test_argument_validation_and_help_without_hardware(self):
        tool = self.load_tool()
        for args in [["--samples", "0"], ["--interval", "0.01"],
                     ["--interval", "nan"], ["--station-id", " "]]:
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as result:
                    tool.main(args)
                self.assertEqual(result.exception.code, 2)
        with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(SystemExit) as result:
            tool.main(["--help"])
        self.assertEqual(result.exception.code, 0)
