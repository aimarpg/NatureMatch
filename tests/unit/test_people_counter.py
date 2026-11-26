"""Replay synthetic pair records through the standalone entrance counter."""

import contextlib
import io
import json
import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from naturematch.tools.count_people import main

CLEAR = (100, 120)
A = (50, 120)
BOTH = (50, 60)
B = (100, 60)


class PeopleCounterTests(unittest.TestCase):
    def replay(self, pairs, *, interval=200, initial=0, times=None):
        start = datetime(2026, 1, 1, tzinfo=UTC)
        records = []
        for index, (a, b) in enumerate(pairs):
            elapsed = times[index] if times is not None else index * interval
            ts = (start + timedelta(milliseconds=elapsed)).isoformat()
            records.append(json.dumps({
                "station_id": "simulated-test",
                "ts": ts,
                "sensors": [
                    {"pin_bcm": pin, "ts": ts, "distance": {"value": value, "unit": "cm"},
                     "quality": "missing" if value is None else "experimental"}
                    for pin, value in [(5, a), (18, b)]
                ],
            }))
        output = io.StringIO()
        with patch("sys.stdin", io.StringIO("\n".join(records))), contextlib.redirect_stdout(output):
            code = main([
                "--initial-count", str(initial),
                "--a-enter-cm", "65", "--a-clear-cm", "75",
                "--b-enter-cm", "80", "--b-clear-cm", "90",
            ])
        return code, [json.loads(line) for line in output.getvalue().splitlines()]

    def test_counts_full_crossings_at_different_speeds(self):
        for interval in (200, 450):
            with self.subTest(interval=interval):
                code, rows = self.replay(
                    [CLEAR, A, A, BOTH, B, B, CLEAR, CLEAR, B, BOTH, A, CLEAR],
                    interval=interval, initial=4,
                )
                self.assertEqual(code, 0)
                self.assertEqual(
                    [r["crossing"] for r in rows if r["crossing"] in ("in", "out")],
                    ["in", "out"],
                )
                self.assertEqual([r["occupancy"]["value"] for r in rows[5:8]], [4, 5, 5])
                self.assertEqual(rows[-1]["occupancy"]["value"], 4)
                self.assertEqual(rows[-1]["occupancy"]["quality"], "experimental")

    def test_reversal_partial_crossing_and_ambiguous_start_are_ignored(self):
        code, rows = self.replay(
            [B, BOTH, A, CLEAR, A, BOTH, B, BOTH, A, CLEAR, A, CLEAR, BOTH, B, CLEAR]
        )
        self.assertEqual(code, 0)
        self.assertTrue(all(r["occupancy"]["value"] == 0 for r in rows))
        self.assertIn("incomplete", [r["crossing"] for r in rows])
        self.assertFalse(any(r["crossing"] in ("in", "out") for r in rows))

    def test_long_pause_discards_crossing_and_resynchronizes_on_clear(self):
        code, rows = self.replay(
            [CLEAR, A, BOTH, *([B] * 6), CLEAR, A, BOTH, B, CLEAR], interval=450
        )
        self.assertEqual(code, 0)
        self.assertEqual(rows[9]["occupancy"]["value"], 0)
        self.assertEqual(rows[-1]["crossing"], "in")

    def test_distances_between_thresholds_keep_previous_state(self):
        _, rows = self.replay([CLEAR, A, (70, 60), (100, 85), CLEAR])
        self.assertEqual([r["zone"] for r in rows], ["clear", "a", "both", "b", "clear"])
        self.assertEqual(rows[-1]["crossing"], "in")

    def test_missing_or_out_of_range_echo_is_unknown_and_count_stays_stale(self):
        for distance in (None, 0, 351):
            with self.subTest(distance=distance):
                code, rows = self.replay([CLEAR, A, (distance, 60), B, CLEAR])
                self.assertEqual(code, 1)
                self.assertEqual(rows[2]["zone"], "unknown")
                self.assertEqual(rows[-1]["occupancy"]["quality"], "stale")
                self.assertEqual(rows[-1]["occupancy"]["value"], 0)

    def test_sampling_gap_discards_crossing_and_marks_count_stale(self):
        code, rows = self.replay(
            [CLEAR, A, BOTH, B, CLEAR], times=[0, 200, 1000, 1200, 1400]
        )
        self.assertEqual(code, 1)
        self.assertIsNone(rows[-1]["crossing"])
        self.assertEqual(rows[-1]["occupancy"]["quality"], "stale")
        self.assertEqual(rows[-1]["occupancy"]["value"], 0)

    def test_exit_from_zero_flags_reconciliation(self):
        code, rows = self.replay([CLEAR, B, BOTH, A, CLEAR])
        self.assertEqual(code, 1)
        self.assertEqual(rows[-1]["crossing"], "out")
        self.assertEqual(rows[-1]["occupancy"], {"value": 0, "quality": "stale", "unit": "people"})
