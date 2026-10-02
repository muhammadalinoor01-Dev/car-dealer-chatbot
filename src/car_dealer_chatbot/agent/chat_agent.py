"""The conversational agent: a bounded OpenAI tool-calling loop.

:class:`ChatAgent` owns the message history and the interaction with the model.
It is completely UI-agnostic -- both the CLI and the Streamlit app create one and
call :meth:`ChatAgent.send`. That keeps the conversation behaviour in exactly one
place.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

from openai import OpenAI, OpenAIError

from car_dealer_chatbot.agent.prompts import build_system_prompt
from car_dealer_chatbot.agent.tools import Toolbox
from car_dealer_chatbot.core.config import Settings, get_settings
from car_dealer_chatbot.core.exceptions import LLMError
from car_dealer_chatbot.core.logging import get_logger
from car_dealer_chatbot.repositories import CarRepository, DealerRepository
from car_dealer_chatbot.services import InventoryService

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = get_logger(__name__)

GREETING = "Hi! Which car are you looking to buy?"

# Safety valve: the maximum number of consecutive tool round-trips per user turn.
# Prevents an unbounded loop if the model keeps requesting tools.
_MAX_TOOL_ITERATIONS = 5


class ChatAgent:
    """Drives a tool-augmented conversation with the language model.

    Args:
        client: An OpenAI client.
        toolbox: The registry of tools the model may call.
        model: Chat model name.
        temperature: Sampling temperature.
        system_prompt: The system prompt (defaults to the standard one).
    """

    def __init__(
        self,
        client: OpenAI,
        toolbox: Toolbox,
        model: str,
        temperature: float,
        system_prompt: str | None = None,
    ) -> None:
        """Initialise the agent with its client, tools and model settings."""
        self._client = client
        self._toolbox = toolbox
        self._model = model
        self._temperature = temperature
        self._messages: list[dict[str, Any]] = [
            {"role": "system", "content": system_prompt or build_system_prompt()}
        ]

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> ChatAgent:
        """Build a fully-wired agent from application settings.

        This composes the whole object graph (repositories -> service -> toolbox
        -> agent), so callers do not need to know the wiring.

        Args:
            settings: Application settings; loaded from the environment if omitted.

        Returns:
            A ready-to-use :class:`ChatAgent`.

        Raises:
            DataError: If the CSV data files are missing or invalid.
        """
        settings = settings or get_settings()
        car_repo = CarRepository(settings.cars_csv_path)
        dealer_repo = DealerRepository(settings.dealers_csv_path)
        service = InventoryService(car_repo, dealer_repo)
        toolbox = Toolbox(service)
        client = OpenAI(
            api_key=settings.openrouter_api_key.get_secret_value(),
            base_url=settings.openrouter_base_url,
        )
        return cls(
            client=client,
            toolbox=toolbox,
            model=settings.openrouter_model,
            temperature=settings.temperature,
        )

    @property
    def greeting(self) -> str:
        """The assistant's opening line."""
        return GREETING

    @property
    def model(self) -> str:
        """The chat model this agent uses."""
        return self._model

    def send(self, user_message: str) -> str:
        """Send one user message and return the assistant's reply.

        Runs the tool-calling loop until the model returns a plain text answer
        (or the iteration cap is hit).

        Args:
            user_message: The user's input.

        Returns:
            The assistant's natural-language reply.

        Raises:
            LLMError: If the model provider fails.
        """
        self._messages.append({"role": "user", "content": user_message})

        for _ in range(_MAX_TOOL_ITERATIONS):
            message = self._complete()
            tool_calls = message.get("tool_calls")
            if not tool_calls:
                content = message.get("content") or ""
                self._messages.append({"role": "assistant", "content": content})
                return content

            # Record the assistant's tool request, then answer each call.
            self._messages.append(message)
            self._run_tool_calls(tool_calls)

        logger.warning("Tool-iteration cap reached; forcing a text answer.")
        return self._force_final_answer()

    def _complete(self) -> dict[str, Any]:
        """Call the Chat Completions API once and return the message as a dict."""
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                temperature=self._temperature,
                messages=self._messages,  # type: ignore[arg-type]
                tools=self._toolbox.openai_schema(),  # type: ignore[arg-type]
            )
        except OpenAIError as exc:
            logger.error("OpenAI request failed: %s", exc)
            raise LLMError("The language model is currently unavailable.") from exc

        # Convert the SDK object to a plain dict so history stays serialisable.
        return response.choices[0].message.model_dump(exclude_none=True)

    def _run_tool_calls(self, tool_calls: Sequence[dict[str, Any]]) -> None:
        """Execute each requested tool call and append its result to history."""
        for call in tool_calls:
            function = call["function"]
            name = function["name"]
            args = self._parse_arguments(function.get("arguments"))
            result = self._toolbox.dispatch(name, args)
            self._messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call["id"],
                    "content": json.dumps(result),
                }
            )

    @staticmethod
    def _parse_arguments(raw: str | None) -> dict[str, Any]:
        """Parse a tool call's JSON argument string, tolerating malformed input."""
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Model produced invalid tool arguments: %r", raw)
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _force_final_answer(self) -> str:
        """Ask the model for a final text answer with tools disabled."""
        try:
            response = self._client.chat.completions.create(
                model=self._model,
                temperature=self._temperature,
                messages=self._messages,  # type: ignore[arg-type]
            )
        except OpenAIError as exc:
            raise LLMError("The language model is currently unavailable.") from exc
        content = response.choices[0].message.content or ""
        self._messages.append({"role": "assistant", "content": content})
        return content
