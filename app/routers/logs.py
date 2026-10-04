"""Daily log and weigh-in HTTP endpoints."""

from fastapi import APIRouter, HTTPException, Response, status

from app.routers.batches import DatabaseConnection
from app.schemas import (
    DailyLogCreate,
    DailyLogResponse,
    DailyLogUpdate,
    SummaryCountsResponse,
    WeighInCreate,
    WeighInResponse,
)
from app.services.logs import (
    BatchNotFoundError,
    LogNotFoundError,
    WeighInNotFoundError,
    add_daily_log,
    add_weigh_in,
    delete_daily_log,
    delete_weigh_in,
    list_daily_logs,
    list_weigh_ins,
    summary_counts,
    update_daily_log,
)

router = APIRouter(tags=["logs"])


def _raise_http_error(error: ValueError) -> None:
    """Translate service errors into concise API responses."""
    if isinstance(error, (BatchNotFoundError, LogNotFoundError, WeighInNotFoundError)):
        raise HTTPException(status_code=404, detail=str(error)) from error
    raise HTTPException(status_code=422, detail=str(error)) from error


@router.post(
    "/api/batches/{batch_id}/logs",
    response_model=DailyLogResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_daily_log(
    batch_id: int, daily_log: DailyLogCreate, connection: DatabaseConnection
) -> dict[str, object]:
    """Create one daily log for a batch date."""
    try:
        return add_daily_log(connection, batch_id, daily_log)
    except ValueError as error:
        _raise_http_error(error)


@router.get("/api/batches/{batch_id}/logs", response_model=list[DailyLogResponse])
def read_daily_logs(
    batch_id: int, connection: DatabaseConnection
) -> list[dict[str, object]]:
    """List a batch's daily logs."""
    try:
        return list_daily_logs(connection, batch_id)
    except ValueError as error:
        _raise_http_error(error)


@router.patch("/api/logs/{log_id}", response_model=DailyLogResponse)
def edit_daily_log(
    log_id: int, update: DailyLogUpdate, connection: DatabaseConnection
) -> dict[str, object]:
    """Edit one daily log."""
    try:
        return update_daily_log(connection, log_id, update)
    except ValueError as error:
        _raise_http_error(error)


@router.delete("/api/logs/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_daily_log(log_id: int, connection: DatabaseConnection) -> Response:
    """Delete one daily log."""
    try:
        delete_daily_log(connection, log_id)
    except ValueError as error:
        _raise_http_error(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/api/batches/{batch_id}/weigh-ins",
    response_model=WeighInResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_weigh_in(
    batch_id: int, weigh_in: WeighInCreate, connection: DatabaseConnection
) -> dict[str, object]:
    """Create a weigh-in for a batch."""
    try:
        return add_weigh_in(connection, batch_id, weigh_in)
    except ValueError as error:
        _raise_http_error(error)


@router.get("/api/batches/{batch_id}/weigh-ins", response_model=list[WeighInResponse])
def read_weigh_ins(batch_id: int, connection: DatabaseConnection) -> list[dict[str, object]]:
    """List a batch's weigh-ins."""
    try:
        return list_weigh_ins(connection, batch_id)
    except ValueError as error:
        _raise_http_error(error)


@router.delete("/api/weigh-ins/{weigh_in_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_weigh_in(weigh_in_id: int, connection: DatabaseConnection) -> Response:
    """Delete one weigh-in."""
    try:
        delete_weigh_in(connection, weigh_in_id)
    except ValueError as error:
        _raise_http_error(error)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/api/batches/{batch_id}/summary-counts", response_model=SummaryCountsResponse)
def read_summary_counts(batch_id: int, connection: DatabaseConnection) -> dict[str, int]:
    """Return count summary for a batch."""
    try:
        return summary_counts(connection, batch_id)
    except ValueError as error:
        _raise_http_error(error)
