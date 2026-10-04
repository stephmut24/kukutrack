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


class DailyLogCreate(BaseModel):
    log_date: date
    dead_count: int = 0
    feed_kg: float = 0
    water_note: str | None = None
    note: str | None = None

    @field_validator("dead_count")
    @classmethod
    def validate_dead_count(cls, value: int) -> int:
        if value < 0:
            raise ValueError("Le nombre de morts ne peut pas être négatif.")
        return value

    @field_validator("feed_kg")
    @classmethod
    def validate_feed_kg(cls, value: float) -> float:
        if value < 0:
            raise ValueError("La quantité d'aliment ne peut pas être négative.")
        return value

    @field_validator("water_note", "note", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            return value.strip() or None
        return value


class DailyLogUpdate(BaseModel):
    log_date: date | None = None
    dead_count: int | None = None
    feed_kg: float | None = None
    water_note: str | None = None
    note: str | None = None

    @field_validator("dead_count")
    @classmethod
    def validate_dead_count(cls, value: int | None) -> int | None:
        if value is not None and value < 0:
            raise ValueError("Le nombre de morts ne peut pas être négatif.")
        return value

    @field_validator("feed_kg")
    @classmethod
    def validate_feed_kg(cls, value: float | None) -> float | None:
        if value is not None and value < 0:
            raise ValueError("La quantité d'aliment ne peut pas être négative.")
        return value

    @field_validator("water_note", "note", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if isinstance(value, str):
            return value.strip() or None
        return value


class DailyLogResponse(BaseModel):
    id: int
    batch_id: int
    log_date: date
    dead_count: int
    feed_kg: float
    water_note: str | None
    note: str | None


class WeighInCreate(BaseModel):
    weigh_date: date
    sample_size: int
    average_weight_g: float

    @field_validator("sample_size")
    @classmethod
    def validate_sample_size(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("La taille de l'échantillon doit être supérieure à zéro.")
        return value

    @field_validator("average_weight_g")
    @classmethod
    def validate_average_weight(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("Le poids moyen doit être supérieur à zéro.")
        return value


class WeighInResponse(BaseModel):
    id: int
    batch_id: int
    weigh_date: date
    sample_size: int
    average_weight_g: float


class SummaryCountsResponse(BaseModel):
    birds_alive: int
    total_dead: int
    day_number: int
