"""LLM tool definitions and dispatch.

Each capability the model can invoke is described once as a :class:`Tool`
(name, JSON-schema parameters, and a Python handler). The :class:`Toolbox`
exposes them to the OpenAI SDK and routes a tool call to its handler via a
registry -- so adding a tool means adding one :class:`Tool`, with no ``if/elif``
chains anywhere (DRY, open/closed).

Handlers always return a JSON-serialisable ``dict`` and never raise: expected
problems (unknown car, unparseable date) are returned as ``{"error": ...}`` so
the model can recover and reply gracefully.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from dateutil import parser as date_parser

from car_dealer_chatbot.core.exceptions import ChatbotError
from car_dealer_chatbot.core.logging import get_logger
from car_dealer_chatbot.domain.models import Car
from car_dealer_chatbot.services import InventoryService

logger = get_logger(__name__)

# A handler receives the service plus the model-supplied arguments and returns a
# JSON-serialisable result.
ToolHandler = Callable[[InventoryService, dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class Tool:
    """A single capability exposed to the language model."""

    name: str
    description: str
    parameters: dict[str, Any]
    handler: ToolHandler

    def to_openai_schema(self) -> dict[str, Any]:
        """Render this tool in the OpenAI ``tools`` array format."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


# -- Serialisation helpers ----------------------------------------------------


def _car_summary(service: InventoryService, car: Car) -> dict[str, Any]:
    """Serialise a car together with its dealer for the model to present."""
    dealer = service.get_dealer(car.dealer_id)
    return {
        "car_id": car.car_id,
        "make": car.make,
        "model": car.model,
        "variant": car.variant,
        "full_name": car.full_name,
        "year": car.year,
        "body_type": car.body_type,
        "fuel_type": car.fuel_type,
        "transmission": car.transmission,
        "price": car.price_display,
        "color": car.color,
        "mileage_km": car.mileage_km,
        "dealer_name": dealer.name,
        "dealer_city": dealer.city,
    }


# -- Handlers -----------------------------------------------------------------


def _handle_search_cars(
    service: InventoryService, args: dict[str, Any]
) -> dict[str, Any]:
    query = str(args.get("query", "")).strip()
    if not query:
        return {"error": "empty_query", "message": "No search text was provided."}

    matches = service.search_cars(query)
    return {
        "query": query,
        "count": len(matches),
        "results": [_car_summary(service, car) for car in matches],
    }


def _handle_get_dealer_details(
    service: InventoryService, args: dict[str, Any]
) -> dict[str, Any]:
    car_id = str(args.get("car_id", "")).strip()
    pairing = service.get_car_with_dealer(car_id)
    if pairing is None:
        return {
            "error": "car_not_found",
            "message": f"No car exists with id '{car_id}'.",
        }
    dealer = pairing.dealer
    return {
        "car_id": pairing.car.car_id,
        "car_full_name": pairing.car.full_name,
        "dealer": {
            "name": dealer.name,
            "phone": dealer.phone,
            "email": dealer.email,
            "address": dealer.address,
            "city": dealer.city,
            "country": dealer.country,
            "rating": dealer.rating,
        },
    }


def _handle_schedule_call(
    service: InventoryService, args: dict[str, Any]
) -> dict[str, Any]:
    car_id = str(args.get("car_id", "")).strip()
    raw_when = str(args.get("preferred_datetime", "")).strip()

    try:
        when = date_parser.parse(raw_when)
    except (ValueError, OverflowError):
        return {
            "error": "invalid_datetime",
            "message": (
                f"Could not understand the date/time '{raw_when}'. "
                "Please provide a specific date and time."
            ),
        }

    try:
        call = service.schedule_call(car_id, when)
    except ValueError as exc:
        return {"error": "cannot_schedule", "message": str(exc)}

    return {
        "confirmed": True,
        "dealer_name": call.dealer_name,
        "dealer_phone": call.dealer_phone,
        "car_full_name": call.car_full_name,
        "slot": call.slot_display,
    }


# -- Registry -----------------------------------------------------------------

_CAR_ID_PROPERTY = {
    "type": "string",
    "description": "The car_id returned by search_cars, e.g. 'C001'.",
}

TOOLS: tuple[Tool, ...] = (
    Tool(
        name="search_cars",
        description=(
            "Search the dealership inventory for cars matching a free-text "
            "description (make, model, variant, fuel type, body style, etc.). "
            "Always call this first to find the car the user is asking about."
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "What the user is looking for, e.g. "
                    "'Toyota Corolla hybrid' or 'electric SUV'.",
                }
            },
            "required": ["query"],
            "additionalProperties": False,
        },
        handler=_handle_search_cars,
    ),
    Tool(
        name="get_dealer_details",
        description=(
            "Return full contact details for the dealer selling a specific car. "
            "Call this when the user asks to see the dealer's details."
        ),
        parameters={
            "type": "object",
            "properties": {"car_id": _CAR_ID_PROPERTY},
            "required": ["car_id"],
            "additionalProperties": False,
        },
        handler=_handle_get_dealer_details,
    ),
    Tool(
        name="schedule_call",
        description=(
            "Schedule a (mock) call between the user and the dealer selling a "
            "specific car. Convert the user's requested day/time into an "
            "ISO-8601 datetime using today's date before calling."
        ),
        parameters={
            "type": "object",
            "properties": {
                "car_id": _CAR_ID_PROPERTY,
                "preferred_datetime": {
                    "type": "string",
                    "description": "Preferred slot as ISO-8601, "
                    "e.g. '2025-10-03T15:00'.",
                },
            },
            "required": ["car_id", "preferred_datetime"],
            "additionalProperties": False,
        },
        handler=_handle_schedule_call,
    ),
)


class Toolbox:
    """Registry that exposes tools to the model and dispatches calls to them.

    Args:
        service: The inventory service every handler operates on.
        tools: The tools to register (defaults to the module-level ``TOOLS``).
    """

    def __init__(
        self, service: InventoryService, tools: tuple[Tool, ...] = TOOLS
    ) -> None:
        """Initialise the toolbox with a service and the tools to register."""
        self._service = service
        self._tools: dict[str, Tool] = {tool.name: tool for tool in tools}

    def openai_schema(self) -> list[dict[str, Any]]:
        """Return the ``tools`` array to pass to the Chat Completions API."""
        return [tool.to_openai_schema() for tool in self._tools.values()]

    def dispatch(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        """Execute the tool ``name`` with ``args`` and return its result.

        Unknown tool names and unexpected handler failures are converted into
        ``{"error": ...}`` results rather than raised, keeping the agent loop
        resilient.
        """
        tool = self._tools.get(name)
        if tool is None:
            logger.warning("Model requested unknown tool '%s'", name)
            return {"error": "unknown_tool", "message": f"No such tool: {name}."}

        logger.debug("Dispatching tool %s(%s)", name, args)
        try:
            return tool.handler(self._service, args)
        except ChatbotError as exc:
            logger.error("Tool '%s' failed: %s", name, exc)
            return {"error": "tool_failed", "message": str(exc)}
