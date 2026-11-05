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
