from __future__ import annotations

from src.satlight.format import format_line


# This test checks if the format_line function sorts the pairs by ID and formats them into a single line.
def test_FR_1_2_1__sorts_by_id_and_formats_single_line():
    pairs = [(48915, "pink"), (25544, "blue")]
    out = format_line(pairs)
    assert out == "25544: blue, 48915: pink"
    print("\n.✅test_FR_1_2_1__sorts_by_id_and_formats_single_line passed")


# This test checks if the format_line function returns an empty string if the input is empty.
def test_FR_1_2_1__empty_input_returns_empty_string():
    assert format_line([]) == ""
    print("✅test_FR_1_2_1__empty_input_returns_empty_string passed")


# This test checks if the format_line function formats a single item without a trailing comma.
def test_FR_1_2_1__single_item_formats_without_trailing_comma():
    assert format_line([(25544, "blue")]) == "25544: blue"
    print("✅test_FR_1_2_1__single_item_formats_without_trailing_comma passed")
