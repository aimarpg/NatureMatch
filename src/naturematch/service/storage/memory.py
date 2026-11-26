"""Small in-process observation store used by the HTTP API scaffold.

The store deliberately keeps ingestion semantics separate from the FastAPI
route. It can be replaced by the InfluxDB-backed implementation without
changing the request contract.
"""

from dataclasses import dataclass

from naturematch.common.models import Observation


@dataclass(frozen=True)
class IngestResult:
    accepted: int
    duplicates: int


class MemoryObservationStore:
    """Idempotent observation store for local development and API tests."""

    def __init__(self) -> None:
        self._by_id: dict[str, Observation] = {}
        self._latest: dict[tuple[str, str], Observation] = {}

    def ingest(self, observations: list[Observation]) -> IngestResult:
        """Store observations, treating an identical resend as a duplicate.

        An observation with an existing ID but different content is rejected by
        the route before this method mutates the store. The timestamp check
        prevents a delayed retry from replacing a newer latest reading.
        """
        accepted = 0
        duplicates = 0
        for observation in observations:
            existing = self._by_id.get(observation.id)
            if existing is not None:
                duplicates += 1
                continue

            self._by_id[observation.id] = observation
            current = self._latest.get((observation.station_id, observation.metric))
            if current is None or observation.ts >= current.ts:
                self._latest[(observation.station_id, observation.metric)] = observation
            accepted += 1

        return IngestResult(accepted=accepted, duplicates=duplicates)

    def get_latest(self, station_id: str) -> list[Observation]:
        return sorted(
            (
                observation
                for (station, _), observation in self._latest.items()
                if station == station_id
            ),
            key=lambda observation: observation.metric,
        )

    def get_by_id(self, observation_id: str) -> Observation | None:
        return self._by_id.get(observation_id)

    def clear(self) -> None:
        """Reset state for tests and local demonstrations."""
        self._by_id.clear()
        self._latest.clear()
