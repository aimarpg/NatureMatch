import pytest
pytestmark = pytest.mark.hardware   # run on the Pi: pytest -m hardware


def test_placeholder():
    pytest.skip("wire IR pairs, then compare against 20 manual trials")
