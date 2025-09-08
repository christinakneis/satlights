.PHONY: help run fmt lint test

help:
	@echo "Targets: run, fmt, lint, test"

# Run the CLI, assuming config.yaml is in the current directory.
run: 
	PYTHONPATH=src python3 -m satlight.cli --config config.yaml

testrun: 
	PYTHONPATH=src python3 -m satlight.cli $(ARGS)      # can do > make testrun ARGS="--config config.example.yaml --once"


fmt:
	python3 -m ruff format .

lint:
	python3 -m ruff check .
	python3 -m mypy src

test:
	python3 -m pytest $(ARGS) 		# can type make test ARGS="-s -v" for more verbose output
