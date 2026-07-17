"""Offline tests for smhi2epw (no network access required)."""

from __future__ import annotations

import json
import os

import numpy as np
import pandas as pd
import pytest

from smhi2epw import compile_epw
from smhi2epw.compiler import EPWConfig
from smhi2epw.errors import DataGapError
from smhi2epw import constants as C
from smhi2epw import export, processing, solar


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
        lines.append(
            f"{ts.strftime('%Y-%m-%d')};{ts.strftime('%H:%M:%S')};{val:.2f};G"
        )
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

    def get_text(self, url, suffix="txt"):
        if "/parameter/11/" in url and "station" in url and url.endswith(".csv"):
            return _metobs_csv("Globalstrålning", 300.0)  # measured GHI (W/m²)
        if "/parameter/1/" in url and "station" in url and url.endswith(".csv"):
            csv = _metobs_csv("Lufttemperatur", 5.0)
            if self.gap_hours:
                csv = self._inject_gap(csv)
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
    def _inject_gap(csv):
        lines = csv.splitlines()
        header = next(i for i, l in enumerate(lines) if l.startswith("Datum"))
        # Blank out 6 consecutive value cells -> a 6-hour gap.
        for i in range(header + 10, header + 16):
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
    _, cos_z = solar.solar_zenith(idx, LAT, LON)
    # STRÅNG path: DNI forced to 0 when the sun is below the horizon floor.
    assert (frame["dni"].to_numpy()[cos_z <= C.COS_ZENITH_FLOOR] == 0).all()
    # DHI closes as GHI - beam_horizontal and is never negative.
    assert (frame["dhi"] >= 0).all()
    assert np.isclose(frame["dhi"].iloc[0], 200.0)
    # _kt temp column must be cleaned up.
    assert "_kt" not in frame.columns


def test_imputation_short_gap_ok():
    idx = _utc_grid(YEAR)
    frame = pd.DataFrame({"dry_bulb": np.arange(len(idx), dtype=float)}, index=idx)
    frame.iloc[5:8, 0] = np.nan  # 3-hour gap
    report = processing.impute(frame, ["dry_bulb"])
    assert not frame["dry_bulb"].isna().any()
    assert report.total_interpolated_fraction > 0


def test_imputation_long_gap_raises():
    idx = _utc_grid(YEAR)
    frame = pd.DataFrame({"dry_bulb": np.arange(len(idx), dtype=float)}, index=idx)
    frame.iloc[5:11, 0] = np.nan  # 6-hour gap
    with pytest.raises(DataGapError):
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
        "Stockholm", "SE", "SWE", "024640", 59.3, 18.0, 1.0, 12.0
    )
    assert len(header) == 8
    assert header[0].startswith("LOCATION,Stockholm,SE,SWE,SMHI-AMY,024640")
    assert header[3] == "GROUND TEMPERATURES,0"


# --------------------------------------------------------------------------- #
# End-to-end test against the fake client
# --------------------------------------------------------------------------- #
def test_compile_epw_end_to_end(tmp_path):
    out = tmp_path / "synthetic.epw"
    config = EPWConfig(
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
    assert first[1] == "1"        # month
    assert first[2] == "1"        # day
    assert first[3] == "1"        # hour 1
    assert first[4] == "60"       # minute
    assert first[5] == C.EPW_DATA_FLAGS

    last = lines[-1].split(",")
    assert last[3] == "24"        # final row is hour 24


def test_compile_epw_aborts_on_long_gap(tmp_path):
    out = tmp_path / "broken.epw"
    config = EPWConfig(
        station_id=STATION_ID, year=YEAR, output_path=str(out), cache_dir=None
    )
    with pytest.raises(DataGapError):
        compile_epw(config, client=FakeClient(gap_hours=6))


# --------------------------------------------------------------------------- #
# New-feature tests
# --------------------------------------------------------------------------- #
def test_station_metadata_uses_title_and_year_position():
    from smhi2epw.ingestion import get_station_metadata

    meta = get_station_metadata(STATION_ID, FakeClient(), year=YEAR)
    assert meta.name == "Synthetic Station"
    assert np.isclose(meta.latitude, LAT)
    assert np.isclose(meta.elevation, 12.0)


def test_find_nearest_station_resolves_closest():
    from smhi2epw.ingestion import find_nearest_station

    meta = find_nearest_station(LAT, LON, YEAR, FakeClient())
    assert meta.station_id == STATION_ID


def test_cloud_term_increases_ir():
    dry = pd.Series([15.0])
    td = pd.Series([8.0])
    clear = processing.horizontal_ir(dry, td)
    overcast = processing.horizontal_ir(dry, td, opaque_fraction=pd.Series([1.0]))
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
    _, cos_z = solar.solar_zenith(idx, LAT, LON)
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
        station_id=STATION_ID,
        year=YEAR,
        output_path=str(out),
        city="Stockholm",
        cache_dir=None,
        utc_offset=1.0,
        radiation_station_id=STATION_ID,  # same fake station serves param 11
    )
    result = compile_epw(config, client=FakeClient())
    assert result.report.solar_source == "measured+strang_beam"
    assert result.rows == 8760

