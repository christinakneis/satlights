# SatLight — one line every 10 seconds when satellites are overhead

A small CLI service that watches for specific satellites passing above your lab and emits **one command line** in the form of `NORAD_ID_0: color_0, NORAD_ID_1: color_1, .., NORAD_ID_N: color_N` every 10 s while any of them are "overhead".

## Outputs
- Example output line:  
  `25544: blue, 43013: teal`
- Output sinks (choose any/all): **STDOUT**, **file**, or **TCP**.
- All diagnostics/logs go to **STDERR** (never STDOUT).

## Inputs 
The only input to SatLight is a YAML configuration file (`config.yaml`) placed in the project root. See the configuration section below for more details 

## Design Method
This project follows the **IDT** decomposition of Customer Needs (CN) and Constraints (C) mapped to Functional Requirements (FR) > Design Parameters (DP). 

---

## How it works (quick)

1. **Config** (`config.yaml`) defines your lab location, the satellites to track (`NORAD_ID → color`), outputs, and an optional `min_elevation_deg`.
2. **API**: for each configured satellite, the service queries the public **sat.terrestre.ar** "passes" endpoint to get the **next pass window** (rise/culmination/set).
3. **Overhead rule** (design choice):
   - It is "overhead now" if `rise.utc_timestamp ≤ now ≤ set.utc_timestamp` **and**
     `culmination.alt ≥ min_elevation_deg`.
   - This uses the pass's **peak** elevation (not instantaneous elevation).
4. Every ~10 s the loop:
   - gathers the satellites that are "overhead now"
   - formats **one** line `"id: color, id: color, …"`
   - fans it out to the configured sinks  
   - sleeps the remainder of the 10 s period (drift-free cadence)

Politeness to the free API:
- Caches pass windows per satellite
- Only **one** satellite fetch per tick (round-robin)
- **Exponential backoff** with jitter after errors (e.g., 429/500)

---

## Constraints satisfied

- **C-1** Python ≥ 3.12 → uses **Python 3.13**
- **C-2** Type annotations → typed code + `mypy`
- **C-3** Unit tests → `pytest`
- **C-4** Docker used for containerization → `Dockerfile` + `docker-compose.yml`
- **C-5** Logging only to **STDERR** → app logs (incl. a 10 s heartbeat) do not use STDOUT
- **C-6** Outputs limited to STDOUT, file, or TCP → only these sinks are implemented

---

## Traceability

See the Traceability.md document to see the Functional Requirement Decomposition and tracability into Deisgn Parameters and testing.  

---

## Design Choices and Tradeoffs 


### 1) Public API & “overhead” definition
- **Choice:** Use `sat.terrestre.ar` per-satellite **passes** endpoint.  
  **Why:** Free, no key, simple JSON with `rise/culmination/set`.  
  **Tradeoff:** No “what’s overhead now?” discovery; you must pre-select NORAD IDs. Occasional 429/500s.  
  **Alternatives (later):** Use N2YO `/above` for discovery; or compute locally (Skyfield + TLEs) for zero external calls.

- **Choice:** “Overhead now” = `rise.utc_timestamp ≤ now ≤ set.utc_timestamp` **and** `culmination.alt ≥ min_elevation_deg`.  
  **Why:** Fast, easy to reason about; one call gives the pass window + peak elevation.  
  **Tradeoff:** Uses **peak** elevation to gate the whole pass, not instantaneous elevation at `now`. Slightly permissive near edges.  
  **Alternatives (later):** Use an API or local propagation to compute **instantaneous** elevation each tick.


### 2) Cadence & timing
- **Choice:** Drift-free **10 s** cadence using `time.monotonic()`; subtract work time each tick.  
  **Why:** Predictable loop that satisfies CN-1.3 precisely; immune to wall-clock jumps.  
  **Tradeoff:** If a tick is slow, the next tick may start immediately (sleep 0).  
  **Alternatives (later):** Cron/scheduler (less precise); async scheduling or job queues (more complexity).

- **Choice:** Fetch **one satellite per tick** (round-robin) with an **in-memory cache** of pass windows.  
  **Why:** Polite to the free API; smooths request rate; still converges across ticks.  
  **Tradeoff:** With many IDs, freshness updates spread across multiple ticks.  
  **Alternatives (later):** Raise per-tick budget; batch endpoints (if available); or local predictions.


### 3) Rate limits & resilience
- **Choice:** **Timeout (~5 s), one retry, exponential backoff** with jitter; treat failures as “not visible this tick.”  
  **Why:** Loop stays healthy; one bad call doesn’t block others (DP-1.2.2).  
  **Tradeoff:** During API issues you may miss a legitimate pass.  
  **Alternatives (later):** Multi-provider fallback; longer/persistent cache; circuit breaker.


### 4) Configuration & validation
- **Choice:** **YAML** config + **Pydantic** validation.  
  **Why:** Human-friendly file; strong schema errors early; normalized object for the app.  
  **Tradeoff:** Extra dependency; must keep schema/docs in sync.  
  **Alternatives (later):** JSON/TOML; env-only; hot-reload.

- **Choice:** `min_elevation_deg` default **10.0°** with `0 ≤ min ≤ 90`.  
  **Why:** Sensible horizon threshold; safe bounds.  
  **Tradeoff:** Labs may prefer a different default (overridable in config).


### 5) Output & logging (constraints-driven)
- **Choice:** Outputs limited to **STDOUT**, **file**, or **TCP**; validation rejects others (**C-6**).  
  **Why:** Exactly matches constraint and keeps interface simple.  
  **Tradeoff:** No MQTT/HTTP/webhooks.  
  **Alternatives (later, only if constraints change):** Pluggable sink system.

- **Choice:** **Logs only to STDERR** (**C-5**); STDOUT reserved **only** for the command line when sats are overhead.  
  **Why:** Clean separation of data vs diagnostics; predictable piping.  
  **Tradeoff:** No structured JSON logs to STDOUT.  
  **Alternatives (later):** Structured logs to STDERR; optional exporters (if constraints allow).

- **Choice:** **One line at most per tick**; stable format `"id: color, id: color"` sorted by ID.  
  **Why:** Deterministic, easy to parse and diff; downstream-friendly.  
  **Tradeoff:** No custom formatting per sink.  
  **Alternatives (later):** Configurable formatter (if needs emerge).


### 6) Simplicity of runtime model
- **Choice:** **Synchronous** Python; no threads/async.  
  **Why:** Minimal complexity; straightforward tests; reliable timing.  
  **Tradeoff:** Not maximally parallel; per-tick IO budget is limited.  
  **Alternatives (later):** `async` + `httpx`, threadpool for IO, or worker processes.


### 7) Packaging & operations
- **Choice:** **Docker** (`python:3.13-slim`), non-root user, `docker-compose` mounts `/app/config.yaml`.  
  **Why:** Reproducible, portable, one-command runs (CN-2/C-4).  
  **Tradeoff:** Image size/overhead vs pure host install.  
  **Alternatives (later):** Multi-stage builds to slim further; publish to a registry.

- **Choice:** **Makefile** targets for run/lint/test/docker/compose.  
  **Why:** Short, memorable commands; avoids long flags.  
  **Tradeoff:** Another layer of tooling (standard on dev machines).


### 8) Testing & quality
- **Choice:** **pytest** with HTTP mocking + time monkeypatch; **mypy**; **ruff**.  
  **Why:** Fast feedback; enforces C-2/C-3; keeps code consistent.  
  **Tradeoff:** Some boilerplate in tests and configs.  
  **Alternatives (later):** Coverage gates; property-based tests; mutation testing.


### 9) Scope boundaries (intentional “non-features”)
- **Not included (on purpose):** Instantaneous elevation, sunlit/visibility optics, TLE lifecycle, discovery of nearby IDs, fancy sinks, metrics/telemetry, persistent cache.  
  **Why:** Keep MVP minimal, testable, and constraint-true; ship a robust core first.  
  **Future options:** Each is a clear extension seam without rewriting the core.




---

## Configuration

Create `config.yaml` in the repo root (there's a `config.example.yaml` you can copy):

```yaml
lat: 37.8
lon: -122.4
min_elevation_deg: 20.0        # optional; default 10.0
satellites:
  25544: blue                  # ISS
  43013: teal                  # NOAA-20 / JPSS-1
  37849: purple                # Suomi NPP
outputs:
  - stdout
  - file:/out/passes.log
  # - tcp:127.0.0.1:9000       # optional TCP sink
```

### Config schema

- `lat`, `lon`: Your lab's coordinates (required)
- `satellites`: Map of `NORAD_ID → color` (required, non-empty)
- `outputs`: List of sinks (required, non-empty):
  - `stdout` → prints to standard output
  - `file:<path>` → appends to file (creates if missing)
  - `tcp:<host>:<port>` → sends over TCP connection
- `min_elevation_deg`: Minimum peak elevation in degrees (optional, default 10.0, range 0-90)

---

## Prerequisites

- **Python 3.13+** (for local development)
- **Docker** (for containerized deployment)
- **Make** (for convenient commands)

---

## Quick start

### Option 1: Docker (recommended)

```bash
# Copy example config and customize
cp config.example.yaml config.yaml

# Build and run
make up

# Watch the logs (STDERR diagnostics)
make logs-realtime

# See satellite commands (STDOUT)
make stdout-realtime

# Check output file
make read-outputfile
```

### Option 2: Local development

```bash
# Set up virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run tests
make test

# Run locally (with custom config)
make testrun ARGS="--config config.yaml --once"
```

---

## Makefile commands

### Development
- `make help` → show all available commands
- `make test` → run unit tests
- `make fmt` → format code with ruff
- `make lint` → check code with ruff + mypy
- `make run` → run locally (uses Docker default config path)
- `make testrun ARGS="..."` → run locally with custom arguments

### Docker operations
- `make docker-build` → build Docker image
- `make docker-run` → run containerized service (forever, background)
- `make docker-run-once` → run containerized service (single cycle)
- `make up` → start containerized service
- `make down` → stop service
- `make logs` → show container logs (STDOUT + STDERR)
- `make logs-realtime` → follow container logs in real-time
- `make logs-tail` → show last 100 container log lines
- `make stdout-realtime` → follow STDOUT (satellite commands) in real-time
- `make stdout-logs` → show last 100 STDOUT log lines

### Output management
- `make read-outputfile` → display contents of configured file output
- `make clean-outputfile` → remove configured file output
- `make down-clean` → stop service and clean output file

---

## Sample outputs

### STDOUT (satellite commands)
```
25544: blue, 43013: teal
25544: blue
43013: teal, 37849: purple
```

### STDERR (diagnostics/heartbeat)
```
2024-01-15 14:30:15 INFO satlight.emit: tick: sats=2, emitted=True, work=0.123s, sleep=9.877s
2024-01-15 14:30:25 INFO satlight.emit: tick: sats=1, emitted=True, work=0.098s, sleep=9.902s
2024-01-15 14:30:35 INFO satlight.emit: tick: sats=0, emitted=False, work=0.045s, sleep=9.955s
```

---

## Troubleshooting

### No satellites showing up?
- Check your `lat`/`lon` coordinates
- Verify `min_elevation_deg` isn't too high
- Look at container logs for API errors
- Try `make logs-tail` to see recent diagnostics

### API rate limiting (HTTP 429)?
- The service automatically handles this with exponential backoff
- Reduce the number of satellites in your config
- The round-robin system limits to 1 API call per 10s tick

### Container issues?
- Ensure Docker is running: `docker --version`
- Check container status: `docker compose ps`
- View all logs: `make logs`

### File output not working?
- Check file permissions in the `out/` directory
- Verify the path in your config exists
- Use `make read-outputfile` to check the configured file

---

## Architecture

The service follows a clean separation of concerns:

- **`cli.py`** → Command-line interface and argument parsing
- **`config.py`** → YAML loading and Pydantic validation
- **`api.py`** → HTTP client for satellite pass data
- **`visibility.py`** → Core logic: determine which satellites are overhead
- **`format.py`** → Convert satellite list to command line string
- **`emit.py`** → 10-second loop with drift-free timing
- **`sinks.py`** → Output implementations (STDOUT, file, TCP)
- **`log.py`** → STDERR-only logging setup

---

## Testing

The test suite covers all major functionality:

```bash
make test
```

Key test areas:
- Config validation (lat/lon bounds, output formats, satellite mapping)
- API client (timeouts, retries, error handling)
- Visibility logic (time windows, elevation filtering, caching)
- Emitter timing (10s cadence, drift compensation)
- Output sinks (STDOUT, file append, TCP)

---

## License

This project is part of a technical challenge/assessment.