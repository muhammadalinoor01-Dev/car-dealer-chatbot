"""Shared pytest fixtures.

Tests run entirely offline: the repositories read small CSV fixtures written to a
temporary directory, and the agent test uses a fake OpenAI client. No network or
API key is required.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from car_dealer_chatbot.repositories import CarRepository, DealerRepository
from car_dealer_chatbot.services import InventoryService

_DEALERS_CSV = """\
dealer_id,name,phone,email,address,city,country,rating
D001,Utrecht Auto Centre,+31 30 123 4567,sales@utrechtauto.nl,Europalaan 12,Utrecht,Netherlands,4.6
D002,Amsterdam Motors,+31 20 555 0198,contact@amsterdammotors.nl,Overtoom 210,Amsterdam,Netherlands,4.3
"""

_CARS_CSV = """\
car_id,make,model,variant,year,body_type,fuel_type,transmission,price_eur,color,mileage_km,dealer_id
C001,Toyota,Corolla,1.8 Hybrid Dynamic,2023,Hatchback,Hybrid,Automatic,28950,Silver,18500,D001
C002,Toyota,Yaris,1.5 Hybrid Executive,2023,Hatchback,Hybrid,Automatic,24990,White,21000,D001
C003,Tesla,Model 3,Long Range AWD,2023,Sedan,Electric,Automatic,46990,White,19800,D002
C099,Ghost,Phantom,Base,2023,Sedan,Petrol,Automatic,10000,Black,0,D404
"""


@pytest.fixture()
def dealers_csv(tmp_path: Path) -> Path:
    """Write the dealers fixture CSV and return its path."""
    path = tmp_path / "dealers.csv"
    path.write_text(_DEALERS_CSV, encoding="utf-8")
    return path


@pytest.fixture()
def cars_csv(tmp_path: Path) -> Path:
    """Write the cars fixture CSV and return its path.

    Note: car ``C099`` intentionally references a non-existent dealer (``D404``)
    to exercise the data-integrity edge case.
    """
    path = tmp_path / "cars.csv"
    path.write_text(_CARS_CSV, encoding="utf-8")
    return path


@pytest.fixture()
def car_repo(cars_csv: Path) -> CarRepository:
    """A car repository over the fixture data."""
    return CarRepository(cars_csv)


@pytest.fixture()
def dealer_repo(dealers_csv: Path) -> DealerRepository:
    """A dealer repository over the fixture data."""
    return DealerRepository(dealers_csv)


@pytest.fixture()
def service(car_repo: CarRepository, dealer_repo: DealerRepository) -> InventoryService:
    """An inventory service wired to the fixture repositories."""
    return InventoryService(car_repo, dealer_repo)
