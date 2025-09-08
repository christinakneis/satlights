from __future__ import annotations

import socket
import sys
from typing import Final

"""
Sinks (C-6):
  - stdout_sink(line)
  - file_sink(path, line)
  - tcp_sink(host, port, line)
No logging here; emitter handles error isolation/logging (C-5).
"""

# This is the newline character.
_NEWLINE: Final[str] = "\n"


# This function writes the line to the standard output.
def stdout_sink(line: str) -> None:
    sys.stdout.write(line + _NEWLINE)
    sys.stdout.flush()


# This function writes the line to the file.
def file_sink(path: str, line: str) -> None:
    # Append mode; create file if it doesn't exist
    with open(path, "a", encoding="utf-8") as f:
        f.write(line + _NEWLINE)
        f.flush()


# This function writes the line to the TCP.
def tcp_sink(host: str, port: int, line: str, *, timeout: float = 3.0) -> None:
    with socket.create_connection((host, port), timeout=timeout) as sock:
        data = (line + _NEWLINE).encode("utf-8")
        sock.sendall(data)
