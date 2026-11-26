"""Count crossings from paired Grove ultrasonic JSON lines on stdin."""

import argparse
import json
import sys
from datetime import datetime

from naturematch.station.counter.crossing import ZoneCrossingDetector
from naturematch.station.counter.occupancy import Occupancy

ZONE_NAMES = {(False, False): "clear", (True, False): "a",
              (True, True): "both", (False, True): "b"}


def _occupied(sensor, previous, enter_cm, clear_cm):
    value = sensor["distance"]["value"]
    if (sensor["quality"] != "experimental" or sensor["distance"]["unit"] != "cm"
            or type(value) not in (int, float) or not 2 <= value <= 350):
        return None
    if value <= enter_cm:
        return True
    if value >= clear_cm:
        return False
    return previous


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--initial-count", required=True, type=int, help="Known starting headcount")
    for zone in ("a", "b"):
        parser.add_argument(f"--{zone}-enter-cm", required=True, type=float,
                            help=f"At or below this distance, zone {zone.upper()} is occupied")
        parser.add_argument(f"--{zone}-clear-cm", required=True, type=float,
                            help=f"At or above this distance, zone {zone.upper()} is clear")
    parser.add_argument("--max-crossing-ms", default=2500, type=int,
                        help="Time from first occupied zone to both clear (default: 2500)")
    parser.add_argument("--max-sample-gap-ms", default=500, type=int,
                        help="Maximum time between pair records (default: 500)")
    args = parser.parse_args(argv)
    if args.initial_count < 0:
        parser.error("--initial-count must be nonnegative")
    if not (2 <= args.a_enter_cm < args.a_clear_cm <= 350
            and 2 <= args.b_enter_cm < args.b_clear_cm <= 350):
        parser.error("each zone must satisfy 2 <= enter-cm < clear-cm <= 350")
    if args.max_crossing_ms <= 0 or args.max_sample_gap_ms <= 0:
        parser.error("timing limits must be positive")

    detector = ZoneCrossingDetector(args.max_crossing_ms)
    occupancy = Occupancy(args.initial_count)
    station_id, previous_ms = None, None
    a, b = None, None
    stale = False
    try:
        for line_number, line in enumerate(sys.stdin, 1):
            try:
                record = json.loads(line)
                ts = datetime.fromisoformat(record["ts"])
                if ts.utcoffset() is None:
                    raise ValueError("expected timestamp with an offset")
                now_ms = int(ts.timestamp() * 1000)
                current_station = record["station_id"]
                if not isinstance(current_station, str) or not current_station.strip():
                    raise ValueError("expected a station ID")
                if station_id is not None and station_id != current_station:
                    raise ValueError("expected records from one station")
                station_id = current_station
                outer, inner = record["sensors"]
                if (outer["pin_bcm"], inner["pin_bcm"]) != (5, 18):
                    raise ValueError("expected sensors on BCM 5 (A) and BCM 18 (B), in that order")

                gap = (previous_ms is not None
                       and not 0 < now_ms - previous_ms <= args.max_sample_gap_ms)
                if gap:
                    detector.on_zones("unknown", now_ms)
                    a, b = None, None
                previous_ms = now_ms
                a = _occupied(outer, a, args.a_enter_cm, args.a_clear_cm)
                b = _occupied(inner, b, args.b_enter_cm, args.b_clear_cm)
            except (KeyError, TypeError, ValueError, OverflowError) as exc:
                print(f"Invalid paired record on line {line_number}: {exc}", file=sys.stderr)
                return 1

            zone = ZONE_NAMES.get((a, b), "unknown")
            crossing = detector.on_zones(zone, now_ms)
            underflow = crossing == "out" and occupancy.count == 0
            stale = stale or gap or zone == "unknown" or underflow
            record["zone"] = zone
            record["crossing"] = crossing
            record["occupancy"] = {
                "value": occupancy.apply(crossing) if crossing in ("in", "out") else occupancy.count,
                "unit": "people",
                "quality": "stale" if stale else "experimental",
            }
            print(json.dumps(record, allow_nan=False), flush=True)
    except KeyboardInterrupt:
        return 130
    if station_id is None:
        print("No paired readings received.", file=sys.stderr)
        return 1
    return int(stale)


if __name__ == "__main__":
    raise SystemExit(main())
