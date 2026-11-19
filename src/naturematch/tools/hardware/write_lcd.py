"""Test a Grove 16x2 LCD (White on Blue, JHD1802 controller) over I2C.

Writes two lines of text, holds them on screen, then clears the display. The
controller gives no read-back: a "sent" status means the I2C writes were accepted,
not that the text is visible, so check the screen by eye.
Confirm module voltage, wiring, I2C address and Pi 5 driver compatibility before use.
"""
import argparse
import contextlib
import json
import math
import sys
import time
from datetime import UTC, datetime

MODEL = "Grove 16x2 LCD (White on Blue, JHD1802)"
ROWS, COLUMNS = 2, 16
CLEAR_DELAY_S = 0.002  # HD44780-style clear needs about 1.5 ms


def lcd_text(value):
    """Accept at most 16 printable ASCII characters (the character ROM's safe range)."""
    if len(value) > COLUMNS:
        raise argparse.ArgumentTypeError(f"at most {COLUMNS} characters per line")
    if any(not " " <= char <= "~" for char in value):
        raise argparse.ArgumentTypeError("use printable ASCII characters only")
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--address", default=0x3E, type=lambda value: int(value, 0),
        help="7-bit LCD I2C address (default: 0x3E)",
    )
    parser.add_argument("--station-id", default="sensor-test")
    parser.add_argument("--line1", type=lcd_text, default="NatureMatch", help="Top row text")
    parser.add_argument("--line2", type=lcd_text, default="LCD test", help="Bottom row text")
    parser.add_argument("--hold", type=float, default=10.0,
                        help="Seconds to keep the text on screen (>=0, default: 10)")
    parser.add_argument("--keep", action="store_true",
                        help="Leave the text on screen instead of clearing at exit")
    args = parser.parse_args(argv)
    if not 0x03 <= args.address <= 0x77:
        parser.error("--address must be a 7-bit I2C address between 0x03 and 0x77")
    if not math.isfinite(args.hold) or args.hold < 0:
        parser.error("--hold must be finite and not negative")
    if not args.station_id.strip():
        parser.error("--station-id must not be empty")

    try:
        # Keep driver diagnostics off the JSON output stream.
        with contextlib.redirect_stdout(sys.stderr):
            from grove.display.jhd1802 import JHD1802

            lcd = JHD1802(args.address)
    except (Exception, SystemExit) as exc:
        print(f"Cannot initialize LCD at 0x{args.address:02x}: {exc}. Check grove.py "
              "installation, I2C socket/setup and Pi 5 driver compatibility.", file=sys.stderr)
        return 1

    lines = [args.line1, args.line2]

    def show():
        lcd.clear()
        time.sleep(CLEAR_DELAY_S)
        for row, text in enumerate(lines):
            lcd.setCursor(row, 0)
            lcd.write(text.ljust(COLUMNS))  # pad so older characters are overwritten

    def clear():
        lcd.clear()
        time.sleep(CLEAR_DELAY_S)

    def run(action, step, **fields):
        status, error = "sent", None
        try:
            # Seeed's drivers may print and raise SystemExit on I2C errors.
            with contextlib.redirect_stdout(sys.stderr):
                step()
        except (Exception, SystemExit) as exc:
            status, error = "failed", f"LCD {action} failed: {exc}"
        record = {
            "station_id": args.station_id,
            "ts": datetime.now(UTC).isoformat(),
            "model": MODEL,
            "i2c_address": f"0x{args.address:02x}",
            "action": action,
            **fields,
            "status": status,
        }
        if error is not None:
            record["error"] = error
        print(json.dumps(record), flush=True)
        return error is None

    ok, interrupted = True, False
    try:
        ok = run("write", show, lines=lines)
        if ok:
            print("Text sent; check the screen by eye.", file=sys.stderr)
        if args.hold > 0:
            time.sleep(args.hold)
    except KeyboardInterrupt:
        interrupted = True
    if not args.keep:
        try:
            ok = run("clear", clear) and ok
        except KeyboardInterrupt:
            interrupted = True
    if interrupted:
        print("LCD test stopped.", file=sys.stderr)
        return 130
    return int(not ok)


if __name__ == "__main__":
    raise SystemExit(main())
