"""Car Dealer Chatbot.

An LLM-powered assistant that helps a user find a car and connect with the
dealer who sells it. The package is organised in clear layers:

* :mod:`car_dealer_chatbot.repository` -- CSV data access.
* :mod:`car_dealer_chatbot.services` -- domain logic (search, join, scheduling).
* :mod:`car_dealer_chatbot.tools` -- LLM tool schemas and dispatch.
* :mod:`car_dealer_chatbot.agent` -- the tool-calling conversation loop.

The CLI (:mod:`car_dealer_chatbot.cli`) and the Streamlit web app both drive the
same :class:`~car_dealer_chatbot.agent.ChatAgent`, so the conversation behaviour
lives in exactly one place.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
