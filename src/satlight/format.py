from __future__ import annotations

from typing import List, Tuple

"""
Formatter (DP-1.2.1)

- Input: list[(id:int, color:str)] from DP-1.1.2
- Output: stable, comma-separated one-liner: "id: color, id: color"
- Returns "" if input is empty (FR-1.2.1)
"""


# This function formats the pairs into a comma-separated one-liner.
def format_line(pairs: List[Tuple[int, str]]) -> str:
    """Return a single command line without a trailing newline."""
    if not pairs:
        return ""
    # Sort by ID for stability
    pairs_sorted = sorted(pairs, key=lambda t: t[0])
    return ", ".join(f"{sid}: {color}" for sid, color in pairs_sorted)
