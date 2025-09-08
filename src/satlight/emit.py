from __future__ import annotations

import time
from typing import Callable, List

from .config import AppConfig
from .visibility import visible_now
from .format import format_line
from . import sinks as _sinks
from .log import get_logger

"""
Emitter (DP-1.2.2)
- Every 10 s (cadence via monotonic clock):
  * Query visible_now (DP-1.1.2)
  * If any: format one line (DP-1.2.1) and fan out to sinks (C-6)
  * Errors in one sink do not block others; log to STDERR (C-5)
"""

_LOG = get_logger(__name__)
_PERIOD_SEC = 10.0


# This function emits the line to the outputs.
def _emit_to_outputs(outputs: List[str], line: str) -> None:
    for out in outputs:
        try:
            if out == "stdout":  # If the output is stdout, emit the line to the standard output.
                _sinks.stdout_sink(line)
            elif out.startswith("file:"):  # If the output is a file, emit the line to the file.
                path = out.split(":", 1)[1]
                _sinks.file_sink(path, line)
            elif out.startswith("tcp:"):  # If the output is a TCP, emit the line to the TCP.
                _, host, port_str = out.split(":", 2)
                _sinks.tcp_sink(host, int(port_str), line)
            else:
                # Should never happen because DP-1.1.1.2 validated outputs (C-6)
                _LOG.error("disallowed sink encountered at runtime: %s", out)
        except Exception as e:  # C-5: error to STDERR; continue with other sinks
            _LOG.error("sink failure for %s: %s", out, e)


# This function runs the main loop.
def run_forever(
    cfg: AppConfig,
    *,
    monotonic_fn: Callable[[], float] = time.monotonic,
    sleep_fn: Callable[[float], None] = time.sleep,
    now_fn: Callable[[], float] = time.time,
) -> None:
    """Main loop: maintain a ~10 s cadence (drift-free)."""
    while True:
        t0 = monotonic_fn()  # Get the start time.

        pairs = visible_now(
            cfg, now_fn=now_fn, mono_fn=monotonic_fn, max_fetches_per_tick=1
        )  # Get the satellite and color pairs from the visible_now function.
        if pairs:
            line = format_line(
                pairs
            )  # Format the pairs into a line using the format_line function.
            if line:  # If the line is not empty, emit the line to the outputs.
                _emit_to_outputs(cfg.outputs, line)

        elapsed = monotonic_fn() - t0  # Get the elapsed time.
        delay = _PERIOD_SEC - elapsed  # Get the delay.
        if delay > 0:  # If the delay is greater than 0, sleep for the delay.
            sleep_fn(delay)
        # If delay <= 0, skip sleep and immediately start next cycle


# This function runs the main loop once. This is useful for CLI --once and tests.
def run_once(
    cfg: AppConfig,
    *,
    monotonic_fn: Callable[[], float] = time.monotonic,
    sleep_fn: Callable[[float], None] = time.sleep,
    now_fn: Callable[[], float] = time.time,
    do_sleep: bool = True,
) -> None:
    """
    Single-tick helper (useful for CLI --once and tests).
    If do_sleep=False, executes one cycle without the final sleep.
    """
    t0 = monotonic_fn()

    pairs = visible_now(cfg, now_fn=now_fn, mono_fn=monotonic_fn, max_fetches_per_tick=1)
    if pairs:
        line = format_line(pairs)
        if line:
            _emit_to_outputs(cfg.outputs, line)

    elapsed = monotonic_fn() - t0
    delay = _PERIOD_SEC - elapsed
    if do_sleep and delay > 0:
        sleep_fn(delay)
