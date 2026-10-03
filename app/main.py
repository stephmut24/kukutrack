"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.db import initialize_database
from app.routers import batches, reminders


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Prepare local storage before serving requests."""
    initialize_database()
    yield


app = FastAPI(title="KukuTrack", lifespan=lifespan)
app.include_router(batches.router)
app.include_router(reminders.router)


@app.get("/api/health")
def health_check() -> dict[str, str]:
    """Return a small liveness response for local checks."""
    return {"status": "ok"}


app.mount("/", StaticFiles(directory="static", html=True), name="static")
