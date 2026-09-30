"""CSV data-access layer.

A single generic :class:`CsvRepository` handles the mechanics common to every
CSV table -- reading the file, validating each row into a pydantic model, and
indexing by primary key -- so the concrete repositories stay tiny (DRY). The
typed :class:`CarRepository` and :class:`DealerRepository` add only the
table-specific query methods.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError

from .exceptions import DataFileNotFoundError, DataValidationError
from .logging_config import get_logger
from .models import Car, Dealer

logger = get_logger(__name__)

ModelT = TypeVar("ModelT", bound=BaseModel)


class CsvRepository(Generic[ModelT]):
    """In-memory repository backed by a CSV file.

    Rows are read once at construction time, validated into ``model`` instances,
    and indexed by the primary-key column for O(1) lookups.

    Attributes:
        model: The pydantic model each row is parsed into.
        id_field: Name of the primary-key column (also a model field).
    """

    def __init__(self, csv_path: Path, model: type[ModelT], id_field: str) -> None:
        """Load and index the CSV file.

        Args:
            csv_path: Path to the CSV file.
            model: Pydantic model used to validate each row.
            id_field: Name of the primary-key column.

        Raises:
            DataFileNotFoundError: If ``csv_path`` does not exist.
            DataValidationError: If a row fails validation or a duplicate primary
                key is found.
        """
        self.model = model
        self.id_field = id_field
        self._by_id: dict[str, ModelT] = {}
        self._load(csv_path)

    def _load(self, csv_path: Path) -> None:
        if not csv_path.is_file():
            raise DataFileNotFoundError(f"CSV data file not found: {csv_path}")

        with csv_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            for line_no, row in enumerate(reader, start=2):  # line 1 = header
                item = self._parse_row(row, csv_path, line_no)
                key = getattr(item, self.id_field)
                if key in self._by_id:
                    raise DataValidationError(
                        f"Duplicate {self.id_field} '{key}' in {csv_path.name} "
                        f"(line {line_no})."
                    )
                self._by_id[key] = item

        if not self._by_id:
            logger.warning("Loaded 0 rows from %s", csv_path)
        else:
            logger.info(
                "Loaded %d %s row(s) from %s",
                len(self._by_id),
                self.model.__name__,
                csv_path.name,
            )

    def _parse_row(self, row: dict[str, str], csv_path: Path, line_no: int) -> ModelT:
        try:
            return self.model.model_validate(row)
        except ValidationError as exc:
            raise DataValidationError(
                f"Invalid row in {csv_path.name} (line {line_no}): {exc}"
            ) from exc

    def get(self, item_id: str) -> ModelT | None:
        """Return the item with the given primary key, or ``None`` if absent."""
        return self._by_id.get(item_id)

    def all(self) -> list[ModelT]:
        """Return all items in file order."""
        return list(self._by_id.values())

    def __len__(self) -> int:
        """Return the number of rows loaded."""
        return len(self._by_id)


class DealerRepository(CsvRepository[Dealer]):
    """Repository over ``dealers.csv``."""

    def __init__(self, csv_path: Path) -> None:
        """Initialise the dealer repository from ``csv_path``."""
        super().__init__(csv_path, Dealer, id_field="dealer_id")


class CarRepository(CsvRepository[Car]):
    """Repository over ``cars.csv`` with car-specific queries."""

    def __init__(self, csv_path: Path) -> None:
        """Initialise the car repository from ``csv_path``."""
        super().__init__(csv_path, Car, id_field="car_id")

    def for_dealer(self, dealer_id: str) -> list[Car]:
        """Return every car sold by the given dealer."""
        return [car for car in self.all() if car.dealer_id == dealer_id]
