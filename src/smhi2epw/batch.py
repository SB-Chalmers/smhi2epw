# File: src/smhi2epw/batch.py
# Purpose: Plan and generate location-by-year weather batches.
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 smhi2epw contributors
# License: See LICENSE at the project root.
# Author: OpenAI Codex, implementing the requested smhi2epw feature.
# Created/modified: 2026-10-21. Changelog: Add batch climate workflow.
"""Plan location-by-year AMY studies and optionally morph each baseline."""

from __future__ import annotations

import re
import reprlib
import tempfile
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any, Mapping, Sequence

from ._logging import operation
from .compiler import CompileResult, EPWConfig, _validate_config, compile_epw
from .errors import ValidationError
from .io import publish_file, read_json, write_json
from .morphing import (
    MorphConfig,
    MorphResult,
    _runtime,
    _selection,
    morph_epw,
)


@dataclass(frozen=True)
class WeatherLocation:
    """Describe a batch location with a unique filesystem-safe identifier.

    ``name`` is used for output folders; ``city`` defaults to that name in the
    EPW header. Supply either a SMHI ``station_id`` or both coordinates.
    Explicit coordinates retain the single-file compiler's target semantics.

    Parameters
    ----------
    name : str
        Unique output identifier using ASCII letters, digits, underscores or hyphens.
    station_id : int, optional
        Positive SMHI meteorological station identifier.
    latitude, longitude : float, optional
        Target WGS84 coordinates in decimal degrees, supplied together.
    city, region, country : str, optional
        EPW location labels. City defaults to name; region/country to SE/SWE.
    utc_offset : float, default 1
        Whole-hour local standard time offset, without daylight saving time.
    target_elevation_m : float, optional
        Target elevation above sea level in metres.

    Examples
    --------
    >>> from smhi2epw import WeatherLocation
    >>> location = WeatherLocation("gothenburg", station_id=71420)
    >>> location.summary()["station_id"]
    71420
    """

    name: str
    station_id: int | None = None
    latitude: float | None = None
    longitude: float | None = None
    city: str | None = None
    region: str = "SE"
    country: str = "SWE"
    utc_offset: float = 1.0
    target_elevation_m: float | None = None

    def __repr__(self) -> str:
        """Show a bounded location identity and available selection inputs."""
        return f"WeatherLocation(name={reprlib.repr(self.name)}, station_id={reprlib.repr(self.station_id)}, coordinates={self.latitude is not None and self.longitude is not None})"

    def __str__(self) -> str:
        """Return the same bounded description for ordinary printing."""
        return repr(self)

    def summary(self) -> dict:
        """Copy all supplied location metadata without looking up a station."""
        return asdict(self)


@dataclass
class BatchResult:
    """Collect completed AMY diagnostics, future files and the batch manifest.

    Attributes
    ----------
    amy_results : list of CompileResult
        Existing compiler diagnostics, one per completed baseline.
    morph_results : list of MorphResult
        Artifact and scenario references, one per completed future EPW.
    manifest_path : str
        JSON progress inventory path. Inspection never opens it.

    Examples
    --------
    >>> from smhi2epw import BatchResult
    >>> result = BatchResult([], [], "weather/manifest.json")
    >>> result.summary()["future_count"]
    0
    """

    amy_results: list[CompileResult]
    morph_results: list[MorphResult]
    manifest_path: str

    def __repr__(self) -> str:
        """Show completed file counts without expanding annual weather reports."""
        return f"BatchResult(amys={len(self.amy_results)}, future_epws={len(self.morph_results)}, manifest={reprlib.repr(self.manifest_path)})"

    def __str__(self) -> str:
        """Return the same bounded description for ordinary printing."""
        return repr(self)

    def summary(self) -> dict:
        """Describe completed outputs using already loaded artifact references."""
        return {
            "amy_count": len(self.amy_results),
            "future_count": len(self.morph_results),
            "manifest_path": self.manifest_path,
            "amy_paths": [item.output_path for item in self.amy_results],
            "future_paths": [item.output_path for item in self.morph_results],
        }


def plan_amy_batch(
    locations: Sequence[WeatherLocation],
    years: Sequence[int],
    output_dir: str | Path,
    *,
    compiler_options: Mapping[str, Any] | None = None,
) -> list[EPWConfig]:
    """Validate every location/year and return compiler jobs without I/O.

    Output paths are ``OUTPUT/LOCATION/YEAR/LOCATION_YEAR.epw``. Common
    ``compiler_options`` accept EPWConfig's cache, recovery and solar settings;
    location, year, output and provenance fields belong to the batch planner.
    Duplicate locations and years are errors, preventing output collisions.

    Parameters
    ----------
    locations : sequence of WeatherLocation
        Explicit station or coordinate selections. No objects are modified.
    years : sequence of int
        Completed source calendar years from 1999 onward.
    output_dir : str or Path
        Destination root, relative to the current working directory.
    compiler_options : mapping, optional
        Common EPWConfig recovery, radiation, cache and worker settings.

    Returns
    -------
    list of EPWConfig
        Validated configurations in location order, then year order.

    Raises
    ------
    ValidationError, IngestionError
        If selections, names or compiler settings are invalid.

    Examples
    --------
    >>> from smhi2epw import WeatherLocation, plan_amy_batch
    >>> jobs = plan_amy_batch([WeatherLocation("gbg", station_id=71420)],
    ...                       [2022, 2023], "weather")
    >>> [job.year for job in jobs]
    [2022, 2023]
    """
    if not locations or not years:
        raise ValidationError("provide at least one location and one source year")
    if any(not isinstance(loc, WeatherLocation) for loc in locations):
        raise ValidationError("locations must contain WeatherLocation values")
    names = [loc.name for loc in locations]
    if any(
        not isinstance(name, str)
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", name) is None
        for name in names
    ):
        raise ValidationError(
            "location names must use letters, numbers, underscores or hyphens"
        )
    if len({name.casefold() for name in names}) != len(names):
        raise ValidationError("location names must be unique (case insensitive)")
    if any(type(year) is not int for year in years):
        raise ValidationError("source years must be integers")
    if len(set(years)) != len(years):
        raise ValidationError("duplicate source years")
    options = dict(compiler_options or {})
    reserved = set(WeatherLocation.__dataclass_fields__) | {
        "year",
        "output_path",
        "provenance_path",
    }
    if reserved & options.keys():
        raise ValidationError(
            f"batch controls these compiler options: {sorted(reserved & options.keys())}"
        )
    unknown = options.keys() - EPWConfig.__dataclass_fields__.keys()
    if unknown:
        raise ValidationError(f"unknown compiler options: {sorted(unknown)}")
    jobs = []
    for location in locations:
        fields = asdict(location)
        fields.pop("name")
        fields["city"] = location.city or location.name
        for year in years:
            output = (
                Path(output_dir).absolute()
                / location.name
                / str(year)
                / f"{location.name}_{year}.epw"
            )
            config = EPWConfig(
                year=year,
                output_path=str(output),
                provenance_path=str(output) + ".json",
                **fields,
                **options,
            )
            _validate_config(config)
            jobs.append(config)
    return jobs


def _compile_baseline(config: EPWConfig) -> CompileResult:
    """Stage a compiler result and receipt before enforcing no-overwrite publication."""
    target = Path(config.output_path)
    with tempfile.TemporaryDirectory(
        prefix=".smhi2epw-amy-", dir=target.parent
    ) as temporary:
        staged = Path(temporary) / target.name
        staged_receipt = Path(str(staged) + ".json")
        job = replace(
            config, output_path=str(staged), provenance_path=str(staged_receipt)
        )
        result = compile_epw(job)
        result.output_path = config.output_path
        if staged_receipt.is_file():
            receipt = read_json(staged_receipt)
            if not isinstance(receipt, dict):
                raise ValidationError("compiler provenance must be a JSON object")
            receipt["configuration"]["output_path"] = config.output_path
            receipt["configuration"]["provenance_path"] = config.provenance_path
            receipt["result"]["output_path"] = config.output_path
            write_json(staged_receipt, receipt, overwrite=True)
        publish_file(staged, target)
        if staged_receipt.is_file():
            publish_file(staged_receipt, Path(str(target) + ".json"))
    return result


@operation("weather.batch")
def compile_amy_batch(
    locations: Sequence[WeatherLocation],
    years: Sequence[int],
    output_dir: str | Path,
    *,
    morphing: Sequence[MorphConfig] = (),
    compiler_options: Mapping[str, Any] | None = None,
) -> BatchResult:
    """Compile each location/year and morph each AMY with every climate family.

    All configurations and optional runtime prerequisites are checked before
    provider access. Runs are sequential; individual compilations retain their
    own concurrent provider requests. Existing outputs are rejected. The
    manifest is updated after each completed stage, and records a failed run
    without discarding earlier valid outputs. Reruns need a fresh output root.

    Parameters
    ----------
    locations, years, output_dir, compiler_options
        Same inputs as :func:`plan_amy_batch`.
    morphing : sequence of MorphConfig, optional
        At most one configuration per climate family; empty means AMYs only.

    Returns
    -------
    BatchResult
        Completed diagnostics and paths. Returned lists can be edited without
        changing previously written JSON receipts.

    Raises
    ------
    Smhi2EpwError
        If planning, acquisition, validation or morphing fails.
    OSError
        If output directories or progress receipts cannot be written.

    Notes
    -----
    Explicitly contacts SMHI and potentially Open-Meteo, writes files and,
    when morphing is supplied, starts Java. No study scheduling or resume is
    provided. Multi-file publication is not transactional.

    Examples
    --------
    This live example needs provider access and a new output directory::

        from smhi2epw import WeatherLocation, compile_amy_batch
        result = compile_amy_batch(
            [WeatherLocation("gbg", station_id=71420)], [2022, 2023], "weather"
        )
        assert len(result.amy_results) == 2
    """
    from . import __version__

    jobs = plan_amy_batch(
        locations, years, output_dir, compiler_options=compiler_options
    )
    families = [config.family for config in morphing]
    if len(set(families)) != len(families):
        raise ValidationError("provide at most one morphing configuration per family")
    manifest = Path(output_dir).resolve() / "manifest.json"
    if manifest.exists():
        raise ValidationError(f"refusing to overwrite batch manifest: {manifest}")
    for job in jobs:
        for path in (Path(job.output_path), Path(str(job.output_path) + ".json")):
            if path.exists():
                raise ValidationError(f"refusing to overwrite batch output: {path}")
        for config in morphing:
            _selection(config)
            future = Path(job.output_path).parent / "future" / config.family
            if future.exists() and any(future.iterdir()):
                raise ValidationError(
                    f"morphing output directory is not empty: {future}"
                )
    for config in morphing:
        _runtime(config)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    payload: dict[str, Any] = {
        "schema_version": 1,
        "package_version": __version__,
        "status": "running",
        "locations": [asdict(location) for location in locations],
        "source_years": list(years),
        "compiler_options": dict(compiler_options or {}),
        "morphing": [asdict(config) for config in morphing],
        "jobs": [],
    }
    result = BatchResult([], [], str(manifest))
    write_json(manifest, payload)
    try:
        for job in jobs:
            Path(job.output_path).parent.mkdir(parents=True, exist_ok=True)
            entry: dict[str, Any] = {
                "source_year": job.year,
                "amy_path": job.output_path,
                "status": "compiling",
                "morphed": [],
            }
            payload["jobs"].append(entry)
            write_json(manifest, payload, overwrite=True)
            amy = _compile_baseline(job)
            result.amy_results.append(amy)
            entry.update(
                status="morphing",
                provenance_path=job.provenance_path,
                rows=amy.rows,
                warnings=amy.report.warnings,
            )
            write_json(manifest, payload, overwrite=True)
            for config in morphing:
                future = Path(job.output_path).parent / "future" / config.family
                outputs = morph_epw(job.output_path, future, config)
                result.morph_results.extend(outputs)
                entry["morphed"].extend(asdict(output) for output in outputs)
                write_json(manifest, payload, overwrite=True)
            entry["status"] = "completed"
            write_json(manifest, payload, overwrite=True)
        payload["status"] = "completed"
        write_json(manifest, payload, overwrite=True)
    except Exception as exc:
        payload.update(status="failed", error=str(exc))
        if payload["jobs"]:
            payload["jobs"][-1].update(status="failed", error=str(exc))
        write_json(manifest, payload, overwrite=True)
        raise
    return result
