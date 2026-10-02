"""Streamlit web interface for the car dealer chatbot.

Run with::

    streamlit run src/car_dealer_chatbot/interfaces/web/streamlit_app.py

Like the CLI, this is a thin frontend over
:class:`car_dealer_chatbot.agent.ChatAgent`; no conversation logic is duplicated.
The UI presents a clean, messaging-app style chat: the user's messages align
right, the assistant's align left, each with an avatar and sender label.
"""

from __future__ import annotations

import html

import streamlit as st
from pydantic import ValidationError

from car_dealer_chatbot.agent import ChatAgent
from car_dealer_chatbot.core.config import get_settings
from car_dealer_chatbot.core.exceptions import DataError, LLMError
from car_dealer_chatbot.core.logging import configure_logging

st.set_page_config(
    page_title="Car Dealer Assistant",
    page_icon="🚗",
    layout="centered",
)

_ASSISTANT_AVATAR = "🚗"
_USER_AVATAR = "🧑"

# A self-contained, theme-aware stylesheet. Colours are defined as CSS variables
# and overridden for dark mode via prefers-color-scheme, so the UI looks right in
# both Streamlit themes without any JS.
_STYLES = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');

:root {
    --accent: #2f6bff;
    --accent-2: #4f86ff;
    --bg-bot: #f5f7fa;
    --avatar-bot: #e7ecf5;
    --border: #e6e8ee;
    --text: #1f2430;
    --muted: #8a93a6;
}
@media (prefers-color-scheme: dark) {
    :root {
        --accent: #3b82f6;
        --accent-2: #60a5fa;
        --bg-bot: #1c2230;
        --avatar-bot: #2a3242;
        --border: #2c3440;
        --text: #e7eaf0;
        --muted: #8b93a3;
    }
}

/* Hide default Streamlit chrome for a cleaner, app-like surface. */
#MainMenu, header, footer { visibility: hidden; }
.stApp { font-family: 'Inter', system-ui, -apple-system, sans-serif; }
.block-container { padding-top: 1.5rem; padding-bottom: 7rem; max-width: 760px; }

/* Brand header */
.brand { display: flex; align-items: center; gap: 14px; margin-bottom: 4px; }
.brand-logo {
    width: 46px; height: 46px; border-radius: 13px;
    background: linear-gradient(135deg, var(--accent), var(--accent-2));
    display: flex; align-items: center; justify-content: center;
    font-size: 24px; box-shadow: 0 6px 16px rgba(47, 107, 255, 0.28);
}
.brand-title {
    font-size: 20px; font-weight: 700; color: var(--text); line-height: 1.2;
}
.brand-sub { font-size: 13px; color: var(--muted); }
.brand-divider {
    height: 1px; background: var(--border); margin: 16px 0 8px; border: 0;
}

/* Message rows */
.row { display: flex; gap: 10px; margin: 16px 0; align-items: flex-end; }
.row.user { flex-direction: row-reverse; }
.avatar {
    width: 34px; height: 34px; border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-size: 17px; flex: 0 0 34px;
}
.avatar.assistant { background: var(--avatar-bot); }
.avatar.user {
    background: linear-gradient(135deg, var(--accent), var(--accent-2));
}
.stack { display: flex; flex-direction: column; max-width: 78%; }
.row.user .stack { align-items: flex-end; }
.name {
    font-size: 11px; color: var(--muted); margin: 0 8px 4px;
    text-transform: uppercase; letter-spacing: 0.04em; font-weight: 600;
}
.bubble {
    padding: 11px 15px; border-radius: 16px; line-height: 1.5;
    font-size: 15px; white-space: pre-wrap; word-wrap: break-word;
}
.bubble.assistant {
    background: var(--bg-bot); color: var(--text);
    border: 1px solid var(--border); border-bottom-left-radius: 5px;
}
.bubble.user {
    background: linear-gradient(135deg, var(--accent), var(--accent-2));
    color: #ffffff; border-bottom-right-radius: 5px;
}
</style>
"""

_HEADER = """
<div class="brand">
    <div class="brand-logo">🚗</div>
    <div>
        <div class="brand-title">Car Dealer Assistant</div>
        <div class="brand-sub">Find your next car and reach its dealer.</div>
    </div>
</div>
<hr class="brand-divider" />
"""


@st.cache_resource(show_spinner="Starting the assistant…")
def _build_agent() -> ChatAgent:
    """Create a single shared agent for the session.

    ``st.cache_resource`` keeps one agent (and thus one loaded dataset and API
    client) across reruns.
    """
    settings = get_settings()
    configure_logging(settings.log_level)
    return ChatAgent.from_settings(settings)


def _init_history(agent: ChatAgent) -> None:
    """Seed the chat transcript with the assistant's greeting once."""
    if "history" not in st.session_state:
        st.session_state.history = [{"role": "assistant", "content": agent.greeting}]


def _render_message(role: str, content: str) -> None:
    """Render one message as an avatar + label + aligned chat bubble.

    Content is HTML-escaped to prevent injection; newlines are preserved via the
    ``white-space: pre-wrap`` rule on the bubble.
    """
    side = "user" if role == "user" else "assistant"
    avatar = _USER_AVATAR if side == "user" else _ASSISTANT_AVATAR
    label = "You" if side == "user" else "Assistant"
    safe = html.escape(content)
    st.markdown(
        f'<div class="row {side}">'
        f'<div class="avatar {side}">{avatar}</div>'
        f'<div class="stack">'
        f'<div class="name">{label}</div>'
        f'<div class="bubble {side}">{safe}</div>'
        f"</div></div>",
        unsafe_allow_html=True,
    )


def _generate_reply(agent: ChatAgent, user_input: str) -> str:
    """Get the assistant's reply, converting LLM failures into a soft message."""
    try:
        return agent.send(user_input)
    except LLMError as exc:
        return f"Sorry, {exc} Please try again in a moment."


def _render_reset() -> None:
    """Render a small, right-aligned 'New chat' reset control."""
    _, right = st.columns([5, 1])
    with right:
        if st.button("New chat", use_container_width=True):
            st.session_state.pop("history", None)
            st.rerun()


def main() -> None:
    """Render the Streamlit chat UI."""
    st.markdown(_STYLES, unsafe_allow_html=True)
    st.markdown(_HEADER, unsafe_allow_html=True)

    try:
        agent = _build_agent()
    except ValidationError:
        st.error(
            "Missing configuration. Copy `.env.example` to `.env` and set your "
            "`OPENROUTER_API_KEY`, then restart."
        )
        st.stop()
    except DataError as exc:
        st.error(f"Data error: {exc}")
        st.stop()

    _render_reset()
    _init_history(agent)

    for message in st.session_state.history:
        _render_message(message["role"], message["content"])

    user_input = st.chat_input("Which car are you looking to buy?")
    if not user_input:
        return

    # Show the user's message immediately, before the (slow) model call, so it
    # is visible while the assistant is "thinking".
    _render_message("user", user_input)
    st.session_state.history.append({"role": "user", "content": user_input})

    with st.spinner("Thinking…"):
        reply = _generate_reply(agent, user_input)
    st.session_state.history.append({"role": "assistant", "content": reply})

    # Re-run so the whole transcript (incl. this turn) renders uniformly.
    st.rerun()


if __name__ == "__main__":
    main()
