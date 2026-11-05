"""light sensor driver (Grove). Implement Sensor.read(); verify on the Pi first."""
from naturematch.common.models import Observation

from .base import Sensor


class LightSensor(Sensor):
    name = "light"

    def __init__(self, station_id: str, **hw):
        self.station_id, self.hw = station_id, hw

    def read(self) -> list[Observation]:
        raise NotImplementedError
