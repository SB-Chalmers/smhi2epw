# SPDX-License-Identifier: MIT
# Copyright (c) 2026 smhi2epw contributors
# License: See LICENSE at the project root.
"""Offline weather batches and real pyfwg adapter contract tests."""

from __future__ import annotations

import importlib.util
import json
import logging
import os
import shutil
import subprocess
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

import pandas as pd
import pytest
from fixtures.provider_replay import ReplaySession, compile_weather

from smhi2epw import (
    MorphConfig,
    MorphingError,
    WeatherLocation,
    batch,
    cli,
    compile_amy_batch,
    morph_epw,
    morphing,
    plan_amy_batch,
    read_epw,
)
from smhi2epw.errors import IngestionError, ValidationError
from smhi2epw.export import build_header, expected_rows, write_epw
from smhi2epw.ingestion import CachedClient


def _epw(path, year=2023):
    count = expected_rows(year)
    frame = pd.DataFrame(
        {
            "dry_bulb": 10,
            "dew_point": 5,
            "relative_humidity": 70,
            "pressure": 101325,
            "etrh": 500,
            "etrn": 1367,
            "horizontal_ir": 300,
            "ghi": 0,
            "dni": 0,
            "dhi": 0,
            "wind_direction": 180,
            "wind_speed": 3,
            "sky_cover": 5,
        },
        index=pd.date_range(f"{year}-01-01 01:00", periods=count, freq="h"),
    )
    header = build_header(
        "Gothenburg", "VG", "SWE", "999999", 57.7, 12, 1, 3, year, 71420
    )
    write_epw(str(path), header, frame, year)
    return path


@pytest.fixture
def source(tmp_path):
    (tmp_path / "fwg.jar").write_bytes(b"test jar")
    return _epw(tmp_path / "gothenburg_2023.epw")


def _backend(source, family="ssp", missing=None, corrupt=None):
    def run(**options):
        output = Path(options["output_dir"])
        output.mkdir(parents=True)
        files = []
        for scenario in morphing.SCENARIOS[family]:
            for period in morphing.PERIODS:
                name = f"{scenario}_{period}.epw"
                if name == missing:
                    continue
                target = output / name
                shutil.copyfile(options["epw_paths"], target)
                if name == corrupt:
                    target.write_text("malformed weather")
                files.append(str(target))
        return files

    return SimpleNamespace(
        morph_epw_global=run,
        morph_epw_europe=run,
        DEFAULT_GLOBAL_GCMS={"CanESM5"},
        DEFAULT_EUROPE_RCMS={"ICHEC_EC_EARTH_SMHI_RCA4"},
        __version__="0.4.0",
        detect_fwg_version=lambda _: "4",
        get_fwg_distribution_info=lambda _: None,
    )


def test_plan_cross_product_and_no_writes(tmp_path):
    jobs = plan_amy_batch(
        [
            WeatherLocation("gbg", station_id=71420),
            WeatherLocation("sto", latitude=59.3, longitude=18.1),
        ],
        [2023, 2024],
        tmp_path / "study",
        compiler_options={"weather_policy": "strict"},
    )
    assert [(Path(job.output_path).stem, job.year) for job in jobs] == [
        ("gbg_2023", 2023),
        ("gbg_2024", 2024),
        ("sto_2023", 2023),
        ("sto_2024", 2024),
    ]
    assert all(job.weather_policy == "strict" and job.provenance_path for job in jobs)
    assert not (tmp_path / "study").exists()


@pytest.mark.parametrize(
    "locations,years,options",
    [
        ([WeatherLocation("../escape", station_id=1)], [2023], {}),
        (
            [WeatherLocation("A", station_id=1), WeatherLocation("a", station_id=2)],
            [2023],
            {},
        ),
        ([WeatherLocation("a", station_id=1)], [2023, 2023], {}),
        ([WeatherLocation("a", station_id=1)], [True], {}),
        ([WeatherLocation("a", station_id=1)], [1998], {}),
        ([WeatherLocation("a", station_id=1)], [2023], {"output_path": "other.epw"}),
        ([WeatherLocation("a", station_id=1)], [2023], {"typo": True}),
        ([WeatherLocation("a")], [2023], {}),
    ],
)
def test_plan_rejects_unsafe_or_invalid_jobs(tmp_path, locations, years, options):
    with pytest.raises((ValidationError, IngestionError)):
        plan_amy_batch(locations, years, tmp_path, compiler_options=options)


@pytest.mark.parametrize(
    "family,scenario,version", [("ssp", "ssp245", "4"), ("rcp", "rcp85", "2")]
)
def test_morph_filters_and_records_baseline(
    tmp_path, monkeypatch, source, family, scenario, version
):
    original = source.read_bytes()
    monkeypatch.setattr(morphing, "_runtime", lambda _: _backend(source, family))
    results = morph_epw(
        source,
        tmp_path / "future",
        MorphConfig(
            str(tmp_path / "fwg.jar"),
            family=family,
            scenarios=(scenario,),
            periods=(2080,),
            version=version,
        ),
    )
    assert len(results) == 1
    assert Path(results[0].output_path).name == f"gothenburg_2023_{scenario}_2080.epw"
    receipt = json.loads(Path(results[0].provenance_path).read_text())
    assert receipt["source_calendar_years"] == [2023]
    assert receipt["future_period"] == 2080
    assert receipt["urban_heat_island"] is False
    assert receipt["weather_classification"] == "morphed_future_scenario"
    assert read_epw(results[0].output_path).year.eq(2023).all()
    assert source.read_bytes() == original
    assert len(list((tmp_path / "future").glob("*.epw"))) == 1
    with pytest.raises(ValidationError, match="overwrite"):
        morph_epw(
            source,
            tmp_path / "future",
            MorphConfig(
                str(tmp_path / "fwg.jar"),
                family=family,
                scenarios=(scenario,),
                periods=(2080,),
                version=version,
            ),
        )


@pytest.mark.parametrize("failure", ["missing", "corrupt"])
def test_no_publishing_when_any_requested_output_fails(
    tmp_path, monkeypatch, source, failure
):
    monkeypatch.setattr(
        morphing, "_runtime", lambda _: _backend(source, **{failure: "ssp585_2080.epw"})
    )
    with pytest.raises((MorphingError, ValidationError)):
        morph_epw(
            source,
            tmp_path / "future",
            MorphConfig(str(tmp_path / "fwg.jar"), version="4"),
        )
    assert not list((tmp_path / "future").iterdir())


def test_baseline_named_like_a_scenario_is_not_accepted_as_future_output(
    tmp_path, source, monkeypatch
):
    """pyfwg may return its staged input alongside actual generated files."""
    source = source.rename(tmp_path / "ssp245_2050.epw")
    backend = _backend(source)

    def only_input(**options):
        output = Path(options["output_dir"])
        output.mkdir(parents=True)
        target = output / Path(options["epw_paths"]).name
        shutil.copyfile(options["epw_paths"], target)
        return [str(target)]

    backend.morph_epw_global = only_input
    monkeypatch.setattr(morphing, "_runtime", lambda _: backend)
    with pytest.raises(MorphingError, match="did not produce"):
        morph_epw(
            source,
            tmp_path / "future",
            MorphConfig(
                str(tmp_path / "fwg.jar"),
                scenarios=("ssp245",),
                periods=(2050,),
                version="4",
            ),
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"scenarios": ("rcp45",)},
        {"periods": (2100,)},
        {"models": "CanESM5"},
        {"version": "2"},
        {"scenarios": ("ssp245", "ssp245")},
    ],
)
def test_morph_selection_errors_before_runtime(tmp_path, monkeypatch, changes):
    monkeypatch.setattr(
        morphing, "_runtime", lambda _: pytest.fail("runtime should not be used")
    )
    with pytest.raises(ValidationError):
        morph_epw(
            "absent.epw",
            tmp_path,
            replace(MorphConfig("fwg.jar", version="4"), **changes),
        )


def test_batch_records_partial_failure_and_checks_whole_plan(tmp_path, monkeypatch):
    calls = []

    def compile(config):
        calls.append(config.year)
        if config.year == 2024:
            raise IngestionError("provider unavailable")
        Path(config.output_path).write_text("completed baseline")
        return SimpleNamespace(rows=8760, report=SimpleNamespace(warnings=[]))

    monkeypatch.setattr(batch, "compile_epw", compile)
    location = WeatherLocation("gbg", station_id=71420)
    with pytest.raises(IngestionError, match="provider unavailable"):
        compile_amy_batch([location], [2023, 2024], tmp_path)
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert manifest["status"] == "failed"
    assert [job["status"] for job in manifest["jobs"]] == ["completed", "failed"]
    with pytest.raises(ValidationError, match="overwrite"):
        compile_amy_batch([location], [2023, 2024], tmp_path)
    assert calls == [2023, 2024]


def test_batch_morphs_every_location_year_and_family(tmp_path, monkeypatch):
    monkeypatch.setattr(batch, "_runtime", lambda _: None)
    monkeypatch.setattr(
        morphing, "_runtime", lambda config: _backend(current[0], config.family)
    )
    current = [None]
    (tmp_path / "fwg.jar").write_bytes(b"fake jar for receipt hashing")

    def compile(config):
        current[0] = _epw(Path(config.output_path), config.year)
        return SimpleNamespace(
            rows=expected_rows(config.year), report=SimpleNamespace(warnings=[])
        )

    monkeypatch.setattr(batch, "compile_epw", compile)
    result = compile_amy_batch(
        [WeatherLocation("a", station_id=1), WeatherLocation("b", station_id=2)],
        [2023, 2024],
        tmp_path / "study",
        morphing=[
            MorphConfig(
                str(tmp_path / "fwg.jar"),
                scenarios=("ssp245",),
                periods=(2050,),
                version="4",
            ),
            MorphConfig(
                str(tmp_path / "fwg.jar"),
                family="rcp",
                scenarios=("rcp45",),
                periods=(2080,),
                version="2",
            ),
        ],
    )
    assert len(result.amy_results) == 4
    assert len(result.morph_results) == 8
    assert len({result.output_path for result in result.morph_results}) == 8
    assert json.loads(Path(result.manifest_path).read_text())["status"] == "completed"


def test_missing_runtime_fails_before_compilation(tmp_path, monkeypatch):
    monkeypatch.setattr(
        batch, "compile_epw", lambda _: pytest.fail("should preflight JAR first")
    )
    with pytest.raises(MorphingError, match="JAR does not exist"):
        compile_amy_batch(
            [WeatherLocation("a", station_id=1)],
            [2023],
            tmp_path,
            morphing=[MorphConfig("FutureWeatherGenerator_v4.0.2.jar")],
        )
    assert not (tmp_path / "manifest.json").exists()


def test_batch_publication_preserves_a_concurrent_writer(tmp_path, monkeypatch):
    target = tmp_path / "a" / "2023" / "a_2023.epw"

    def compile(config):
        target.write_bytes(b"concurrent writer")
        Path(config.output_path).write_bytes(b"new compilation")
        return SimpleNamespace(
            output_path=config.output_path,
            rows=8760,
            report=SimpleNamespace(warnings=[]),
        )

    monkeypatch.setattr(batch, "compile_epw", compile)
    with pytest.raises(FileExistsError):
        compile_amy_batch([WeatherLocation("a", station_id=1)], [2023], tmp_path)
    assert target.read_bytes() == b"concurrent writer"


def test_batch_real_compiler_receipt_uses_published_paths(tmp_path, monkeypatch):
    compile = batch.compile_epw

    def replay(config):
        return compile(
            config,
            client=CachedClient(
                cache_dir=None, session=ReplaySession(config.year), max_retries=0
            ),
        )

    monkeypatch.setattr(batch, "compile_epw", replay)
    result = compile_amy_batch(
        [WeatherLocation("fixture", latitude=57.7, longitude=12.0)], [2023], tmp_path
    )
    output = result.amy_results[0].output_path
    receipt = json.loads(Path(output + ".json").read_text())
    assert receipt["configuration"]["output_path"] == output
    assert receipt["configuration"]["provenance_path"] == output + ".json"
    assert receipt["result"]["output_path"] == output
    assert receipt["epw_sha256"] == morphing.file_sha256(Path(output))
    assert len(read_epw(output)) == 8760
    assert not list(Path(output).parent.glob(".smhi2epw-amy-*"))


def test_cli_dry_run_resolves_relative_paths_without_runtime(tmp_path, capsys):
    config = tmp_path / "batch.json"
    config.write_text(
        json.dumps(
            {
                "locations": [{"name": "gbg", "station_id": 71420}],
                "years": [2023, 2024],
                "output_dir": "study",
                "morphing": [
                    {
                        "fwg_jar_path": "FutureWeatherGenerator_v4.0.2.jar",
                        "scenarios": ["ssp245"],
                    }
                ],
            }
        )
    )
    assert cli.main(["batch", str(config), "--dry-run"]) == 0
    plan = json.loads(capsys.readouterr().out)
    assert len(plan["amy_jobs"]) == 2
    assert plan["morphing"][0]["fwg_jar_path"] == str(
        tmp_path / "FutureWeatherGenerator_v4.0.2.jar"
    )
    assert not (tmp_path / "study").exists()


def test_cli_malformed_config_returns_handled_error(tmp_path, capsys):
    config = tmp_path / "batch.json"
    config.write_text('{"locations": null, "years": [2023], "output_dir": "study"}')
    assert cli.main(["batch", str(config)]) == 1
    assert "locations must be a list" in capsys.readouterr().err


@pytest.mark.skipif(
    importlib.util.find_spec("pyfwg") is None,
    reason="optional morphing extra not installed",
)
@pytest.mark.parametrize(
    "family,version,model",
    [
        ("ssp", "4", "CanESM5"),
        ("rcp", "2", "ICHEC_EC_EARTH_SMHI_RCA4"),
        ("ssp", "5", "CanESM5"),
        ("rcp", "3", "ICHEC_EC_EARTH_SMHI_RCA4"),
    ],
)
@pytest.mark.parametrize("default_models", [False, True])
def test_real_pyfwg_api_with_simulated_java(
    tmp_path, source, monkeypatch, family, version, model, default_models
):
    """Exercise actual pyfwg staging, validation and file naming offline."""
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    backend = morphing._load_pyfwg()
    assert root.handlers == handlers and root.level == level
    jar = (
        tmp_path
        / f"FutureWeatherGenerator_{'Europe_' if family == 'rcp' else ''}v{version}.0.2.jar"
    )
    jar.write_bytes(b"simulated java tool")
    commands = []

    def java(command, **kwargs):
        commands.append(command)
        if command == ["java", "-version"]:
            return subprocess.CompletedProcess(command, 0, "java test", "")
        engine = (family == "ssp" and version == "5") or (
            family == "rcp" and version == "3"
        )
        assert ("-g" in command) is engine
        assert ("-uhi=false" in command) is not engine
        assert "-models=None" not in command
        output = Path(
            next(
                arg.split("=", 1)[1]
                for arg in command
                if arg.startswith("-output_folder=")
            )
        )
        input_path = Path(
            next(arg.split("=", 1)[1] for arg in command if arg.startswith("-epw="))
        )
        if engine:
            assert input_path.read_text().splitlines()[7].endswith(",1/1,12/31")
            output = output / "weather"
            output.mkdir()
        for scenario in morphing.SCENARIOS[family]:
            for period in morphing.PERIODS:
                name = (
                    f"SWE_Gothenburg_ensemble_{scenario}_{period}.epw"
                    if engine
                    else f"{scenario}_{period}.epw"
                )
                content = input_path.read_text().splitlines()
                if engine:
                    content[8:] = [
                        str(period) + "," + row.split(",", 1)[1] for row in content[8:]
                    ]
                (output / name).write_text("\n".join(content) + "\n")
        return subprocess.CompletedProcess(command, 0, "morphed", "")

    monkeypatch.setattr(morphing.shutil, "which", lambda _: "/fake/java")
    monkeypatch.setattr(morphing.subprocess, "run", java)
    scenario = morphing.SCENARIOS[family][0]
    results = morph_epw(
        source,
        tmp_path / "future",
        MorphConfig(
            str(jar),
            family=family,
            scenarios=(scenario,),
            periods=(2050,),
            models=() if default_models else (model,),
        ),
    )
    assert len(results) == 1 and len(commands) == 2
    assert backend.__version__ == "0.4.0"
    assert read_epw(results[0].output_path).minute.eq(60).all()
    assert read_epw(results[0].output_path).year.eq(2023).all()
    assert read_epw(source).minute.eq(60).all()


@pytest.mark.parametrize(
    "family,version,scenario", [("ssp", "5", "ssp245"), ("rcp", "3", "rcp45")]
)
def test_current_engine_receives_selected_scenarios_and_periods(
    tmp_path, source, monkeypatch, family, version, scenario
):
    backend = _backend(source, family)
    run = backend.morph_epw_global if family == "ssp" else backend.morph_epw_europe
    calls = []

    def capture(**options):
        calls.append(options)
        return run(**options)

    backend.morph_epw_global = capture
    backend.morph_epw_europe = capture
    monkeypatch.setattr(morphing, "_runtime", lambda _: backend)
    result = morph_epw(
        source,
        tmp_path / "future",
        MorphConfig(
            str(tmp_path / "fwg.jar"),
            family=family,
            scenarios=(scenario,),
            periods=(2050,),
            version=version,
        ),
    )
    assert len(result) == 1
    assert calls[0]["fwg_scenarios"] == [scenario]
    assert calls[0]["fwg_timeframes"] == [2050]
    assert calls[0]["fwg_uncertainty_variant"] == "CENTRAL"
    receipt = json.loads(Path(result[0].provenance_path).read_text())
    # pyfwg disables ensemble generation for a current engine with one model.
    assert receipt["ensemble"] is False


@pytest.mark.parametrize(
    "failure", ["missing_interval", "shifted_interval", "ambiguous"]
)
def test_morph_rejects_unmatched_calendar_or_ambiguous_product(
    tmp_path, source, monkeypatch, failure
):
    backend = _backend(source)
    run = backend.morph_epw_global

    def invalid(**options):
        paths = run(**options)
        target = Path(paths[0])
        if failure == "ambiguous":
            duplicate = target.with_name("different_model_" + target.name)
            shutil.copyfile(target, duplicate)
            paths.append(str(duplicate))
        else:
            lines = target.read_text().splitlines()
            if failure == "missing_interval":
                lines.pop()
            else:
                fields = lines[8].split(",")
                fields[3] = "2"
                lines[8] = ",".join(fields)
            target.write_text("\n".join(lines) + "\n")
        return paths

    backend.morph_epw_global = invalid
    monkeypatch.setattr(morphing, "_runtime", lambda _: backend)
    destination = tmp_path / "future"
    with pytest.raises(MorphingError):
        morph_epw(
            source,
            destination,
            MorphConfig(
                str(tmp_path / "fwg.jar"),
                scenarios=("ssp126",),
                periods=(2050,),
                version="4",
            ),
        )
    assert not list(destination.glob("*.epw"))


@pytest.mark.fwg
@pytest.mark.parametrize(
    "family,variable,scenario,model",
    [
        ("ssp", "SMHI2EPW_GLOBAL_FWG_JAR", "ssp245", "CanESM5"),
        ("rcp", "SMHI2EPW_EUROPE_FWG_JAR", "rcp45", "ICHEC_EC_EARTH_SMHI_RCA4"),
    ],
)
def test_real_fwg_generates_valid_weather(tmp_path, family, variable, scenario, model):
    """Require real supplied executables when this integration gate is selected."""
    jar = os.environ.get(variable)
    assert jar, f"set {variable} to a real FWG JAR before selecting the fwg gate"
    source = Path(compile_weather(tmp_path / "baseline").output_path)
    before = read_epw(source)
    source_hash = morphing.file_sha256(source)
    outputs = morph_epw(
        source,
        tmp_path / "real-future",
        MorphConfig(
            jar, family=family, scenarios=(scenario,), periods=(2050,), models=(model,)
        ),
    )
    assert len(outputs) == 1
    weather = read_epw(outputs[0].output_path)
    assert len(weather) == 8760
    assert weather.dry_bulb.notna().all()
    assert not weather.dry_bulb.equals(before.dry_bulb)
    for column in ("year", "month", "day", "hour", "minute"):
        assert weather[column].equals(before[column])
    assert morphing.file_sha256(source) == source_hash
    assert json.loads(Path(outputs[0].provenance_path).read_text())[
        "source_calendar_years"
    ] == [2023]
