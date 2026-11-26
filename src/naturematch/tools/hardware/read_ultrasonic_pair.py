"""Read Grove Ultrasonic Distance Sensor V2.0 modules on BCM 5 and 18.

Combine sequential experimental distances in one JSON record per pair.
Confirm voltage, wiring and Pi 5 driver compatibility before use.
"""
import argparse
import contextlib
import json
import math
import sys
import time
from datetime import UTC, datetime


def read_sensor(sensor, pin):
    """Make one attempt, keeping quality and observation time per sensor."""
    quality, error = "experimental", None
    distance = None
    try:
        with contextlib.redirect_stdout(sys.stderr):
            # Public get_distance() retries indefinitely on missing echoes.
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
        distance = None
    record = {
        "pin_bcm": pin,
        "ts": datetime.now(UTC).isoformat(),
        "distance": {"value": distance, "unit": "cm"},
        "quality": quality,
    }
    if error is not None:
        record["error"] = error
    return record


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--station-id", default="sensor-test")
    parser.add_argument("--samples", type=int, default=10, help="Number of pairs (default: 10)")
    parser.add_argument("--interval", type=float, default=2.0,
                        help="Seconds after each pair (minimum: 0.1; default: 2)")
    args = parser.parse_args(argv)
    if args.samples < 1:
        parser.error("--samples must be positive")
    if not math.isfinite(args.interval) or args.interval < 0.1:
        parser.error("--interval must be finite and at least 0.1 seconds")
    if not args.station_id.strip():
        parser.error("--station-id must not be empty")

    try:
        with contextlib.redirect_stdout(sys.stderr):
            from grove.grove_ultrasonic_ranger import GroveUltrasonicRanger

            sensors = [(pin, GroveUltrasonicRanger(pin)) for pin in (5, 18)]
    except (Exception, SystemExit) as exc:
        print(f"Cannot initialize ultrasonic sensors: {exc}. Check grove.py installation, "
              "Base Hat wiring and Pi 5 driver compatibility.", file=sys.stderr)
        return 1

    failed = False
    try:
        for attempt in range(args.samples):
            readings = []
            for index, (pin, sensor) in enumerate(sensors):
                if index:
                    # Initial bench-test spacing; acoustic isolation needs physical validation.
                    time.sleep(0.1)
                reading = read_sensor(sensor, pin)
                readings.append(reading)
                if reading["quality"] != "experimental":
                    failed = True
            record = {
                "station_id": args.station_id,
                "ts": datetime.now(UTC).isoformat(),
                "model": "Grove Ultrasonic Distance Sensor V2.0",
                "sensors": readings,
            }
            print(json.dumps(record, allow_nan=False), flush=True)
            if attempt + 1 < args.samples:
                time.sleep(args.interval)
    except KeyboardInterrupt:
        print("Sensor test stopped.", file=sys.stderr)
        return 130
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
