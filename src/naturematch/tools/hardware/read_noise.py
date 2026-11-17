"""Test an analog Grove sound sensor through the Grove Base Hat ADC.

Reports experimental raw ADC counts, not calibrated sound levels in dB. Audio is
neither recorded nor transmitted. Confirm the module model, voltage, wiring and
Pi 5 driver compatibility before use.
"""
import argparse
import contextlib
import json
import math
import sys
import time
from datetime import UTC, datetime


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--channel", default=0, type=int, help="Confirmed HAT ADC channel (A0=0)")
    parser.add_argument(
        "--address", default=0x04, type=lambda value: int(value, 0),
        help="7-bit HAT ADC I2C address (default: 0x04)",
    )
    parser.add_argument("--station-id", default="sensor-test")
    parser.add_argument("--samples", type=int, default=10, help="Number of attempts (default: 10)")
    parser.add_argument("--interval", type=float, default=2.0, help="Seconds between attempts (>0)")
    args = parser.parse_args(argv)
    if not 0 <= args.channel <= 7:
        parser.error("--channel must be a HAT ADC channel between 0 and 7")
    if not 0x03 <= args.address <= 0x77:
        parser.error("--address must be a 7-bit I2C address between 0x03 and 0x77")
    if args.samples < 1:
        parser.error("--samples must be positive")
    if not math.isfinite(args.interval) or args.interval <= 0:
        parser.error("--interval must be finite and positive")
    if not args.station_id.strip():
        parser.error("--station-id must not be empty")

    try:
        with contextlib.redirect_stdout(sys.stderr):
            from grove.adc import ADC

            adc = ADC(address=args.address)
    except (Exception, SystemExit) as exc:
        print(f"Cannot initialize sound sensor ADC at 0x{args.address:02x}: {exc}. "
              "Check grove.py installation, "
              "Base Hat/I2C setup and Pi 5 driver compatibility.", file=sys.stderr)
        return 1

    failed = False
    try:
        for attempt in range(args.samples):
            quality, error = "experimental", None
            noise = None
            try:
                # Seeed's ADC driver prints and raises SystemExit on some I2C errors.
                with contextlib.redirect_stdout(sys.stderr):
                    noise = adc.read_raw(args.channel)
                if noise is None:
                    quality, error = "missing", "No reading"
                elif (isinstance(noise, bool) or not math.isfinite(noise)
                      or not 0 <= noise <= 4095):
                    quality, error = "invalid", "Nonfinite or out-of-range ADC reading"
            except (TypeError, ValueError) as exc:
                quality, error = "invalid", str(exc)
            except (Exception, SystemExit) as exc:
                quality, error = "missing", f"ADC read failed: {exc}"
            if error is not None:
                failed = True
                noise = None
            record = {
                "station_id": args.station_id,
                "ts": datetime.now(UTC).isoformat(),
                "model": "Grove analog sound sensor (model unconfirmed)",
                "channel_adc": args.channel,
                "i2c_address": f"0x{args.address:02x}",
                "noise": {"value": noise, "unit": "ADC counts"},
                "quality": quality,
            }
            if error is not None:
                record["error"] = error
            print(json.dumps(record, allow_nan=False), flush=True)
            if attempt + 1 < args.samples:
                time.sleep(args.interval)
    except KeyboardInterrupt:
        print("Sensor test stopped.", file=sys.stderr)
        return 130
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
