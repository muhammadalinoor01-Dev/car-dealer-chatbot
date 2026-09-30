"""Unit tests for the CSV repository layer."""

from __future__ import annotations

from pathlib import Path

import pytest

from car_dealer_chatbot.exceptions import (
    DataFileNotFoundError,
    DataValidationError,
)
from car_dealer_chatbot.repository import CarRepository, DealerRepository


def test_loads_and_indexes_rows(car_repo: CarRepository) -> None:
    assert len(car_repo) == 4
    corolla = car_repo.get("C001")
    assert corolla is not None
    assert corolla.model == "Corolla"


def test_get_unknown_returns_none(car_repo: CarRepository) -> None:
    assert car_repo.get("NOPE") is None


def test_for_dealer_filters(car_repo: CarRepository) -> None:
    cars = car_repo.for_dealer("D001")
    assert {c.car_id for c in cars} == {"C001", "C002"}


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(DataFileNotFoundError):
        CarRepository(tmp_path / "does_not_exist.csv")


def test_duplicate_primary_key_raises(tmp_path: Path) -> None:
    path = tmp_path / "dealers.csv"
    path.write_text(
        "dealer_id,name,phone,email,address,city,country,rating\n"
        "D001,A,1,a@x.nl,addr,City,NL,4.0\n"
        "D001,B,2,b@x.nl,addr,City,NL,4.0\n",
        encoding="utf-8",
    )
    with pytest.raises(DataValidationError, match="Duplicate"):
        DealerRepository(path)


def test_invalid_row_raises(tmp_path: Path) -> None:
    path = tmp_path / "dealers.csv"
    path.write_text(
        "dealer_id,name,phone,email,address,city,country,rating\n"
        "D001,A,1,a@x.nl,addr,City,NL,not-a-number\n",
        encoding="utf-8",
    )
    with pytest.raises(DataValidationError):
        DealerRepository(path)
