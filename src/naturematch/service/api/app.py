from fastapi import FastAPI
from .routes import health, observations, assessments

app = FastAPI(title="NatureMatch API", version="0.1.0")  # OpenAPI at /docs, /openapi.json
app.include_router(health.router)
app.include_router(observations.router, prefix="/api/v1")
app.include_router(assessments.router, prefix="/api/v1")
