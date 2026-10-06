"""Automatic-policy integration with deterministic, same-year source payloads."""

import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import numpy as np
import pandas as pd
import pytest

from smhi2epw import compiler, export, ingestion, read_epw, reanalysis
from smhi2epw.errors import DataGapError, IngestionError
from smhi2epw.ingestion import StationMeta
from smhi2epw.solar import solar_zenith

LAT, LON = 59.3, 18.0


def _payload(index, elevation=100.0):
    cosine = solar_zenith(index - pd.Timedelta(minutes=30), LAT, LON)[1]
    ghi = np.maximum(cosine, 0) * 700
    heatwave = (index >= "2020-07-20") & (index < "2020-07-23")
    values = {
        "temperature_2m": np.where(heatwave, 35.0, 12.0),
        "relative_humidity_2m": np.full(len(index), 60.0),
        "surface_pressure": np.full(len(index), 990.0),
        "wind_speed_10m": np.full(len(index), 3.0),
        "wind_direction_10m": np.full(len(index), 359.0),
        "cloud_cover": np.full(len(index), 40.0),
        "shortwave_radiation": ghi,
        "direct_normal_irradiance": np.where(cosine > 0, 420.0, 0.0),
        "direct_radiation": ghi * 0.6,
    }
    return {
        "latitude": LAT,
        "longitude": LON,
        "elevation": elevation,
        "utc_offset_seconds": 0,
        "hourly": {
            "time": index.strftime("%Y-%m-%dT%H:%M").tolist(),
            **{key: values[key].tolist() for key in values},
        },
        "hourly_units": {key: unit for key, (_, unit) in reanalysis.VARIABLES.items()},
    }


class ArchiveClient:
    def __init__(self, malformed=None):
        self.urls = []
        self.malformed = malformed

    def get_json(self, url):
        self.urls.append(url)
        if not url.startswith(reanalysis.ENDPOINT):
            raise IngestionError("SMHI source offline")
        query = parse_qs(urlparse(url).query)
        assert query["models"] == ["era5"]
        assert query["timezone"] == ["GMT"]
        assert query["wind_speed_unit"] == ["ms"]
        index = pd.date_range(
            query["start_date"][0], query["end_date"][0] + " 23:00", freq="h", tz="UTC"
        )
        result = _payload(index, float(query.get("elevation", [100])[0]))
        if self.malformed:
            self.malformed(result)
        return result


def _primary_frame(year=2020, offset=1):
    buffer = abs(offset) + 1
    index = pd.date_range(
        pd.Timestamp(year=year, month=1, day=1, tz="UTC") - pd.Timedelta(hours=buffer),
        pd.Timestamp(year=year + 1, month=1, day=1, tz="UTC")
        + pd.Timedelta(hours=buffer - 1),
        freq="h",
    )
    payload = _payload(index)
    return pd.DataFrame(
        {
            "dry_bulb": payload["hourly"]["temperature_2m"],
            "relative_humidity": 60.0,
            "pressure": 1013.0,
            "wind_speed": 3.0,
            "wind_direction": 359.0,
            "cloud_cover": 3.2,
            "ghi": payload["hourly"]["shortwave_radiation"],
            "dni": payload["hourly"]["direct_normal_irradiance"],
            "dirh": payload["hourly"]["direct_radiation"],
        },
        index=index,
    )


@pytest.fixture
def primary(monkeypatch):
    frame = _primary_frame()
    monkeypatch.setattr(
        compiler,
        "get_station_metadata",
        lambda *a, **k: StationMeta(1, "Test", LAT, LON, 100),
    )
    monkeypatch.setattr(compiler, "ingest", lambda *a, **k: frame.copy(deep=True))
    monkeypatch.setattr(ingestion, "_stations_for_parameter", lambda *a, **k: {})
    return frame


def _config(tmp_path, **kwargs):
    return compiler.EPWConfig(
        2020,
        str(tmp_path / "weather.epw"),
        station_id=1,
        radiation_station_auto=False,
        **kwargs,
    )


def test_default_preserves_requested_heatwave_with_reanalysis(primary, tmp_path):
    missing = (primary.index >= "2020-07-20") & (primary.index < "2020-07-23")
    primary.loc[missing, "dry_bulb"] = np.nan
    original = primary.dry_bulb.copy()
    client = ArchiveClient()
    result = compiler.compile_epw(_config(tmp_path), client=client)
    weather = read_epw(result.output_path)
    assert result.rows == 8784
    assert result.report.reanalysis_filled_hours["dry_bulb"] == 72
    assert result.report.weather_classification == "mixed_reconstructed"
    assert len(client.urls) == 1
    assert (
        weather.loc[(weather.month == 7) & weather.day.between(20, 22), "dry_bulb"]
        .eq(35)
        .all()
    )
    assert weather.dry_bulb.max() == 35
    assert original.dropna().eq(12).all()
    saved = json.loads((tmp_path / "weather.epw.json").read_text())
    assert saved["configuration"]["weather_policy"] == "automatic"
    assert saved["result"]["report"]["reanalysis_metadata"]["model"] == "ERA5"
    assert not saved["raw_response_receipts_complete"]
    assert "Open-Meteo" in (tmp_path / "weather.epw").read_text().splitlines()[6]
    assert {w["code"] for w in result.report.warnings} >= {
        "reanalysis_used",
        "source_boundary_jump",
    }


def test_strict_preserves_long_gap_failure(primary, tmp_path):
    primary.iloc[100:150, primary.columns.get_loc("dry_bulb")] = np.nan
    client = ArchiveClient()
    with pytest.raises(DataGapError):
        compiler.compile_epw(_config(tmp_path, weather_policy="strict"), client=client)
    assert client.urls == []
    assert not (tmp_path / "weather.epw").exists()


def test_complete_sources_require_no_reanalysis(primary, tmp_path):
    client = ArchiveClient()
    result = compiler.compile_epw(_config(tmp_path), client=client)
    assert client.urls == []
    assert result.report.weather_classification == "observation_based"
    assert result.report.source_fractions["dry_bulb"] == {"primary": 1.0}


def test_temporal_diagnostics_are_preserved(primary, tmp_path):
    primary.iloc[100:102, primary.columns.get_loc("dry_bulb")] = np.nan
    result = compiler.compile_epw(_config(tmp_path), client=ArchiveClient())
    assert result.report.linear_filled_hours["dry_bulb"] == 2
    assert result.report.interpolated_fraction["dry_bulb"] > 0
    assert result.report.weather_classification == "mixed_reconstructed"
    assert result.report.source_fractions["dry_bulb"]["temporal"] == pytest.approx(
        2 / 8784
    )


def test_automatic_medium_gap_uses_assessed_donor_before_profiles(
    primary, tmp_path, monkeypatch
):
    primary.iloc[2000:2048, primary.columns.get_loc("dry_bulb")] = np.nan
    donor = pd.Series(14.0, index=primary.index)
    donor.iloc[2000:2048] = 25.0
    monkeypatch.setattr(
        ingestion,
        "_stations_for_parameter",
        lambda parameter, client: (
            {2: (LAT, LON, 0, 9999999999999)} if parameter == 1 else {}
        ),
    )
    monkeypatch.setattr(
        ingestion,
        "get_station_metadata",
        lambda *a, **k: StationMeta(2, "Donor", LAT, LON, 100),
    )
    monkeypatch.setattr(ingestion, "fetch_metobs_parameter", lambda *a, **k: donor)
    client = ArchiveClient()
    result = compiler.compile_epw(_config(tmp_path), client=client)
    assert client.urls == []
    assert result.report.cross_station_filled_hours == {"dry_bulb": 48}
    assert result.report.diurnal_filled_hours["dry_bulb"] == 0
    assert result.report.source_fractions["dry_bulb"]["donor"] == pytest.approx(
        48 / 8784
    )
    assert read_epw(result.output_path).dry_bulb.eq(23).sum() == 48


def test_era5_clouds_do_not_change_unmasked_epw_hours(primary, tmp_path):
    primary["cloud_cover"] = np.nan
    baseline_dir, candidate_dir = tmp_path / "baseline", tmp_path / "candidate"
    baseline_dir.mkdir()
    candidate_dir.mkdir()
    baseline = compiler.compile_epw(_config(baseline_dir), client=ArchiveClient())
    missing = (primary.index >= "2020-07-20") & (primary.index < "2020-07-23")
    primary.loc[missing, "dry_bulb"] = np.nan
    candidate = compiler.compile_epw(_config(candidate_dir), client=ArchiveClient())
    baseline_rows = Path(baseline.output_path).read_text().splitlines()[8:]
    candidate_rows = Path(candidate.output_path).read_text().splitlines()[8:]
    changed = export.shift_to_lst(
        pd.DataFrame({"mask": missing}, index=primary.index), 2020, 1
    )["mask"]
    assert sum(changed) == 72
    assert all(
        before == after
        for before, after, hidden in zip(baseline_rows, candidate_rows, changed)
        if not hidden
    )
    assert candidate.report.reanalysis_filled_hours["cloud_cover"] == 72


@pytest.mark.parametrize("year,offset,rows", [(2020, 14, 8784), (2021, -12, 8760)])
def test_reanalysis_only_year_without_station(
    monkeypatch, tmp_path, year, offset, rows
):
    config = compiler.EPWConfig(
        year,
        str(tmp_path / "only-model.epw"),
        latitude=LAT,
        longitude=LON,
        utc_offset=offset,
        radiation_station_auto=False,
    )
    result = compiler.compile_epw(config, client=ArchiveClient())
    weather = read_epw(result.output_path)
    assert result.rows == rows
    assert result.station is None
    assert result.coordinate_distance_km is None
    assert result.target_elevation_m == 100
    assert result.pressure_method == "era5_surface_pressure"
    assert weather.pressure.eq(99000).all()
    assert result.report.weather_classification == "reanalysis_only"
    assert weather.iloc[0][["month", "day", "hour"]].tolist() == [1, 1, 1]
    assert weather.iloc[-1][["month", "day", "hour"]].tolist() == [12, 31, 24]
    assert weather.attrs["location"]["source"] == "ERA5-AMY"


def test_invalid_primary_samples_recovered_and_counted(primary, tmp_path):
    primary.loc[primary.index[100:150], "wind_speed"] = np.inf
    result = compiler.compile_epw(_config(tmp_path), client=ArchiveClient())
    assert result.report.invalid_observation_hours["wind_speed"] == 50
    assert result.report.reanalysis_filled_hours["wind_speed"] == 50
    assert read_epw(result.output_path).wind_speed.eq(3).all()


def test_failed_reanalysis_preserves_existing_output(primary, tmp_path):
    primary["wind_speed"] = np.nan
    output = tmp_path / "weather.epw"
    output.write_text("previous valid artifact")

    class Offline:
        def get_json(self, url):
            raise IngestionError("all providers offline")

    with pytest.raises(DataGapError, match="Same-year sources"):
        compiler.compile_epw(_config(tmp_path), client=Offline())
    assert output.read_text() == "previous valid artifact"


def test_provenance_failure_returns_valid_epw_warning(primary, tmp_path, monkeypatch):
    from smhi2epw import provenance

    def fail(*args):
        raise OSError("disk full")

    monkeypatch.setattr(provenance, "write_provenance", fail)
    result = compiler.compile_epw(_config(tmp_path), client=ArchiveClient())
    assert len(read_epw(result.output_path)) == 8784
    assert result.report.warnings[-1]["code"] == "provenance_write_failed"


@pytest.mark.parametrize("settings", [{"weather_policy": "unknown"}, {"year": 2099}])
def test_unsupported_policy_and_future_year_before_network(tmp_path, settings):
    client = ArchiveClient()
    config = _config(tmp_path)
    for key, value in settings.items():
        setattr(config, key, value)
    with pytest.raises(IngestionError):
        compiler.compile_epw(config, client=client)
    assert client.urls == []


def test_adapter_keeps_preceding_hour_radiation_and_surface_pressure():
    index = pd.date_range("2020-06-20 00:00", periods=48, freq="h", tz="UTC")
    result, metadata = reanalysis.fetch(LAT, LON, 300, index, ArchiveClient())
    expected = _payload(index, 300)
    np.testing.assert_array_equal(result.ghi, expected["hourly"]["shortwave_radiation"])
    assert result.reanalysis_surface_pressure.eq(99000).all()
    assert result.wind_speed.eq(3).all()
    assert result.cloud_cover.eq(3.2).all()
    assert metadata["elevation_m"] == 300


@pytest.mark.parametrize(
    "defect",
    [
        "units",
        "length",
        "offset",
        "duplicate",
        "missing",
        "elevation",
        "nonfinite_meta",
    ],
)
def test_adapter_rejects_malformed_payload(defect):
    index = pd.date_range("2020-01-01", periods=48, freq="h", tz="UTC")

    def corrupt(payload):
        if defect == "units":
            payload["hourly_units"]["surface_pressure"] = "Pa"
        elif defect == "length":
            payload["hourly"]["temperature_2m"].pop()
        elif defect == "offset":
            payload["utc_offset_seconds"] = 3600
        elif defect == "duplicate":
            payload["hourly"]["time"][1] = payload["hourly"]["time"][0]
        elif defect == "missing":
            payload["hourly"]["time"][0] = "2019-12-31T23:00"
        elif defect == "elevation":
            payload["elevation"] = 200
        else:
            payload["latitude"] = float("nan")

    with pytest.raises(IngestionError):
        reanalysis.fetch(LAT, LON, 100, index, ArchiveClient(corrupt))


def test_automatic_ingestion_records_failed_required_endpoint(monkeypatch):
    def unavailable(*args, **kwargs):
        raise IngestionError("source down")

    monkeypatch.setattr(ingestion, "fetch_metobs_parameter", unavailable)
    monkeypatch.setattr(ingestion, "fetch_strang_parameter", unavailable)
    frame = ingestion.ingest(
        StationMeta(1, "test", LAT, LON), 2020, ArchiveClient(), tolerate_failures=True
    )
    assert len(frame.attrs["source_failures"]) == 9
    assert frame.isna().all().all()
    with pytest.raises(IngestionError):
        ingestion.ingest(StationMeta(1, "test", LAT, LON), 2020, ArchiveClient())


def test_partial_station_selection(monkeypatch):
    start = int(pd.Timestamp("2020-06-01", tz="UTC").timestamp() * 1000)
    end = int(pd.Timestamp("2020-09-01", tz="UTC").timestamp() * 1000)
    monkeypatch.setattr(
        ingestion,
        "_stations_for_parameter",
        lambda param, client: {2: (LAT, LON, start, end)} if param == 1 else {},
    )
    monkeypatch.setattr(
        ingestion,
        "get_station_metadata",
        lambda *a, **k: StationMeta(2, "partial", LAT, LON),
    )
    assert (
        ingestion.find_nearest_station(
            LAT, LON, 2020, ArchiveClient(), allow_partial=True
        ).station_id
        == 2
    )
    with pytest.raises(IngestionError):
        ingestion.find_nearest_station(LAT, LON, 2020, ArchiveClient())
