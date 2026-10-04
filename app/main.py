"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.db import initialize_database
from app.routers import alerts, assistant, batches, dashboard, logs, reminders, status


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Prepare local storage before serving requests."""
    initialize_database()
    yield


app = FastAPI(title="KukuTrack", lifespan=lifespan)
app.include_router(batches.router)
app.include_router(assistant.router)
app.include_router(alerts.router)
app.include_router(dashboard.router)
app.include_router(logs.router)
app.include_router(reminders.router)
app.include_router(status.router)


@app.get("/", include_in_schema=False)
def home_page() -> FileResponse:
    """Serve the general home screen."""
    return FileResponse("static/home.html")


@app.get("/lots", include_in_schema=False)
def batches_page() -> FileResponse:
    """Serve the batch list and creation screen."""
    return FileResponse("static/index.html")


@app.get("/api/health")
def health_check() -> dict[str, str]:
    """Return a small liveness response for local checks."""
    return {"status": "ok"}


app.mount("/", StaticFiles(directory="static", html=True), name="static")
