"""Regression tests for target-site metadata and SMHI QFF semantics."""

import numpy as np
import pytest
from test_pipeline import STATION_ID, YEAR, FakeClient

from smhi2epw import compile_epw, processing
from smhi2epw.compiler import EPWConfig
from smhi2epw.errors import IngestionError


def test_pressure_sea_level_and_height_direction():
    temperatures = np.array([-20.0, -7.0, 0.0, 2.0, 20.0])
    source = np.full(5, 101325.0)
    assert np.array_equal(
        processing.pressure_at_elevation(source, temperatures, 68, 0), source
    )
    elevated = processing.pressure_at_elevation(source, temperatures, 68, 300)
    np.testing.assert_allclose(
        elevated,
        [97473.906, 97569.191, 97619.282, 97632.956, 97869.122],
        atol=0.002,
        rtol=0,
    )
    assert np.all(
        processing.pressure_at_elevation(source, temperatures, 68, 600) < elevated
    )
    assert np.all(
        processing.pressure_at_elevation(source, temperatures, 68, -100) > source
    )


@pytest.mark.parametrize("height", [float("nan"), float("inf"), -1001.0, 10000.0])
def test_bad_target_rejected_before_network(tmp_path, height):
    client = FakeClient()
    with pytest.raises(IngestionError, match="elevation"):
        compile_epw(
            EPWConfig(
                YEAR,
                str(tmp_path / "bad.epw"),
                station_id=STATION_ID,
                target_elevation_m=height,
            ),
            client=client,
        )
    assert client.urls == []


@pytest.mark.parametrize("height", [None, 300.0])
def test_compile_keeps_target_separate_from_station(tmp_path, height):
    output = tmp_path / "weather.epw"
    result = compile_epw(
        EPWConfig(
            YEAR,
            str(output),
            station_id=STATION_ID,
            latitude=59.4,
            longitude=18.1,
            target_elevation_m=height,
        ),
        client=FakeClient(),
    )
    lines = output.read_text().splitlines()
    target = 12.0 if height is None else height
    assert float(lines[0].split(",")[9]) == target
    assert result.station.elevation == 12.0
    assert result.target_elevation_m == target
    assert result.target_latitude == 59.4
    assert result.pressure_method == "smhi_qff_inverse_v1"
    pressures = [float(line.split(",")[9]) for line in lines[8:]]
    assert len(pressures) == 8760
    assert max(pressures) < 101300.0 if height else max(pressures) < 101400.0


def test_cli_target_option():
    from smhi2epw.cli import build_parser

    args = build_parser().parse_args(
        ["2018", "test.epw", "--station", "180940", "--target-elevation-m", "446.7"]
    )
    assert args.target_elevation_m == 446.7


@pytest.mark.parametrize(
    "latitude,height,temperature",
    [(91, 0, 10), (-91, 0, 10), (60, 10000, 10), (60, -1001, 10), (60, 0, -273.15)],
)
def test_low_level_pressure_rejects_invalid_physical_domain(
    latitude, height, temperature
):
    with pytest.raises(ValueError):
        processing.pressure_at_elevation([101325.0], [temperature], latitude, height)


@pytest.mark.parametrize(
    "pressure,temperature",
    [(float("nan"), 10), (float("inf"), 10), (0, 10), (-1, 10), (101325, float("nan"))],
)
def test_low_level_pressure_rejects_missing_or_nonpositive_inputs(
    pressure, temperature
):
    with pytest.raises(ValueError):
        processing.pressure_at_elevation([pressure], [temperature], 60, 100)
