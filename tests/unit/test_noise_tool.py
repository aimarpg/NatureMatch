"""Software-only tests; Grove ADC hardware is mocked."""
import contextlib
import importlib.util
import io
import json
import sys
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import patch

SCRIPT = Path(__file__).parents[2] / "src/naturematch/tools/hardware/read_noise.py"
spec = importlib.util.spec_from_file_location("noise_tool", SCRIPT)
tool = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)


class NoiseToolTests(unittest.TestCase):
    def run_tool(self, readings, extra=()):
        attempts = iter(readings)

        def read_raw(channel):
            reading = next(attempts)
            if isinstance(reading, Exception):
                raise reading
            return reading

        adc = SimpleNamespace(read_raw=read_raw)
        grove = ModuleType("grove")
        grove.__path__ = []
        grove_adc = ModuleType("grove.adc")
        adc_factory = unittest.mock.Mock(return_value=adc)
        grove_adc.ADC = adc_factory
        output = io.StringIO()
        with patch.dict(sys.modules, {"grove": grove, "grove.adc": grove_adc}), \
                patch("time.sleep"), contextlib.redirect_stdout(output):
            code = tool.main(["--samples", str(len(readings)), *extra])
        return code, [json.loads(line) for line in output.getvalue().splitlines()], adc_factory

    def test_reports_experimental_raw_noise_counts_and_metadata(self):
        code, rows, adc_factory = self.run_tool([0])
        self.assertEqual(code, 0)
        self.assertEqual(rows[0]["noise"], {"value": 0, "unit": "ADC counts"})
        self.assertEqual(rows[0]["station_id"], "sensor-test")
        self.assertEqual(rows[0]["channel_adc"], 0)
        self.assertEqual(rows[0]["i2c_address"], "0x04")
        adc_factory.assert_called_once_with(address=0x04)
        self.assertTrue(rows[0]["ts"].endswith("+00:00"))
        self.assertEqual(rows[0]["quality"], "experimental")
        self.assertIn("model unconfirmed", rows[0]["model"])

    def test_failed_read_is_null_and_sampling_continues(self):
        code, rows, _ = self.run_tool([1200, RuntimeError("I2C unavailable"), 1300])
        self.assertEqual(code, 1)
        self.assertEqual(rows[1]["quality"], "missing")
        self.assertIsNone(rows[1]["noise"]["value"])
        self.assertEqual(rows[2]["noise"]["value"], 1300)

    def test_rejects_nonfinite_or_out_of_range_adc_values(self):
        for reading in [True, float("nan"), -1, 4096]:
            with self.subTest(reading=reading):
                code, rows, _ = self.run_tool([reading])
                self.assertEqual(code, 1)
                self.assertEqual(rows[0]["quality"], "invalid")
                self.assertIsNone(rows[0]["noise"]["value"])

    def test_uses_requested_adc_channel(self):
        attempts = iter([1234])
        read_raw = unittest.mock.Mock(side_effect=lambda channel: next(attempts))
        grove = ModuleType("grove")
        grove.__path__ = []
        grove_adc = ModuleType("grove.adc")
        adc_factory = unittest.mock.Mock(return_value=SimpleNamespace(read_raw=read_raw))
        grove_adc.ADC = adc_factory
        output = io.StringIO()
        with patch.dict(sys.modules, {"grove": grove, "grove.adc": grove_adc}), \
                contextlib.redirect_stdout(output):
            code = tool.main(["--channel", "3", "--samples", "1"])
        self.assertEqual(code, 0)
        adc_factory.assert_called_once_with(address=0x04)
        read_raw.assert_called_once_with(3)

    def test_uses_requested_hex_i2c_address(self):
        code, rows, adc_factory = self.run_tool([1234], ["--address", "0x08"])
        self.assertEqual(code, 0)
        self.assertEqual(rows[0]["i2c_address"], "0x08")
        adc_factory.assert_called_once_with(address=0x08)

    def test_rejects_invalid_channel_before_loading_hardware(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            tool.main(["--channel", "8"])
        self.assertEqual(error.exception.code, 2)

    def test_rejects_reserved_i2c_address_before_loading_hardware(self):
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            tool.main(["--address", "0x02"])
        self.assertEqual(error.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
