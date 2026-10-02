#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
exec streamlit run src/car_dealer_chatbot/interfaces/web/streamlit_app.py "$@"
