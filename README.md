# 🛰️🚨 SatLight — one line every 10 seconds when satellites are overhead

A small CLI service that watches for specific satellites passing above your lab and emits **one command line** in the form of `NORAD_ID_0: color_0, NORAD_ID_1: color_1, .., NORAD_ID_N: color_N` every 10 s while any of them are "overhead".

## 📤 Outputs
- Example output line:  
  `25544: blue, 43013: teal`
- Output sinks (choose any/all): **STDOUT**, **file**, or **TCP**.
- All diagnostics/logs go to **STDERR** (never STDOUT).

## 📥 Inputs 
The only input to SatLight is a YAML configuration file (`config.yaml`) placed in the project root. See the configuration section below for more details 

---

## ✨ How it works (quick)

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

## 👩‍🎨 Design Method
This project follows the **Innovative Design Theory (IDT)** decomposition of Customer Needs (CN) and Constraints (C) mapped to Functional Requirements (FR) > Design Parameters (DP). See the TRACEABILITY.md document for more details.  

---

## 🚧 Constraints satisfied

See the TRACEABILITY.md document to see the the list of constraints satisfied and how they are verified. 

---

## ⚙️ Functional Requirements and Design Parameters 

See the TRACEABILITY.md document to see the Functional Requirement Decomposition and mapping to Deisgn Parameters. 

---

## 🫆 Traceability

See the TRACEABILITY.md document to see how Functional Requirement and Constraint Compliance are traced into testing of design parameters.  

---

## ⚖️ Design Choices and Tradeoffs 

See the TRACEABILITY.md document to see how Design Choices were made and Tradeoffs were assessed. 

---

## 📝 Configuration

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

## 🌱 Prerequisites

- **Python 3.13+** (for local development)
- **Docker** (for containerized deployment)
- **Make** (for convenient commands)

---

## 🚀 Quick start

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

## ▶️ Makefile commands

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

## 📦 Sample outputs

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

## 🤔 Troubleshooting

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

## 🏛️ Architecture

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

## 🧪 Testing

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

See the TRACEABILITY.md document for more details on which unit tests were used to verify each functionality. 

---

## 🪪 License

This project is part of a technical challenge/assessment.