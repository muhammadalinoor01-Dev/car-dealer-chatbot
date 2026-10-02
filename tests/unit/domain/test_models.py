"""Unit tests for the domain models."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from pydantic import ValidationError

from car_dealer_chatbot.domain.models import Car, Dealer, ScheduledCall


def _make_car(**overrides: object) -> Car:
    data = {
        "car_id": "C001",
        "make": "Toyota",
        "model": "Corolla",
        "variant": "1.8 Hybrid Dynamic",
        "year": 2023,
        "body_type": "Hatchback",
        "fuel_type": "Hybrid",
        "transmission": "Automatic",
        "price_eur": 28950,
        "color": "Silver",
        "mileage_km": 18500,
        "dealer_id": "D001",
    }
    data.update(overrides)
    return Car.model_validate(data)


def test_car_full_name_and_price_display() -> None:
    car = _make_car()
    assert car.full_name == "Toyota Corolla 1.8 Hybrid Dynamic"
    assert car.price_display == "€28,950"


def test_car_rejects_negative_price() -> None:
    with pytest.raises(ValidationError):
        _make_car(price_eur=-1)


def test_dealer_location() -> None:
    dealer = Dealer(
        dealer_id="D001",
        name="Utrecht Auto Centre",
        phone="+31 30 123 4567",
        email="sales@utrechtauto.nl",
        address="Europalaan 12",
        city="Utrecht",
        country="Netherlands",
        rating=4.6,
    )
    assert dealer.location == "Utrecht, Netherlands"


def test_scheduled_call_rejects_past_slot() -> None:
    with pytest.raises(ValidationError):
        ScheduledCall(
            dealer_name="Utrecht Auto Centre",
            dealer_phone="+31 30 123 4567",
            car_full_name="Toyota Corolla 1.8 Hybrid Dynamic",
            scheduled_for=datetime(2000, 1, 1, 15, 0),
        )


def test_scheduled_call_slot_display() -> None:
    when = datetime.now() + timedelta(days=2)
    call = ScheduledCall(
        dealer_name="Utrecht Auto Centre",
        dealer_phone="+31 30 123 4567",
        car_full_name="Toyota Corolla 1.8 Hybrid Dynamic",
        scheduled_for=when,
    )
    assert call.slot_display == when.strftime("%A %d %b %Y at %H:%M")
