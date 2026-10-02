"""Domain models.

These :mod:`pydantic` models are the single source of truth for the shape of a
dealer, a car, and a scheduled call. Field names map 1:1 to the CSV column
headers, so the repository layer can validate rows simply by constructing a
model. Validation errors here surface bad data early and clearly.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Dealer(BaseModel):
    """A car dealer, as stored in ``dealers.csv``."""

    model_config = ConfigDict(frozen=True)

    dealer_id: str = Field(..., description="Primary key, e.g. 'D001'.")
    name: str
    phone: str
    email: str
    address: str
    city: str
    country: str
    rating: float = Field(..., ge=0.0, le=5.0, description="0-5 star rating.")

    @property
    def location(self) -> str:
        """Human-readable location, e.g. 'Utrecht, Netherlands'."""
        return f"{self.city}, {self.country}"


class Car(BaseModel):
    """A car listing, as stored in ``cars.csv``.

    Each car is linked to exactly one dealer via :attr:`dealer_id` (a foreign key
    into ``dealers.csv``).
    """

    model_config = ConfigDict(frozen=True)

    car_id: str = Field(..., description="Primary key, e.g. 'C001'.")
    make: str
    model: str
    variant: str
    year: int = Field(..., ge=1900, le=2100)
    body_type: str
    fuel_type: str
    transmission: str
    price_eur: int = Field(..., ge=0)
    color: str
    mileage_km: int = Field(..., ge=0)
    dealer_id: str = Field(..., description="Foreign key into dealers.csv.")

    @property
    def full_name(self) -> str:
        """The car's full display name: '<make> <model> <variant>'."""
        return f"{self.make} {self.model} {self.variant}"

    @property
    def price_display(self) -> str:
        """Price formatted with thousands separators, e.g. '€28,950'."""
        return f"€{self.price_eur:,}"


class ScheduledCall(BaseModel):
    """A (mock) scheduled call between the user and a dealer."""

    model_config = ConfigDict(frozen=True)

    dealer_name: str
    dealer_phone: str
    car_full_name: str
    scheduled_for: datetime

    @field_validator("scheduled_for")
    @classmethod
    def _reject_past(cls, value: datetime) -> datetime:
        """Guard against obviously invalid slots in the past."""
        if value < datetime.now(tz=value.tzinfo):
            raise ValueError("The requested slot is in the past.")
        return value

    @property
    def slot_display(self) -> str:
        """Chosen slot formatted for humans, e.g. 'Friday 03 Oct 2025 at 15:00'."""
        return self.scheduled_for.strftime("%A %d %b %Y at %H:%M")
