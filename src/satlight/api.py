from __future__ import annotations

from typing import Any, Dict, Optional

import requests
from requests import Session, Response
from requests.exceptions import Timeout, RequestException

from .log import get_logger

"""
API client (DP-1.1.2.1)

fetch_next_pass:
  - GET https://sat.terrestre.ar/passes/{id}?lat=<lat>&lon=<lon>&limit=1
  - One retry on timeout
  - Non-200 or bad JSON => return None
  - Log errors to STDERR via logger (C-5)
"""

# This function gets the logger for the API client.
_LOG = get_logger(__name__)
_BASE_URL = "https://sat.terrestre.ar"


# This function builds the URL for the API client.
def _build_url(norad_id: int) -> str:
    return f"{_BASE_URL}/passes/{norad_id}"


# This function fetches the next pass for a given NORAD ID at (lat, lon).
def fetch_next_pass(
    norad_id: int,
    lat: float,
    lon: float,
    *,
    timeout: float = 5.0,
    session: Optional[Session] = None,
) -> Optional[Dict[str, Any]]:
    """
    DP-1.1.2.1: Fetch the next pass for a given NORAD ID at (lat, lon).

    Returns:
        dict (pass object) on success, or None if no pass / error.
    """
    params = {"lat": lat, "lon": lon, "limit": 1}
    url = _build_url(norad_id)
    s = session or requests.Session()

    # try up to 2 attempts total on timeout
    attempts = 2
    for attempt in range(1, attempts + 1):
        try:
            resp: Response = s.get(url, params=params, timeout=timeout)
            if (
                resp.status_code != 200
            ):  # 200 is the status code for a successful response. If the status code is not 200, it means there was an error.
                _LOG.error("passes endpoint non-200 (id=%s, status=%s)", norad_id, resp.status_code)
                return None
            try:  # Try to parse the response as JSON. If it fails, it means the response is not valid JSON.
                data = resp.json()
            except ValueError as e:
                _LOG.error("invalid JSON from passes endpoint (id=%s): %s", norad_id, e)
                return None

            if not isinstance(data, list) or not data:
                # No passes found
                return None

            first = data[0]
            if not isinstance(
                first, dict
            ):  # If the first item is not a dictionary, log the error and return None.
                _LOG.error("unexpected JSON shape for passes (id=%s): %r", norad_id, first)
                return None
            return first

        except Timeout:  # If the request times out, retry the request once.
            if attempt < attempts:
                _LOG.warning("timeout calling passes endpoint (id=%s), retrying once...", norad_id)
                continue
            _LOG.error("timeout calling passes endpoint after retry (id=%s)", norad_id)
            return None
        except (
            RequestException
        ) as e:  # If the request fails for any other reason, log the error and return None.
            _LOG.error("request error calling passes endpoint (id=%s): %s", norad_id, e)
            return None

    # Should never reach here
    return None
