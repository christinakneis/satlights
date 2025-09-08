from __future__ import annotations

import argparse
from typing import Optional, List

from pydantic import ValidationError
from yaml import YAMLError

from .log import get_logger
from .config import load_yaml, validate_config, AppConfig
from .emit import run_forever, run_once

"""
CLI entrypoint (DP-1)

Usage:
  python -m satlight.cli --config /path/config.yaml [--once]

Behavior:
  - Loads & validates config (DP-1.1.1.*)
  - Runs one tick (--once) or the 10s loop (DP-1.2.2)
  - All diagnostics/logs go to STDERR (C-5)
"""

_LOG = get_logger(__name__)
_DEFAULT_CONFIG = "/app/config.yaml"  # matches DP-2 container default


# This function builds the parser for the CLI.
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="satlight", description="Satellite pass -> light command emitter"
    )
    p.add_argument(  # This adds the --config flag to the parser.
        "-c",
        "--config",
        default=_DEFAULT_CONFIG,
        help=f"Path to YAML config (default: {_DEFAULT_CONFIG})",
    )
    p.add_argument(  # This adds the --once flag to the parser.
        "--once",
        action="store_true",
        help="Run a single 10 s cycle and exit (no final sleep).",
    )
    return p


# This function is the main function for the CLI.
def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)  # This parses the arguments and returns the Namespace object.

    config_path: str = args.config  # This gets the config path from the arguments.

    # Load and validate config
    try:
        raw = load_yaml(config_path)  # This loads the config file.
        cfg: AppConfig = validate_config(raw)  # This validates the config file.
    except FileNotFoundError:  # This handles the case where the config file is not found.
        _LOG.error("Config file not found: %s", config_path)
        return 1
    except YAMLError as e:  # This handles the case where the config file is not a valid YAML file.
        _LOG.error("Failed to parse YAML config (%s): %s", config_path, e)
        return 1
    except (
        ValidationError
    ) as e:  # This handles the case where the config file is not a valid AppConfig object.
        _LOG.error("Config validation error: %s", e)
        return 1
    except (
        Exception
    ) as e:  # This handles the case where the config file is not a valid AppConfig object.
        _LOG.exception("Unexpected error loading config: %s", e)
        return 1

    # Run
    try:
        if args.once:  # This handles the case where the --once flag is provided.
            # For --once, do not sleep at end; execute one cycle immediately.
            run_once(cfg, do_sleep=False)
        else:  # This handles the case where the --once flag is not provided.
            run_forever(cfg)
        return 0
    except KeyboardInterrupt:  # This handles the case where the user interrupts the program.
        _LOG.info("Interrupted, exiting.")
        return 130
    except (
        Exception
    ) as e:  # This handles the case where the program encounters an unexpected error.
        _LOG.exception("Unexpected runtime error: %s", e)
        return 1


# Run the main function for the CLI.
if __name__ == "__main__":
    raise SystemExit(main())
