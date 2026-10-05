"""Normalize cloud units from explicit SMHI CSV metadata, never value magnitude."""

from __future__ import annotations

import pandas as pd
import pytest

from smhi2epw import ingestion as I
from smhi2epw.errors import IngestionError

WINDOW = (pd.Timestamp("2023-01-01", tz="UTC"), pd.Timestamp("2023-01-02", tz="UTC"))


def cloud_csv(unit="procent", values=("100", "63", "6"), *, flags=None):
    """Match SMHI's station, parameter and data metadata blocks."""
    preamble = (
        "Stationsnamn;Stationsnummer;Stationshöjd (meter över havet);Latitud;Longitud\n"
        "Synthetic;12345;30;57.7;12.0\n\n"
        "Parameternamn;Beskrivning;Enhet\n"
        f"Total molnmängd;momentanvärde,1gång/tim;{unit}\n\n"
        "Datum;Tid (UTC);Total molnmängd;Kvalitet;;Tidsutsnitt:\n"
    )
    flags = flags or ["G"] * len(values)
    rows = [
        f"2023-01-01;{hour:02}:00:00;{value};{flag};;\n"
        for hour, (value, flag) in enumerate(zip(values, flags))
    ]
    return preamble + "".join(rows)


class TextClient:
    """Return one CSV and assert normalization never requests metadata separately."""

    def __init__(self, text):
        self.text = text
        self.urls = []

    def get_text(self, url, suffix="txt"):
        self.urls.append(url)
        assert suffix == "csv"
        return self.text

    def get_json(self, url):
        raise AssertionError("Cloud normalization must use the fetched CSV preamble")


@pytest.mark.parametrize("unit", ["procent", "percent", "%", " PROCENT "])
def test_declared_percent_normalizes_even_low_values_without_guessing(unit):
    client = TextClient(cloud_csv(unit))
    series = I.fetch_metobs_parameter(12345, 16, "cloud_cover", WINDOW, client)
    assert series.to_list() == pytest.approx([8.0, 5.04, 0.48])
    assert series.name == "cloud_cover" and str(series.index.tz) == "UTC"
    assert series.attrs == {"source_unit": unit.strip(), "output_unit": "octas"}
    assert len(client.urls) == 1


@pytest.mark.parametrize("unit", ["octas", "octa", "oktas", "okta"])
def test_declared_octas_are_preserved_and_source_bounds_are_checked(unit):
    series = I.fetch_metobs_parameter(
        12345,
        16,
        "cloud_cover",
        WINDOW,
        TextClient(cloud_csv(unit, values=("6", "0", "8", "8,01", "-1", "inf"))),
    )
    assert series.iloc[:3].to_list() == [6, 0, 8]
    assert series.iloc[3:].isna().all()
    assert series.attrs["output_unit"] == "octas"


def test_percent_bounds_decimal_commas_and_quality_filter_survive_conversion():
    series = I.fetch_metobs_parameter(
        12345,
        16,
        "cloud_cover",
        WINDOW,
        TextClient(
            cloud_csv(
                values=("62,5", "100,01", "-0,01", "inf", "50", "6"),
                flags=("Y", "G", "G", "G", "R", "G"),
            )
        ),
    )
    assert series.iloc[0] == 5
    assert series.iloc[1:5].isna().all()
    assert series.iloc[5] == pytest.approx(0.48)
    override = I.fetch_metobs_parameter(
        12345,
        16,
        "cloud_cover",
        WINDOW,
        TextClient(cloud_csv(values=("50", "6"), flags=("R", "G"))),
        accepted_quality={"R"},
    )
    assert override.iloc[0] == 4 and pd.isna(override.iloc[1])


@pytest.mark.parametrize(
    "unit", ["", "unknown", "tenths", "W/m²", "0-100", "procentish"]
)
def test_missing_or_unknown_declared_units_are_rejected(unit):
    with pytest.raises(IngestionError, match="CSV Enhet declaration"):
        I.fetch_metobs_parameter(
            12345, 16, "cloud_cover", WINDOW, TextClient(cloud_csv(unit))
        )


def test_unit_must_be_in_parameter_preamble_not_data_name_or_comments():
    text = cloud_csv().replace(
        "Parameternamn;Beskrivning;Enhet\nTotal molnmängd;momentanvärde,1gång/tim;procent\n",
        "Kommentar;Enhet\nprocent;procent\n",
    )
    with pytest.raises(IngestionError, match="CSV Enhet declaration"):
        I.fetch_metobs_parameter(12345, 16, "cloud_cover", WINDOW, TextClient(text))


@pytest.mark.parametrize(
    "param,column",
    [(6, "relative_humidity"), (6, "cloud_cover"), (16, "relative_humidity")],
)
def test_normalization_is_specific_to_cloud_parameter_and_canonical_name(param, column):
    series = I.fetch_metobs_parameter(
        12345, param, column, WINDOW, TextClient(cloud_csv())
    )
    assert series.to_list() == [100, 63, 6]
    assert series.attrs == {}


def test_ingest_propagates_units_and_handles_unknown_cloud_as_optional_failure():
    """Exercise hourly resampling and existing optional-source failure handling."""
    from test_pipeline import LAT, LON, STATION_ID, YEAR, FakeClient

    class CloudClient(FakeClient):
        def __init__(self, unit):
            super().__init__()
            self.unit = unit

        def get_text(self, url, suffix="txt"):
            text = super().get_text(url, suffix)
            if "/parameter/16/" in url:
                text = text.replace(
                    "Total molnmangd;;octas", f"Total molnmangd;;{self.unit}"
                )
            return text

    meta = I.StationMeta(STATION_ID, "Synthetic", LAT, LON)
    frame = I.ingest(meta, YEAR, CloudClient("octas"))
    assert frame.cloud_cover.notna().any()
    assert frame.attrs["cloud_source_unit"] == "octas"
    assert frame.attrs["cloud_output_unit"] == "octas"
    assert not frame.attrs["source_failures"]
    unavailable = I.ingest(meta, YEAR, CloudClient("unknown"))
    assert unavailable.cloud_cover.isna().all()
    assert "cloud_source_unit" not in unavailable.attrs
    assert "cloud_output_unit" not in unavailable.attrs
    assert [
        failure["variable"] for failure in unavailable.attrs["source_failures"]
    ] == ["cloud_cover"]
