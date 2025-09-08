# Design Traceability 


## FR/DP Decomposition

### FR-1: To control the lab lighting behavior based on real-time satellite passes. *(CN-1, C-6)*
- **FR-1.1** To decide which configured satellites are “overhead” according to the referenced API and the lab's location *(CN-1.1, CN-1.2)*
  - **FR-1.1.1** To read and check the config file (get lab lat/lon, the {NORAD_ID: color} list, the outputs list, and the minimum elevation if provided). *(CN-1.2)*
    - **FR-1.1.1.1** To load and parse the config file into raw data. *(CN-1.2)*
    - **FR-1.1.1.2** To validate and normalize the config into a structured object. *(CN-1.2)*
  - **FR-1.1.2** To ask a public satellite API which of the satellites that fit our configured IDs are visible now at the lab’s configured location and filtered by min elevation if provided in the config. *(CN-1.1, CN-1.2)*
    - **FR-1.1.2.1** To fetch pass prediction data for each configured satellite. *(CN-1.1)*
    - **FR-1.1.2.2** To filter passes by configured minimum elevation. *(CN-1.1, CN-1.2)*
    - **FR-1.1.2.3** To output the list of visible configured satellites with their colors. *(CN-1.1, CN-1.2)*
- **FR-1.2** To emit a single command line every 10 s to all configured outputs when any satellites are overhead. *(CN-1.3, C-6)*
  - **FR-1.2.1** To build one command line `"NORAD_ID: color, ..."` from the overhead satellites. *(CN-1.3.2)*
  - **FR-1.2.2** To every 10 s, if any satellites are overhead, send that one line to all chosen outputs (STDOUT, file, or TCP); if none are overhead, send nothing. *(CN-1.3, CN-1.3.1, C-6)*

**DP-1:** A CLI service that reads a config, checks passes, decides who’s overhead, and emits a single line every 10s when anyone is overhead. *(CN-1, C-6)*  
- **DP-1.1:** A visibility module that outputs overhead satellite *(id, color)* pairs given the config + API. *(CN-1.1, CN-1.2)*
  - **DP-1.1.1:** A config reader that validates fields and outputs *(lat, lon)*, the set of configured NORAD IDs, the color map, and an elevation filter. *(CN-1.2)*
    - **DP-1.1.1.1:** Use `yaml.safe_load(open("config.yaml"))` from PyYAML to return a Python dict.
    - **DP-1.1.1.2:** Use a Pydantic model that enforces ranges and types, returning a model instance with *(lat, lon)*, `{norad_id → color}`, `[outputs]`, and `min_elevation_deg` *(default 10.0, 0 ≤ min_elevation_deg ≤ 90)*. Validate `satellites` is a non-empty dict of positive-int keys and non-empty string colors; validate each output is exactly `stdout` or `file:<path>` or `tcp:<host>:<port>`. *(CN-1.2)*
  - **DP-1.1.2:** An API provider that takes *(lat, lon, configured_ids, color_map, min_elevation_deg)* and returns the list of visible/overhead *(id, color)* pairs according to the API’s rule and the configured `min_elevation_deg`. *(CN-1.1, CN-1.2)*
    - **DP-1.1.2.1:** Use Python `requests` to call the Satellite Passes API at **sat.terrestre.ar** for each id in `configured_ids`:  
      `GET https://sat.terrestre.ar/passes/{id}?lat=<lat>&lon=<lon>&limit=1` with a ~5s timeout and one retry. On error, treat that satellite as not visible for this tick and log the error to STDERR. The response is a JSON array; each pass includes `rise`, `culmination`, and `set` objects with `utc_timestamp` fields and altitude strings (`alt`) in degrees, plus top-level `visible` and `norad_id`. *(CN-1.1)*
    - **DP-1.1.2.2:** Read `min_elevation_deg` from the validated config produced by **DP-1.1.1.2**. For each satellite pass object returned by **DP-1.1.2.1**, parse altitude strings to floats and decide “overhead now” as follows: compute `now_utc = int(time.time())`; check the time window `rise.utc_timestamp ≤ now_utc ≤ set.utc_timestamp`; then apply the pass elevation filter `culmination.alt ≥ min_elevation_deg`. If both are true, include this satellite; otherwise exclude it. *(CN-1.1, CN-1.2)*
    - **DP-1.1.2.3:** Collect satellites that pass the checks into a list of *(id, color)* pairs by looking up colors from the config map; return `list[(int, str)]`. *(CN-1.1, CN-1.2)*
- **DP-1.2:** A timed emitter that, every 10 s, formats one line with the overhead satellites and their colors and sends it to the chosen outputs (STDOUT, file, or TCP). *(CN-1.3, C-6)*
  - **DP-1.2.1:** A formatter that takes the list of *(id, color)* pairs from **DP-1.1.2** (and uses the stable color map validated in **DP-1.1.1**), sorts by ascending id for stability, and joins into a single one-line string: `"{id}: {color}, {id}: {color}, ..."`. Return `""` (empty string) if the list is empty. *(CN-1.3.2)*
  - **DP-1.2.2:** A module that maintains a steady 10 s cadence using a monotonic clock and subtracts elapsed work time each cycle: start tick with `t0 = time.monotonic()`; call **DP-1.1.2** to get the current *(id, color)* list; if empty, do nothing this tick; if non-empty, pass to **DP-1.2.1** to build the one command line, then send that line to the configured sinks (STDOUT, file append, TCP); compute `elapsed = time.monotonic() - t0` and `sleep(max(0, 10 - elapsed))`. If `elapsed ≥ 10`, sleep 0 and immediately start the next tick. Failures in one sink do not block others; errors go to STDERR. Only these sinks are allowed. *(CN-1.3, CN-1.3.1, C-6)*

---

### FR-2: To provide ease of installation and interaction for end user *(CN-2, C-4)*
- **FR-2.1** To containerize the service for portability. *(CN-2.1, C-4)*
  - **FR-2.1.1** To provide a Dockerfile deliverable. *(CN-2.1.1, C-4)*
  - **FR-2.1.2** To provide a docker-compose.yml deliverable. *(CN-2.1.2, C-4)*
- **FR-2.2** To make the service easy to run and understand. *(CN-2.2)*
  - **FR-2.2.1** To ship a Makefile with one-command tasks. *(CN-2.2.1)*
  - **FR-2.2.2** To ship a README.md explaining how to run it. *(CN-2.2.2)*

**DP-2:** A containerization of the CLI service (**DP-1**) with one-command run paths (Make + Compose) that expects a mounted `/app/config.yaml` by default. *(CN-2, C-4)*  
- **DP-2.1** Docker containerization files *(CN-2.1, C-4)*
  - **DP-2.1.1** Dockerfile (Python 3.13, non-root): base `python:3.13-slim`; `WORKDIR /app`; copy `requirements.txt` → `pip install`; copy `src/` and `config.example.yaml`; `ENV PYTHONUNBUFFERED=1 PYTHONPATH=/app/src`; create user `10001`; `ENTRYPOINT ["python","-m","satlight","--config","/app/config.yaml"]`. *(CN-2.1.1, C-1, C-4)*
  - **DP-2.1.2** `docker-compose.yml`: `build: .`; `volumes: ["./config.yaml:/app/config.yaml:ro"]` (and optionally `./out:/out`); optional env; optional restart policy. *(CN-2.1.2, C-4)*
- **DP-2.2** Interaction artifacts *(CN-2.2)*
  - **DP-2.2.1** Makefile with targets: `run`, `docker-build`, `docker-run` (mount config + out), `up`, `down`, `logs`, `fmt`, `lint`, `test`. *(CN-2.2.1)*
  - **DP-2.2.2** README.md with prerequisites; config schema; examples for local/Docker/Compose; sample outputs; troubleshooting (logs to STDERR). *(CN-2.2.2)*

---

### FR-3: To document, test, and easily debug codebase *(CN-3, C-1, C-2, C-3, C-5)*
- **FR-3.1** To make the code readable and visible (docs and comments). *(CN-3.1)*
- **FR-3.2** To validate behavior with unit tests. *(CN-3.2, C-3)*
- **FR-3.3** To ensure static typing and type-checked code. *(CN-3.3, C-2)*
- **FR-3.4** To enforce consistent style and linting. *(CN-3.1)*

**DP-3:** A lightweight quality toolchain: pytest for tests, type hints + mypy for static checks, ruff for format/lint, and a logging setup that writes only to STDERR. *(CN-3, C-1, C-2, C-3)*  
- **DP-3.1** Aggressive documentation approach. *(CN-3.1)*
  - **DP-3.1.1** Inline comments for each section of code. *(CN-3.1)*
  - **DP-3.1.2** Add module/class/function docstrings describing purpose, inputs/outputs, side effects. *(CN-3.1)*
- **DP-3.2** Unit testing with pytest for all of FR-1 (see tests). Use `responses` to mock HTTP and `monkeypatch` to simulate time. *(CN-3.2, C-3)*
- **DP-3.3** Static typing with mypy. *(CN-3.3, C-2)*
  - **DP-3.3.1** Add type hints across public functions/models (e.g., `dict[int, str]`, `list[tuple[int, str]]`). *(C-2)*
  - **DP-3.3.2** Configure mypy in `pyproject.toml` (`python_version=3.13`, `disallow_untyped_defs=true` for `src/`). *(C-2)*
  - **DP-3.3.3** Makefile `lint` target runs `ruff check .` and `mypy src`. *(C-2)*
- **DP-3.4** Style and lint with ruff. *(CN-3.1)*
  - **DP-3.4.1** Use ruff for format and lint; set `line-length` and `target-version=py313` in `pyproject.toml`. *(CN-3.1)*
  - **DP-3.4.2** Makefile `fmt` → `ruff format .`; `lint` → `ruff check . && mypy src`. *(CN-3.1)*

---


## Testing Traceability 

### A) FR 1 (service application) Decomposition Verification

| Artifact | Verification method | Evidence (tests / checks) |
|---|---|---|
| **FR-1** Control behavior by real-time passes | Unit tests (end-to-end behavior) | `test_FR_1__emits_line_to_all_sinks_when_any_overhead` (also C-6), `test_FR_1__no_output_when_no_overhead` |
| **FR-1.1** Decide which configured sats are “overhead” | Unit tests | `test_FR_1_1__visible_now_returns_only_configured_ids_with_min_elev_applied` |
| **FR-1.1.1** Read & check config | Unit tests | `test_FR_1_1_1__loader_and_validator_produce_structured_config` (also enforces outputs; C-6) |
| **FR-1.1.1.1** Load/parse YAML | Unit tests | `test_FR_1_1_1_1__loads_valid_yaml_to_dict`, `test_FR_1_1_1_1__malformed_yaml_raises_clear_error`, `test_FR_1_1_1_1__missing_config_file_raises_clear_error` |
| **FR-1.1.1.2** Validate/normalize config | Unit tests | `test_FR_1_1_1_2__validates_lat_lon_bounds_and_defaults_min_elev_10`, `test_FR_1_1_1_2__rejects_disallowed_output_sinks` (C-6) |
| **FR-1.1.2** Ask public API & filter | Unit tests | `test_FR_1_1_2__integrates_fetch_filter_and_maps_to_pairs` |
| **FR-1.1.2.1** Fetch pass prediction per sat | Unit tests (HTTP mocked) | `test_FR_1_1_2_1__calls_passes_endpoint_per_id_with_timeout_and_retry`, `test_FR_1_1_2_1__api_error_results_in_not_visible_and_logs_error` (C-5) |
| **FR-1.1.2.2** Filter by min elevation + time window | Unit tests | `test_FR_1_1_2_2__includes_inside_window_and_peak_ge_min`, `test_FR_1_1_2_2__excludes_if_peak_below_min_even_when_inside_window`, `test_FR_1_1_2_2__includes_exactly_at_rise_and_set_edges` |
| **FR-1.1.2.3** Output visible configured sats w/ colors | Unit tests | `test_FR_1_1_2_3__maps_ids_to_configured_colors_and_returns_list_of_pairs` |
| **FR-1.2** Emit one line per 10 s when any are overhead | Unit tests | `test_FR_1_2__one_line_per_tick_when_overhead_else_silent` (C-6) |
| **FR-1.2.1** Build `"NORAD_ID: color, ..."` | Unit tests | `test_FR_1_2_1__sorts_by_id_and_formats_single_line`, `test_FR_1_2_1__empty_input_returns_empty_string` |
| **FR-1.2.2** 10 s cadence & fan-out to sinks | Unit tests | `test_FR_1_2_2__cadence_subtracts_elapsed_time_for_10s_period`, `test_FR_1_2_2__fanout_writes_to_all_configured_sinks_once` (C-6), `test_FR_1_2_2__sink_failure_isolated_and_error_logged` (C-6, C-5) |
| **DP-1** CLI service | Manual/CLI check | `python -m satlight.cli --config ./config.yaml --once` produces either one line or nothing w/o errors |
| **DP-1.1** Visibility module | Covered by FR-1.1/1.1.2 tests | See tests above under FR-1.1 and FR-1.1.2 |
| **DP-1.2** Timed emitter + sinks | Covered by FR-1.2 tests | See tests above under FR-1.2 |

> All FR-1 sub-items are backed by executable pytest cases with mocked HTTP and time control.

---

### B) FR-2 (Install/Interaction) Decomposition Verification


| Artifact | Verification method | Evidence (checks / commands) |
|---|---|---|
| **FR-2.1.1** Dockerfile deliverable | Build succeeds | `docker build -t satlight:dev .` (also via `make docker-build`) |
| **FR-2.1.2** docker-compose.yml deliverable | Compose up works | `make up` starts service; `make logs` shows 10 s heartbeat (STDERR) |
| **FR-2.2.1** Makefile tasks | Commands exist & run | `make run / fmt / lint / test / docker-build / docker-run / up / down / logs` |
| **FR-2.2.2** README.md | Manual review | README is present and explains config, run modes, outputs, troubleshooting |

---

### C) FR-2 FR-3 (Docs/Tests/Typing/Lint) Decomposition Verification

| Artifact | Verification method | Evidence |
|---|---|---|
| **FR-3.1** Docs & comments | Manual/code review | Docstrings and inline comments in modules; README present |
| **FR-3.2** Unit tests | Automated | `make test` (CI: `pytest`) passes |
| **FR-3.3** Static typing | Automated | `make lint` runs `mypy src` (passes); `pyproject.toml` sets `python_version=3.13`, `disallow_untyped_defs=true` |
| **FR-3.4** Style & lint | Automated | `make fmt` (`ruff format`) and `make lint` (`ruff check`) pass cleanly |

---

### D) Constraints (C-1 … C-6)Verification


| Constraint | What it means here | Verification |
|---|---|---|
| **C-1** Python ≥ 3.12 | Project targets Python **3.13** | Dockerfile uses `python:3.13-slim`; `pyproject.toml` `python_version=3.13` |
| **C-2** Type annotations | Public functions/models typed; static checks | `mypy` passes via `make lint`; hints across code (`dict[int, str]`, `list[tuple[int,str]]`, etc.) |
| **C-3** Pytest for unit tests | Tests exist and run | `make test` passes; CI runs `pytest` |
| **C-4** Docker containerization | Shippable container & compose | Dockerfile + `docker-compose.yml`; `make docker-build`, `make up` succeed |
| **C-5** Logs only to **STDERR** | No logs on STDOUT; errors/info on STDERR | Tests: `test_FR_1_1_2_1__api_error_results_in_not_visible_and_logs_error`, `test_FR_1_2_2__sink_failure_isolated_and_error_logged`; code routes logging to STDERR |
| **C-6** Outputs limited (STDOUT/file/TCP) | Only these sinks; invalid rejected | Tests: `test_FR_1_1_1_2__rejects_disallowed_output_sinks`, `test_FR_1_2_2__fanout_writes_to_all_configured_sinks_once`; sinks implemented are `stdout`, `file`, `tcp` only |

---

## E) How to show evidence quickly

- **Run unit tests (FR-1, FR-3.2):** `make test -s -v`
- **Typing & lint (FR-3.3/3.4):** `make fmt && make lint`
- **Local CLI smoke (DP-1):** `PYTHONPATH=src python -m satlight.cli --config ./config.yaml --once`
- **Docker build (FR-2.1.1/C-4):** `make docker-build`
- **Compose run + logs (FR-2.1.2/C-4):** `make up` then `make logs` (heartbeat every ~10 s)
- **Output sinks (C-6):** enable `file:/out/passes.log` in `config.yaml`, then `tail -f out/passes.log`

> **Interpretation:** Silence on STDOUT usually just means “no satellites overhead this tick.” Errors/rate limits appear on **STDERR** and do not break the 10 s cadence.
