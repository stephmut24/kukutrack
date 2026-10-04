"""Local status and backup HTTP endpoints."""

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks
from fastapi.responses import FileResponse

from app.schemas import SystemStatusResponse
from app.services.backup import create_database_backup
from app.services.system_status import get_system_status

router = APIRouter(tags=["system"])


def _remove_temporary_backup(path: Path) -> None:
    """Remove a generated download after FastAPI has sent it."""
    path.unlink(missing_ok=True)


@router.get("/api/status", response_model=SystemStatusResponse)
def read_system_status() -> dict[str, str]:
    """Report the server, database, and local assistant availability."""
    return get_system_status()


@router.get("/api/backup")
def download_backup(background_tasks: BackgroundTasks) -> FileResponse:
    """Download a consistent local SQLite backup without exposing its temp path."""
    backup_path = create_database_backup()
    filename = f"kukutrack-sauvegarde-{datetime.now(timezone.utc):%Y-%m-%d}.db"
    background_tasks.add_task(_remove_temporary_backup, backup_path)
    return FileResponse(
        backup_path,
        media_type="application/x-sqlite3",
        filename=filename,
        background=background_tasks,
    )
