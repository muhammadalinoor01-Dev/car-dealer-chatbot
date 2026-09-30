"""Domain services: search, dealer matching and (mock) call scheduling.

This layer is pure Python with no knowledge of the LLM or any user interface. It
is therefore fully unit-testable in isolation and is the natural home for the
"core logic" the assignment asks us to test.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from difflib import SequenceMatcher

from .exceptions import DealerNotFoundError
from .logging_config import get_logger
from .models import Car, Dealer, ScheduledCall
from .repository import CarRepository, DealerRepository

logger = get_logger(__name__)

# A token is treated as a fuzzy match when its similarity to a candidate word is
# at least this high. Tuned to catch common typos ("corola") without matching
# unrelated words.
_FUZZY_THRESHOLD = 0.82
_DEFAULT_SEARCH_LIMIT = 5


@dataclass(frozen=True)
class CarWithDealer:
    """A car paired with the dealer that sells it."""

    car: Car
    dealer: Dealer


def _tokenize(text: str) -> list[str]:
    """Lower-case and split ``text`` into alphanumeric-ish tokens."""
    return [token for token in text.lower().replace("-", " ").split() if token]


class InventoryService:
    """Query cars, resolve their dealers, and schedule calls.

    Args:
        car_repo: Repository over the cars table.
        dealer_repo: Repository over the dealers table.
    """

    def __init__(self, car_repo: CarRepository, dealer_repo: DealerRepository) -> None:
        """Initialise the service with the car and dealer repositories."""
        self._cars = car_repo
        self._dealers = dealer_repo

    # -- Search ---------------------------------------------------------------

    def search_cars(self, query: str, limit: int = _DEFAULT_SEARCH_LIMIT) -> list[Car]:
        """Return cars matching ``query``, best match first.

        Matching is token-based over each car's make/model/variant plus its key
        attributes (year, fuel, body, transmission, colour), with a fuzzy
        fallback so small typos still match. An empty result is a valid,
        expected outcome (the "car not found" edge case).

        Args:
            query: Free-text description of the desired car.
            limit: Maximum number of results to return.

        Returns:
            Matching cars ordered by descending relevance, then ascending price.
        """
        tokens = _tokenize(query)
        if not tokens:
            return []

        scored: list[tuple[float, Car]] = []
        for car in self._cars.all():
            score = self._score(car, tokens)
            if score > 0:
                scored.append((score, car))

        scored.sort(key=lambda pair: (-pair[0], pair[1].price_eur))
        results = [car for _, car in scored[:limit]]
        logger.debug("search_cars(%r) -> %d hit(s)", query, len(results))
        return results

    def _score(self, car: Car, tokens: list[str]) -> float:
        """Compute a relevance score for ``car`` against query ``tokens``."""
        haystack = _tokenize(
            f"{car.full_name} {car.year} {car.fuel_type} "
            f"{car.body_type} {car.transmission} {car.color}"
        )
        haystack_set = set(haystack)

        score = 0.0
        for token in tokens:
            if token in haystack_set:
                score += 2.0
                continue
            best = max(
                (SequenceMatcher(None, token, word).ratio() for word in haystack),
                default=0.0,
            )
            if best >= _FUZZY_THRESHOLD:
                score += 1.0

        # Reward matches on the most identifying fields.
        if car.make.lower() in tokens:
            score += 1.5
        if car.model.lower() in tokens:
            score += 1.5
        return score

    # -- Dealer join ----------------------------------------------------------

    def get_dealer(self, dealer_id: str) -> Dealer:
        """Return the dealer for ``dealer_id``.

        Raises:
            DealerNotFoundError: If no such dealer exists (a data-integrity
                problem, e.g. a car pointing at a missing dealer).
        """
        dealer = self._dealers.get(dealer_id)
        if dealer is None:
            raise DealerNotFoundError(f"No dealer found with id '{dealer_id}'.")
        return dealer

    def get_car(self, car_id: str) -> Car | None:
        """Return the car for ``car_id``, or ``None`` if it does not exist."""
        return self._cars.get(car_id)

    def get_car_with_dealer(self, car_id: str) -> CarWithDealer | None:
        """Return a car joined with its dealer, or ``None`` if the car is absent.

        Raises:
            DealerNotFoundError: If the car exists but its dealer does not.
        """
        car = self._cars.get(car_id)
        if car is None:
            return None
        return CarWithDealer(car=car, dealer=self.get_dealer(car.dealer_id))

    # -- Scheduling -----------------------------------------------------------

    def schedule_call(self, car_id: str, when: datetime) -> ScheduledCall:
        """Create a (mock) scheduled call for the dealer selling ``car_id``.

        No real booking is performed; this returns a confirmation object.

        Args:
            car_id: The car the user is interested in.
            when: The requested date and time.

        Returns:
            A :class:`ScheduledCall` confirmation.

        Raises:
            DealerNotFoundError: If the car exists but its dealer does not.
            ValueError: If ``car_id`` is unknown or the slot is in the past.
        """
        pairing = self.get_car_with_dealer(car_id)
        if pairing is None:
            raise ValueError(f"Cannot schedule a call: unknown car id '{car_id}'.")

        call = ScheduledCall(
            dealer_name=pairing.dealer.name,
            dealer_phone=pairing.dealer.phone,
            car_full_name=pairing.car.full_name,
            scheduled_for=when,
        )
        logger.info(
            "Scheduled call with %s for %s", call.dealer_name, call.slot_display
        )
        return call
