import argparse
import json
import math
import sys
import time
from datetime import UTC, datetime


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default="11", choices=("11", "22"), help="DHT model")
    parser.add_argument("--pin", default=16, type=int, help="Confirmed BCM GPIO number")
    parser.add_argument("--station-id", default="sensor-test")
    parser.add_argument("--samples", type=int, default=10, help="Number of attempts (default: 10)")
    parser.add_argument("--interval", type=float, default=2.0, help="Seconds between attempts (>=2)")
    args = parser.parse_args(argv)
    if not 0 <= args.pin <= 27:
        parser.error("--pin must be a BCM GPIO number between 0 and 27")
    if args.samples < 1:
        parser.error("--samples must be positive")
    if not math.isfinite(args.interval) or args.interval < 2:
        parser.error("--interval must be finite and at least 2 seconds")
    if not args.station_id.strip():
        parser.error("--station-id must not be empty")

    try:
        import seeed_dht

        sensor = seeed_dht.DHT(args.model, args.pin)
        if not callable(getattr(sensor, "_read", None)):
            raise RuntimeError("Driver lacks single-attempt _read(); check Seeed driver version")
    except Exception as exc:
        print(f"Cannot initialize DHT: {exc}. Check seeed-python-dht/grove.py installation "
              "and Pi 5 driver compatibility.", file=sys.stderr)
        return 1

    failed = False
    try:
        for attempt in range(args.samples):
            quality, error = "experimental", None
            humidity = temperature = None
            try:
                humidity, temperature = sensor._read()
                if humidity is None:
                    error = str(temperature or "No reading")
                    quality = "missing"
                else:
                    low_t, high_t = (0, 50) if args.model == "11" else (-40, 80)
                    low_h, high_h = (20, 90) if args.model == "11" else (0, 100)
                    if not (math.isfinite(humidity) and math.isfinite(temperature)
                            and low_h <= humidity <= high_h
                            and low_t <= temperature <= high_t):
                        quality, error = "invalid", "Nonfinite or out-of-range reading"
            except (TypeError, ValueError) as exc:
                quality, error = "invalid", str(exc)
            except Exception as exc:
                quality, error = "missing", str(exc)
            if error is not None:
                failed = True
                humidity = temperature = None
            record = {
                "station_id": args.station_id,
                "ts": datetime.now(UTC).isoformat(),
                "model": f"DHT{args.model}",
                "pin_bcm": args.pin,
                "temperature": {"value": temperature, "unit": "C"},
                "humidity": {"value": humidity, "unit": "%"},
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
