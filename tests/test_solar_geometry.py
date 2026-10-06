"""Independent geometry references and timestamp/EPW conventions."""

import numpy as np
import pandas as pd
import pytest

from smhi2epw import solar


def test_nrel_spa_benchmark_uses_geometric_zenith():
    """Check the published Golden, Colorado example without refraction."""
    # NREL/TP-560-34302, Appendix A.5, specifies 2003-10-17 12:30:30 MST.
    # https://www.nlr.gov/docs/fy08osti/34302.pdf
    # The report's 50.11162° includes refraction. The same reference's true
    # elevation is 39.872046° in pvlib's published SPA benchmark fixture:
    # https://github.com/pvlib/pvlib-python/blob/v0.16.1/tests/test_solarposition.py
    index = pd.DatetimeIndex(["2003-10-17 19:30:30"], tz="UTC")
    zenith, cosine = solar.solar_zenith(index, 39.742476, -105.1786)
    expected = 50.127954
    # Allow sea-level altitude and estimated delta-T, rather than the
    # reference's 1830.14 m and 67 s. This still separates apparent zenith.
    np.testing.assert_allclose(zenith, [expected], rtol=0, atol=0.0003)
    np.testing.assert_allclose(
        cosine, [np.cos(np.deg2rad(expected))], rtol=0, atol=5e-6
    )


def test_utc_and_local_dates_agree_across_leap_and_year_boundaries():
    """Preserve absolute times when their local calendar dates differ."""
    utc = pd.DatetimeIndex(
        [
            "2023-12-31 23:30",
            "2024-01-01 00:30",
            "2024-02-29 23:30",
            "2024-03-01 00:30",
            "2024-12-31 23:30",
            "2025-01-01 00:30",
        ],
        tz="UTC",
    )
    local = utc.tz_convert("Europe/Stockholm")
    for calculation in (solar.solar_zenith, solar.interval_solar_geometry):
        expected = calculation(utc, 59.3, 18.0)
        actual = calculation(local, 59.3, 18.0)
        for result, reference in zip(actual, expected, strict=True):
            np.testing.assert_array_equal(result, reference)
    # Each calendar boundary must also work within an otherwise single-year
    # call; selecting one year for the entire batch would violate this.
    batch = solar.solar_zenith(utc, 59.3, 18.0)[0]
    separate = [solar.solar_zenith(utc[i : i + 1], 59.3, 18.0)[0][0] for i in range(6)]
    np.testing.assert_array_equal(batch, separate)


@pytest.mark.parametrize(
    "calculation", [solar.solar_zenith, solar.interval_solar_geometry]
)
def test_geometry_rejects_naive_timestamps(calculation):
    """Prevent accidental interpretation of local timestamps as UTC."""
    with pytest.raises(ValueError, match="timezone-aware"):
        calculation(pd.DatetimeIndex(["2024-02-29 12:00"]), 59.3, 18.0)


def test_asce_distance_correction_retains_1367_and_utc_day_of_year():
    """Use the ASCE daily correction, including the leap year's day 366."""
    utc = pd.DatetimeIndex(
        [
            "2024-01-01 23:30",
            "2024-02-29 23:30",
            "2024-06-20 23:30",
            "2024-12-31 23:30",
        ],
        tz="UTC",
    )
    cosine = np.array([0.25, 0.5, 0.75, 1.0])
    horizontal, normal = solar.extraterrestrial_radiation(
        utc.tz_convert("Europe/Stockholm"), cosine
    )
    # ASCE's closed-form daily Earth-Sun correction; the denominator remains
    # 365 even in leap years. This is independent of SPA's calendar handling.
    day = np.array([1, 60, 172, 366])
    expected = 1367.0 * (1.0 + 0.033 * np.cos(2.0 * np.pi * day / 365.0))
    np.testing.assert_allclose(normal, expected, rtol=0, atol=1e-10)
    np.testing.assert_allclose(horizontal, expected * cosine, rtol=0, atol=1e-10)


def test_epw_extraterrestrial_fields_are_zero_at_night_and_horizon():
    """Suppress both normal and horizontal ETR where cosine is nonpositive."""
    index = pd.date_range("2024-02-29", periods=3, freq="h", tz="UTC")
    horizontal, normal = solar.extraterrestrial_radiation(index, [-0.5, 0.0, 0.5])
    np.testing.assert_array_equal(horizontal[:2], [0.0, 0.0])
    np.testing.assert_array_equal(normal[:2], [0.0, 0.0])
    assert horizontal[2] > 0
    assert normal[2] == pytest.approx(2.0 * horizontal[2])


def test_preceding_hour_geometry_recognizes_polar_night():
    """A wholly dark hour contains no positive-cosine radiation samples."""
    index = pd.DatetimeIndex(["2024-12-21 12:00"], tz="UTC")
    cosine, horizontal, normal, dark = solar.interval_solar_geometry(index, 69.0, 18.0)
    np.testing.assert_array_equal(cosine, [0.0])
    np.testing.assert_array_equal(horizontal, [0.0])
    np.testing.assert_array_equal(normal, [0.0])
    np.testing.assert_array_equal(dark, [True])
