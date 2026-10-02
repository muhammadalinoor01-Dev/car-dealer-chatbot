# Car Dealer Chatbot

An LLM-powered chatbot that helps a user find a car to buy and connects them with
the dealer who sells it. It reads car and dealer data from CSV files, and uses a
**tool-calling agent** (via OpenRouter) so the model drives a natural conversation
while all data access stays deterministic and testable.

Two frontends share the exact same conversation engine:

- **CLI** - `car-dealer-chatbot`
- **Web** - a Streamlit app (`streamlit run app/streamlit_app.py`)

---

## Contents

- [Architecture](#architecture)
- [Setup and installation](#setup-and-installation)
- [Configuring API keys](#configuring-api-keys)
- [Running the chatbot](#running-the-chatbot)
- [Running the tests](#running-the-tests)
- [Data design](#data-design)
- [Edge cases](#edge-cases)
- [Assumptions and design decisions](#assumptions-and-design-decisions)
- [Code quality](#code-quality)

---

## Architecture

The code follows a strict layering with a single responsibility per module. Each
layer depends only on the ones beneath it, and the LLM/UI layers never touch the
CSV files directly.

```
                +-------------------+      +--------------------------+
   frontends    |   cli.py (REPL)   |      | app/streamlit_app.py (web)|
                +---------+---------+      +-------------+------------+
                          \                              /
                           v                            v
                        +--------------------------------+
      conversation      |         agent.py               |  tool-calling loop
                        |        (ChatAgent)             |  (UI-agnostic)
                        +----------------+---------------+
                                         |
                        +----------------v---------------+
      LLM interface     |          tools.py              |  tool schemas + dispatch
                        |     (Tool, Toolbox)            |  registry (no if/elif)
                        +----------------+---------------+
                                         |
                        +----------------v---------------+
      domain logic      |        services.py             |  search / join / schedule
                        |      (InventoryService)        |
                        +----------------+---------------+
                                         |
                        +----------------v---------------+
      data access       |       repository.py            |  generic CsvRepository[T]
                        | (CarRepository, DealerRepo)    |
                        +----------------+---------------+
                                         |
                        +----------------v---------------+
      data              |   data/cars.csv, dealers.csv   |
                        +--------------------------------+
```

Key points:

- **One conversation engine, two frontends.** `ChatAgent` owns the message
  history and the tool-calling loop. The CLI and Streamlit app are thin I/O
  wrappers - no dialogue logic is duplicated (DRY).
- **Data-driven tool dispatch.** Every model capability is declared once as a
  `Tool` (name, JSON-schema, handler) and routed through a registry. Adding a
  tool means adding one `Tool` object; there are no `if name == ...` chains.
- **Deterministic core.** Search, dealer matching and scheduling are pure Python
  in `services.py`, so the "core logic" is unit-tested with no network or API
  key. Handlers never raise across the LLM boundary - expected problems come back
  as `{"error": ...}` so the model can recover.

---

## Setup and installation

Requires **Python 3.11+**. Set up a virtual environment for your OS below, then
run the common install step.

### macOS

```bash
# Install Python 3.11 if you don't have it (Homebrew)
brew install python@3.11

# Create and activate a virtual environment (run from the project root)
python3.11 -m venv .venv
source .venv/bin/activate
```

### Linux (Debian / Ubuntu)

```bash
# Install Python 3.11 if you don't have it
sudo apt update && sudo apt install -y python3.11 python3.11-venv

# Create and activate a virtual environment (run from the project root)
python3.11 -m venv .venv
source .venv/bin/activate
```

On Fedora/RHEL use `sudo dnf install python3.11`; on Arch use `sudo pacman -S python`.

### Windows (PowerShell)

```powershell
# Install Python 3.11 from https://www.python.org/downloads/ (tick "Add to PATH")
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
```

### Install (all platforms)

With the virtual environment activated, from the project root:

```bash
# Editable install with the web + dev extras
pip install -e ".[web,dev]"
```

`pip install -e .` installs only the runtime dependencies. The extras are:

- `web`: Streamlit (the web frontend)
- `dev`: pytest, coverage, Black, Ruff, mypy

A pinned `requirements.txt` is also provided for a runtime-only install
(`pip install -r requirements.txt`).

---

## Configuring API keys

The chatbot uses **OpenRouter** as its LLM provider. Secrets are loaded from
environment variables or a local `.env` file and are **never committed** (`.env`
is git-ignored).

```bash
cp .env.example .env
# then edit .env and set your key:
#   OPENROUTER_API_KEY=sk-or-...
```

Get a key at <https://openrouter.ai/keys>.

| Variable             | Required | Default                        | Purpose                                   |
| -------------------- | -------- | ------------------------------ | ----------------------------------------- |
| `OPENROUTER_API_KEY` | ✅       | -                              | OpenRouter API key                        |
| `OPENROUTER_MODEL`   | ❌       | `openai/gpt-4o-mini`           | Model id (must support tool calling)      |
| `OPENROUTER_BASE_URL`| ❌       | `https://openrouter.ai/api/v1` | OpenRouter endpoint                       |
| `TEMPERATURE`        | ❌       | `0.2`                          | Sampling temperature                      |
| `LOG_LEVEL`          | ❌       | `INFO`                         | Logging verbosity                         |
| `CARS_CSV_PATH`      | ❌       | bundled data                   | Override the cars CSV                      |
| `DEALERS_CSV_PATH`   | ❌       | bundled data                   | Override the dealers CSV                   |

Choose a model that supports **tool/function calling** (e.g.
`openai/gpt-4o-mini`, `anthropic/claude-3.5-sonnet`, `google/gemini-flash-1.5`).
Browse models at <https://openrouter.ai/models>.

---

## Running the chatbot

**CLI** (installed as a console script):

```bash
car-dealer-chatbot
# or:  python -m car_dealer_chatbot.cli
```

**Web** (Streamlit - the bonus interface):

```bash
streamlit run app/streamlit_app.py
```

Example CLI session:

```
Bot: Hi! Which car are you looking to buy?
You: I'm interested in a Toyota Corolla.
Bot: I found the Toyota Corolla 1.8 Hybrid Dynamic, sold by Utrecht Auto Centre.
     Would you like (1) the dealer's details or (2) to schedule a call?
You: Schedule a call please.
Bot: Sure - what date and time suit you?
You: Friday at 3pm.
Bot: Call scheduled with Utrecht Auto Centre (+31 30 123 4567)
     on Friday 03 Oct 2025 at 15:00. The dealer will call you then.
```

---

## Running the tests

The suite runs fully offline (no API key needed) - the agent test uses a fake
OpenAI client and the data layer reads temporary CSV fixtures.

```bash
pytest                 # runs tests with coverage (configured in pyproject.toml)
```

Lint, format and type checks:

```bash
ruff check .
black --check .
mypy src
```

---

## Data design

Two CSV files in `src/car_dealer_chatbot/data/`, modelled as a classic
one-to-many (**one dealer sells many cars**) linked by a foreign key.

**`dealers.csv`** - one row per dealer (`dealer_id` is the primary key):

| column      | example              |
| ----------- | -------------------- |
| `dealer_id` | `D001`               |
| `name`      | `Utrecht Auto Centre`|
| `phone`     | `+31 30 123 4567`    |
| `email`     | `sales@utrechtauto.nl`|
| `address`   | `Europalaan 12`      |
| `city`      | `Utrecht`            |
| `country`   | `Netherlands`        |
| `rating`    | `4.6`                |

**`cars.csv`** - one row per car (`car_id` primary key, `dealer_id` foreign key):

| column         | example              |
| -------------- | -------------------- |
| `car_id`       | `C001`               |
| `make`         | `Toyota`             |
| `model`        | `Corolla`            |
| `variant`      | `1.8 Hybrid Dynamic` |
| `year`         | `2023`               |
| `body_type`    | `Hatchback`          |
| `fuel_type`    | `Hybrid`             |
| `transmission` | `Automatic`          |
| `price_eur`    | `28950`              |
| `color`        | `Silver`             |
| `mileage_km`   | `18500`              |
| `dealer_id`    | `D001`               |

**Why this shape:**

- **Normalised (foreign key over duplication).** Dealer details live in one place;
  cars reference a dealer by id. This mirrors the required flow - "find a car,
  then show *its* dealer" is a simple join - and avoids inconsistent duplicated
  dealer data.
- **`make` / `model` / `variant` are separate columns.** The assignment asks to
  show these three explicitly, and separating them makes search scoring on each
  field straightforward.
- **Rich-but-realistic attributes** (fuel, body, transmission, price, mileage)
  let the user search naturally ("electric SUV", "hybrid hatchback") and give the
  model something concrete to present. 25 cars across 6 dealers keep it small
  enough to read yet varied enough to demo ambiguity and no-match cases.

The data files are packaged with the wheel and can be overridden via
`CARS_CSV_PATH` / `DEALERS_CSV_PATH` without code changes.

---

## Edge cases

Edge cases are handled at the layer that owns the concern, and surfaced to the
user gracefully rather than crashing.

| Edge case | Handling |
| --------- | -------- |
| **Requested car not found** | `search_cars` returns an empty result; the model tells the user plainly and invites a re-phrase. |
| **Typos in the car name** | Search is token-based with a fuzzy fallback (`difflib`), so "Corola" still matches "Corolla". |
| **Ambiguous request** (several matches) | Top matches are ranked and returned; the system prompt instructs the model to list options and ask the user to choose. |
| **Dangling dealer reference** (car points at a missing dealer) | `get_dealer` raises `DealerNotFoundError`; the tool converts it to a clean error result instead of crashing. |
| **Unparseable date/time for scheduling** | The `schedule_call` tool returns `invalid_datetime`; the model asks again. |
| **Slot in the past** | `ScheduledCall` validation rejects it. |
| **Missing / malformed CSV files** | Repositories raise typed `DataError`s at startup; the CLI/web frontends show a clear message and exit cleanly. |
| **Missing API key / bad config** | Caught at startup with an actionable message pointing to `.env.example`. |
| **OpenAI API failure** | Wrapped as `LLMError`; the turn fails softly with "try again in a moment" and is logged - the session continues. |
| **Model requests an unknown tool / malformed arguments** | Dispatch returns an `unknown_tool` error; invalid JSON arguments are tolerated. |
| **Runaway tool loop** | The agent caps tool round-trips per turn and forces a final text answer. |
| **Empty user input** | Ignored (CLI re-prompts). |

---

## Assumptions and design decisions

- **Tool-calling agent over a hand-rolled state machine.** The LLM owns the
  dialogue and calls typed tools; the deterministic data layer stays behind those
  tools. This gives natural language understanding "for free" while keeping the
  business logic testable and the model unable to invent cars/dealers.
- **OpenRouter as the provider**, accessed through the OpenAI-compatible Python
  SDK (`openai/gpt-4o-mini` by default - cheap and capable). One gateway gives
  access to many models; the provider is isolated inside `ChatAgent`, so swapping
  models is just an env-var change.
- **Relative dates are resolved by the model**, which is given today's date in the
  system prompt and asked to emit ISO-8601; the tool then parses strictly. This
  keeps date logic simple and testable rather than reimplementing NL date parsing.
- **Scheduling is a mock**, as specified - it returns a confirmation object; no
  calendar/booking backend is contacted.
- **In-memory repositories.** The dataset is tiny, so CSVs are loaded once and
  indexed by primary key. If the data grew, only `repository.py` would change.
- **Config is centralised and typed** (`pydantic-settings`), so every layer reads
  one validated settings object and secrets never appear in code.

---

## Code quality

- **`src/` layout, installable package** with `pyproject.toml`; pinned deps.
- **Type hints throughout**, checked with **mypy** (strict).
- **Docstrings** on every module, class and public function (Google style).
- **Formatting/linting** with **Black** and **Ruff**.
- **Unit tests** for the core logic (repository, services, tools) plus the agent
  loop with a fake client, run with coverage.
- **Logging** via a centralised config; **typed exception hierarchy** for errors.
