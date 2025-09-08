from __future__ import annotations

import re
from typing import Any, Dict

import yaml
from pydantic import BaseModel, field_validator

"""
Config layer
- DP-1.1.1.1: load_yaml(path) -> dict
- DP-1.1.1.2: AppConfig (Pydantic v2) + validate_config(raw) -> AppConfig

Maps to:
  FR-1.1.1, CN-1.2
  C-6 (allowed sinks enforced here)
"""

#This function loads and parses YAML into a raw dictionary using yaml.safe_load.
def load_yaml(path: str) -> Dict[str, Any]:
    """
    DP-1.1.1.1: Load and parse YAML into raw dict using yaml.safe_load.

    Raises:
        FileNotFoundError: if the file does not exist
        yaml.YAMLError: if YAML is malformed/unsafe
        ValueError: if the top-level document is not a mapping
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except FileNotFoundError:
        raise
    except yaml.YAMLError as e:
        # Re-raise so tests can assert YAMLError specifically
        raise e

    if data is None:
        # Treat empty file as empty mapping (consistent/friendly)
        data = {}
    if not isinstance(data, dict):
        raise ValueError(f"Top-level YAML must be a mapping/dict (file: {path})")
    return data


# ----- DP-1.1.1.2: Pydantic config model -----

# Allowed outputs (C-6): exactly 'stdout', 'file:<path>', or 'tcp:<host>:<port>'
_TCP_RE = re.compile(r"^tcp:([^:]+):(\d{1,5})$")  # simple host:port (no IPv6 colons)

# Pydantic config model for DP-1.1.1.2
class AppConfig(BaseModel):
    lat: float
    lon: float
    satellites: dict[int, str]
    outputs: list[str]
    min_elevation_deg: float = 10.0  # default per spec

    # --- Validators ---

    #This validator checks if the latitude is between -90 and 90 degrees.
    @field_validator("lat")
    @classmethod
    def _lat_in_range(cls, v: float) -> float:
        if not (-90.0 <= v <= 90.0):
            raise ValueError("lat must be between -90 and 90 degrees")
        return float(v)

    #This validator checks if the longitude is between -180 and 180 degrees.
    @field_validator("lon")
    @classmethod
    def _lon_in_range(cls, v: float) -> float:
        if not (-180.0 <= v <= 180.0):
            raise ValueError("lon must be between -180 and 180 degrees")
        return float(v)

    #This validator checks if the minimum elevation is between 0 and 90 degrees.
    @field_validator("min_elevation_deg")
    @classmethod
    def _min_elev_in_range(cls, v: float) -> float:
        v = float(v) 
        if not (0.0 <= v <= 90.0):
            raise ValueError("min_elevation_deg must be between 0 and 90 inclusive")
        return v

    #This validator checks if the satellites keys are positive integers and if the color is a non-empty string.
    @field_validator("satellites")
    @classmethod
    def _satellites_non_empty_and_int_keys(cls, m: dict[Any, Any]) -> dict[int, str]:
        if not isinstance(m, dict) or len(m) == 0:
            raise ValueError("satellites must be a non-empty mapping of NORAD_ID -> color")

        normalized: dict[int, str] = {}
        for k, color in m.items():
            # Allow keys given as strings of digits; normalize to int
            if isinstance(k, str) and k.isdigit():
                k = int(k)
            if not isinstance(k, int) or k <= 0:
                raise ValueError(f"satellites keys must be positive integers; got {k!r}")
            if not isinstance(color, str) or not color.strip():
                raise ValueError(f"color for NORAD {k} must be a non-empty string")
            normalized[k] = color.strip()
        return normalized

    #This validator checks if the outputs are exactly 'stdout', 'file:<path>', or 'tcp:<host>:<port>'.
    @field_validator("outputs")
    @classmethod
    def _outputs_allowed_only(cls, items: list[str]) -> list[str]:
        if not isinstance(items, list) or len(items) == 0:
            raise ValueError("outputs must be a non-empty list")
        out: list[str] = []
        for s in items:
            if s == "stdout":
                out.append(s)
                continue
            if s.startswith("file:"):
                path = s.removeprefix("file:")
                if not path:
                    raise ValueError("file sink must be 'file:<path>' with a non-empty path")
                out.append(s)
                continue
            m = _TCP_RE.match(s)
            if m:
                host, port_str = m.groups()
                port = int(port_str)
                if not (1 <= port <= 65535):
                    raise ValueError("tcp port must be 1..65535")
                if not host or ":" in host:
                    # keep host simple (no colons) per spec; users can use DNS/IP
                    raise ValueError("tcp host must be non-empty and must not contain ':'")
                out.append(s)
                continue
            raise ValueError(
                "outputs entries must be exactly 'stdout', 'file:<path>', or 'tcp:<host>:<port>'"
            )
        return out

#This function validates and normalizes a raw dictionary into an AppConfig object using Pydantic's model_validate.
def validate_config(raw: dict[str, Any]) -> AppConfig:
    """Validate and normalize raw dict into AppConfig (DP-1.1.1.2)."""
    return AppConfig.model_validate(raw)


__all__ = ["load_yaml", "AppConfig", "validate_config"]