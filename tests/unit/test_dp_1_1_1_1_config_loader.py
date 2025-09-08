import yaml
import pytest

from src.satlight.config import load_yaml


def test_FR_1_1_1_1__loads_valid_yaml_to_dict(tmp_path):
    p = tmp_path / "config.yaml"
    p.write_text("lat: 37.8\nlon: -122.4\nsatellites:\n  25544: blue\noutputs:\n  - stdout\n", encoding="utf-8")
    data = load_yaml(str(p))
    assert isinstance(data, dict)
    assert data["lat"] == 37.8
    assert data["lon"] == -122.4
    assert data["satellites"] == {25544: "blue"}
    assert data["outputs"] == ["stdout"]


def test_FR_1_1_1_1__malformed_yaml_raises_clear_error(tmp_path):
    p = tmp_path / "bad.yaml"
    p.write_text("lat: 37.8\nlon: [broken\n", encoding="utf-8")  # missing closing bracket
    with pytest.raises(yaml.YAMLError):
        _ = load_yaml(str(p))


def test_FR_1_1_1_1__missing_config_file_raises_clear_error(tmp_path):
    missing = tmp_path / "nope.yaml"
    with pytest.raises(FileNotFoundError):
        _ = load_yaml(str(missing))
