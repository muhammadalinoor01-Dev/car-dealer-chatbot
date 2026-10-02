"""Unit tests for the tool layer and dispatch registry."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from car_dealer_chatbot.agent.tools import TOOLS, Toolbox
from car_dealer_chatbot.services import InventoryService


@pytest.fixture()
def toolbox(service: InventoryService) -> Toolbox:
    return Toolbox(service)


def test_openai_schema_lists_all_tools(toolbox: Toolbox) -> None:
    schema = toolbox.openai_schema()
    names = {entry["function"]["name"] for entry in schema}
    assert names == {t.name for t in TOOLS}
    assert all(entry["type"] == "function" for entry in schema)


def test_search_cars_tool(toolbox: Toolbox) -> None:
    result = toolbox.dispatch("search_cars", {"query": "Toyota Corolla"})
    assert result["count"] >= 1
    assert result["results"][0]["car_id"] == "C001"
    assert result["results"][0]["dealer_name"] == "Utrecht Auto Centre"


def test_search_cars_empty_query(toolbox: Toolbox) -> None:
    result = toolbox.dispatch("search_cars", {"query": "   "})
    assert result["error"] == "empty_query"


def test_get_dealer_details_tool(toolbox: Toolbox) -> None:
    result = toolbox.dispatch("get_dealer_details", {"car_id": "C001"})
    assert result["dealer"]["phone"] == "+31 30 123 4567"


def test_get_dealer_details_unknown_car(toolbox: Toolbox) -> None:
    result = toolbox.dispatch("get_dealer_details", {"car_id": "NOPE"})
    assert result["error"] == "car_not_found"


def test_schedule_call_tool_success(toolbox: Toolbox) -> None:
    slot = (datetime.now() + timedelta(days=2)).replace(microsecond=0).isoformat()
    result = toolbox.dispatch(
        "schedule_call", {"car_id": "C001", "preferred_datetime": slot}
    )
    assert result["confirmed"] is True
    assert result["dealer_name"] == "Utrecht Auto Centre"


def test_schedule_call_invalid_datetime(toolbox: Toolbox) -> None:
    result = toolbox.dispatch(
        "schedule_call",
        {"car_id": "C001", "preferred_datetime": "whenever-ish"},
    )
    assert result["error"] == "invalid_datetime"


def test_schedule_call_unknown_car(toolbox: Toolbox) -> None:
    slot = (datetime.now() + timedelta(days=2)).isoformat()
    result = toolbox.dispatch(
        "schedule_call", {"car_id": "NOPE", "preferred_datetime": slot}
    )
    assert result["error"] == "cannot_schedule"


def test_dispatch_unknown_tool(toolbox: Toolbox) -> None:
    result = toolbox.dispatch("frobnicate", {})
    assert result["error"] == "unknown_tool"
