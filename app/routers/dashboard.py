"""Dashboard HTTP endpoint."""

from fastapi import APIRouter, HTTPException

from app.routers.batches import DatabaseConnection
from app.schemas import DashboardResponse
from app.services.dashboard import get_dashboard
from app.services.logs import BatchNotFoundError

router = APIRouter(tags=["dashboard"])


@router.get("/api/batches/{batch_id}/dashboard", response_model=DashboardResponse)
def read_dashboard(batch_id: int, connection: DatabaseConnection) -> dict[str, object]:
    """Return all local dashboard data for a batch."""
    try:
        return get_dashboard(connection, batch_id)
    except BatchNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
