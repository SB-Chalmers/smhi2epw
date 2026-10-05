import numpy as np
import pandas as pd
import pytest

from smhi2epw import constants as C
from smhi2epw import gap_recovery as G
from smhi2epw import ingestion as I
from smhi2epw import processing as P
from smhi2epw.errors import DataGapError, IngestionError


def frame(hours=720):
    index = pd.date_range("2020-01-01", periods=hours, freq="h", tz="UTC")
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


def donors(monkeypatch, f, values, stations=None):
    """Provide deterministic donors without exercising source transports."""
    stations = stations or {2: (60.1, 15.0, 0, 9999999999999)}
    monkeypatch.setattr(I, "_stations_for_parameter", lambda *a: stations)
    monkeypatch.setattr(
        I,
        "get_station_metadata",
        lambda sid, *a, **k: I.StationMeta(
            sid, "donor", stations[sid][0], stations[sid][1]
        ),
    )
    monkeypatch.setattr(
        I,
        "fetch_metobs_parameter",
        lambda sid, param, column, window, client, **k: values(sid, column),
    )


def recover(f, report=None):
    """Apply donor recovery with a fixed primary station."""
    return G.recover(
        f,
        I.StationMeta(1, "primary", 60.0, 15.0),
        2020,
        60.0,
        15.0,
        None,
        report=report,
    )


def test_long_gap_assessed_correction_and_receipt(monkeypatch):
    f = frame()
    f.loc[f.index[300:370], "dry_bulb"] = np.nan
    donor = pd.Series(12.0, index=f.index)
    donor.iloc[300:370] = 25.0
    donors(monkeypatch, f, lambda sid, column: donor)
    report = recover(f)
    assert report.cross_station_filled_hours == {"dry_bulb": 70}
    assert f.dry_bulb.iloc[0] == 10 and f.dry_bulb.iloc[310] == 23
    assert report.required_reconstructed_fraction == 70 / 3600
    assert len(report.gap_fallback_sources) == 1
    assessment = report.gap_fallback_sources[0]["assessments"]["dry_bulb"][0]
    assert assessment["method"] == "median_offset"
    assert assessment["offset"] == -2
    assert assessment["raw_mae"] == 2
    assert assessment["selected_mae"] == 0
    assert assessment["filled_hours"] == 70
    assert len(assessment["folds"]) == 3
    for fold in assessment["folds"]:
        held_out = pd.Timestamp(fold["validation_day_utc"])
        assert fold["training_hours"] >= 168
        assert fold["training_dates"] >= 7
        for start, end in fold["training_intervals_utc"]:
            assert pd.Timestamp(end) < held_out - pd.Timedelta(days=1) or (
                pd.Timestamp(start) >= held_out + pd.Timedelta(days=2)
            )
    assert report.warnings[-1]["code"] == "donor_gap_filled"
    P.impute(f, list(C.METOBS_REQUIRED_PARAMETERS.values()), [], report=report)


@pytest.mark.parametrize("hours", [1, 3, 4, 12, 48, 49])
def test_short_interpolation_precedes_donors_and_donors_precede_profiles(
    monkeypatch, hours
):
    f = frame()
    original = f.dry_bulb.copy()
    f.loc[f.index[300 : 300 + hours], "dry_bulb"] = np.nan
    donor = pd.Series(12.0, index=f.index)
    donor.iloc[300 : 300 + hours] = 25.0
    donors(monkeypatch, f, lambda sid, column: donor)
    report = recover(f)
    P.impute(f, list(C.METOBS_REQUIRED_PARAMETERS.values()), [], report=report)
    if hours <= C.SHORT_GAP_HOURS:
        assert not report.gap_fallback_attempts
        assert not report.cross_station_filled_hours
        assert f.dry_bulb.iloc[300 : 300 + hours].eq(10).all()
        assert report.linear_filled_hours["dry_bulb"] == hours
    else:
        assert report.cross_station_filled_hours == {"dry_bulb": hours}
        assert f.dry_bulb.iloc[300 : 300 + hours].eq(23).all()
        assert report.diurnal_filled_hours["dry_bulb"] == 0
    known = np.ones(len(f), dtype=bool)
    known[300 : 300 + hours] = False
    pd.testing.assert_series_equal(f.dry_bulb[known], original[known])


def test_rejected_medium_gap_donor_retains_bounded_profile_fallback(monkeypatch):
    f = frame()
    f.loc[f.index[300:348], "dry_bulb"] = np.nan
    donor = pd.Series(10.0 + np.where(np.arange(len(f)) % 2, 10, -10), index=f.index)
    donors(monkeypatch, f, lambda sid, column: donor)
    report = recover(f)
    assert f.dry_bulb.iloc[300:348].isna().all()
    assert not report.cross_station_filled_hours
    assert (
        report.gap_fallback_attempts[0]["assessments"]["dry_bulb"][0]["reason"]
        == "excessive_validation_error"
    )
    P.impute(f, list(C.METOBS_REQUIRED_PARAMETERS.values()), [], report=report)
    assert f.dry_bulb.iloc[300:348].eq(10).all()
    assert report.diurnal_filled_hours["dry_bulb"] == 48


def test_unfillable_short_wind_vectors_can_use_assessed_donor(monkeypatch):
    f = frame()
    f.loc[f.index[299], "wind_direction"] = 90.0
    f.loc[f.index[300], "wind_direction"] = np.nan
    f.loc[f.index[301], "wind_direction"] = 270.0
    donor = pd.Series(359.0, index=f.index)
    donors(monkeypatch, f, lambda sid, column: donor)
    report = recover(f)
    assert f.wind_direction.iloc[300] == 359.0
    assert report.cross_station_filled_hours == {"wind_direction": 1}


def test_correction_worsening_held_out_days_keeps_raw(monkeypatch):
    f = frame()
    f.loc[f.index[300:370], "dry_bulb"] = np.nan
    donor = pd.Series(12.0, index=f.index)
    overlap = f.dry_bulb.notna()
    days = f.index[overlap].normalize()
    complete = pd.Series(1, index=days).groupby(level=0).sum()
    complete = complete[complete == 24].index
    selected = complete[[0, len(complete) // 2, -1]]
    donor[f.index.normalize().isin(selected)] = 10.0
    donors(monkeypatch, f, lambda sid, column: donor)
    report = recover(f)
    assessment = report.gap_fallback_sources[0]["assessments"]["dry_bulb"][0]
    assert assessment["method"] == "same_hour_observation"
    assert assessment["raw_mae"] == 0
    assert assessment["corrected_mae"] == 2
    assert f.dry_bulb.iloc[310] == 12


def test_excessive_held_out_error_rejects_donor(monkeypatch):
    f = frame()
    f.loc[f.index[300:370], "dry_bulb"] = np.nan
    donor = pd.Series(10.0 + np.where(np.arange(len(f)) % 2, 10, -10), index=f.index)
    donors(monkeypatch, f, lambda sid, column: donor)
    report = recover(f)
    assert f.dry_bulb.iloc[300:370].isna().all()
    assert not report.cross_station_filled_hours
    assessment = report.gap_fallback_attempts[0]["assessments"]["dry_bulb"][0]
    assert assessment["reason"] == "excessive_validation_error"
    assert assessment["selected_mae"] == 10
    assert report.warnings[-1]["code"] == "donor_rejected"


@pytest.mark.parametrize("whole_variable", [False, True])
def test_insufficient_original_overlap_rejects_donor(monkeypatch, whole_variable):
    f = frame(240)
    if whole_variable:
        f["dry_bulb"] = np.nan
    else:
        f.loc[f.index[50:120], "dry_bulb"] = np.nan
    donor = pd.Series(10.0, index=f.index)
    donors(monkeypatch, f, lambda sid, column: donor)
    report = recover(f)
    assert not report.cross_station_filled_hours
    assessment = report.gap_fallback_attempts[0]["assessments"]["dry_bulb"][0]
    assert assessment["reason"] == "insufficient_overlap"
    assert f.dry_bulb.isna().sum() == (240 if whole_variable else 70)


def test_wind_only_donor_uses_parameter_metadata_and_angular_errors(monkeypatch):
    f = frame()
    f.loc[f.index[300:370], "wind_direction"] = np.nan
    donor = pd.Series(1.0, index=f.index)
    donors(monkeypatch, f, lambda sid, column: donor)
    calls = []

    def wind_metadata(sid, client, year=None, *, parameter=1):
        calls.append(parameter)
        if parameter != 3:
            raise IngestionError("This donor has no temperature metadata")
        return I.StationMeta(2, "wind only", 60.1, 15.0)

    monkeypatch.setattr(I, "get_station_metadata", wind_metadata)
    report = recover(f)
    assert calls == [3]
    assessment = report.gap_fallback_sources[0]["assessments"]["wind_direction"][0]
    assert assessment["raw_mae"] == 2
    assert assessment["method"] == "same_hour_observation"
    assert assessment["corrected_mae"] is None
    assert assessment["offset"] == 0
    assert (f.wind_direction.iloc[300:370] == 1).all()
    assert (f.wind_direction.iloc[:300] == 359).all()


def test_invalid_corrected_gap_values_are_not_clipped(monkeypatch):
    f = frame()
    f.loc[f.index[300:370], "relative_humidity"] = np.nan
    donor = pd.Series(70.0, index=f.index)
    donor.iloc[300:370] = 95.0
    donors(monkeypatch, f, lambda sid, column: donor)
    report = recover(f)
    assert f.relative_humidity.iloc[300:370].isna().all()
    assert not report.cross_station_filled_hours
    assert report.warnings[-1]["code"] == "donor_correction_out_of_bounds"
    assert report.warnings[-1]["details"]["hours"] == 70


def test_invalid_correction_on_validation_day_retains_usable_raw(monkeypatch):
    f = frame()
    f.loc[f.index[300:370], "relative_humidity"] = np.nan
    donor = pd.Series(70.0, index=f.index)
    donor.iloc[0:24] = 95.0
    donor.iloc[300:370] = 75.0
    donors(monkeypatch, f, lambda sid, column: donor)
    report = recover(f)
    assessment = report.gap_fallback_sources[0]["assessments"]["relative_humidity"][0]
    assert assessment["method"] == "same_hour_observation"
    assert (f.relative_humidity.iloc[300:370] == 75).all()


def test_multiple_donors_fill_partial_coverage_using_originals(monkeypatch):
    f = frame()
    f.loc[f.index[300:500], "dry_bulb"] = np.nan
    first = pd.Series(12.0, index=f.index)
    first.iloc[350:500] = np.nan
    second = pd.Series(14.0, index=f.index)
    stations = {
        2: (60.1, 15.0, 0, 9999999999999),
        3: (60.2, 15.0, 0, 9999999999999),
    }
    donors(monkeypatch, f, lambda sid, column: first if sid == 2 else second, stations)
    original = f.dry_bulb.copy()
    report = recover(f)
    assert report.cross_station_filled_hours == {"dry_bulb": 200}
    assert [s["filled_hours"]["dry_bulb"] for s in report.gap_fallback_sources] == [
        50,
        150,
    ]
    assert (f.dry_bulb == 10).all()
    pd.testing.assert_series_equal(f.dry_bulb[original.notna()], original.dropna())
    second_assessment = report.gap_fallback_sources[1]["assessments"]["dry_bulb"][0]
    assert second_assessment["overlap_hours"] == int(original.notna().sum())
    assert second_assessment["offset"] == -4


def test_partial_medium_gap_keeps_small_holes_eligible_for_later_donors(monkeypatch):
    f = frame()
    f.loc[f.index[300:348], "dry_bulb"] = np.nan
    first = pd.Series(12.0, index=f.index)
    first.iloc[300:348] = 25.0
    first.iloc[320:323] = np.nan
    second = pd.Series(14.0, index=f.index)
    second.iloc[300:348] = 30.0
    stations = {
        2: (60.1, 15.0, 0, 9999999999999),
        3: (60.2, 15.0, 0, 9999999999999),
    }
    donors(monkeypatch, f, lambda sid, column: first if sid == 2 else second, stations)
    report = recover(f)
    assert report.cross_station_filled_hours == {"dry_bulb": 48}
    assert [s["filled_hours"]["dry_bulb"] for s in report.gap_fallback_sources] == [
        45,
        3,
    ]
    assert f.dry_bulb.iloc[320:323].eq(26).all()
    assert f.dry_bulb.iloc[300:320].eq(23).all()


def test_request_failures_are_recorded_and_later_donor_can_fill(monkeypatch):
    f = frame()
    f.loc[f.index[300:370], "dry_bulb"] = np.nan
    stations = {
        2: (60.1, 15.0, 0, 9999999999999),
        3: (60.2, 15.0, 0, 9999999999999),
    }

    def fetch(sid, column):
        if sid == 2:
            raise IngestionError("Donor transport is unavailable")
        return pd.Series(10.0, index=f.index)

    donors(monkeypatch, f, fetch, stations)
    report = recover(f)
    assert report.cross_station_filled_hours == {"dry_bulb": 70}
    assert "unavailable" in report.gap_fallback_attempts[0]["errors"]["dry_bulb"]
    assert report.warnings[0]["code"] == "donor_request_failed"
    assert report.gap_fallback_sources[0]["station_id"] == 3


def test_catalog_failure_preserves_existing_warnings(monkeypatch):
    f = frame()
    f.loc[f.index[300:370], "dry_bulb"] = np.nan

    def unavailable(*args):
        raise IngestionError("Catalog unavailable")

    monkeypatch.setattr(I, "_stations_for_parameter", unavailable)
    supplied = P.ProcessingReport()
    supplied.warnings.append({"code": "primary_failed", "message": "Primary failed"})
    report = recover(f, supplied)
    assert report is supplied
    assert [w["code"] for w in report.warnings] == [
        "primary_failed",
        "donor_catalog_failed",
    ]


def test_assessment_window_excludes_distant_training_data(monkeypatch):
    f = frame(24 * 150)
    f.loc[f.index[24 * 70 : 24 * 74], "dry_bulb"] = np.nan
    donor = pd.Series(30.0, index=f.index)
    donor.iloc[24 * 40 : 24 * 104] = 12.0
    donors(monkeypatch, f, lambda sid, column: donor)
    report = recover(f)
    assessment = report.gap_fallback_sources[0]["assessments"]["dry_bulb"][0]
    assert assessment["offset"] == -2
    assert pd.Timestamp(assessment["overlap_period_utc"][0]) == f.index[24 * 40]
    assert pd.Timestamp(assessment["overlap_period_utc"][1]) == f.index[24 * 104 - 1]


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
    cancelling = G.hourly_observations(
        pd.Series([90.0, 270.0], index=index), "wind_direction"
    )
    assert cancelling.isna().all()


def test_invalid_primary_values_are_excluded_from_donor_calibration(monkeypatch):
    f = frame()
    f.loc[f.index[300:370], "dry_bulb"] = np.nan
    f.loc[f.index[0:24], "dry_bulb"] = float("inf")
    f.loc[f.index[24:48], "dry_bulb"] = 200
    donor = pd.Series(12.0, index=f.index)
    donors(monkeypatch, f, lambda sid, column: donor)
    report = recover(f)
    assert report.invalid_observation_hours["dry_bulb"] == 48
    assert report.primary_missing_hours["dry_bulb"] == 118
    long_assessment = report.gap_fallback_sources[0]["assessments"]["dry_bulb"][0]
    assert long_assessment["offset"] == -2
    assert pd.Timestamp(long_assessment["overlap_period_utc"][0]) == f.index[48]
    assert (f.dry_bulb.iloc[300:370] == 10).all()


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
