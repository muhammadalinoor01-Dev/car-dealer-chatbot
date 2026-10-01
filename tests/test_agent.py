"""Unit tests for the ChatAgent tool-calling loop, using a fake OpenAI client."""

from __future__ import annotations

from typing import Any

import pytest
from openai import OpenAIError

from car_dealer_chatbot.agent import ChatAgent
from car_dealer_chatbot.exceptions import LLMError
from car_dealer_chatbot.services import InventoryService
from car_dealer_chatbot.tools import Toolbox


class _FakeMessage:
    """Stands in for an OpenAI response message."""

    def __init__(self, dump: dict[str, Any]) -> None:
        self._dump = dump
        self.content = dump.get("content")

    def model_dump(self, exclude_none: bool = False) -> dict[str, Any]:
        if exclude_none:
            return {k: v for k, v in self._dump.items() if v is not None}
        return dict(self._dump)


class _FakeChoice:
    def __init__(self, message: _FakeMessage) -> None:
        self.message = message


class _FakeResponse:
    def __init__(self, message: _FakeMessage) -> None:
        self.choices = [_FakeChoice(message)]


class _FakeCompletions:
    def __init__(self, dumps: list[dict[str, Any]]) -> None:
        self._responses = [_FakeResponse(_FakeMessage(d)) for d in dumps]
        self.calls: list[dict[str, Any]] = []

    def create(self, **kwargs: Any) -> _FakeResponse:
        self.calls.append(kwargs)
        return self._responses.pop(0)


class _FakeClient:
    def __init__(self, dumps: list[dict[str, Any]]) -> None:
        self.chat = type("Chat", (), {"completions": _FakeCompletions(dumps)})()


class _RaisingCompletions:
    def create(self, **kwargs: Any) -> Any:
        raise OpenAIError("boom")


class _RaisingClient:
    def __init__(self) -> None:
        self.chat = type("Chat", (), {"completions": _RaisingCompletions()})()


def _agent(client: Any, service: InventoryService) -> ChatAgent:
    return ChatAgent(
        client=client,
        toolbox=Toolbox(service),
        model="test-model",
        temperature=0.0,
        system_prompt="system",
    )


def test_send_runs_tool_then_returns_text(service: InventoryService) -> None:
    dumps = [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "search_cars",
                        "arguments": '{"query": "Toyota Corolla"}',
                    },
                }
            ],
        },
        {"role": "assistant", "content": "I found the Toyota Corolla."},
    ]
    client = _FakeClient(dumps)
    agent = _agent(client, service)

    reply = agent.send("I want a Toyota Corolla")

    assert reply == "I found the Toyota Corolla."
    # The second API call must have seen the tool result in the message list.
    second_call_messages = client.chat.completions.calls[1]["messages"]
    assert any(m.get("role") == "tool" for m in second_call_messages)


def test_send_returns_plain_answer_without_tools(service: InventoryService) -> None:
    client = _FakeClient([{"role": "assistant", "content": "Hello!"}])
    agent = _agent(client, service)
    assert agent.send("hi") == "Hello!"


def test_send_wraps_api_errors(service: InventoryService) -> None:
    agent = _agent(_RaisingClient(), service)
    with pytest.raises(LLMError):
        agent.send("hi")


def test_malformed_tool_arguments_are_tolerated(service: InventoryService) -> None:
    dumps = [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [
                {
                    "id": "call_1",
                    "type": "function",
                    "function": {"name": "search_cars", "arguments": "not-json"},
                }
            ],
        },
        {"role": "assistant", "content": "Let me try again."},
    ]
    agent = _agent(_FakeClient(dumps), service)
    # Should not raise despite invalid JSON arguments.
    assert agent.send("find me a car") == "Let me try again."
