.PHONY: help run fmt lint test docker-build docker-run up down logs

help:
	@echo "Targets: run, fmt, lint, test, docker-build, docker-run, up, down, logs"

# Run the CLI assuming config.yaml is in the current directory (uses CLI default /app/config.yaml for containers)
run: 
	PYTHONPATH=src python3 -m satlight.cli

testrun: 
	PYTHONPATH=src python3 -m satlight.cli $(ARGS)      # can do > make testrun ARGS="--config config.example.yaml --once"


fmt:
	python3 -m ruff format .

lint:
	python3 -m ruff check .
	python3 -m mypy src

test:
	python3 -m pytest $(ARGS) 		# can type make test ARGS="-s -v" for more verbose output

# --- Docker / Compose helpers ---
# Name and tag of the image from the docker-compose.yml
IMAGE ?= satlight:dev # can set IMAGE=satlight:ops for ops version later if needed.

docker-build:
	docker build -t $(IMAGE) .

# Runs one cycle by default (adds --once). Remove it to run forever.
docker-run: | out
	docker run --rm -it \
	  -v $(PWD)/config.yaml:/app/config.yaml:ro \
	  -v $(PWD)/out:/out \
	  $(IMAGE) --once

up: | out
	docker compose up --build -d

down:
	docker compose down

logs:
	docker compose logs -f

out:
	mkdir -p out
	chmod 777 out
