.PHONY: help run fmt lint test docker-build docker-run up down down-clean errlogs-realtime errlogs-tail stdout-realtime stdout-logs read-outputfile clean-outputfile

help:
	@echo "Targets: run, fmt, lint, test, docker-build, docker-run, up, down, down-clean, errlogs-realtime, errlogs-tail, stdout-realtime, stdout-logs, read-outputfile, clean-outputfile"

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

# ------------------------------------------------------------
# --- Docker / Compose helpers ---
# ------------------------------------------------------------

# Name and tag of the image from the docker-compose.yml
IMAGE ?= satlight:dev # can set IMAGE=satlight:ops for ops version later if needed.

docker-build:
	docker build -t $(IMAGE) .

# Runs forever by default 
docker-run: | out 		# out is a helper to create the out directory if it doesn't exist.
	docker run --rm -it \
	  -v $(PWD)/config.yaml:/app/config.yaml:ro \
	  -v $(PWD)/out:/out \
	  $(IMAGE) \
	  &  # run in background

# Runs one cycle by default (adds --once).
docker-run-once: | out
	docker run --rm -it \
	  -v $(PWD)/config.yaml:/app/config.yaml:ro \
	  -v $(PWD)/out:/out \
	  $(IMAGE) --once

# Starts the container in the background and runs forever.
up: | out
	docker compose up --build -d

# Stops the container.
down:
	docker compose down

# Stops the container and cleans the output file
down-clean: down clean-outputfile

# Creates the out directory if it doesn't exist.
out:
	mkdir -p out
	chmod 777 out


# --- Docker log and output helpers -----------

# Shows the logs (STDERR error messages) of the current running container. -f follows the logs in realtime 
logs:
	docker compose logs

logs-realtime:
	docker compose logs -f 

# Shows the last 100 lines of the logs (STDERR error messages) of the current running container.
logs-tail:
	docker compose logs --tail 100

# Shows the logs (STDOUT output messages) of the current running container.
stdout-realtime:
	@echo "Following STDOUT from Docker container in real-time..."
	@echo "Press Ctrl+C to stop"
	@CONTAINER_ID=$$(docker compose ps -q); \
	if [ -n "$$CONTAINER_ID" ]; then \
		docker logs -f "$$CONTAINER_ID" 2>/dev/null; \
	else \
		echo "No running container found. Run 'make up' first."; \
	fi

# Shows historical STDOUT logs (last 100 lines, no real-time following)
stdout-logs:
	@echo "Showing historical STDOUT logs..."
	@CONTAINER_ID=$$(docker compose ps -q); \
	if [ -n "$$CONTAINER_ID" ]; then \
		docker logs --tail 100 "$$CONTAINER_ID" 2>/dev/null; \
	else \
		echo "No running container found. Run 'make up' first."; \
	fi


# Reads the output file from config.yaml and displays the contents from within the container.
read-outputfile:
	@echo "Reading output file from within Docker container..."
	@CONTAINER_ID=$$(docker compose ps -q); \
	if [ -n "$$CONTAINER_ID" ]; then \
		OUTPUT_FILE=$$(grep -E "^\s*-\s*\"file:" config.yaml | sed 's/.*"file://' | sed 's/".*//' | head -1); \
		if [ -n "$$OUTPUT_FILE" ]; then \
			echo "Output file: $$OUTPUT_FILE"; \
			echo "--- File contents from container ---"; \
			docker exec "$$CONTAINER_ID" cat "$$OUTPUT_FILE" 2>/dev/null || echo "File does not exist yet in container: $$OUTPUT_FILE"; \
		else \
			echo "No file output found in config.yaml"; \
		fi; \
	else \
		echo "No running container found. Run 'make up' first."; \
	fi

clean-outputfile:
	@echo "Cleaning output file from config.yaml..."
	@OUTPUT_FILE=$$(grep -E "^\s*-\s*\"file:" config.yaml | sed 's/.*"file://' | sed 's/".*//' | head -1); \
	if [ -n "$$OUTPUT_FILE" ]; then \
		echo "Removing: $$OUTPUT_FILE"; \
		if [ -f "$$OUTPUT_FILE" ]; then \
			rm "$$OUTPUT_FILE"; \
			echo "File removed successfully"; \
		else \
			echo "File does not exist: $$OUTPUT_FILE"; \
		fi; \
	else \
		echo "No file output found in config.yaml"; \
	fi
