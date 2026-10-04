"""Human-confirmed local assistant HTTP endpoints."""

from fastapi import APIRouter, HTTPException

from app.routers.batches import DatabaseConnection
from app.schemas import (
    AssistantConfirmRequest,
    AssistantConfirmResponse,
    AssistantParseRequest,
    AssistantParseResponse,
)
from app.services.assistant import AssistantBadOutput, AssistantUnavailable, parse_entry
from app.services.assistant_confirmation import (
    AssistantConfirmationError,
    confirm_entry,
    get_log_for_date,
)
from app.services.logs import (
    BatchNotFoundError,
    LogValidationError,
    birds_alive,
    current_utc_date,
)

router = APIRouter(tags=["assistant"])


@router.post("/api/batches/{batch_id}/assistant/parse", response_model=AssistantParseResponse)
def parse_assistant_entry(
    batch_id: int, request: AssistantParseRequest, connection: DatabaseConnection
) -> dict[str, object]:
    """Return an AI proposal and context without making any database changes."""
    today = current_utc_date()
    try:
        proposal = parse_entry(request.text, today)
    except AssistantUnavailable as error:
        raise HTTPException(
            status_code=503,
            detail="Assistant indisponible. La saisie manuelle fonctionne toujours.",
        ) from error
    except AssistantBadOutput as error:
        raise HTTPException(
            status_code=422,
            detail="Je n'ai pas compris. Reformulez avec les nombres et les unités.",
        ) from error

    log_date = proposal.log_date or today
    try:
        return {
            "proposal": proposal,
            "birds_alive": birds_alive(connection, batch_id, log_date),
            "existing_log": get_log_for_date(connection, batch_id, log_date),
        }
    except BatchNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error


@router.post("/api/batches/{batch_id}/assistant/confirm", response_model=AssistantConfirmResponse)
def confirm_assistant_entry(
    batch_id: int, request: AssistantConfirmRequest, connection: DatabaseConnection
) -> dict[str, object | None]:
    """Persist only the proposal that the user has explicitly confirmed."""
    try:
        return confirm_entry(connection, batch_id, request.proposal, request.mode)
    except BatchNotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except (AssistantConfirmationError, LogValidationError) as error:
        raise HTTPException(status_code=422, detail=str(error)) from error
