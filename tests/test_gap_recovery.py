import numpy as np
import pandas as pd
import pytest

from smhi2epw import constants as C
from smhi2epw import gap_recovery as G
from smhi2epw import ingestion as I
from smhi2epw import processing as P
from smhi2epw.errors import DataGapError


def frame():
    index = pd.date_range("2020-01-01", periods=240, freq="h", tz="UTC")
    return pd.DataFrame(
        {
            c: v
            for c, v in [
                ("dry_bulb", 10.0),
                ("relative_humidity", 80.0),
                ("wind_speed", 3.0),
                ("wind_direction", 359.0),
                ("pressure", 1000.0),
            ]
        },
        index=index,
    )


def test_long_gap_actual_observations_and_receipt(monkeypatch):
    f = frame()
    f.loc[f.index[50:120], "dry_bulb"] = np.nan
    f["wind_direction"] = np.nan
    station = I.StationMeta(1, "primary", 60.0, 15.0)
    monkeypatch.setattr(
        I, "_stations_for_parameter", lambda *a: {2: (60.1, 15.0, 0, 9999999999999)}
    )
    monkeypatch.setattr(
        I, "get_station_metadata", lambda *a, **k: I.StationMeta(2, "donor", 60.1, 15.0)
    )
    monkeypatch.setattr(
        I,
        "fetch_metobs_parameter",
        lambda sid, param, column, window, client, **k: pd.Series(
            12.0 if column == "dry_bulb" else 1.0, index=f.index
        ),
    )
    report = G.recover(f, station, 2020, 60.0, 15.0, None)
    assert report.cross_station_filled_hours == {"dry_bulb": 70, "wind_direction": 240}
    assert f.dry_bulb.iloc[0] == 10 and f.dry_bulb.iloc[60] == 12
    assert report.required_reconstructed_fraction == 310 / 1200
    assert len(report.gap_fallback_sources) == 1
    P.impute(f, list(C.METOBS_REQUIRED_PARAMETERS.values()), [], report=report)


def test_no_donor_retains_hard_ceiling(monkeypatch):
    f = frame()
    f.iloc[50:120, 0] = np.nan
    monkeypatch.setattr(
        I, "_stations_for_parameter", lambda *a: {2: (10.0, 15.0, 0, 9999999999999)}
    )
    report = G.recover(
        f, I.StationMeta(1, "primary", 60.0, 15.0), 2020, 60.0, 15.0, None
    )
    assert not report.cross_station_filled_hours
    with pytest.raises(DataGapError):
        P.impute(f, list(C.METOBS_REQUIRED_PARAMETERS.values()), [])


def test_circular_hourly_and_invalid_donor():
    index = pd.date_range("2020-01-01", periods=2, freq="30min", tz="UTC")
    result = G.hourly_observations(
        pd.Series([359.0, 1.0], index=index), "wind_direction"
    )
    assert min(abs(result.iloc[0]), abs(result.iloc[0] - 360)) < 1e-6
    assert G.valid_observations(
        pd.Series([-1.0, 3.0, 41.0]), "wind_speed"
    ).isna().tolist() == [True, False, True]


def test_more_distant_daily_reference_and_ceiling():
    f = frame()
    f.iloc[80:86, 0] = np.nan
    f.iloc[60, 0] = np.nan
    f.iloc[100, 0] = np.nan
    filled, *_ = P._fill_scalar_series(
        f.dry_bulb, required=True, solar=False, short_gap_hours=3, max_gap_hours=48
    )
    assert filled.notna().all()
    f.iloc[80:140, 0] = np.nan
    with pytest.raises(DataGapError):
        P._fill_scalar_series(
            f.dry_bulb, required=True, solar=False, short_gap_hours=3, max_gap_hours=48
        )


def test_bounds_apply_only_to_reconstructed_values(monkeypatch):
    f = frame()
    f.iloc[5:10, 1] = np.nan
    f.iloc[0, 1] = 101.0

    def overshoot(series, **kwargs):
        return series.fillna(120.0), 0, 5, 5

    monkeypatch.setattr(P, "_fill_scalar_series", overshoot)
    report = P.impute(f, ["relative_humidity"], [])
    assert (f.relative_humidity.iloc[5:10] == 100.0).all()
    assert f.relative_humidity.iloc[0] == 101.0
    assert report.bounded_filled_hours["relative_humidity"] == 5


def test_compiler_opt_in_recovers_49_hours(tmp_path, monkeypatch):
    from test_pipeline import LAT, LON, STATION_ID, YEAR, FakeClient

    from smhi2epw.compiler import EPWConfig, compile_epw

    class DonorClient(FakeClient):
        def get_json(self, url):
            if url.endswith("/parameter/1.json"):
                return {
                    "station": [
                        {
                            "key": "2",
                            "latitude": LAT + 0.01,
                            "longitude": LON,
                            "from": 0,
                            "to": 9999999999999,
                        }
                    ]
                }
            if url.endswith("/station/2.json"):
                return {
                    "title": "Donor",
                    "key": "2",
                    "position": [
                        {
                            "from": 0,
                            "to": 9999999999999,
                            "latitude": LAT + 0.01,
                            "longitude": LON,
                            "height": 12.0,
                        }
                    ],
                }
            return super().get_json(url)

        def get_text(self, url, suffix="txt"):
            if "/station/2/" in url:
                return FakeClient().get_text(url, suffix)
            return super().get_text(url, suffix)

    config = EPWConfig(
        year=YEAR,
        station_id=STATION_ID,
        output_path=str(tmp_path / "recovered.epw"),
        metobs_gap_fallback=True,
    )
    result = compile_epw(config, client=DonorClient(gap_hours=49))
    assert result.rows == 8760
    assert result.report.cross_station_filled_hours["dry_bulb"] == 49
    assert result.report.gap_fallback_sources[0]["station_id"] == 2


@pytest.mark.parametrize(
    "settings",
    [
        {"gap_fallback_max_distance_km": float("nan")},
        {"gap_fallback_max_stations": 0},
        {"metobs_gap_fallback": "yes"},
    ],
)
def test_invalid_config_before_network(tmp_path, settings):
    from smhi2epw.compiler import EPWConfig, compile_epw
    from smhi2epw.errors import IngestionError

    with pytest.raises(IngestionError):
        compile_epw(
            EPWConfig(
                year=2020,
                station_id=1,
                output_path=str(tmp_path / "weather.epw"),
                **settings,
            ),
            client=object(),
        )
