"""Reject unusable station metadata before automatic source recovery."""

import copy

import pytest
from test_automatic import LAT, LON, ArchiveClient

from smhi2epw import EPWConfig, compile_epw, read_epw
from smhi2epw.errors import IngestionError, ValidationError


class MetadataClient(ArchiveClient):
    def __init__(self, metadata):
        super().__init__()
        self.metadata = metadata

    def get_json(self, url):
        if url.endswith("/station/1.json"):
            self.urls.append(url)
            return self.metadata
        return super().get_json(url)


def _metadata(**changes):
    position = {
        "from": 0,
        "to": 9999999999999,
        "latitude": LAT,
        "longitude": LON,
        "height": 100.0,
    }
    position.update(changes)
    return {"title": "Unusable station", "position": [position]}


@pytest.mark.parametrize(
    "metadata",
    [
        _metadata(latitude="not-a-coordinate"),
        _metadata(latitude=float("nan")),
        _metadata(longitude=181),
        _metadata(height=float("inf")),
        _metadata(height=10000),
        {"position": [{"from": 0, "to": 9999999999999, "latitude": LAT}]},
    ],
)
def test_unusable_metadata_falls_back_with_coordinates_and_warns(tmp_path, metadata):
    config = EPWConfig(
        2020,
        str(tmp_path / "weather.epw"),
        station_id=1,
        latitude=LAT,
        longitude=LON,
        radiation_station_auto=False,
    )
    client = MetadataClient(copy.deepcopy(metadata))
    result = compile_epw(config, client=client)

    assert result.station is None
    assert len(read_epw(result.output_path)) == 8784
    assert result.report.weather_classification == "reanalysis_only"
    assert "station_unavailable" in {
        warning["code"] for warning in result.report.warnings
    }
    assert len(client.urls) == 2

    strict_client = MetadataClient(copy.deepcopy(metadata))
    config.weather_policy = "strict"
    config.output_path = str(tmp_path / "strict.epw")
    with pytest.raises(IngestionError):
        compile_epw(config, client=strict_client)
    assert len(strict_client.urls) == 1
    assert not (tmp_path / "strict.epw").exists()


@pytest.mark.parametrize("field", ["cache_ttl", "radiation_station_max_distance_km"])
@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_optional_limits_fail_before_network(tmp_path, field, value):
    config = EPWConfig(2020, str(tmp_path / "weather.epw"), station_id=1)
    setattr(config, field, value)
    client = ArchiveClient()

    with pytest.raises(IngestionError):
        compile_epw(config, client=client)

    assert client.urls == []
    assert not (tmp_path / "weather.epw").exists()


@pytest.mark.parametrize("policy", ["automatic", "strict"])
def test_sidecar_serialization_failure_keeps_valid_epw_with_clear_outcome(
    tmp_path, monkeypatch, policy
):
    from smhi2epw import provenance

    def fail_serialization(*args):
        raise ValueError("simulated JSON serialization failure")

    monkeypatch.setattr(provenance, "write_provenance", fail_serialization)
    output = tmp_path / "weather.epw"
    config = EPWConfig(
        2020,
        str(output),
        station_id=1,
        latitude=LAT,
        longitude=LON,
        radiation_station_auto=False,
        weather_policy=policy,
        provenance_path=str(tmp_path / "weather.json"),
    )
    if policy == "automatic":
        client = MetadataClient(_metadata(latitude="invalid"))
        result = compile_epw(config, client=client)
        assert "provenance_write_failed" in {
            warning["code"] for warning in result.report.warnings
        }
    else:
        from test_provenance import _RecordingFakeClient

        config.year = 2021
        config.station_id = 98210
        with pytest.raises(ValidationError, match="EPW written but provenance failed"):
            compile_epw(config, client=_RecordingFakeClient())
    assert len(read_epw(output)) == (8784 if policy == "automatic" else 8760)
