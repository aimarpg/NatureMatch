"""Shared data model. Every module imports from here; nothing else defines records."""
from __future__ import annotations
from datetime import datetime, timezone
from enum import StrEnum
from uuid import uuid4
from pydantic import BaseModel, Field


class Quality(StrEnum):
    OK = "ok"
    STALE = "stale"
    MISSING = "missing"
    EXPERIMENTAL = "experimental"   # gas / UV
    SIMULATED = "simulated"


class Observation(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)  # dedupe on resend
    station_id: str
    metric: str            # temperature | humidity | noise | light | uv | air | occupancy
    value: float | None
    unit: str              # C | % | dB | lx | idx | people
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    quality: Quality = Quality.OK


class CrossingEvent(BaseModel):
    station_id: str
    direction: str         # "in" | "out" | "incomplete"
    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Assessment(BaseModel):
    place_id: str
    activity: str
    suitable: bool
    score: float | None
    reasons: list[str]
    measured_at: datetime | None
