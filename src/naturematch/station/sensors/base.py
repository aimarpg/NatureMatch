from abc import ABC, abstractmethod
from naturematch.common.models import Observation


class Sensor(ABC):
    """One sensor = one class. Hardware access stays inside implementations."""
    name: str

    @abstractmethod
    def read(self) -> list[Observation]: ...
