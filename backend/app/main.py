from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from .config import get_settings
from .database import engine
from .routers.api import router
from .services.scheduler import start_scheduler, stop_scheduler


settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if settings.app_env != "test":
        start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title=settings.app_name,
    description="Tamil Nadu Transport and Southern Railway service update tracker.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.include_router(router)


@app.get("/api/health", tags=["system"])
def health_check() -> dict[str, str]:
    """Report API and database readiness without exposing connection details."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return {
            "status": "degraded",
            "service": "tn-transit-tracker-api",
            "database": "unavailable",
        }

    return {
        "status": "ok",
        "service": "tn-transit-tracker-api",
        "database": "connected",
    }


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {"message": "Tamil Nadu Transport & Railway Advisory API", "docs": "/docs"}
