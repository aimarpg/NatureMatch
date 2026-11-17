"""Test an analog Grove Light Sensor V1.2 through the Grove Base Hat ADC.

Reports experimental raw ADC counts, not calibrated illuminance in lux.
Confirm module voltage, wiring and Pi 5 driver compatibility before use.
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
    parser.add_argument("--channel", default=2, type=int, help="Confirmed HAT ADC channel (A2=2)")
    parser.add_argument("--station-id", default="sensor-test")
    parser.add_argument("--samples", type=int, default=10, help="Number of attempts (default: 10)")
    parser.add_argument("--interval", type=float, default=2.0, help="Seconds between attempts (>0)")
    args = parser.parse_args(argv)
    if not 0 <= args.channel <= 7:
        parser.error("--channel must be a HAT ADC channel between 0 and 7")
    if args.samples < 1:
        parser.error("--samples must be positive")
    if not math.isfinite(args.interval) or args.interval <= 0:
        parser.error("--interval must be finite and positive")
    if not args.station_id.strip():
        parser.error("--station-id must not be empty")

    try:
        # Keep driver diagnostics off the JSON output stream.
        with contextlib.redirect_stdout(sys.stderr):
            from grove.adc import ADC

            adc = ADC()
    except (Exception, SystemExit) as exc:
        print(f"Cannot initialize light sensor ADC: {exc}. Check grove.py installation, "
              "Base Hat/I2C setup and Pi 5 driver compatibility.", file=sys.stderr)
        return 1

    failed = False
    try:
        for attempt in range(args.samples):
            quality, error = "experimental", None
            light = None
            try:
                # Seeed's ADC driver prints and raises SystemExit on some I2C errors.
                with contextlib.redirect_stdout(sys.stderr):
                    light = adc.read_raw(args.channel)
                if light is None:
                    quality, error = "missing", "No reading"
                elif (isinstance(light, bool) or not math.isfinite(light)
                      or not 0 <= light <= 4095):
                    quality, error = "invalid", "Nonfinite or out-of-range ADC reading"
            except (TypeError, ValueError) as exc:
                quality, error = "invalid", str(exc)
            except (Exception, SystemExit) as exc:
                quality, error = "missing", f"ADC read failed: {exc}"
            if error is not None:
                failed = True
                light = None
            record = {
                "station_id": args.station_id,
                "ts": datetime.now(UTC).isoformat(),
                "model": "Grove Light Sensor V1.2",
                "channel_adc": args.channel,
                "light": {"value": light, "unit": "ADC counts"},
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
