"""Command-line interface for the car dealer chatbot.

A thin REPL around :class:`~car_dealer_chatbot.agent.ChatAgent`. All conversation
logic lives in the agent; this module only handles terminal I/O and startup
error reporting.
"""

from __future__ import annotations

import sys

from pydantic import ValidationError

from car_dealer_chatbot.agent import ChatAgent
from car_dealer_chatbot.core.config import get_settings
from car_dealer_chatbot.core.exceptions import ChatbotError, DataError, LLMError
from car_dealer_chatbot.core.logging import configure_logging, get_logger

logger = get_logger(__name__)

_EXIT_COMMANDS = {"quit", "exit", "bye", ":q"}
_PROMPT = "You: "
_BOT_PREFIX = "Bot: "


def _startup() -> ChatAgent:
    """Load settings, configure logging and build the agent.

    Returns:
        A ready :class:`ChatAgent`.

    Raises:
        SystemExit: With a friendly message if startup cannot complete.
    """
    try:
        settings = get_settings()
    except ValidationError as exc:
        missing = ", ".join(str(err["loc"][0]) for err in exc.errors())
        raise SystemExit(
            f"Configuration error: missing/invalid setting(s): {missing}.\n"
            "Copy .env.example to .env and set your OPENROUTER_API_KEY."
        ) from exc

    configure_logging(settings.log_level)

    try:
        return ChatAgent.from_settings(settings)
    except DataError as exc:
        raise SystemExit(f"Data error: {exc}") from exc


def _read_user_input() -> str | None:
    """Read one line from the user, or ``None`` on EOF/Ctrl-C."""
    try:
        return input(_PROMPT).strip()
    except (EOFError, KeyboardInterrupt):
        return None


def main() -> int:
    """Run the interactive CLI chatbot.

    Returns:
        Process exit code (0 on normal exit).
    """
    agent = _startup()

    print("Car Dealer Chatbot  (type 'quit' to exit)\n")
    print(f"{_BOT_PREFIX}{agent.greeting}")

    while True:
        user_input = _read_user_input()
        if user_input is None:
            print("\nGoodbye!")
            return 0
        if not user_input:
            continue
        if user_input.lower() in _EXIT_COMMANDS:
            print(f"{_BOT_PREFIX}Thanks for stopping by. Goodbye!")
            return 0

        try:
            reply = agent.send(user_input)
        except LLMError as exc:
            print(f"{_BOT_PREFIX}Sorry, {exc} Please try again in a moment.")
            continue
        except ChatbotError as exc:  # pragma: no cover - defensive catch-all
            logger.exception("Unexpected application error")
            print(f"{_BOT_PREFIX}Something went wrong: {exc}")
            continue

        print(f"{_BOT_PREFIX}{reply}")


if __name__ == "__main__":
    sys.exit(main())
