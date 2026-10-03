"""Request and response models for the HTTP API."""

from datetime import date
from typing import Literal

from pydantic import BaseModel, field_validator

ReminderCategory = Literal[
    "heating", "vaccine", "vitamin", "protein", "booster", "other"
]


class BatchCreate(BaseModel):
    name: str
    start_date: date
    initial_count: int
    target_weight_g: int = 3000

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        cleaned_value = value.strip()
        if not cleaned_value:
            raise ValueError("Le nom du lot est obligatoire.")
        return cleaned_value

    @field_validator("initial_count")
    @classmethod
    def validate_initial_count(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Le nombre initial doit être supérieur à zéro.")
        return value

    @field_validator("target_weight_g")
    @classmethod
    def validate_target_weight(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Le poids cible doit être supérieur à zéro.")
        return value


class BatchResponse(BaseModel):
    id: int
    name: str
    start_date: date
    initial_count: int
    target_weight_g: int
    status: Literal["active", "closed"]
    created_at: str


class ReminderResponse(BaseModel):
    id: int
    batch_id: int
    due_date: date
    category: ReminderCategory
    title: str
    details: str | None
    done: bool
    done_at: str | None


class BatchDetailResponse(BatchResponse):
    reminders: list[ReminderResponse]


class ReminderUpdate(BaseModel):
    due_date: date | None = None
    done: bool | None = None
