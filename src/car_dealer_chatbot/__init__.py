"""Car Dealer Chatbot.

An LLM-powered assistant that helps a user find a car and connect with the
dealer who sells it. The package is organised in clear layers:

* :mod:`car_dealer_chatbot.core` -- settings, logging and errors.
* :mod:`car_dealer_chatbot.domain` -- domain entities.
* :mod:`car_dealer_chatbot.repositories` -- CSV data access.
* :mod:`car_dealer_chatbot.services` -- domain logic (search, join, scheduling).
* :mod:`car_dealer_chatbot.agent` -- prompt, tools and the tool-calling loop.
* :mod:`car_dealer_chatbot.interfaces` -- CLI and Streamlit frontends.

The CLI (:mod:`car_dealer_chatbot.interfaces.cli`) and the Streamlit web app
both drive the same :class:`~car_dealer_chatbot.agent.ChatAgent`, so the
conversation behaviour lives in exactly one place.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
