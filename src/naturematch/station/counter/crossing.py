"""Two-beam crossing state machine. Pure logic: no GPIO, fully unit-testable.

Beam A is outside, beam B inside.  A then B = entry.  B then A = exit.
Anything else (timeout, same beam twice) = incomplete / ignored, count unchanged.
"""
from dataclasses import dataclass


@dataclass
class CrossingDetector:
    max_gap_ms: int = 1500
    _first: str | None = None
    _t0: int = 0

    def on_break(self, beam: str, t_ms: int) -> str | None:
        """Feed a beam interruption. Returns 'in' | 'out' | 'incomplete' | None."""
        if self._first and t_ms - self._t0 > self.max_gap_ms:
            self._first = None
            return "incomplete"
        if self._first is None:
            self._first, self._t0 = beam, t_ms
            return None
        if beam == self._first:          # reversal / retrigger
            self._t0 = t_ms
            return None
        direction = "in" if self._first == "A" else "out"
        self._first = None
        return direction


class ZoneCrossingDetector:
    """Confirm a crossing after traversing two overlapping zones and clearing both."""

    _paths = {
        "a": ("a", "both", "b", "clear"),
        "b": ("b", "both", "a", "clear"),
    }

    def __init__(self, max_crossing_ms: int):
        self.max_crossing_ms = max_crossing_ms
        self._previous = "unknown"
        self._steps: list[str] = []
        self._started_ms = 0

    def on_zones(self, zone: str, t_ms: int) -> str | None:
        previous, self._previous = self._previous, zone
        if not self._steps:
            if previous == "clear" and zone in self._paths:
                self._steps.append(zone)
                self._started_ms = t_ms
            elif previous == "clear" and zone == "both":
                return "incomplete"
            return None

        if t_ms - self._started_ms > self.max_crossing_ms or zone == "unknown":
            self._steps.clear()
            return "incomplete"
        if zone == previous:
            return None

        first = self._steps[0]
        path = self._paths[first]
        if zone != path[len(self._steps)]:
            self._steps.clear()
            return "incomplete"
        if zone == "clear":
            self._steps.clear()
            return "in" if first == "a" else "out"
        self._steps.append(zone)
        return None
