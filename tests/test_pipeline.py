"""Offline tests for smhi2epw (no network access required)."""

from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd
import pytest

from smhi2epw import compile_epw, export, processing, solar
from smhi2epw import constants as C
from smhi2epw.compiler import EPWConfig
from smhi2epw.errors import DataGapError, IngestionError, ValidationError

# --------------------------------------------------------------------------- #
# Fake client returning deterministic synthetic payloads
# --------------------------------------------------------------------------- #
YEAR = 2021  # non-leap -> 8760 rows
STATION_ID = 98210
LAT, LON = 59.3, 18.0


def _utc_grid(year):
    return pd.date_range(f"{year}-01-01", f"{year}-12-31 23:00", freq="h", tz="UTC")


def _metobs_csv(name, base):
    grid = _utc_grid(YEAR)
    lines = [
        "Stationsnamn;Stationsnummer",
        f"Synthetic;{STATION_ID}",
        "",
        f"Datum;Tid (UTC);{name};Kvalitet",
    ]
    for i, ts in enumerate(grid):
        val = base + np.sin(i / 24.0)
        lines.append(f"{ts.strftime('%Y-%m-%d')};{ts.strftime('%H:%M:%S')};{val:.2f};G")
    return "\n".join(lines)


def _strang_json(base):
    grid = _utc_grid(YEAR)
    out = []
    for i, ts in enumerate(grid):
        # Daylight-shaped positive irradiance.
        val = max(0.0, base * np.sin(np.pi * (ts.hour) / 24.0))
        out.append({"date_time": ts.strftime("%Y-%m-%dT%H:%M:%SZ"), "value": val})
    return json.dumps(out)


class FakeClient:
    def __init__(self, gap_hours=0):
        self.gap_hours = gap_hours
        self.urls = []

    def get_text(self, url, suffix="txt"):
        self.urls.append(url)
        if "/parameter/11/" in url and "station" in url and url.endswith(".csv"):
            return _metobs_csv("Globalstrålning", 300.0)  # measured GHI (W/m²)
        if "/parameter/1/" in url and "station" in url and url.endswith(".csv"):
            csv = _metobs_csv("Lufttemperatur", 5.0)
            if self.gap_hours:
                csv = self._inject_gap(csv, self.gap_hours)
            return csv
        if "/parameter/6/" in url:
            return _metobs_csv("Relativ Luftfuktighet", 70.0)
        if "/parameter/9/" in url:
            return _metobs_csv("Lufttryck", 1013.0)
        if "/parameter/4/" in url:
            return _metobs_csv("Vindhastighet", 3.0)
        if "/parameter/3/" in url:
            return _metobs_csv("Vindriktning", 180.0)
        if "/parameter/16/" in url:
            return _metobs_csv("Total molnmangd", 4.0)  # octas
        raise AssertionError(f"unexpected text url: {url}")

    def get_json(self, url):
        self.urls.append(url)
        if url.endswith(f"/station/{STATION_ID}.json"):
            return {
                "title": "Synthetic Station",
                "key": "024640",
                "position": [
                    {
                        "from": 0,
                        "to": 9999999999999,
                        "latitude": LAT,
                        "longitude": LON,
                        "height": 12.0,
                    }
                ],
            }
        if url.endswith("/parameter/11.json"):
            return {
                "station": [
                    {
                        "key": str(STATION_ID),
                        "name": "Synthetic Sol",
                        "latitude": LAT,
                        "longitude": LON,
                        "from": 0,
                        "to": 9999999999999,
                    }
                ]
            }
        if url.endswith("/parameter/1.json"):
            return {
                "station": [
                    {
                        "key": str(STATION_ID),
                        "latitude": LAT,
                        "longitude": LON,
                        "from": 0,
                        "to": 9999999999999,
                    },
                    {
                        "key": "11111",
                        "latitude": LAT + 5.0,
                        "longitude": LON + 5.0,
                        "from": 0,
                        "to": 9999999999999,
                    },
                ]
            }
        if any(url.endswith(f"/parameter/{p}.json") for p in (3, 4, 6, 9)):
            return {
                "station": [
                    {
                        "key": str(STATION_ID),
                        "latitude": LAT,
                        "longitude": LON,
                        "from": 0,
                        "to": 9999999999999,
                    }
                ]
            }
        if "/parameter/117/" in url:
            return json.loads(_strang_json(800.0))  # GHI
        if "/parameter/118/" in url:
            return json.loads(_strang_json(600.0))  # DNI (direct normal)
        if "/parameter/121/" in url:
            return json.loads(_strang_json(300.0))  # direct beam on horizontal
        raise AssertionError(f"unexpected json url: {url}")

    @staticmethod
    def _inject_gap(csv, gap_hours):
        lines = csv.splitlines()
        header = next(i for i, line in enumerate(lines) if line.startswith("Datum"))
        for i in range(header + 10, header + 10 + gap_hours):
            parts = lines[i].split(";")
            parts[2] = ""
            lines[i] = ";".join(parts)
        return "\n".join(lines)


# --------------------------------------------------------------------------- #
# Unit-level tests
# --------------------------------------------------------------------------- #
def test_dew_point_below_dry_bulb():
    dry = pd.Series([20.0, 0.0, 30.0])
    rh = pd.Series([50.0, 80.0, 90.0])
    td = processing.dew_point(dry, rh)
    assert (td <= dry).all()


def test_horizontal_ir_reasonable_range():
    dry = pd.Series([15.0])
    td = pd.Series([8.0])
    ir = processing.horizontal_ir(dry, td)
    assert 200.0 < ir.iloc[0] < 450.0


def test_apply_solar_floor_and_diffuse():
    idx = pd.date_range("2021-06-21", periods=24, freq="h", tz="UTC")
    frame = pd.DataFrame(
        {
            "ghi": np.full(24, 500.0),
            "dni": np.full(24, 700.0),
            "dirh": np.full(24, 300.0),
        },
        index=idx,
    )
    processing.apply_solar(frame, LAT, LON)
    _, cos_z = solar.solar_zenith(idx - pd.Timedelta(minutes=30), LAT, LON)
    # STRÅNG path: DNI forced to 0 when the sun is below the horizon floor.
    assert (frame["dni"].to_numpy()[cos_z <= C.COS_ZENITH_FLOOR] == 0).all()
    # DHI closes with the exported DNI and is never negative.
    assert (frame["dhi"] >= 0).all()
    residual = frame["ghi"] - (frame["dhi"] + frame["dni"] * np.clip(cos_z, 0.0, None))
    assert np.max(np.abs(residual)) < 1e-9


def test_imputation_short_gap_ok():
    idx = _utc_grid(YEAR)
    frame = pd.DataFrame({"dry_bulb": np.arange(len(idx), dtype=float)}, index=idx)
    frame.iloc[5:8, 0] = np.nan  # 3-hour gap
    report = processing.impute(frame, ["dry_bulb"])
    assert not frame["dry_bulb"].isna().any()
    assert report.total_interpolated_fraction > 0


def test_imputation_reference_gap_fills():
    idx = _utc_grid(YEAR)
    frame = pd.DataFrame({"dry_bulb": np.arange(len(idx), dtype=float)}, index=idx)
    frame.iloc[5:11, 0] = np.nan  # 6-hour gap
    report = processing.impute(frame, ["dry_bulb"])
    assert not frame["dry_bulb"].isna().any()
    assert report.diurnal_filled_hours["dry_bulb"] == 6


def test_imputation_over_48_hours_raises():
    idx = _utc_grid(YEAR)
    frame = pd.DataFrame({"dry_bulb": np.arange(len(idx), dtype=float)}, index=idx)
    frame.iloc[100:149, 0] = np.nan
    with pytest.raises(DataGapError, match="49-hour"):
        processing.impute(frame, ["dry_bulb"])


def test_pressure_unit_conversion():
    idx = _utc_grid(YEAR)
    frame = pd.DataFrame({"pressure": np.full(len(idx), 1013.0)}, index=idx)
    processing.convert_units(frame)
    assert np.isclose(frame["pressure"].iloc[0], 101300.0)


# --------------------------------------------------------------------------- #
# Export-level tests
# --------------------------------------------------------------------------- #
def test_expected_rows():
    assert export.expected_rows(2021) == 8760
    assert export.expected_rows(2020) == 8784


def test_header_has_eight_lines():
    header = export.build_header(
        "Stockholm", "SE", "SWE", "024640", 59.3, 18.0, 1.0, 12.0, 2021, STATION_ID
    )
    assert len(header) == 8
    assert header[0].startswith("LOCATION,Stockholm,SE,SWE,SMHI-AMY,024640")
    assert header[2] == "TYPICAL/EXTREME PERIODS,0"
    assert header[3] == "GROUND TEMPERATURES,0"
    assert header[7] == "DATA PERIODS,1,1,Data,Friday,1/1,12/31"


# --------------------------------------------------------------------------- #
# End-to-end test against the fake client
# --------------------------------------------------------------------------- #
def test_compile_epw_end_to_end(tmp_path):
    out = tmp_path / "synthetic.epw"
    config = EPWConfig(
        weather_policy="strict",
        station_id=STATION_ID,
        year=YEAR,
        output_path=str(out),
        city="Stockholm",
        cache_dir=None,
        utc_offset=1.0,
    )
    result = compile_epw(config, client=FakeClient())

    assert result.rows == 8760
    assert os.path.exists(out)

    lines = out.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 8 + 8760  # 8 header + data rows
    assert lines[0].startswith("LOCATION,")

    first = lines[8].split(",")
    assert first[0] == str(YEAR)  # year
    assert first[1] == "1"  # month
    assert first[2] == "1"  # day
    assert first[3] == "1"  # hour 1
    assert first[4] == "60"  # minute
    assert first[5] == C.EPW_DATA_FLAGS
    assert len(first) == 35
    assert first[22] != "99"  # observed total cover
    assert first[23] == "99"  # opaque cover is not available from SMHI

    last = lines[-1].split(",")
    assert last[3] == "24"  # final row is hour 24


def test_compile_epw_aborts_on_long_gap(tmp_path):
    out = tmp_path / "broken.epw"
    config = EPWConfig(
        weather_policy="strict",
        station_id=STATION_ID,
        year=YEAR,
        output_path=str(out),
        cache_dir=None,
    )
    with pytest.raises(DataGapError):
        compile_epw(config, client=FakeClient(gap_hours=49))


# --------------------------------------------------------------------------- #
# New-feature tests
# --------------------------------------------------------------------------- #
def test_station_metadata_uses_title_and_year_position():
    from smhi2epw.ingestion import get_station_metadata

    meta = get_station_metadata(STATION_ID, FakeClient(), year=YEAR)
    assert meta.name == "Synthetic Station"
    assert np.isclose(meta.latitude, LAT)
    assert np.isclose(meta.elevation, 12.0)
    assert meta.wmo_id == "999999"


def test_find_nearest_station_resolves_closest():
    from smhi2epw.ingestion import find_nearest_station

    meta = find_nearest_station(LAT, LON, YEAR, FakeClient())
    assert meta.station_id == STATION_ID


def test_find_nearest_station_requires_full_year_coverage():
    from smhi2epw.ingestion import find_nearest_station

    start = int(pd.Timestamp("2021-01-01", tz="UTC").timestamp() * 1000)
    end = int(pd.Timestamp("2022-01-01", tz="UTC").timestamp() * 1000) - 1
    partial_start = int(pd.Timestamp("2021-06-01", tz="UTC").timestamp() * 1000)
    partial_end = int(pd.Timestamp("2021-09-01", tz="UTC").timestamp() * 1000)

    class CoverageClient:
        def get_json(self, url):
            if "/station/222.json" in url:
                return {
                    "key": "222",
                    "title": "Full-year station",
                    "position": [
                        {
                            "from": start,
                            "to": end,
                            "latitude": LAT + 0.1,
                            "longitude": LON,
                            "height": 10,
                        }
                    ],
                }
            return {
                "station": [
                    {
                        "key": "111",
                        "latitude": LAT,
                        "longitude": LON,
                        "from": partial_start,
                        "to": partial_end,
                    },
                    {
                        "key": "222",
                        "latitude": LAT + 0.1,
                        "longitude": LON,
                        "from": start,
                        "to": end,
                    },
                ]
            }

    meta = find_nearest_station(LAT, LON, YEAR, CoverageClient())
    assert meta.station_id == 222


def test_cloud_term_increases_ir():
    dry = pd.Series([15.0])
    td = pd.Series([8.0])
    clear = processing.horizontal_ir(dry, td)
    overcast = processing.horizontal_ir(dry, td, cloud_cover_tenths=pd.Series([10.0]))
    assert (overcast > clear).all()


def test_sky_cover_octas_to_tenths():
    octas = pd.Series([0.0, 4.0, 8.0])
    tenths = processing.sky_cover_tenths(octas)
    assert list(tenths) == [0.0, 5.0, 10.0]


def test_optional_column_long_gap_does_not_abort():
    idx = _utc_grid(YEAR)
    frame = pd.DataFrame(
        {
            "dry_bulb": np.arange(len(idx), dtype=float),
            "cloud_cover": np.full(len(idx), 4.0),
        },
        index=idx,
    )
    frame.iloc[20:40, frame.columns.get_loc("cloud_cover")] = np.nan  # 20-hour gap
    report = processing.impute(frame, ["dry_bulb"], optional=["cloud_cover"])
    # Optional long gaps survive (left as NaN) without raising.
    assert report.interpolated_fraction["cloud_cover"] > 0


def test_extraterrestrial_columns_present_and_nonnegative():
    idx = pd.date_range("2021-06-21", periods=24, freq="h", tz="UTC")
    frame = pd.DataFrame(
        {
            "ghi": np.full(24, 500.0),
            "dni": np.full(24, 700.0),
            "dirh": np.full(24, 300.0),
        },
        index=idx,
    )
    processing.apply_solar(frame, LAT, LON)
    assert "etrh" in frame.columns and "etrn" in frame.columns
    assert (frame["etrh"] >= 0).all()
    # etrn is non-zero only when sun is above horizon.
    _, cos_z = solar.solar_zenith(idx - pd.Timedelta(minutes=30), LAT, LON)
    daytime = cos_z > 0.0
    assert (frame["etrn"].to_numpy()[daytime] > 1300).all()
    assert (frame["etrn"].to_numpy()[~daytime] == 0.0).all()


def test_erbs_decomposition_energy_balance():
    """DHI + DNI * cos(z) should equal GHI."""
    idx = pd.date_range("2021-06-21 06:00", periods=12, freq="h", tz="UTC")
    _, cos_z = solar.solar_zenith(idx, LAT, LON)
    etrh, _ = solar.extraterrestrial_radiation(idx, cos_z)
    ghi = np.clip(800.0 * cos_z, 0.0, None)
    dhi, dni = solar.erbs_decomposition(ghi, etrh, cos_z)
    beam_h = dni * np.clip(cos_z, 0.0, None)
    residual = np.abs(ghi - (dhi + beam_h))
    assert np.max(residual) < 1.0  # < 1 W/m²


def test_erbs_decomposition_clear_sky_high_dni():
    """Under a clear sky (high kt) Erbs should produce significant DNI."""
    idx = pd.date_range("2021-06-21 10:00", periods=1, freq="h", tz="UTC")
    _, cos_z = solar.solar_zenith(idx, LAT, LON)
    etrh, _ = solar.extraterrestrial_radiation(idx, cos_z)
    # kt ~ 0.8 → clear sky
    ghi = np.array([0.8 * etrh[0]])
    dhi, dni = solar.erbs_decomposition(ghi, etrh, cos_z)
    assert dni[0] > 0.0
    assert dhi[0] >= 0.0


def test_compile_epw_uses_measured_ghi_when_available(tmp_path):
    out = tmp_path / "synthetic_erbs.epw"
    config = EPWConfig(
        weather_policy="strict",
        station_id=STATION_ID,
        year=YEAR,
        output_path=str(out),
        city="Stockholm",
        cache_dir=None,
        utc_offset=1.0,
        radiation_station_id=STATION_ID,  # same fake station serves param 11
    )
    result = compile_epw(config, client=FakeClient())
    assert result.report.solar_source == "measured+strang_partition"
    assert result.rows == 8760


def test_gap_policy_boundaries_and_optional_missing():
    idx = pd.date_range("2021-01-01", periods=200, freq="h", tz="UTC")
    for size, method in (
        (3, "linear"),
        (4, "diurnal"),
        (11, "diurnal"),
        (48, "diurnal"),
    ):
        frame = pd.DataFrame({"dry_bulb": np.sin(np.arange(200) / 24.0)}, index=idx)
        frame.iloc[72 : 72 + size, 0] = np.nan
        report = processing.impute(frame, ["dry_bulb"])
        assert not frame["dry_bulb"].isna().any()
        filled = (
            report.linear_filled_hours
            if method == "linear"
            else report.diurnal_filled_hours
        )
        assert filled["dry_bulb"] == size

    optional = pd.DataFrame(
        {"dry_bulb": np.ones(200), "cloud_cover": np.ones(200)}, index=idx
    )
    optional.iloc[72:121, 1] = np.nan
    processing.impute(optional, ["dry_bulb"], optional=["cloud_cover"])
    assert optional["cloud_cover"].isna().sum() == 49


def test_gap_fill_uses_one_sided_profile_at_boundary():
    idx = pd.date_range("2021-01-01", periods=72, freq="h", tz="UTC")
    frame = pd.DataFrame(
        {"dry_bulb": np.tile(np.arange(24), 3).astype(float)}, index=idx
    )
    frame.iloc[:8, 0] = np.nan
    report = processing.impute(frame, ["dry_bulb"])
    assert not frame["dry_bulb"].isna().any()
    assert report.diurnal_filled_hours["dry_bulb"] == 8


def test_gap_fill_fails_without_reference_profile():
    idx = pd.date_range("2021-01-01", periods=20, freq="h", tz="UTC")
    frame = pd.DataFrame({"dry_bulb": np.arange(20, dtype=float)}, index=idx)
    frame.iloc[5:10, 0] = np.nan
    with pytest.raises(DataGapError, match="reference profile"):
        processing.impute(frame, ["dry_bulb"])


def test_wind_direction_interpolates_across_north():
    idx = pd.date_range("2021-01-01", periods=10, freq="h", tz="UTC")
    values = np.array([350.0, np.nan, np.nan, np.nan, 10.0, 20, 30, 40, 50, 60])
    frame = pd.DataFrame({"wind_direction": values}, index=idx)
    processing.impute(frame, ["wind_direction"])
    filled = frame["wind_direction"].iloc[1:4].to_numpy()
    distance_from_north = np.minimum(filled, 360.0 - filled)
    assert np.max(distance_from_north) < 10.0


def test_measured_partition_closes_under_extreme_disagreement():
    idx = pd.date_range("2021-06-21 08:00", periods=8, freq="h", tz="UTC")
    frame = pd.DataFrame(
        {
            "ghi": np.full(8, 800.0),
            "dni": np.full(8, 900.0),
            "dirh": np.full(8, 700.0),
            "ghi_measured": np.full(8, 100.0),
        },
        index=idx,
    )
    report = processing.ProcessingReport()
    processing.apply_solar(frame, LAT, LON, report)
    _, cos_z = solar.solar_zenith(idx - pd.Timedelta(minutes=30), LAT, LON)
    residual = frame["ghi"].to_numpy() - (
        frame["dhi"].to_numpy() + frame["dni"].to_numpy() * np.clip(cos_z, 0, None)
    )
    assert report.solar_source == "measured+strang_partition"
    assert np.max(np.abs(residual)) < 1e-9
    assert (frame["dhi"] >= 0).all()


def test_energyplus_horizontal_ir_documented_example():
    value = processing.horizontal_ir(pd.Series([20.0]), pd.Series([10.0])).iloc[0]
    assert value == pytest.approx(340.6, abs=1.0)


@pytest.mark.parametrize(
    "updates, message",
    [
        ({"utc_offset": 5.5}, "fractional UTC offsets"),
        ({"latitude": 91.0, "longitude": 18.0}, "latitude"),
        ({"max_workers": 0}, "max_workers"),
        ({"radiation_station_max_distance_km": -1.0}, "maximum distance"),
    ],
)
def test_invalid_config_rejected_before_network(tmp_path, updates, message):
    kwargs = dict(
        station_id=STATION_ID,
        year=YEAR,
        output_path=str(tmp_path / "invalid.epw"),
        cache_dir=None,
    )
    kwargs.update(updates)
    with pytest.raises(IngestionError, match=message):
        compile_epw(EPWConfig(weather_policy="strict", **kwargs), client=FakeClient())


def test_requested_coordinates_drive_solar_and_header(tmp_path):
    client = FakeClient()
    out = tmp_path / "target.epw"
    result = compile_epw(
        EPWConfig(
            weather_policy="strict",
            station_id=STATION_ID,
            year=YEAR,
            output_path=str(out),
            latitude=60.0,
            longitude=17.0,
            cache_dir=None,
            radiation_station_auto=False,
        ),
        client=client,
    )
    assert result.coordinate_distance_km > 0
    assert any("/lon/17.000000/lat/60.000000/" in url for url in client.urls)
    assert ",60.0000,17.0000," in out.read_text().splitlines()[0]


def test_radiation_station_radius_falls_back_to_strang(tmp_path):
    class FarRadiationClient(FakeClient):
        def get_json(self, url):
            payload = super().get_json(url)
            if url.endswith("/parameter/11.json"):
                payload["station"][0]["latitude"] = LAT + 5.0
            return payload

    client = FarRadiationClient()
    result = compile_epw(
        EPWConfig(
            weather_policy="strict",
            station_id=STATION_ID,
            year=YEAR,
            output_path=str(tmp_path / "strang.epw"),
            cache_dir=None,
        ),
        client=client,
    )
    assert result.report.solar_source == "strang"
    assert result.radiation_station_id is None
    assert not any("/parameter/11/station/" in url for url in client.urls)


def test_optional_cloud_endpoint_failure_is_soft(tmp_path):
    class NoCloudClient(FakeClient):
        def get_text(self, url, suffix="txt"):
            if "/parameter/16/" in url:
                raise IngestionError("cloud endpoint unavailable")
            return super().get_text(url, suffix)

    result = compile_epw(
        EPWConfig(
            weather_policy="strict",
            station_id=STATION_ID,
            year=YEAR,
            output_path=str(tmp_path / "no-cloud.epw"),
            cache_dir=None,
            radiation_station_auto=False,
        ),
        client=NoCloudClient(),
    )
    assert not result.report.cloud_available
    first = (tmp_path / "no-cloud.epw").read_text().splitlines()[8].split(",")
    assert first[22:24] == ["99", "99"]


def test_auto_measured_ghi_gap_falls_back_but_explicit_fails(tmp_path):
    class GappyRadiationClient(FakeClient):
        def get_text(self, url, suffix="txt"):
            text = super().get_text(url, suffix)
            if "/parameter/11/" in url and url.endswith(".csv"):
                return self._inject_gap(text, 49)
            return text

    auto = compile_epw(
        EPWConfig(
            weather_policy="strict",
            station_id=STATION_ID,
            year=YEAR,
            output_path=str(tmp_path / "fallback.epw"),
            cache_dir=None,
        ),
        client=GappyRadiationClient(),
    )
    assert auto.report.solar_source == "strang"

    with pytest.raises(DataGapError):
        compile_epw(
            EPWConfig(
                weather_policy="strict",
                station_id=STATION_ID,
                year=YEAR,
                output_path=str(tmp_path / "explicit.epw"),
                cache_dir=None,
                radiation_station_id=STATION_ID,
            ),
            client=GappyRadiationClient(),
        )


def test_2017_ingestion_uses_ghi_only():
    from smhi2epw.ingestion import StationMeta, ingest

    client = FakeClient()
    ingest(StationMeta(STATION_ID, "Synthetic", LAT, LON), 2017, client)
    assert any("/parameter/117/" in url for url in client.urls)
    assert not any("/parameter/118/" in url for url in client.urls)
    assert not any("/parameter/121/" in url for url in client.urls)


def test_shift_to_lst_rejects_fractional_offset():
    idx = pd.date_range("2021-01-01", periods=8760, freq="h", tz="UTC")
    with pytest.raises(ValidationError, match="fractional"):
        export.shift_to_lst(pd.DataFrame({"x": 1.0}, index=idx), 2021, 5.5)


def test_invalid_export_does_not_replace_existing_file(tmp_path):
    output = tmp_path / "existing.epw"
    output.write_text("keep me\n")
    header = export.build_header(
        "Stockholm", "SE", "SWE", "999999", 59.3, 18.0, 1.0, 12.0, 2021, STATION_ID
    )
    bad = pd.DataFrame(index=pd.date_range("2021-01-01 01:00", periods=1, freq="h"))
    with pytest.raises(ValidationError, match="cardinality"):
        export.write_epw(str(output), header, bad, 2021)
    assert output.read_text() == "keep me\n"


def test_metobs_quality_flags_and_strang_sentinel_are_missing():
    from smhi2epw.ingestion import _parse_metobs_csv, fetch_strang_parameter

    text = "Datum;Tid (UTC);Värde;Kvalitet\n2021-01-01;00:00:00;1.5;R\n"
    window = (
        pd.Timestamp("2021-01-01", tz="UTC"),
        pd.Timestamp("2021-01-02", tz="UTC"),
    )
    parsed = _parse_metobs_csv(text, "dry_bulb", window)
    assert parsed.isna().all()

    class SentinelClient:
        def get_json(self, _url):
            return [{"date_time": "2021-01-01T00:00:00Z", "value": -999}]

    strang = fetch_strang_parameter(59.0, 18.0, 117, "ghi", window, SentinelClient())
    assert strang.isna().all()


def test_retry_session_covers_transient_statuses():
    from smhi2epw.ingestion import CachedClient

    session = CachedClient._build_session(4)
    retries = session.get_adapter("https://").max_retries
    assert retries.total == 4
    assert {429, 500, 502, 503, 504}.issubset(set(retries.status_forcelist))
