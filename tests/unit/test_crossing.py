from naturematch.station.counter.crossing import CrossingDetector
from naturematch.station.counter.occupancy import Occupancy


def test_entry():
    d = CrossingDetector()
    assert d.on_break("A", 0) is None
    assert d.on_break("B", 300) == "in"


def test_exit():
    d = CrossingDetector()
    d.on_break("B", 0)
    assert d.on_break("A", 300) == "out"


def test_pause_is_incomplete():
    d = CrossingDetector(max_gap_ms=1000)
    d.on_break("A", 0)
    assert d.on_break("B", 5000) == "incomplete"


def test_reversal_no_count():
    d = CrossingDetector()
    d.on_break("A", 0)
    assert d.on_break("A", 200) is None


def test_occupancy_never_negative():
    assert Occupancy(0).apply("out") == 0
