"""Test one single-SIG Grove Ultrasonic Distance Sensor V2.0 via the Base Hat.

Reports experimental distances in cm, without counting visitors. Confirm module
voltage, wiring and Pi 5 driver compatibility before use. Test sensors separately.
"""
import argparse
import contextlib
import json
import math
import sys
import time
from datetime import UTC, datetime


def main(argv=None):
    # 1. Options follow the other standalone sensor diagnostics.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pin", required=True, type=int, help="Confirmed BCM GPIO, not header pin")
    parser.add_argument("--station-id", default="sensor-test")
    parser.add_argument("--samples", type=int, default=10, help="Number of attempts (default: 10)")
    parser.add_argument("--interval", type=float, default=2.0, help="Seconds between attempts (>0)")
    args = parser.parse_args(argv)
    if not 0 <= args.pin <= 27:
        parser.error("--pin must be a BCM GPIO between 0 and 27")
    if args.samples < 1:
        parser.error("--samples must be positive")
    if not math.isfinite(args.interval) or args.interval <= 0:
        parser.error("--interval must be finite and positive")
    if not args.station_id.strip():
        parser.error("--station-id must not be empty")

    # 2. Import only after parsing, so --help works without Grove hardware.
    try:
        with contextlib.redirect_stdout(sys.stderr):
            from grove.grove_ultrasonic_ranger import GroveUltrasonicRanger

            sensor = GroveUltrasonicRanger(args.pin)
    except (Exception, SystemExit) as exc:
        print(f"Cannot initialize ultrasonic sensor: {exc}. Check grove.py installation, "
              "Base Hat wiring and Pi 5 driver compatibility.", file=sys.stderr)
        return 1

    failed = False
    try:
        for attempt in range(args.samples):
            # 3. Reset every attempt; never substitute an earlier distance.
            quality, error = "experimental", None
            distance = None
            try:
                with contextlib.redirect_stdout(sys.stderr):
                    # Public get_distance() retries indefinitely on missing echoes.
                    # This private method makes one attempt; recheck on driver upgrades.
                    distance = sensor._get_distance()
                if distance is None:
                    quality, error = "missing", "No echo reading (driver timeout)"
                elif (isinstance(distance, bool) or not math.isfinite(distance)
                      or not 2 <= distance <= 350):
                    quality, error = "invalid", "Nonfinite or outside the specified 2-350 cm range"
            except (TypeError, ValueError) as exc:
                quality, error = "invalid", str(exc)
            except (Exception, SystemExit) as exc:
                quality, error = "missing", f"Distance read failed: {exc}"
            if error is not None:
                failed = True
                distance = None

            # 4. Keep stdout machine-readable, matching the other sensor scripts.
            record = {
                "station_id": args.station_id,
                "ts": datetime.now(UTC).isoformat(),
                "model": "Grove Ultrasonic Distance Sensor V2.0",
                "pin_bcm": args.pin,
                "distance": {"value": distance, "unit": "cm"},
                "quality": quality,
            }
            if error is not None:
                record["error"] = error
            print(json.dumps(record, allow_nan=False), flush=True)

            # 5. Pause between attempts, then report overall success/failure.
            if attempt + 1 < args.samples:
                time.sleep(args.interval)
    except KeyboardInterrupt:
        print("Sensor test stopped.", file=sys.stderr)
        return 130
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
