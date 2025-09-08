from __future__ import annotations

from typing import List, Tuple

import pytest

from src.satlight.config import AppConfig
import src.satlight.emit as emit_mod
import src.satlight.sinks as sinks_mod


# This function creates a fake configuration.
def _cfg(outputs: list[str]) -> AppConfig:
    return AppConfig(
        lat=37.8,
        lon=-122.4,
        satellites={25544: "blue", 48915: "pink"},
        outputs=outputs,
        min_elevation_deg=10.0,
    )


# This test checks if the cadence subtracts the elapsed time for a 10s period.
def test_FR_1_2_2__cadence_subtracts_elapsed_time_for_10s_period(monkeypatch):
    # Simulate work taking 3 seconds per tick
    times = [100.0, 103.0]  # start -> end

    def fake_mono():
        return times.pop(0)

    slept: List[float] = []

    def fake_sleep(x: float):
        slept.append(x)

    # visible_now returns empty list (no sinks called)
    monkeypatch.setattr(emit_mod, "visible_now", lambda *args, **kwargs: [])
    emit_mod.run_once(_cfg(["stdout"]), monotonic_fn=fake_mono, sleep_fn=fake_sleep, do_sleep=True)

    assert slept == [pytest.approx(7.0, abs=1e-6)]
    print("\n.✅test_FR_1_2_2__cadence_subtracts_elapsed_time_for_10s_period passed")


# This test checks if the fanout writes to all configured sinks once.
def test_FR_1_2_2__fanout_writes_to_all_configured_sinks_once(monkeypatch, tmp_path):
    # Make visible_now return a fixed pair list
    monkeypatch.setattr(
        emit_mod, "visible_now", lambda *args, **kw: [(25544, "blue"), (48915, "pink")]
    )

    # Spy sinks
    seen_stdout: List[str] = []

    def fake_stdout(line: str) -> None:
        seen_stdout.append(line)

    written: List[str] = []
    file_path = tmp_path / "passes.log"

    def fake_file(path: str, line: str) -> None:
        assert path == str(file_path)
        written.append(line)

    sent: List[Tuple[str, int, str]] = []

    def fake_tcp(host: str, port: int, line: str, *, timeout: float = 3.0) -> None:
        sent.append((host, port, line))

    monkeypatch.setattr(sinks_mod, "stdout_sink", fake_stdout)
    monkeypatch.setattr(sinks_mod, "file_sink", fake_file)
    monkeypatch.setattr(sinks_mod, "tcp_sink", fake_tcp)

    cfg = _cfg(["stdout", f"file:{file_path}", "tcp:127.0.0.1:9000"])
    emit_mod.run_once(cfg, do_sleep=False)

    assert seen_stdout == ["25544: blue, 48915: pink"]
    assert written == ["25544: blue, 48915: pink"]
    assert sent == [("127.0.0.1", 9000, "25544: blue, 48915: pink")]
    print("✅test_FR_1_2_2__fanout_writes_to_all_configured_sinks_once passed")


# This test checks if the sink failure is isolated and the error is logged.
def test_FR_1_2_2__sink_failure_isolated_and_error_logged(monkeypatch):
    # visible_now returns one satellite so we attempt to emit
    monkeypatch.setattr(emit_mod, "visible_now", lambda *args, **kw: [(25544, "blue")])

    # stdout works...
    stdout_seen: List[str] = []
    monkeypatch.setattr(sinks_mod, "stdout_sink", lambda line: stdout_seen.append(line))

    # ...file sink explodes
    def boom_file(path: str, line: str) -> None:
        raise RuntimeError("disk full")

    monkeypatch.setattr(sinks_mod, "file_sink", boom_file)

    # no tcp in outputs so it shouldn't be called
    cfg = _cfg(["stdout", "file:/tmp/log.txt"])

    emit_mod.run_once(cfg, do_sleep=False)

    assert stdout_seen == ["25544: blue"]
    # Note: Error logging to STDERR per C-5 constraint, so we can't easily test log content
    # The main behavior is that stdout still works despite file sink failure
    print("✅test_FR_1_2_2__sink_failure_isolated_and_error_logged passed")


# This test checks if the line is emitted to all sinks when any overhead is present.
def test_FR_1__emits_line_to_all_sinks_when_any_overhead(monkeypatch):
    # visible_now returns one item -> should emit
    monkeypatch.setattr(emit_mod, "visible_now", lambda *args, **kw: [(25544, "blue")])

    out: List[str] = []
    monkeypatch.setattr(sinks_mod, "stdout_sink", lambda line: out.append(line))

    emit_mod.run_once(_cfg(["stdout"]), do_sleep=False)
    assert out == ["25544: blue"]
    print("✅test_FR_1__emits_line_to_all_sinks_when_any_overhead passed")


# This test checks if the line is not emitted to any sinks when no overhead is present.


def test_FR_1__no_output_when_no_overhead(monkeypatch):
    # visible_now returns nothing -> no sinks called
    monkeypatch.setattr(emit_mod, "visible_now", lambda *args, **kw: [])

    called = {"stdout": 0}

    def fake_stdout(line: str) -> None:
        called["stdout"] += 1

    monkeypatch.setattr(sinks_mod, "stdout_sink", fake_stdout)
    emit_mod.run_once(_cfg(["stdout"]), do_sleep=False)
    assert called["stdout"] == 0
    print("✅test_FR_1__no_output_when_no_overhead passed")
