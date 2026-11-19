# HTTP ingest

The station sends a JSON array of `Observation` records to:

```text
POST /api/v1/observations
Content-Type: application/json
```

Example:

```json
[
  {
    "id": "station-record-0001",
    "station_id": "NM-01",
    "metric": "temperature",
    "value": 21.4,
    "unit": "C",
    "ts": "2026-11-19T12:00:00Z",
    "quality": "ok"
  }
]
```

The API returns `202 Accepted` with counts for `accepted` and `duplicates`.
The station must preserve each record's `id` when retrying a batch. Repeating
the same record is therefore safe; reusing an ID with different content returns
`409 Conflict`. Invalid records are rejected by FastAPI/Pydantic with `422`.

The current scaffold uses an in-process store for exercising the HTTP contract.
It is not durable: restarting the API loses the accepted records. The next
integration step is to replace that store with the InfluxDB writer in
`service/storage/influx.py`, while retaining the same idempotency behavior.

The latest values for one station are available at:

```text
GET /api/v1/stations/{station_id}/latest
```

Export OpenAPI with:

```bash
python -c "from naturematch.service.api.app import app; import json; print(json.dumps(app.openapi()))" > docs/api/openapi.json
```
