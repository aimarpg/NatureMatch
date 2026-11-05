import random

from naturematch.common.models import Observation, Quality

from .base import Sensor


class SimulatedSensor(Sensor):
    name = "simulated"

    def __init__(self, station_id: str):
        self.station_id = station_id

    def read(self) -> list[Observation]:
        def mk(m, v, u):
            return Observation(station_id=self.station_id, metric=m, value=v,
                               unit=u, quality=Quality.SIMULATED)
        return [mk("temperature", random.uniform(18, 25), "C"),
                mk("noise", random.uniform(35, 60), "dB"),
                mk("light", random.uniform(500, 15000), "lx")]
