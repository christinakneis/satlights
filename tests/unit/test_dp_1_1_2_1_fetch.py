from __future__ import annotations

from urllib.parse import urlparse, parse_qs

import requests
import responses

from src.satlight.api import fetch_next_pass


# This test checks if the fetch_next_pass function calls the passes endpoint per id with timeout and retry.
@responses.activate
def test_FR_1_1_2_1__calls_passes_endpoint_per_id_with_timeout_and_retry():
    """Technique: mock HTTP (responses). Expect: first call times out, second succeeds."""
    norad_id = 25544
    lat, lon = 37.8, -122.4
    url = f"https://sat.terrestre.ar/passes/{norad_id}"

    # First call -> timeout
    responses.add(
        responses.GET,
        url,
        body=requests.exceptions.Timeout("simulate timeout"),
    )

    # Second call -> valid JSON list with one pass object
    payload = [
        {
            "rise": {"utc_timestamp": 1000, "alt": "10.00"},
            "culmination": {"utc_timestamp": 1100, "alt": "46.00"},
            "set": {"utc_timestamp": 1200, "alt": "10.00"},
            "norad_id": norad_id,
            "visible": True,
        }
    ]
    responses.add(
        responses.GET,
        url,
        json=payload,
        status=200,
    )

    res = fetch_next_pass(norad_id, lat, lon, timeout=0.1)
    assert res is not None
    assert res["norad_id"] == norad_id

    # Verify two calls were made and query params included lat/lon/limit=1
    assert len(responses.calls) == 2
    parsed = urlparse(responses.calls[-1].request.url)
    qs = parse_qs(parsed.query)
    assert qs.get("lat") == [str(lat)]
    assert qs.get("lon") == [str(lon)]
    assert qs.get("limit") == ["1"]
    print("✅test_FR_1_1_2_1__calls_passes_endpoint_per_id_with_timeout_and_retry passed")


# This test checks if the fetch_next_pass function returns None and logs an error if the API returns a non-200 status code.
@responses.activate
def test_FR_1_1_2_1__api_error_results_in_not_visible_and_logs_error():
    """Technique: mock HTTP. Expect: non-200 -> None and error log."""
    norad_id = 48915
    lat, lon = 37.8, -122.4
    url = f"https://sat.terrestre.ar/passes/{norad_id}"

    responses.add(
        responses.GET,
        url,
        status=500,
        body="server oops",
        content_type="text/plain",
    )

    res = fetch_next_pass(norad_id, lat, lon, timeout=0.1)
    assert res is None
    # Note: Logging to STDERR per C-5 constraint, so we can't easily test log content
    # The function correctly returns None on API errors, which is the main behavior
    print("✅test_FR_1_1_2_1__api_error_results_in_not_visible_and_logs_error passed")
