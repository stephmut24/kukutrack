"""Batch HTTP endpoints."""

import sqlite3
from collections.abc import Generator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.db import get_connection
from app.schemas import BatchCreate, BatchDetailResponse, BatchResponse
from app.services.batches import create_batch, get_batch_detail, list_batches

router = APIRouter(prefix="/api/batches", tags=["batches"])


def get_database_connection() -> Generator[sqlite3.Connection, None, None]:
    """Provide and close one SQLite connection per request."""
    connection = get_connection()
    try:
        yield connection
    finally:
        connection.close()


DatabaseConnection = Annotated[sqlite3.Connection, Depends(get_database_connection)]


@router.post("", response_model=BatchResponse, status_code=status.HTTP_201_CREATED)
def create_new_batch(
    batch: BatchCreate, connection: DatabaseConnection
) -> dict[str, object]:
    """Create a batch and its configured reminder calendar."""
    return create_batch(connection, batch)


@router.get("", response_model=list[BatchResponse])
def read_batches(
    connection: DatabaseConnection,
) -> list[dict[str, object]]:
    """List all batches."""
    return list_batches(connection)


@router.get("/{batch_id}", response_model=BatchDetailResponse)
def read_batch(
    batch_id: int, connection: DatabaseConnection
) -> dict[str, object]:
    """Return a batch and its reminders."""
    batch = get_batch_detail(connection, batch_id)
    if batch is None:
        raise HTTPException(status_code=404, detail="Lot introuvable.")
    return batch
