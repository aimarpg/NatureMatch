from fastapi import APIRouter

from naturematch.common.models import Observation

router = APIRouter(tags=["observations"])
_latest: dict[tuple[str, str], Observation] = {}   # replace with storage layer


@router.post("/observations", status_code=202)
def ingest(obs: list[Observation]) -> dict:
    for o in obs:
        _latest[(o.station_id, o.metric)] = o   # TODO: dedupe by o.id, write to InfluxDB
    return {"accepted": len(obs)}


@router.get("/stations/{station_id}/latest")
def latest(station_id: str) -> list[Observation]:
    return [o for (s, _), o in _latest.items() if s == station_id]
