.PHONY: install run web test lint format typecheck check

install:
	pip install -e ".[web,dev]"

run:
	car-dealer-chatbot

web:
	streamlit run src/car_dealer_chatbot/interfaces/web/streamlit_app.py

test:
	pytest

lint:
	ruff check .
	black --check .

format:
	ruff check --fix .
	black .

typecheck:
	mypy src

check: lint typecheck test
