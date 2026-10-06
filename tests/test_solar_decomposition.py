"""Independent Erbs-Driesse references and hourly wrapper contracts."""

import numpy as np
import pytest
from pvlib import irradiance

from smhi2epw import solar


def test_hourly_horizontal_etr_controls_clearness_index():
    """A low-sun hourly reference must use ETRH/cosine as effective normal ETR."""
    dhi, dni = solar.erbs_decomposition(60.0, 120.0, 0.1)
    # Independent scalar evaluation of published Erbs-Driesse at kt=0.5.
    # Retaining these literal values also detects a return to classic Erbs.
    assert dhi == pytest.approx(39.54488939933313, abs=1e-9)
    assert dni == pytest.approx(204.5511060066687, abs=1e-9)
    assert dhi + 0.1 * dni == pytest.approx(60.0, abs=1e-12)


def test_inferred_dni_cutoff_is_strictly_above_point_087():
    """The exact floor and its lower neighbour retain all GHI as diffuse."""
    cosine = np.array([0.087 - 1e-8, 0.087, 0.087 + 1e-8])
    dhi, dni = solar.erbs_decomposition(60.0, 120.0, cosine)
    np.testing.assert_array_equal(dni[:2], [0.0, 0.0])
    np.testing.assert_array_equal(dhi[:2], [60.0, 60.0])
    assert dni[2] > 0
    np.testing.assert_allclose(dhi + dni * cosine, [60.0] * 3, rtol=0, atol=1e-12)


def test_all_invalid_geometry_returns_full_diffuse_and_zero_dni():
    """Nonpositive ETR or unusable cosine cannot support DNI inversion."""
    ghi = np.array([10.0, 20.0, 30.0, 40.0, 50.0])
    dhi, dni = solar.erbs_decomposition(
        ghi, [0.0, -1.0, 120.0, 120.0, 120.0], [0.5, 0.5, 0.0, -0.5, np.nan]
    )
    np.testing.assert_array_equal(dhi, ghi)
    np.testing.assert_array_equal(dni, np.zeros(5))


def test_zero_ghi_produces_zero_components_in_daylight():
    """The valid branch handles zero irradiation without a singularity."""
    dhi, dni = solar.erbs_decomposition([0.0, 0.0], [120.0, 240.0], [0.1, 0.8])
    np.testing.assert_array_equal(dhi, [0.0, 0.0])
    np.testing.assert_array_equal(dni, [0.0, 0.0])


def test_scalar_and_broadcast_inputs_return_numpy_arrays():
    """Maintain the scalar and array conventions of the public helper."""
    scalar_dhi, scalar_dni = solar.erbs_decomposition(60.0, 120.0, 0.1)
    assert isinstance(scalar_dhi, np.ndarray)
    assert isinstance(scalar_dni, np.ndarray)
    assert scalar_dhi.shape == scalar_dni.shape == ()
    dhi, dni = solar.erbs_decomposition(60.0, [120.0, 240.0], [[0.1], [0.5]])
    assert dhi.shape == dni.shape == (2, 2)
    assert dhi[0, 0] == pytest.approx(float(scalar_dhi))
    assert dni[0, 0] == pytest.approx(float(scalar_dni))
    np.testing.assert_allclose(dhi + dni * np.array([[0.1], [0.5]]), 60.0)


def test_nan_input_preserves_missing_ghi_and_invalid_geometry_fallback():
    """Missing GHI propagates while invalid geometry suppresses inferred DNI."""
    dhi, dni = solar.erbs_decomposition(
        [np.nan, 60.0, np.nan, 60.0],
        [120.0, 120.0, 120.0, np.nan],
        [0.5, np.nan, 0.01, 0.5],
    )
    np.testing.assert_array_equal(dhi, [np.nan, 60.0, np.nan, 60.0])
    np.testing.assert_array_equal(dni, [np.nan, 0.0, 0.0, 0.0])


def test_driesse_diffuse_fraction_stays_close_to_classic_erbs():
    """Compare both models with identical clearness index and geometry."""
    day = 172
    zenith = 60.0
    cosine = np.cos(np.deg2rad(zenith))
    # Classic erbs calculates its own default (Spencer) extra radiation.
    # Give our hourly wrapper exactly that same ETRH for a fair comparison.
    normal = irradiance.get_extra_radiation(day)
    kt = np.linspace(0.01, 1.0, 1001)
    ghi = kt * normal * cosine
    classic = irradiance.erbs(
        ghi,
        zenith,
        day,
        min_cos_zenith=0.087,
        max_zenith=np.rad2deg(np.arccos(0.087)),
    )
    dhi, dni = solar.erbs_decomposition(ghi, normal * cosine, cosine)
    difference = np.abs(dhi / ghi - classic["dhi"] / ghi)
    # The published bound is on diffuse fraction, not irradiance in W/m².
    assert difference.max() < 0.0005
    assert difference.max() > 1e-5
    np.testing.assert_allclose(dhi + dni * cosine, ghi, rtol=1e-12, atol=1e-12)
