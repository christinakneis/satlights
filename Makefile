.PHONY: help run fmt lint test

help:
	@echo "Targets: run, fmt, lint, test"

run:
	python3 -m src.satlight.cli

fmt:
	python3 -m ruff format .

lint:
	python3 -m ruff check .
	python3 -m mypy src

test:
	python3 -m pytest
