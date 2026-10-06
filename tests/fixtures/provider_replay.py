"""Replay synthetic provider payloads through the public compiler and HTTP cache.

This is a deterministic engineering fixture, not observed Swedish weather or a
meteorological validation dataset. Its seasonal/daily weather and independent
daylight approximation exercise real provider parsing, recovery and receipts.
No request can reach the network: only the explicit provider URL contract below
is accepted, and unknown URLs raise AssertionError (including swallowed errors).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import numpy as np
import pandas as pd
import requests

from smhi2epw import EPWConfig, compile_epw, reanalysis
from smhi2epw import constants as C
from smhi2epw.compiler import CompileResult
from smhi2epw.ingestion import CachedClient

PRIMARY_STATION = 90001
DONOR_STATION = 90002
ELEVATION_M = 50.0
SCENARIOS = frozenset({"primary", "reconstructed", "reanalysis_only"})


def _daylight(index, latitude, longitude):
    """Return a simple NOAA-style cosine independent of package solar code."""
    hour = index.hour.to_numpy() + index.minute.to_numpy() / 60
    year_days = np.where(index.is_leap_year, 366, 365)
    gamma = 2 * np.pi / year_days * (index.dayofyear.to_numpy() - 1 + (hour - 12) / 24)
    declination = (
        0.006918
        - 0.399912 * np.cos(gamma)
        + 0.070257 * np.sin(gamma)
        - 0.006758 * np.cos(2 * gamma)
        + 0.000907 * np.sin(2 * gamma)
        - 0.002697 * np.cos(3 * gamma)
        + 0.001480 * np.sin(3 * gamma)
    )
    equation_minutes = 229.18 * (
        0.000075
        + 0.001868 * np.cos(gamma)
        - 0.032077 * np.sin(gamma)
        - 0.014615 * np.cos(2 * gamma)
        - 0.040849 * np.sin(2 * gamma)
    )
    hour_angle = np.deg2rad((hour * 60 + equation_minutes + 4 * longitude) / 4 - 180)
    latitude_radians = np.deg2rad(latitude)
    cosine = np.sin(latitude_radians) * np.sin(declination) + np.cos(
        latitude_radians
    ) * np.cos(declination) * np.cos(hour_angle)
    # A small horizon margin keeps the approximation away from sunrise/sunset.
    return np.where(cosine > 0.05, cosine, 0.0)


def _weather(index, latitude, longitude):
    """Make bounded seasonal/daily inputs and physically closed daylight solar."""
    day = index.dayofyear.to_numpy()
    solar_hour = index.hour.to_numpy() + longitude / 15
    seasonal = np.sin(2 * np.pi * (day - 80) / 365.25)
    daily = np.cos(2 * np.pi * (solar_hour - 14) / 24)
    slow = np.sin(2 * np.pi * day / 9)
    cosine = _daylight(index, latitude, longitude)
    dni = np.where(cosine > 0, 400.0, 0.0)
    return {
        "dry_bulb": 8.0 + 11 * seasonal + 3 * daily,
        "relative_humidity": 65.0 - 12 * daily,
        "pressure": 1013.0 + 8 * slow,  # Primary and donor sea-level QFF, hPa.
        "wind_speed": 3.0 + 0.7 * slow,
        "wind_direction": 220.0 + 25 * slow,
        "cloud_cover": np.full(len(index), 40.0),  # Explicit percent in payload.
        "ghi": 600.0 * cosine,
        "dni": dni,
        "dirh": dni * cosine,
    }


class ReplaySession:
    """Serve only deterministic MetObs, STRÅNG and ERA5 endpoint shapes offline."""

    def __init__(self, year=2023, scenario="primary", latitude=57.7, longitude=12.0):
        """Create one same-year transport with UTC buffers on both boundaries."""
        if scenario not in SCENARIOS:
            raise ValueError(f"Unknown engineering replay scenario: {scenario}")
        self.year = year
        self.scenario = scenario
        self.latitude = latitude
        self.longitude = longitude
        self.urls = []
        self.unknown_urls = []
        self.index = pd.date_range(
            pd.Timestamp(year, 1, 1, tz="UTC") - pd.Timedelta(days=2),
            pd.Timestamp(year + 1, 1, 1, tz="UTC") + pd.Timedelta(days=2),
            freq="h",
        )
        self.weather = _weather(self.index, latitude, longitude)

    def _response(self, url, body, status=200):
        """Return a real requests response consumed by CachedClient.get_text."""
        response = requests.Response()
        response.url = url
        response.status_code = status
        response.encoding = "utf-8"
        response._content = body.encode("utf-8")
        return response

    def _station(self, station_id):
        """Describe a synthetic primary or nearby donor, with year coverage."""
        donor = station_id == DONOR_STATION
        return {
            "key": str(station_id),
            "name": "Engineering replay donor"
            if donor
            else "Engineering replay primary",
            "latitude": self.latitude + (0.08 if donor else 0),
            "longitude": self.longitude,
            "from": 0,
            "to": 9999999999999,
        }

    def _csv(self, station_id, parameter):
        """Serialize SMHI archive format, including G/Y/R quality and units."""
        column = C.METOBS_PARAMETERS[parameter]
        values = self.weather[column].copy()
        quality = np.full(len(values), "G", dtype="<U1")
        quality[::137] = "Y"
        if station_id == DONOR_STATION and column == "dry_bulb":
            values += 0.8  # Local held-out assessment should select a median offset.
        if self.scenario == "reconstructed":
            if column == "dry_bulb" and station_id == PRIMARY_STATION:
                quality[
                    (self.index >= f"{self.year}-04-10")
                    & (self.index < f"{self.year}-04-13")
                ] = "R"
            if column == "pressure":
                # Neither station has this 96-hour block; ERA5 must complete it.
                quality[
                    (self.index >= f"{self.year}-10-10")
                    & (self.index < f"{self.year}-10-14")
                ] = "R"
            if column == "relative_humidity" and station_id == PRIMARY_STATION:
                quality[
                    (self.index >= f"{self.year}-02-10T12:00Z")
                    & (self.index < f"{self.year}-02-10T14:00Z")
                ] = "R"
        unit = "%" if column == "cloud_cover" else "engineering source units"
        lines = [
            "Stationsnamn;Stationsnummer",
            f"Engineering replay fixture;{station_id}",
            "",
            "Parameternamn;Beskrivning;Enhet",
            f"{column};Deterministic engineering fixture;{unit}",
            "",
            f"Datum;Tid (UTC);{column};Kvalitet",
        ]
        lines.extend(
            f"{timestamp:%Y-%m-%d};{timestamp:%H:%M:%S};{value:.6f};{flag}"
            for timestamp, value, flag in zip(self.index, values, quality)
        )
        return "\n".join(lines)

    def _era5(self, query):
        """Serialize declared ERA5 units and preceding-hour radiation means."""
        expected = {
            "models": ["era5"],
            "timezone": ["GMT"],
            "temperature_unit": ["celsius"],
            "wind_speed_unit": ["ms"],
            "timeformat": ["iso8601"],
            "hourly": [",".join(reanalysis.VARIABLES)],
        }
        assert all(query.get(k) == v for k, v in expected.items()), query
        assert float(query["latitude"][0]) == self.latitude
        assert float(query["longitude"][0]) == self.longitude
        index = pd.date_range(
            query["start_date"][0], query["end_date"][0] + " 23:00", freq="h", tz="UTC"
        )
        meteorology = _weather(index, self.latitude, self.longitude)
        radiation = _weather(
            index - pd.Timedelta(minutes=30), self.latitude, self.longitude
        )
        elevation = float(query.get("elevation", [ELEVATION_M])[0])
        hourly = {"time": index.strftime("%Y-%m-%dT%H:%M").tolist()}
        for variable, (column, _) in reanalysis.VARIABLES.items():
            if column == "reanalysis_surface_pressure":
                # The engineering provider emits surface pressure, not QFF.
                values = meteorology["pressure"] * np.exp(-elevation / 8434.5)
            elif column in ("ghi", "dni", "dirh"):
                values = radiation[column]
            else:
                values = meteorology[column]
            hourly[variable] = values.tolist()
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "elevation": elevation,
            "utc_offset_seconds": 0,
            "hourly": hourly,
            "hourly_units": {k: unit for k, (_, unit) in reanalysis.VARIABLES.items()},
        }

    def get(self, url, timeout):
        """Replay one recognized HTTP GET and reject every unspecified URL."""
        self.urls.append(url)
        parsed = urlparse(url)
        if url.startswith(C.METOBS_BASE + "/"):
            relative = url.removeprefix(C.METOBS_BASE + "/")
            catalogue = re.fullmatch(r"parameter/(1|3|4|6|9|11)\.json", relative)
            metadata = re.fullmatch(
                r"parameter/(1|3|4|6|9)/station/(90001|90002)\.json", relative
            )
            archive = re.fullmatch(
                r"parameter/(1|3|4|6|9|16)/station/(90001|90002)/period/corrected-archive/data\.csv",
                relative,
            )
            if catalogue or metadata or archive:
                if self.scenario == "reanalysis_only":
                    return self._response(url, '{"error":"fixture SMHI outage"}', 503)
                if catalogue:
                    parameter = int(catalogue.group(1))
                    body = {
                        "station": []
                        if parameter == 11
                        else [
                            self._station(PRIMARY_STATION),
                            self._station(DONOR_STATION),
                        ]
                    }
                elif metadata:
                    station = self._station(int(metadata.group(2)))
                    body = {**station, "position": [{**station, "height": ELEVATION_M}]}
                else:
                    return self._response(
                        url, self._csv(int(archive.group(2)), int(archive.group(1)))
                    )
                return self._response(url, json.dumps(body))
        if url.startswith(C.STRANG_BASE + "/"):
            relative = parsed.path.removeprefix(urlparse(C.STRANG_BASE).path + "/")
            match = re.fullmatch(
                r"geotype/point/lon/(-?\d+\.\d{6})/lat/(-?\d+\.\d{6})/parameter/(117|118|121)/data\.json",
                relative,
            )
            query = parse_qs(parsed.query)
            if (
                match
                and set(query) == {"from", "to", "interval"}
                and query["interval"] == ["hourly"]
            ):
                assert float(match.group(1)) == self.longitude
                assert float(match.group(2)) == self.latitude
                if self.scenario == "reanalysis_only":
                    return self._response(url, '{"error":"fixture solar outage"}', 503)
                index = pd.date_range(
                    query["from"][0], query["to"][0], freq="h", tz="UTC"
                )
                column = C.STRANG_PARAMETERS[int(match.group(3))]
                values = _weather(index, self.latitude, self.longitude)[column]
                body = [
                    {
                        "date_time": f"{timestamp:%Y-%m-%dT%H:%M:%SZ}",
                        "value": float(value),
                    }
                    for timestamp, value in zip(index, values)
                ]
                return self._response(url, json.dumps(body))
        if (
            parsed.scheme == "https"
            and parsed.netloc == "archive-api.open-meteo.com"
            and parsed.path == "/v1/archive"
        ):
            query = parse_qs(parsed.query)
            allowed = {
                "latitude",
                "longitude",
                "start_date",
                "end_date",
                "hourly",
                "models",
                "timezone",
                "temperature_unit",
                "wind_speed_unit",
                "timeformat",
                "elevation",
            }
            if set(query) <= allowed and allowed - {"elevation"} <= set(query):
                return self._response(url, json.dumps(self._era5(query)))
        self.unknown_urls.append(url)
        raise AssertionError(f"Unexpected URL in offline provider replay: {url}")


def compile_weather(
    output_dir, year=2023, scenario="primary", latitude=57.7, longitude=12.0
) -> CompileResult:
    """Compile weather.epw and its real receipt via an offline provider session."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    session = ReplaySession(year, scenario, latitude, longitude)
    client = CachedClient(
        cache_dir=str(output_dir / f"raw-cache-{year}-{scenario}"),
        session=session,
        max_retries=0,
    )
    result = compile_epw(
        EPWConfig(
            year=year,
            output_path=str(output_dir / "weather.epw"),
            latitude=latitude,
            longitude=longitude,
            city="Deterministic engineering fixture",
            weather_policy="automatic",
            target_elevation_m=ELEVATION_M,
            max_workers=2,
        ),
        client=client,
    )
    # Ingestion deliberately catches source errors. Unknown fixture URLs remain
    # test failures even when automatic recovery could mask such an error.
    assert not session.unknown_urls, session.unknown_urls
    return result
