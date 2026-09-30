"""Unit tests for the inventory service (search, join, scheduling)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from car_dealer_chatbot.exceptions import DealerNotFoundError
from car_dealer_chatbot.services import InventoryService


def test_search_exact_match_first(service: InventoryService) -> None:
    results = service.search_cars("Toyota Corolla")
    assert results
    assert results[0].car_id == "C001"


def test_search_is_typo_tolerant(service: InventoryService) -> None:
    results = service.search_cars("Toyota Corola")  # missing an 'l'
    assert any(car.car_id == "C001" for car in results)


def test_search_by_attribute(service: InventoryService) -> None:
    results = service.search_cars("electric sedan")
    assert results[0].car_id == "C003"


def test_search_no_match_returns_empty(service: InventoryService) -> None:
    assert service.search_cars("Lamborghini Aventador") == []


def test_search_empty_query_returns_empty(service: InventoryService) -> None:
    assert service.search_cars("   ") == []


def test_get_dealer_success(service: InventoryService) -> None:
    dealer = service.get_dealer("D001")
    assert dealer.name == "Utrecht Auto Centre"


def test_get_dealer_missing_raises(service: InventoryService) -> None:
    with pytest.raises(DealerNotFoundError):
        service.get_dealer("D404")


def test_get_car_with_dealer_join(service: InventoryService) -> None:
    pairing = service.get_car_with_dealer("C001")
    assert pairing is not None
    assert pairing.dealer.dealer_id == "D001"


def test_get_car_with_dealer_unknown_car(service: InventoryService) -> None:
    assert service.get_car_with_dealer("NOPE") is None


def test_get_car_with_dealer_dangling_dealer(service: InventoryService) -> None:
    # C099 references non-existent dealer D404.
    with pytest.raises(DealerNotFoundError):
        service.get_car_with_dealer("C099")


def test_schedule_call_success(service: InventoryService) -> None:
    when = datetime.now() + timedelta(days=1)
    call = service.schedule_call("C001", when)
    assert call.dealer_name == "Utrecht Auto Centre"
    assert call.dealer_phone == "+31 30 123 4567"
    assert call.scheduled_for == when


def test_schedule_call_unknown_car_raises(service: InventoryService) -> None:
    with pytest.raises(ValueError, match="unknown car id"):
        service.schedule_call("NOPE", datetime.now() + timedelta(days=1))
