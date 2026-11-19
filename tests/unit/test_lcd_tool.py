"""Software-only checks; the Grove JHD1802 LCD driver is mocked.

These tests do not validate the physical display or what appears on it.
"""
import contextlib
import importlib.util
import io
import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

SCRIPT = Path(__file__).parents[2] / "src/naturematch/tools/hardware/write_lcd.py"


def load_tool():
    spec = importlib.util.spec_from_file_location("lcd_tool", SCRIPT)
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    return tool


class FakeLCD:
    """Records calls and keeps a 2x16 character buffer like the real controller."""

    def __init__(self, address, fail_on=()):
        self.address = address
        self.fail_on = set(fail_on)
        self.calls = []
        self.screen = [[" "] * 16 for _ in range(2)]
        self.cursor = (0, 0)

    def _check(self, name):
        self.calls.append(name)
        if name in self.fail_on:
            print("driver diagnostic")
            raise self.fail_on_error

    def clear(self):
        self._check("clear")
        self.screen = [[" "] * 16 for _ in range(2)]

    def setCursor(self, row, column):
        self._check("setCursor")
        self.cursor = (row, column)

    def write(self, text):
        self._check("write")
        row, column = self.cursor
        for char in text:
            self.screen[row][column] = char
            column += 1
        self.cursor = (row, column)

    def text(self):
        return ["".join(row) for row in self.screen]


class LCDToolTests(unittest.TestCase):
    def run_tool(self, args=(), fail_on=(), error=OSError("bus failed"), sleep=None):
        self.assertTrue(SCRIPT.exists(), "LCD diagnostic script is missing")
        tool = load_tool()
        made = []

        def factory(address):
            lcd = FakeLCD(address, fail_on)
            lcd.fail_on_error = error
            made.append(lcd)
            return lcd

        output, errors = io.StringIO(), io.StringIO()
        driver = SimpleNamespace(JHD1802=factory)
        modules = {"grove": SimpleNamespace(), "grove.display": SimpleNamespace(),
                   "grove.display.jhd1802": driver}
        with patch.dict("sys.modules", modules), patch("time.sleep", side_effect=sleep), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            code = tool.main(list(args))
        rows = [json.loads(line) for line in output.getvalue().splitlines()]
        return code, rows, made[0] if made else None

    def test_default_text_is_written_then_cleared(self):
        # Capture the screen during the hold through the sleep hook.
        holder = {}

        def on_sleep(seconds):
            if seconds == 5:
                holder["screen"] = holder["lcd"].text()

        tool = load_tool()
        output = io.StringIO()

        def factory(address):
            holder["lcd"] = FakeLCD(address)
            return holder["lcd"]

        modules = {"grove": SimpleNamespace(), "grove.display": SimpleNamespace(),
                   "grove.display.jhd1802": SimpleNamespace(JHD1802=factory)}
        with patch.dict("sys.modules", modules), patch("time.sleep", side_effect=on_sleep), \
                contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            code = tool.main(["--hold", "5"])
        rows = [json.loads(line) for line in output.getvalue().splitlines()]

        self.assertEqual(code, 0)
        self.assertEqual(holder["screen"], ["NatureMatch     ", "LCD test        "])
        self.assertEqual(holder["lcd"].text(), [" " * 16] * 2)
        self.assertEqual([r["action"] for r in rows], ["write", "clear"])
        self.assertEqual(rows[0]["lines"], ["NatureMatch", "LCD test"])
        self.assertTrue(all(r["status"] == "sent" for r in rows))
        self.assertEqual(rows[0]["i2c_address"], "0x3e")
        self.assertEqual(rows[0]["station_id"], "sensor-test")
        self.assertTrue(rows[0]["ts"].endswith("+00:00"))
        self.assertEqual(holder["lcd"].address, 0x3E)

    def test_custom_text_address_and_keep(self):
        code, rows, lcd = self.run_tool(
            ["--line1", "Park A: quiet", "--line2", "", "--address", "0x3f", "--keep",
             "--hold", "0"])
        self.assertEqual(code, 0)
        self.assertEqual(lcd.address, 0x3F)
        self.assertEqual(lcd.text(), ["Park A: quiet   ", " " * 16])
        self.assertEqual([r["action"] for r in rows], ["write"])
        self.assertEqual(rows[0]["i2c_address"], "0x3f")

    def test_write_failure_is_reported_and_clear_still_attempted(self):
        for error in (OSError("bus failed"), SystemExit(1)):
            with self.subTest(error=error):
                code, rows, lcd = self.run_tool(fail_on={"write"}, error=error)
                self.assertEqual(code, 1)
                self.assertEqual(rows[0]["status"], "failed")
                self.assertIn("error", rows[0])
                self.assertEqual(rows[1]["action"], "clear")
                self.assertEqual(rows[1]["status"], "sent")

    def test_clear_failure_returns_one(self):
        code, rows, _ = self.run_tool(["--line1", "x"], fail_on={"clear"})
        self.assertEqual(code, 1)
        self.assertEqual([r["status"] for r in rows], ["failed", "failed"])

    def test_invalid_arguments_exit_before_hardware_initialization(self):
        tool = load_tool()
        for args in (["--address", "0x02"], ["--address", "0x78"], ["--address", "zz"],
                     ["--line1", "x" * 17], ["--line2", "café"], ["--line1", "a\tb"],
                     ["--hold", "-1"], ["--hold", "nan"], ["--hold", "inf"],
                     ["--station-id", "  "]):
            with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error:
                    tool.main(args)
                self.assertEqual(error.exception.code, 2)

    def test_sixteen_characters_are_accepted(self):
        code, rows, lcd = self.run_tool(["--line1", "x" * 16, "--keep"])
        self.assertEqual(code, 0)
        self.assertEqual(lcd.text()[0], "x" * 16)

    def test_initialization_failure_returns_one_without_json(self):
        tool = load_tool()

        def broken_lcd(address):
            print("Check if the LCD JHD1802 inserted, then try again")
            raise SystemExit(1)

        output = io.StringIO()
        modules = {"grove": SimpleNamespace(), "grove.display": SimpleNamespace(),
                   "grove.display.jhd1802": SimpleNamespace(JHD1802=broken_lcd)}
        with patch.dict("sys.modules", modules), contextlib.redirect_stdout(output), \
                contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(tool.main([]), 1)
        self.assertEqual(output.getvalue(), "")

    def test_interruption_clears_screen_and_returns_130(self):
        def interrupt(seconds):
            if seconds == 10:
                raise KeyboardInterrupt

        code, rows, lcd = self.run_tool(sleep=interrupt)
        self.assertEqual(code, 130)
        self.assertEqual([r["action"] for r in rows], ["write", "clear"])
        self.assertEqual(lcd.text(), [" " * 16] * 2)


if __name__ == "__main__":
    unittest.main()
