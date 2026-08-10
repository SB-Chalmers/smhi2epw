"""CLI and cache behavior that does not require live SMHI access."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from smhi2epw import cli
from smhi2epw.errors import IngestionError
from smhi2epw.ingestion import CachedClient


class _Response:
    text = '{"fresh": true}'

    def raise_for_status(self):
        return None


class _Session:
    def __init__(self):
        self.calls = 0

    def get(self, url, timeout):
        self.calls += 1
        return _Response()


def test_corrupt_json_cache_is_refetched_atomically(tmp_path):
    session = _Session()
    client = CachedClient(cache_dir=str(tmp_path), session=session, max_retries=0)
    url = "https://example.invalid/data.json"
    cache_path = client._cache_path(url, "json")
    assert cache_path is not None
    Path(cache_path).write_text("not-json", encoding="utf-8")

    assert client.get_json(url) == {"fresh": True}
    assert session.calls == 1
    assert not list(tmp_path.glob(".smhi2epw-*"))


def test_cli_success_passes_radiation_distance(monkeypatch, tmp_path, capsys):
    captured = {}

    def fake_compile(config):
        captured["config"] = config
        return SimpleNamespace(
            rows=8760,
            output_path=config.output_path,
            interpolated_fraction=0.01,
            report=SimpleNamespace(solar_source="strang"),
        )

    monkeypatch.setattr(cli, "compile_epw", fake_compile)
    output = tmp_path / "cli.epw"
    result = cli.main(
        [
            "2023",
            str(output),
            "--station",
            "71420",
            "--radiation-station-max-distance",
            "25",
        ]
    )
    assert result == 0
    assert captured["config"].radiation_station_max_distance_km == 25.0
    assert "OK: 8760 rows" in capsys.readouterr().out


def test_cli_domain_error_returns_one(monkeypatch, tmp_path, capsys):
    def fail(_config):
        raise IngestionError("offline")

    monkeypatch.setattr(cli, "compile_epw", fail)
    result = cli.main(["2023", str(tmp_path / "x.epw"), "--station", "71420"])
    assert result == 1
    assert "error: offline" in capsys.readouterr().err
