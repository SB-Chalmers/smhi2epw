"""Independent physical and source-selection regressions for automatic recovery."""

import numpy as np
import pandas as pd
import pytest

from smhi2epw import automatic as A
from smhi2epw import constants as C
from smhi2epw import processing as P
from smhi2epw import reanalysis
from smhi2epw.errors import DataGapError
from smhi2epw.solar import solar_zenith

LAT, LON = 59.3, 18.0


def weather_frame(hours=240, start="2021-06-01", latitude=LAT):
    """Create smooth, physically consistent weather without source gaps."""
    index = pd.date_range(start, periods=hours, freq="h", tz="UTC")
    _, cosine = solar_zenith(index - pd.Timedelta(minutes=30), latitude, LON)
    positive = np.maximum(cosine, 0)
    dni = np.where(cosine > C.COS_ZENITH_FLOOR, 500.0, 0.0)
    return pd.DataFrame(
        {
            "dry_bulb": 20.0,
            "relative_humidity": 60.0,
            "pressure": 1013.0,
            "wind_speed": 3.0,
            "wind_direction": 180.0,
            "cloud_cover": 4.0,
            "ghi": 600 * positive,
            "dni": dni,
            "dirh": dni * positive,
        },
        index=index,
    )


def mock_model(monkeypatch, original, elevation=500.0, **overrides):
    """Supply independently chosen model values and record model requests."""
    model = original.copy()
    model["reanalysis_surface_pressure"] = 90000.0
    for column, value in overrides.items():
        model[column] = value
    requests = []

    def fetch(lat, lon, requested_elevation, index, client):
        requests.append((lat, lon, requested_elevation, index))
        return model.copy(), {
            "model": "ERA5",
            "provider": "Open-Meteo",
            "elevation_m": elevation,
        }

    monkeypatch.setattr(reanalysis, "fetch", fetch)
    return model, requests


def prepare(frame, elevation=500.0, latitude=LAT):
    """Run automatic selection without invoking station-donor transports."""
    report = P.ProcessingReport()
    elevation, tags = A.prepare(
        frame,
        None,
        2021,
        latitude,
        LON,
        elevation,
        object(),
        report,
        max_distance_km=75.0,
        max_stations=3,
    )
    return elevation, tags, report


def process(frame, elevation, tags, report, latitude=LAT):
    """Derive final physical fields and reduce their source attribution."""
    P.process(frame, latitude, LON, target_elevation_m=elevation, report=report)
    report.solar_source = frame.attrs["automatic_solar_source"]
    report.clamped_dni_hours += frame.attrs.get("automatic_clamped_dni_hours", 0)
    A.summarize(tags, frame, report)


def test_requested_heatwave_keeps_original_peaks_and_model_event_dates(monkeypatch):
    frame = weather_frame()
    temperatures = pd.Series(20.0, index=frame.index)
    temperatures.iloc[72:168] = 36.0
    temperatures.iloc[120] = 40.0
    frame["dry_bulb"] = temperatures
    frame.loc[frame.index[160], "dry_bulb"] = 39.0
    original = frame.dry_bulb.copy()
    frame.loc[frame.index[96:150], "dry_bulb"] = np.nan
    model, requests = mock_model(monkeypatch, frame, dry_bulb=temperatures)
    elevation, tags, report = prepare(frame)
    process(frame, elevation, tags, report)
    known = original.index.difference(frame.index[96:150])
    pd.testing.assert_series_equal(frame.loc[known, "dry_bulb"], original.loc[known])
    pd.testing.assert_series_equal(
        frame.dry_bulb.iloc[96:150], model.dry_bulb.iloc[96:150]
    )
    assert (frame.dry_bulb.iloc[72:168] >= 36).all()
    assert frame.dry_bulb.iloc[120] == 40
    assert frame.dry_bulb.iloc[160] == 39
    assert (frame.dry_bulb.iloc[:72] == 20).all()
    assert (frame.dry_bulb.iloc[168:] == 20).all()
    assert report.reanalysis_filled_hours["dry_bulb"] == 54
    assert (tags.dry_bulb.iloc[96:150] == "reanalysis").all()
    assert report.weather_classification == "mixed_reconstructed"
    assert len(requests) == 1


@pytest.mark.parametrize("missing_temperature", [False, True])
@pytest.mark.parametrize("requested_elevation", [500.0, None])
def test_qff_surface_check_uses_resolved_temperature_and_elevation(
    monkeypatch, missing_temperature, requested_elevation
):
    frame = weather_frame()
    frame.loc[frame.index[:5], "pressure"] = 310.0
    if missing_temperature:
        frame["dry_bulb"] = np.nan
    model, requests = mock_model(monkeypatch, frame, dry_bulb=20.0)
    elevation, tags, report = prepare(frame, requested_elevation)
    process(frame, elevation, tags, report)
    assert elevation == 500
    assert (frame.pressure.iloc[:5] == model.reanalysis_surface_pressure.iloc[:5]).all()
    assert (tags.pressure.iloc[:5] == "reanalysis").all()
    expected_primary = P.pressure_at_elevation(
        pd.Series(101300.0, index=frame.index[5:]),
        pd.Series(20.0, index=frame.index[5:]),
        LAT,
        elevation,
    )
    np.testing.assert_allclose(frame.pressure.iloc[5:], expected_primary)
    assert frame.pressure.between(31000, 120000).all()
    assert report.reanalysis_filled_hours["pressure"] == 5
    assert "invalid_surface_pressure" in [
        warning["code"] for warning in report.warnings
    ]
    assert len(requests) == 1


def test_reanalysis_surface_pressure_is_never_qff_converted_twice(monkeypatch):
    frame = weather_frame()
    frame["pressure"] = np.nan
    mock_model(monkeypatch, frame, elevation=1500, reanalysis_surface_pressure=85000.0)
    elevation, tags, report = prepare(frame, 1500)
    process(frame, elevation, tags, report)
    assert (frame.pressure == 85000).all()
    assert (tags.pressure == "reanalysis").all()
    assert report.reanalysis_filled_hours["pressure"] == len(frame)


@pytest.mark.parametrize("scope", ["meteorology", "solar", "metadata_only"])
def test_optional_model_clouds_follow_actual_reanalysis_replacement(monkeypatch, scope):
    frame = weather_frame()
    frame["cloud_cover"] = np.nan
    _, requests = mock_model(monkeypatch, frame, dry_bulb=25.0, cloud_cover=6.0)
    missing = pd.Series(False, index=frame.index)
    missing.iloc[96:150] = True
    if scope == "meteorology":
        frame.loc[missing, "dry_bulb"] = np.nan
    elif scope == "solar":
        frame[["ghi", "dni", "dirh"]] = np.nan
        missing = ~A._dark_hours(frame.index, LAT, LON)
    else:
        missing[:] = False
    _, tags, report = prepare(frame, None if scope == "metadata_only" else 500.0)
    assert len(requests) == 1
    assert frame.loc[missing, "cloud_cover"].eq(6.0).all()
    assert frame.loc[~missing, "cloud_cover"].isna().all()
    assert report.reanalysis_filled_hours["cloud_cover"] == int(missing.sum())
    if scope == "metadata_only":
        assert tags.eq("primary").all().all()


def test_usable_primary_clouds_survive_required_model_recovery(monkeypatch):
    frame = weather_frame()
    original = frame.cloud_cover.copy()
    frame.loc[frame.index[96:150], "dry_bulb"] = np.nan
    mock_model(monkeypatch, frame, dry_bulb=25.0, cloud_cover=6.0)
    _, _, report = prepare(frame)
    pd.testing.assert_series_equal(frame.cloud_cover, original)
    assert report.reanalysis_filled_hours["cloud_cover"] == 0


def test_invalid_model_surface_pressure_fails_clearly(monkeypatch):
    frame = weather_frame()
    frame["pressure"] = np.nan
    mock_model(monkeypatch, frame, reanalysis_surface_pressure=15000.0)
    with pytest.raises(DataGapError, match="pressure"):
        prepare(frame)


def test_reanalysis_solar_replaces_whole_group_and_marks_mixed_weather(monkeypatch):
    frame = weather_frame(3, start="2021-06-21 10:00")
    frame["ghi"] = 9000.0
    frame["dni"] = 1000.0
    frame["dirh"] = 500.0
    _, cosine = solar_zenith(frame.index - pd.Timedelta(minutes=30), LAT, LON)
    model, requests = mock_model(
        monkeypatch, frame, ghi=500.0, dni=300.0, dirh=300 * cosine
    )
    elevation, tags, report = prepare(frame)
    process(frame, elevation, tags, report)
    pd.testing.assert_series_equal(frame.ghi, model.ghi)
    pd.testing.assert_series_equal(frame.dni, model.dni)
    pd.testing.assert_series_equal(frame.dirh, model.dirh)
    assert frame.dhi.between(0, frame.ghi).all()
    assert (tags.ghi == "reanalysis").all()
    assert (tags.dry_bulb == "primary").all()
    assert report.weather_classification == "mixed_reconstructed"
    assert report.source_fractions["ghi"] == {"reanalysis": 1.0}
    assert report.solar_source == "era5"
    assert any(w["code"] == "invalid_radiation" for w in report.warnings)
    assert len(requests) == 1


def test_impossible_model_radiation_is_not_fabricated_as_success(monkeypatch):
    frame = weather_frame(3, start="2021-06-21 10:00")
    frame["ghi"] = np.nan
    mock_model(monkeypatch, frame, ghi=9000.0)
    with pytest.raises(DataGapError, match="ghi"):
        prepare(frame)


def test_invalid_direct_solar_is_decomposed_without_discarding_valid_ghi(monkeypatch):
    frame = weather_frame(3, start="2021-06-21 10:00")
    original_ghi = frame.ghi.copy()
    frame["dni"] = float("inf")
    model, requests = mock_model(monkeypatch, frame)
    elevation, tags, report = prepare(frame)
    process(frame, elevation, tags, report)
    pd.testing.assert_series_equal(frame.ghi, original_ghi)
    assert np.isfinite(frame[["ghi", "dni", "dhi"]]).all().all()
    assert report.energy_balance_max_residual < 1e-8
    assert "solar_decomposition" in [w["code"] for w in report.warnings]
    assert not requests


def test_extraterrestrial_dni_clamping_remains_visible_in_report():
    frame = weather_frame(3, start="2021-06-21 10:00")
    frame["ghi"] = 1000.0
    frame["dni"] = 1999.0
    elevation, tags, report = prepare(frame)
    process(frame, elevation, tags, report)
    assert (frame.dni <= frame.etrn).all()
    assert report.clamped_dni_hours == len(frame)
    assert report.energy_balance_max_residual < 1e-8


def test_fully_dark_intervals_are_zeroed_without_model_request(monkeypatch):
    frame = weather_frame(24, start="2021-12-21", latitude=69.0)
    frame[["ghi", "dni", "dirh"]] = 200.0
    _, requests = mock_model(monkeypatch, frame)
    elevation, tags, report = prepare(frame, latitude=69.0)
    process(frame, elevation, tags, report, latitude=69.0)
    assert (frame[["ghi", "dni", "dhi"]] == 0).all().all()
    assert (tags.ghi == "physical").all()
    assert any(w["code"] == "nighttime_radiation" for w in report.warnings)
    assert not requests


def test_sunrise_interval_is_not_misclassified_as_fully_dark():
    index = pd.date_range("2021-06-21", periods=24, freq="h", tz="UTC")
    _, start_cosine = solar_zenith(index - pd.Timedelta(hours=1), LAT, LON)
    _, end_cosine = solar_zenith(index, LAT, LON)
    rising = index[(start_cosine <= 0) & (end_cosine > 0)]
    assert len(rising) == 1
    frame = pd.DataFrame({"ghi": 10.0}, index=rising)
    report = P.ProcessingReport()
    ghi, _, dark, tags = A._solar_inputs(frame, report, LAT, LON)
    assert not dark.any()
    assert ghi.iloc[0] == 10
    assert tags.iloc[0] == "primary"


def test_temporally_filled_solar_hours_are_not_counted_as_observed():
    frame = weather_frame()
    frame.loc[frame.index[35], "ghi"] = np.nan
    elevation, tags, report = prepare(frame)
    process(frame, elevation, tags, report)
    assert tags.ghi.iloc[35] == "temporal"
    assert report.source_fractions["ghi"]["temporal"] == 1 / len(frame)
    assert report.weather_classification == "mixed_reconstructed"
    assert report.diurnal_filled_hours["ghi"] == 1
    assert report.interpolated_fraction["ghi"] == 1 / len(frame)


def test_filled_measured_solar_attribution_uses_the_selected_source():
    frame = weather_frame()
    frame[C.METOBS_RADIATION_COLUMN] = frame.ghi * 0.8
    frame.loc[frame.index[35], C.METOBS_RADIATION_COLUMN] = np.nan
    _, tags, report = prepare(frame)
    assert tags.ghi.iloc[35] == "temporal"
    assert report.diurnal_filled_hours[C.METOBS_RADIATION_COLUMN] == 1


def test_model_disagreement_uses_original_overlap_not_recovered_hours(monkeypatch):
    frame = weather_frame()
    frame.loc[frame.index[96:150], "dry_bulb"] = np.nan
    model, _ = mock_model(monkeypatch, frame, dry_bulb=30.0)
    elevation, tags, report = prepare(frame)
    process(frame, elevation, tags, report)
    comparison = report.reanalysis_metadata["overlap"]["dry_bulb"]
    assert comparison["hours"] == len(frame) - 54
    assert comparison["mean_absolute_difference"] == 10
    assert (frame.dry_bulb.iloc[96:150] == 30).all()
    warnings = [w for w in report.warnings if w["code"] == "reanalysis_disagreement"]
    assert any(w["details"]["variable"] == "dry_bulb" for w in warnings)


def test_large_source_boundary_change_warns_and_retains_plausible_extremes(monkeypatch):
    frame = weather_frame()
    frame.loc[frame.index[96:150], "dry_bulb"] = np.nan
    mock_model(monkeypatch, frame, dry_bulb=45.0)
    elevation, tags, report = prepare(frame)
    process(frame, elevation, tags, report)
    warnings = [w for w in report.warnings if w["code"] == "source_boundary_jump"]
    temperature_warning = next(
        w for w in warnings if w["details"]["variable"] == "dry_bulb"
    )
    assert temperature_warning["details"]["hours"] == 2
    assert temperature_warning["details"]["max_change"] == 25
    assert (frame.dry_bulb.iloc[96:150] == 45).all()
    assert frame.dry_bulb.iloc[95] == frame.dry_bulb.iloc[150] == 20


def test_temporal_weather_method_counts_survive_final_derivation():
    frame = weather_frame()
    frame.loc[frame.index[35], "dry_bulb"] = np.nan
    elevation, tags, report = prepare(frame)
    process(frame, elevation, tags, report)
    assert tags.dry_bulb.iloc[35] == "temporal"
    assert report.linear_filled_hours["dry_bulb"] == 1
    assert report.interpolated_fraction["dry_bulb"] == 1 / len(frame)


def test_temporal_wind_interpolation_respects_north_wrap():
    frame = weather_frame(3, start="2021-06-21 10:00")
    frame["wind_direction"] = [359.0, np.nan, 1.0]
    _, tags, _ = prepare(frame)
    assert min(frame.wind_direction.iloc[1], 360 - frame.wind_direction.iloc[1]) < 1e-8
    assert tags.wind_direction.iloc[1] == "temporal"
    assert frame.wind_direction.iloc[0] == 359
    assert frame.wind_direction.iloc[2] == 1


def test_temporal_opposite_wind_vectors_remain_unresolved_for_model():
    index = pd.date_range("2021-06-21", periods=3, freq="h", tz="UTC")
    direction = pd.Series([0.0, np.nan, 180.0], index=index)
    filled, *_ = P._fill_wind_direction(
        direction, required=False, short_gap_hours=3, max_gap_hours=48
    )
    assert pd.isna(filled.iloc[1])
    assert filled.iloc[0] == 0
    assert filled.iloc[2] == 180


def test_reanalysis_only_classification_ignores_physical_dark_zeros():
    frame = weather_frame(3, start="2021-06-21 10:00")
    tags = pd.DataFrame("reanalysis", index=frame.index, columns=A.REQUIRED + ["ghi"])
    tags.loc[tags.index[0], "ghi"] = "physical"
    report = P.ProcessingReport()
    A.summarize(tags, frame, report)
    assert report.weather_classification == "reanalysis_only"
