# File: src/smhi2epw/workflow_cli.py
# Purpose: Expose weather batches and morphing in the CLI.
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 smhi2epw contributors
# License: See LICENSE at the project root.
# Author: OpenAI Codex, implementing the requested smhi2epw feature.
# Created/modified: 2026-10-21. Changelog: Add batch climate workflow.
"""Adapt JSON batch plans and existing-file morphing to the shell command."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from ._logging import configure_cli
from .batch import WeatherLocation, compile_amy_batch, plan_amy_batch
from .errors import Smhi2EpwError, ValidationError
from .io import read_json
from .morphing import MorphConfig, _selection, morph_epw


def _load_batch(path: Path) -> dict:
    """Load strict batch JSON and resolve file paths relative to its directory."""
    data = read_json(path)
    if not isinstance(data, dict):
        raise ValidationError("batch configuration must be a JSON object")
    required = {"locations", "years", "output_dir"}
    if not required <= data.keys() or data.keys() - (
        required | {"morphing", "compiler_options"}
    ):
        raise ValidationError(
            "batch requires locations, years and output_dir; optional keys are morphing and compiler_options"
        )
    if not isinstance(data["locations"], list) or not all(
        isinstance(loc, dict) for loc in data["locations"]
    ):
        raise ValidationError("locations must be a list of objects")
    if not isinstance(data["years"], list):
        raise ValidationError("years must be a list of completed calendar years")
    if not isinstance(data["output_dir"], str) or not data["output_dir"]:
        raise ValidationError("output_dir must be a nonempty path string")
    if not isinstance(data.get("compiler_options", {}), dict):
        raise ValidationError("compiler_options must be an object")
    if not isinstance(data.get("morphing", []), list):
        raise ValidationError("morphing must be a list of objects")
    data["locations"] = [WeatherLocation(**location) for location in data["locations"]]
    data["output_dir"] = str((path.parent / data["output_dir"]).resolve())
    configurations = []
    for item in data.get("morphing", []):
        if not isinstance(item, dict):
            raise ValidationError("morphing must contain configuration objects")
        item = dict(item)
        item["fwg_jar_path"] = str((path.parent / item["fwg_jar_path"]).resolve())
        for key in ("scenarios", "periods", "models"):
            if key in item:
                if not isinstance(item[key], list):
                    raise ValidationError(f"{key} must be a list")
                item[key] = tuple(item[key])
        config = MorphConfig(**item)
        _selection(config)
        configurations.append(config)
    if len({config.family for config in configurations}) != len(configurations):
        raise ValidationError("provide at most one morphing configuration per family")
    data["morphing"] = configurations
    options = data.get("compiler_options", {})
    if options.get("cache_dir"):
        options["cache_dir"] = str((path.parent / options["cache_dir"]).resolve())
    return data


def main(argv: list[str]) -> int:
    """Run a batch or morph command with consistent handled-error exit codes."""
    parser = argparse.ArgumentParser(
        prog="smhi2epw", description="Batch AMY generation and future climate morphing"
    )
    commands = parser.add_subparsers(dest="command", required=True)
    batch = commands.add_parser(
        "batch", help="generate locations × source years from JSON"
    )
    batch.add_argument("config", type=Path)
    batch.add_argument(
        "--dry-run",
        action="store_true",
        help="validate and print a plan without downloads or writes",
    )
    morph = commands.add_parser("morph", help="morph an existing AMY or TMY")
    morph.add_argument("source", type=Path)
    morph.add_argument("--output-dir", required=True, type=Path)
    morph.add_argument("--jar", required=True)
    morph.add_argument("--family", choices=("ssp", "rcp"), default="ssp")
    morph.add_argument("--scenarios", nargs="+")
    morph.add_argument("--periods", nargs="+", type=int)
    morph.add_argument("--models", nargs="+")
    morph.add_argument("--fwg-version")
    for command in (batch, morph):
        command.add_argument(
            "--log-level",
            choices=("OFF", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"),
            default="INFO",
        )
    args = parser.parse_args(argv)
    with configure_cli(args.log_level, "smhi2epw"):
        try:
            if args.command == "batch":
                settings = _load_batch(args.config.resolve())
                if args.dry_run:
                    jobs = plan_amy_batch(
                        settings["locations"],
                        settings["years"],
                        settings["output_dir"],
                        compiler_options=settings.get("compiler_options"),
                    )
                    print(
                        json.dumps(
                            {
                                "amy_jobs": [asdict(job) for job in jobs],
                                "morphing": [
                                    asdict(config) for config in settings["morphing"]
                                ],
                            },
                            indent=2,
                        )
                    )
                    return 0
                result = compile_amy_batch(**settings)
                print(
                    f"OK: {len(result.amy_results)} AMYs, {len(result.morph_results)} future EPWs -> {result.manifest_path}"
                )
            else:
                config = MorphConfig(
                    fwg_jar_path=args.jar,
                    family=args.family,
                    scenarios=tuple(args.scenarios or ()),
                    periods=tuple(args.periods or ()),
                    models=tuple(args.models or ()),
                    version=args.fwg_version,
                )
                outputs = morph_epw(args.source, args.output_dir, config)
                print(f"OK: {len(outputs)} future EPWs -> {args.output_dir}")
        except (Smhi2EpwError, OSError, ValueError, TypeError, KeyError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
    return 0
