# File: src/smhi2epw/morphing.py
# Purpose: Adapt optional pyfwg future climate morphing.
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 smhi2epw contributors
# License: See LICENSE at the project root.
# Author: OpenAI Codex, implementing the requested smhi2epw feature.
# Created/modified: 2026-10-21. Changelog: Add batch climate workflow.
"""Morph existing weather with optional pyfwg and retain source provenance.

FWG generates all supported scenarios and periods in one invocation. This
adapter stages that output, validates every requested EPW, and publishes only
the selected scenarios. The source calendar is never relabelled as a forecast.
"""

from __future__ import annotations

import importlib
import logging
import re
import reprlib
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from types import ModuleType

from ._logging import operation
from .errors import Smhi2EpwError, ValidationError
from .io import file_sha256, publish_file, write_json
from .reader import read_epw

SCENARIOS = {
    "ssp": ("ssp126", "ssp245", "ssp370", "ssp585"),
    "rcp": ("rcp26", "rcp45", "rcp85"),
}
PERIODS = (2050, 2080)


class MorphingError(Smhi2EpwError):
    """Report unavailable morphing dependencies or failed climate generation."""


@dataclass(frozen=True)
class MorphConfig:
    """Select a climate family, scenarios, periods, models and FWG executable.

    ``family='ssp'`` requires the global JAR; ``family='rcp'`` requires the
    Europe JAR. Empty ``scenarios``, ``periods`` or ``models`` select all
    supported values. Models are combined into an ensemble by FWG. ``version``
    overrides detection from the JAR filename (global: 3 or 4; Europe: 1 or 2).
    Urban heat island adjustment is disabled; other scientific settings use
    pyfwg defaults. Java must be available on PATH.

    Parameters
    ----------
    fwg_jar_path : str
        Explicit FWG JAR; relative paths use the working directory.
    family : str, default 'ssp'
        Global SSP or European RCP climate projections.
    scenarios : tuple of str, optional
        Supported scenario identifiers for the selected family.
    periods : tuple of int, optional
        Climate period labels 2050 and/or 2080, separate from source years.
    models : tuple of str, optional
        pyfwg GCM names or European GCM-RCM pairs to ensemble.
    version : str, optional
        Major FWG version override when not present in the JAR filename.

    Examples
    --------
    Construct and inspect selections without accessing a JAR or Java:

    >>> from smhi2epw import MorphConfig
    >>> config = MorphConfig("FutureWeatherGenerator_v4.0.2.jar",
    ...                      scenarios=("ssp245",), periods=(2050,))
    >>> config.summary()["scenarios"]
    ('ssp245',)
    """

    fwg_jar_path: str
    family: str = "ssp"
    scenarios: tuple[str, ...] = ()
    periods: tuple[int, ...] = ()
    models: tuple[str, ...] = ()
    version: str | None = None

    def __repr__(self) -> str:
        """Show selected climate counts without inspecting files or Java."""
        return f"MorphConfig(family={reprlib.repr(self.family)}, scenarios={len(self.scenarios)}, periods={len(self.periods)}, models={len(self.models)})"

    def __str__(self) -> str:
        """Return the same bounded description for ordinary printing."""
        return repr(self)

    def summary(self) -> dict:
        """Copy configured selections without resolving executable dependencies."""
        return asdict(self)


@dataclass(frozen=True)
class MorphResult:
    """Locate a morphed weather file and its auditable climate receipt.

    Attributes
    ----------
    source_path, output_path, provenance_path : str
        Baseline EPW, future EPW and JSON receipt paths, respectively.
    scenario : str
        Selected SSP or RCP identifier.
    period : int
        Future climate period label, independent of the source calendar.

    Examples
    --------
    >>> from smhi2epw import MorphResult
    >>> result = MorphResult("base.epw", "future.epw", "ssp245", 2050,
    ...                      "future.epw.json")
    >>> result.summary()["period"]
    2050
    """

    source_path: str
    output_path: str
    scenario: str
    period: int
    provenance_path: str

    def __repr__(self) -> str:
        """Show the scenario and period with a shortened output reference."""
        return f"MorphResult(scenario={reprlib.repr(self.scenario)}, period={reprlib.repr(self.period)}, output={reprlib.repr(self.output_path)})"

    def __str__(self) -> str:
        """Return the same bounded description for ordinary printing."""
        return repr(self)

    def summary(self) -> dict:
        """Copy artifact references without opening weather files or receipts."""
        return asdict(self)


def _selection(config: MorphConfig) -> tuple[tuple[str, ...], tuple[int, ...]]:
    """Validate local selections without importing optional morphing dependencies."""
    if config.family not in SCENARIOS:
        raise ValidationError("morphing family must be ssp or rcp")
    scenarios = tuple(config.scenarios) or SCENARIOS[config.family]
    periods = tuple(config.periods) or PERIODS
    if any(s not in SCENARIOS[config.family] for s in scenarios):
        raise ValidationError(
            f"supported {config.family} scenarios: {SCENARIOS[config.family]}"
        )
    if any(type(p) is not int or p not in PERIODS for p in periods):
        raise ValidationError(f"supported future periods: {PERIODS}")
    if len(set(scenarios)) != len(scenarios) or len(set(periods)) != len(periods):
        raise ValidationError("duplicate morphing scenarios or periods")
    if isinstance(config.models, str) or any(
        not isinstance(m, str) or not m for m in config.models
    ):
        raise ValidationError("models must be a sequence of model names")
    if len(set(config.models)) != len(config.models):
        raise ValidationError("duplicate morphing models")
    versions = ("3", "4") if config.family == "ssp" else ("1", "2")
    match = re.search(r"v(\d+)\.", Path(config.fwg_jar_path).name)
    version = config.version or (match.group(1) if match else None)
    if version not in versions:
        raise ValidationError(
            f"specify a supported FWG version for {config.family}: {versions}"
        )
    if "europe" in Path(config.fwg_jar_path).name.lower() and config.family != "rcp":
        raise ValidationError("the Europe JAR requires family='rcp'")
    return scenarios, periods


def _load_pyfwg() -> ModuleType:
    """Import pyfwg lazily while preserving the host application's logging."""
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    try:
        return importlib.import_module("pyfwg")
    except ImportError as exc:
        raise MorphingError(
            'install morphing support with pip install "smhi2epw[morphing]"'
        ) from exc
    finally:
        # pyfwg 0.3 clears root handlers and sets INFO during import.
        for handler in root.handlers:
            if handler not in handlers:
                handler.close()
        root.handlers[:] = handlers
        root.setLevel(level)


def _runtime(config: MorphConfig) -> ModuleType:
    """Check executable prerequisites before expensive weather data downloads."""
    _selection(config)
    if not Path(config.fwg_jar_path).is_file():
        raise MorphingError(f"FWG JAR does not exist: {config.fwg_jar_path}")
    if shutil.which("java") is None:
        raise MorphingError("Java is required for FWG; put java on PATH")
    try:
        subprocess.run(
            ["java", "-version"], capture_output=True, check=True, timeout=15
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise MorphingError(f"Java is unavailable: {exc}") from exc
    backend = _load_pyfwg()
    allowed = (
        backend.DEFAULT_GLOBAL_GCMS
        if config.family == "ssp"
        else backend.DEFAULT_EUROPE_RCMS
    )
    invalid = set(config.models) - set(allowed)
    if invalid:
        raise ValidationError(f"unsupported {config.family} models: {sorted(invalid)}")
    return backend


@operation("weather.morph")
def morph_epw(
    source_path: str | Path, output_dir: str | Path, config: MorphConfig
) -> list[MorphResult]:
    """Morph one AMY or TMY into selected future climate scenarios.

    Requires ``smhi2epw[morphing]``, Java and the appropriate FWG JAR. Outputs
    are named ``SOURCE_SCENARIO_PERIOD.epw`` with JSON receipts and optional
    FWG STAT companions. Existing destinations are rejected. Missing outputs
    and malformed EPWs raise :class:`MorphingError` or :class:`ValidationError`;
    pyfwg can otherwise silently return an empty or incomplete file list.

    FWG runs once per input and produces all scenarios internally. Filtering
    selects published files, rather than reducing the external computation.
    All requested outputs are checked before any are published.

    Parameters
    ----------
    source_path : str or Path
        Existing complete-year EPW; never changed. Relative to the working directory.
    output_dir : str or Path
        Explicit destination, created when needed.
    config : MorphConfig
        Family, executable, ensemble and selection settings.

    Returns
    -------
    list of MorphResult
        References in selected scenario order, then period order.

    Raises
    ------
    MorphingError
        If dependencies, Java execution or requested outputs are unavailable.
    ValidationError
        If selections or EPW structure/ranges are invalid, or outputs exist.
    OSError
        If prerequisite files or directories cannot be read or created.

    Notes
    -----
    Reads input weather/JARs, starts Java and writes EPW/JSON/optional STAT
    artifacts. No provider weather is acquired by this operation. Publication
    refuses concurrent overwrites; several files are not a transaction. A disk
    failure can leave earlier complete files. Choose a fresh directory to rerun.

    Examples
    --------
    After providing a real baseline, Java and global FWG JAR::

        from smhi2epw import MorphConfig, morph_epw
        outputs = morph_epw(
            "baseline.epw", "future",
            MorphConfig("FutureWeatherGenerator_v4.0.2.jar",
                        scenarios=("ssp245",), periods=(2050,)),
        )
        assert outputs[0].scenario == "ssp245"
    """
    scenarios, periods = _selection(config)
    from . import __version__

    source = Path(source_path).resolve()
    destination = Path(output_dir).resolve()
    frame = read_epw(source)
    targets = [
        (s, p, destination / f"{source.stem}_{s}_{p}.epw")
        for s in scenarios
        for p in periods
    ]
    for _, _, target in targets:
        for path in (target, target.with_suffix(".stat"), Path(str(target) + ".json")):
            if path.exists():
                raise ValidationError(f"refusing to overwrite morphing output: {path}")
    backend = _runtime(config)
    source_hash = file_sha256(source)
    jar_hash = file_sha256(Path(config.fwg_jar_path))
    destination.mkdir(parents=True, exist_ok=True)
    results = []
    try:
        with tempfile.TemporaryDirectory(
            prefix=".smhi2epw-morph-", dir=destination
        ) as temporary:
            stage = Path(temporary)
            # The direct pyfwg API also returns its temporary input EPW.
            # Give it a neutral name so it cannot masquerade as a scenario.
            baseline = stage / "baseline.epw"
            shutil.copy2(source, baseline)
            options = {
                "epw_paths": str(baseline),
                "fwg_jar_path": str(Path(config.fwg_jar_path).resolve()),
                "output_dir": str(stage / "generated"),
                "temp_base_dir": str(stage / "work"),
                "fwg_add_uhi": False,
                "fwg_create_ensemble": True,
                "fwg_version": config.version,
            }
            options["fwg_gcms" if config.family == "ssp" else "fwg_rcm_pairs"] = (
                list(config.models) or None
            )
            run = (
                backend.morph_epw_global
                if config.family == "ssp"
                else backend.morph_epw_europe
            )
            # Module-level logging.info in pyfwg would call basicConfig when
            # the host has no root handlers. Keep that decision with the host.
            root = logging.getLogger()
            placeholder = logging.NullHandler()
            root.addHandler(placeholder)
            try:
                generated = {Path(p).name: Path(p) for p in run(**options)}
            finally:
                root.removeHandler(placeholder)
                placeholder.close()
            for scenario, period, _ in targets:
                name = f"{scenario}_{period}.epw"
                if name not in generated or not generated[name].is_file():
                    raise MorphingError(f"FWG did not produce requested output: {name}")
                read_epw(generated[name])
            source_receipt = Path(str(source) + ".json")
            for scenario, period, target in targets:
                original = generated[f"{scenario}_{period}.epw"]
                publish_file(original, target)
                stat = generated.get(f"{scenario}_{period}.stat")
                if stat is not None:
                    publish_file(stat, target.with_suffix(".stat"))
                receipt = Path(str(target) + ".json")
                write_json(
                    receipt,
                    {
                        "schema_version": 1,
                        "package_version": __version__,
                        "weather_classification": "morphed_future_scenario",
                        "source_path": str(source),
                        "source_sha256": source_hash,
                        "source_calendar_years": sorted(
                            int(y) for y in frame.year.unique()
                        ),
                        "source_provenance_path": str(source_receipt)
                        if source_receipt.is_file()
                        else None,
                        "source_provenance_sha256": file_sha256(source_receipt)
                        if source_receipt.is_file()
                        else None,
                        "output_path": str(target),
                        "output_sha256": file_sha256(target),
                        "family": config.family,
                        "scenario": scenario,
                        "future_period": period,
                        "models": list(config.models)
                        or sorted(
                            backend.DEFAULT_GLOBAL_GCMS
                            if config.family == "ssp"
                            else backend.DEFAULT_EUROPE_RCMS
                        ),
                        "ensemble": True,
                        "urban_heat_island": False,
                        "pyfwg_version": backend.__version__,
                        "fwg_jar_path": str(Path(config.fwg_jar_path).resolve()),
                        "fwg_jar_sha256": jar_hash,
                        "fwg_version": config.version
                        or backend.detect_fwg_version(config.fwg_jar_path),
                        "note": "Climate scenario applied to source weather; not a forecast of an individual future year. Review the baseline period against FWG's reference climate.",
                    },
                )
                results.append(
                    MorphResult(
                        str(source), str(target), scenario, period, str(receipt)
                    )
                )
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
        raise MorphingError(f"weather morphing failed for {source}: {exc}") from exc
    return results
