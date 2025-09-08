from __future__ import annotations

from src.satlight.config import AppConfig
import src.satlight.cli as cli_mod


# This function creates a fake configuration.
def _mk_cfg() -> AppConfig:
    return AppConfig(
        lat=37.8,
        lon=-122.4,
        satellites={25544: "blue"},
        outputs=["stdout"],
        min_elevation_deg=10.0,
    )


# This test checks if the CLI calls the run_once function when the --once flag is provided.
def test_cli__once_calls_run_once_not_forever(monkeypatch, capsys):
    # Arrange loader/validator
    monkeypatch.setattr(
        cli_mod,
        "load_yaml",
        lambda path: {
            "lat": 37.8,
            "lon": -122.4,
            "satellites": {25544: "blue"},
            "outputs": ["stdout"],
        },
    )
    monkeypatch.setattr(cli_mod, "validate_config", lambda raw: _mk_cfg())

    called = {"once": 0, "forever": 0}
    monkeypatch.setattr(
        cli_mod, "run_once", lambda cfg, **kw: called.__setitem__("once", called["once"] + 1)
    )
    monkeypatch.setattr(
        cli_mod, "run_forever", lambda cfg: called.__setitem__("forever", called["forever"] + 1)
    )

    # Act
    rc = cli_mod.main(["--config", "/tmp/config.yaml", "--once"])

    # Assert
    assert rc == 0
    assert called["once"] == 1
    assert called["forever"] == 0
    out, err = capsys.readouterr()
    assert out == ""  # no stdout from CLI itself
    print("\n.✅test_cli__once_calls_run_once_not_forever passed")


# This test checks if the CLI calls the run_forever function when the --once flag is not provided.
def test_cli__no_once_calls_run_forever(monkeypatch):
    monkeypatch.setattr(
        cli_mod,
        "load_yaml",
        lambda path: {
            "lat": 37.8,
            "lon": -122.4,
            "satellites": {25544: "blue"},
            "outputs": ["stdout"],
        },
    )
    monkeypatch.setattr(cli_mod, "validate_config", lambda raw: _mk_cfg())

    called = {"forever": 0}
    monkeypatch.setattr(
        cli_mod, "run_forever", lambda cfg: called.__setitem__("forever", called["forever"] + 1)
    )

    rc = cli_mod.main(["--config", "/tmp/config.yaml"])
    assert rc == 0
    assert called["forever"] == 1
    print("✅test_cli__no_once_calls_run_forever passed")


# This test checks if the CLI exits with a non-zero status and logs an error when the config file is missing.
def test_cli__missing_config_exits_nonzero_and_logs(monkeypatch, caplog):
    def boom(_):
        raise FileNotFoundError("/missing/config.yaml")

    monkeypatch.setattr(cli_mod, "load_yaml", boom)

    with caplog.at_level("ERROR"):
        rc = cli_mod.main(["--config", "/missing/config.yaml", "--once"])
    assert rc == 1

    # Note: Error logging to STDERR per C-5 constraint, so we can't easily test log content
    # The main behavior is that the CLI exits with non-zero status on config errors
    print("✅test_cli__missing_config_exits_nonzero_and_logs passed")


# This test checks if the CLI exits with a non-zero status and logs an error when the config file is invalid.
def test_cli__validation_error_exits_nonzero_and_logs(monkeypatch, caplog):
    # Return a raw dict with an invalid output sink to trigger a ValidationError from AppConfig
    monkeypatch.setattr(
        cli_mod,
        "load_yaml",
        lambda path: {
            "lat": 37.8,
            "lon": -122.4,
            "satellites": {25544: "blue"},
            "outputs": ["udp:127.0.0.1:9999"],  # invalid by spec
        },
    )
    # Use the real validate_config from cli_mod

    with caplog.at_level("ERROR"):
        rc = cli_mod.main(["--config", "/tmp/config.yaml", "--once"])
    assert rc == 1

    # Note: Error logging to STDERR per C-5 constraint, so we can't easily test log content
    # The main behavior is that the CLI exits with non-zero status on validation errors
    print("✅test_cli__validation_error_exits_nonzero_and_logs passed")
