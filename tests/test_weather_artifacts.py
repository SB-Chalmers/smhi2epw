# SPDX-License-Identifier: MIT
# Copyright (c) 2026 smhi2epw contributors
# License: See LICENSE at the project root.
"""Check artifact publication and bounded weather inspection requirements."""

import json
from pathlib import Path

import pytest

from smhi2epw import BatchResult, MorphConfig, MorphResult, WeatherLocation, io


def test_no_overwrite_is_enforced_at_publication(tmp_path, monkeypatch):
    source, target = tmp_path / "stage", tmp_path / "published"
    source.write_bytes(b"new complete file")
    link = io.os.link

    def race(staged, destination):
        Path(destination).write_bytes(b"concurrent writer")
        return link(staged, destination)

    monkeypatch.setattr(io.os, "link", race)
    with pytest.raises(FileExistsError):
        io.publish_file(source, target)
    assert target.read_bytes() == b"concurrent writer"
    assert source.read_bytes() == b"new complete file"


def test_json_no_overwrite_and_explicit_replace(tmp_path):
    target = tmp_path / "receipt.json"
    io.write_json(target, {"schema_version": 1, "state": "running"})
    with pytest.raises(FileExistsError):
        io.write_json(target, {"state": "other"})
    assert json.loads(target.read_text())["state"] == "running"
    io.write_json(target, {"schema_version": 1, "state": "completed"}, overwrite=True)
    assert json.loads(target.read_text())["state"] == "completed"
    assert len(list(tmp_path.iterdir())) == 1


@pytest.mark.parametrize(
    "document",
    [
        '{"year":2023,"year":2024}',
        '{"latitude":NaN}',
        '{"latitude":Infinity}',
        '{"latitude":1e309}',
    ],
)
def test_json_rejects_ambiguous_or_nonfinite_input(tmp_path, document):
    target = tmp_path / "input.json"
    target.write_text(document)
    with pytest.raises(ValueError):
        io.read_json(target)


def test_json_encoding_failure_preserves_previous_receipt(tmp_path):
    target = tmp_path / "receipt.json"
    target.write_text("existing")
    with pytest.raises(ValueError):
        io.write_json(target, {"invalid": float("nan")}, overwrite=True)
    assert target.read_text() == "existing"
    assert len(list(tmp_path.iterdir())) == 1


def test_weather_objects_offer_bounded_loaded_inspection(tmp_path, monkeypatch):
    unusual = "name\n\\'\t😀" * 200
    objects = [
        WeatherLocation(unusual, station_id=71420),
        MorphConfig(unusual, scenarios=("ssp245",) * 100),
        MorphResult(unusual, unusual, "ssp245", 2050, unusual),
        BatchResult([], [], unusual),
    ]

    def no_io(*args, **kwargs):
        pytest.fail("inspection must not access files")

    monkeypatch.setattr(Path, "open", no_io)
    for item in objects:
        assert len(repr(item)) <= 160
        assert len(str(item)) <= 160
        assert "\n" not in repr(item) and "\n" not in str(item)
        assert isinstance(item.summary(), dict)
    assert objects[0].summary()["name"] == unusual
