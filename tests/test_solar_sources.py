"""Independent radiation-source and interval-processing regressions."""

from urllib.parse import parse_qs, urlparse

import numpy as np
import pandas as pd
import pytest

from smhi2epw import automatic as A
from smhi2epw import ingestion as I
from smhi2epw import processing as P
from smhi2epw import solar


def low_sun_frame():
    """Return fixed SMHI STRÅNG samples averaged over their preceding hours.

    Retrieved at 65 N, 20 E on 2023-12-01, from parameters 117/118/121.
    Raw 10/11/12 UTC values: GHI 17.1/31.4/15.2, DNI 11.8/414.7/269.8,
    horizontal beam 0.7/23.4/8.5 W/m². Their midpoint elevations are below 5°.
    https://strang.smhi.se/extraction/index.php describes the source fields.
    """
    return pd.DataFrame(
        {"ghi": [24.25, 23.30], "dni": [213.25, 342.25], "dirh": [12.05, 15.95]},
        index=pd.DatetimeIndex(["2023-12-01 11:00", "2023-12-01 12:00"], tz="UTC"),
    )


@pytest.mark.parametrize("automatic", [False, True])
@pytest.mark.parametrize("measured_scale", [None, 2.0])
def test_supplied_low_sun_interval_means_survive_both_finalization_paths(
    automatic, measured_scale
):
    frame = low_sun_frame()
    selected = frame.ghi.copy()
    measured = pd.Series(measured_scale is not None, index=frame.index)
    scale = 1.0 if measured_scale is None else measured_scale
    frame["ghi_measured"] = selected * scale if measured_scale else np.nan
    report = P.ProcessingReport()
    if automatic:
        tags = pd.DataFrame({"ghi": "primary"}, index=frame.index)
        A._finish_solar(frame, selected * scale, measured, tags, 65.0, 20.0, report)
        frame.attrs["automatic_prepared"] = True
    P.apply_solar(frame, 65.0, 20.0, report)
    np.testing.assert_allclose(frame.dni, np.array([213.25, 342.25]) * scale)
    np.testing.assert_allclose(frame.dirh, np.array([12.05, 15.95]) * scale)
    np.testing.assert_allclose(frame.dhi, np.array([12.20, 7.35]) * scale)
    np.testing.assert_allclose(frame.ghi, selected * scale)
    assert report.energy_balance_max_residual < 1e-12
    if automatic:
        # Downstream processing must not reinterpret the supplied means again.
        before = frame.copy()
        P.apply_solar(frame, 65.0, 20.0, report)
        pd.testing.assert_frame_equal(frame, before)


def test_missing_horizontal_beam_does_not_suppress_supplied_low_sun_dni():
    frame = low_sun_frame().drop(columns="dirh")
    P.apply_solar(frame, 65.0, 20.0)
    np.testing.assert_allclose(frame.dni, [213.25, 342.25])
    assert frame.dirh.between(0.0, frame.ghi).all()
    np.testing.assert_allclose(frame.dhi + frame.dirh, frame.ghi)


def test_low_angle_inversion_guard_applies_when_dni_is_inferred():
    frame = low_sun_frame().drop(columns=["dni", "dirh"])
    report = P.ProcessingReport()
    P.apply_solar(frame, 65.0, 20.0, report)
    assert frame.dni.eq(0.0).all()
    np.testing.assert_allclose(frame.dhi, frame.ghi)
    assert report.solar_source == "strang_ghi+erbs"


def test_supplied_zero_dni_is_retained_without_erbs_repartition():
    frame = low_sun_frame()
    frame[["dni", "dirh"]] = 0.0
    report = P.ProcessingReport()
    P.apply_solar(frame, 65.0, 20.0, report)
    assert frame.dni.eq(0.0).all()
    np.testing.assert_allclose(frame.dhi, frame.ghi)
    assert report.solar_source == "strang"


def test_partly_sunlit_interval_with_dark_midpoint_keeps_supplied_dni():
    # Sunrise occurs during 08:00–09:00 UTC; its 08:30 midpoint is still dark.
    frame = pd.DataFrame(
        {"ghi": [2.0], "dni": [10.0], "dirh": [0.1]},
        index=pd.DatetimeIndex(["2023-12-10 09:00"], tz="UTC"),
    )
    P.apply_solar(frame, 65.0, 20.0)
    assert frame.dni.iloc[0] == 10.0
    assert frame.dirh.iloc[0] == 0.1
    assert frame.dhi.iloc[0] == 1.9
    assert frame.etrn.iloc[0] > 0.0


def test_wholly_dark_interval_cannot_retain_source_radiation():
    frame = pd.DataFrame(
        {"ghi": [20.0], "dni": [300.0], "dirh": [10.0]},
        index=pd.DatetimeIndex(["2023-12-01 01:00"], tz="UTC"),
    )
    P.apply_solar(frame, 65.0, 20.0)
    assert frame[["ghi", "dni", "dirh", "dhi", "etrh", "etrn"]].eq(0).all().all()


def test_historical_dni_is_projected_at_raw_instants_before_averaging(monkeypatch):
    index = pd.date_range("2010-06-21 11:00", periods=3, freq="h", tz="UTC")
    requests = []

    def radiation(lat, lon, parameter, column, window, client):
        requests.append(parameter)
        values = [107.9, 175.9, 105.3] if parameter == 118 else [600.0] * 3
        return pd.Series(values, index=index, name=column)

    monkeypatch.setattr(I, "fetch_strang_parameter", radiation)
    monkeypatch.setattr(
        I, "fetch_metobs_parameter", lambda *a, **k: pd.Series(dtype=float)
    )

    # Control raw-time geometry independently of the production SPA adapter.
    # Mean(DNI * cosine) must differ from mean(DNI) * a midpoint cosine.
    def geometry(grid, latitude, longitude):
        cosine = pd.Series([0.2, 0.8, 0.4], index=index).reindex(grid).fillna(0)
        return np.zeros(len(grid)), cosine.to_numpy()

    monkeypatch.setattr(solar, "solar_zenith", geometry)
    frame = I.ingest(I.StationMeta(1, "test", 59.3, 18.0), 2010, object())
    assert set(requests) == {117, 118}
    np.testing.assert_allclose(frame.loc[index[1:], "dni"], [141.9, 140.6])
    # Adjacent means of raw projected beams: (21.58 + 140.72) / 2, etc.
    np.testing.assert_allclose(
        frame.loc[index[1:], "dirh"],
        [81.15, 91.42],
        atol=1e-10,
        rtol=0,
    )
    assert frame.attrs["projected_beam_hours"] == 3


def test_2017_transition_uses_available_beam_and_projects_only_missing_instants(
    monkeypatch,
):
    index = pd.date_range("2017-04-17 23:00", periods=3, freq="h", tz="UTC")
    requests = []

    def radiation(lat, lon, parameter, column, window, client):
        requests.append(parameter)
        if parameter == 121:
            return pd.Series([10.0, 20.0], index=index[1:], name=column)
        return pd.Series(100.0 if parameter == 118 else 600.0, index=index, name=column)

    monkeypatch.setattr(I, "fetch_strang_parameter", radiation)
    monkeypatch.setattr(
        I, "fetch_metobs_parameter", lambda *a, **k: pd.Series(dtype=float)
    )
    frame = I.ingest(I.StationMeta(1, "test", 59.3, 18.0), 2017, object())
    assert set(requests) == {117, 118, 121}
    # The earlier dark instant projects to zero; available provider values stay.
    np.testing.assert_allclose(frame.loc[index[1:], "dirh"], [5.0, 15.0])
    assert frame.attrs["projected_beam_hours"] == 1


def test_partial_2017_beam_request_starts_at_provider_availability():
    class Client:
        def __init__(self):
            self.urls = []

        def get_json(self, url):
            self.urls.append(url)
            return []

    client = Client()
    window = (
        pd.Timestamp("2016-12-31", tz="UTC"),
        pd.Timestamp("2018-01-01", tz="UTC"),
    )
    I.fetch_strang_parameter(59.3, 18.0, 121, "dirh", window, client)
    query = parse_qs(urlparse(client.urls[0]).query)
    assert query["from"] == ["2017-04-18T00:00:00"]
    assert query["to"] == ["2018-01-01T00:00:00"]
    before = (window[0], pd.Timestamp("2017-04-17 23:00", tz="UTC"))
    assert I.fetch_strang_parameter(59.3, 18.0, 121, "dirh", before, client).empty
    assert len(client.urls) == 1
