from fastapi import APIRouter, HTTPException, status

from naturematch.common.models import Observation
from naturematch.service.storage.memory import MemoryObservationStore

router = APIRouter(tags=["observations"])
store = MemoryObservationStore()


@router.post("/observations", status_code=status.HTTP_202_ACCEPTED)
def ingest(observations: list[Observation]) -> dict[str, int]:
    """Accept a batch from a station and make it safe to retry.

    Stations should resend the same serialized observation, including its
    ``id``, when the API or network is unavailable. A repeated identical ID is
    acknowledged as a duplicate rather than counted twice.
    """
    records_in_request: dict[str, Observation] = {}
    for observation in observations:
        request_existing = records_in_request.get(observation.id)
        if request_existing is not None and request_existing != observation:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"observation id is reused with different content: {observation.id}",
            )
        records_in_request[observation.id] = observation

        existing = store.get_by_id(observation.id)
        if existing is not None and existing != observation:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"observation id already exists with different content: {observation.id}",
            )

    result = store.ingest(observations)
    return {"accepted": result.accepted, "duplicates": result.duplicates}


@router.get("/stations/{station_id}/latest")
def latest(station_id: str) -> list[Observation]:
    return store.get_latest(station_id)
