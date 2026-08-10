"""Retrieve and align observed MetObs and modelled STRÅNG weather data.

SMHI exposes station observations and gridded solar radiation through separate
APIs with different payloads and missing-value conventions. This module hides
those transport details: it discovers full-year stations, filters observation
quality flags, converts ``-999`` STRÅNG sentinels to missing values, and aligns
all sources on one continuous hourly UTC grid. Raw responses can be cached
atomically to make repeated educational and production runs kind to the APIs.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import math
import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

import pandas as pd
import requests
from requests.adapters import HTTPAdapter

try:  # urllib3 ships with requests; import defensively.
    from urllib3.util.retry import Retry
except Exception:  # pragma: no cover
    Retry = None  # type: ignore[misc,assignment]

from . import constants as C
from .errors import IngestionError

log = logging.getLogger("smhi2epw")


# --------------------------------------------------------------------------- #
# Metadata container
# --------------------------------------------------------------------------- #
@dataclass
class StationMeta:
    """Describe the MetObs station supplying observed weather.

    Attributes
    ----------
    station_id
        Positive SMHI station identifier.
    name
        Human-readable station name with API instruction text removed.
    latitude, longitude
        Station coordinates in decimal degrees.
    elevation
        Station height in metres above sea level.
    wmo_id
        Genuine WMO identifier, or ``"999999"`` when SMHI supplies none.
    """

    station_id: int
    name: str
    latitude: float
    longitude: float
    elevation: float = 0.0
    wmo_id: str = "999999"

    def distance_km(self, lat: float, lon: float) -> float:
        """Calculate great-circle distance to a target coordinate.

        Parameters
        ----------
        lat, lon
            Target latitude and longitude in decimal degrees.

        Returns
        -------
        float
            Haversine distance in kilometres, using mean Earth radius
            6371.0088 km.

        Examples
        --------
        >>> station = StationMeta(71420, "Göteborg A", 57.7156, 11.9924)
        >>> station.distance_km(57.7156, 11.9924)
        0.0
        """
        r = 6371.0088
        p1, p2 = math.radians(self.latitude), math.radians(lat)
        dphi = math.radians(lat - self.latitude)
        dlmb = math.radians(lon - self.longitude)
        a = (
            math.sin(dphi / 2) ** 2
            + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
        )
        return 2 * r * math.asin(min(1.0, math.sqrt(a)))


# --------------------------------------------------------------------------- #
# Cached HTTP client
# --------------------------------------------------------------------------- #
class CachedClient:
    """Thin ``requests`` wrapper that caches raw payloads on disk.

    Caching makes recompilation repeatable and avoids redundant heavy queries
    against SMHI. Transient HTTP failures are retried with exponential
    backoff, cached entries can optionally expire, and writes use temporary
    sibling files followed by atomic replacement.

    Parameters
    ----------
    cache_dir
        Cache directory or ``None`` to disable disk caching.
    timeout
        Per-request timeout in seconds.
    session
        Optional preconfigured :class:`requests.Session`, useful for tests.
    max_retries
        Retry count for GET responses with status 429, 500, 502, 503, or 504.
    cache_ttl
        Maximum cache age in seconds, or ``None`` for no expiry.
    refresh
        Ignore cached responses when ``True``.

    Examples
    --------
    >>> client = CachedClient(cache_dir=".smhi_cache", cache_ttl=86400)
    >>> isinstance(client.session, requests.Session)
    True
    """

    def __init__(
        self,
        cache_dir: Optional[str] = None,
        timeout: float = 60.0,
        session: Optional[requests.Session] = None,
        max_retries: int = 4,
        cache_ttl: Optional[float] = None,
        refresh: bool = False,
    ) -> None:
        """Initialize HTTP retry, timeout, and cache policy.

        See the class-level documentation for parameter semantics. The cache
        directory is created eagerly so later worker threads only write files.
        """
        self.cache_dir = cache_dir
        self.timeout = timeout
        self.session = session or self._build_session(max_retries)
        self.cache_ttl = cache_ttl  # seconds; None = never expire
        self.refresh = refresh  # force re-fetch, ignore cached entries
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)

    @staticmethod
    def _build_session(max_retries: int) -> requests.Session:
        """Construct a GET-only retrying HTTP session.

        Parameters
        ----------
        max_retries
            Total retry budget. Values at or below zero disable adapters.

        Returns
        -------
        requests.Session
            Session with identical retry adapters for HTTP and HTTPS.
        """
        session = requests.Session()
        if Retry is not None and max_retries > 0:
            retry = Retry(
                total=max_retries,
                backoff_factor=0.5,
                status_forcelist=(429, 500, 502, 503, 504),
                allowed_methods=frozenset({"GET"}),
                raise_on_status=False,
            )
            adapter = HTTPAdapter(max_retries=retry)
            session.mount("https://", adapter)
            session.mount("http://", adapter)
        return session

    def _cache_path(self, url: str, suffix: str) -> Optional[str]:
        """Map a URL to a stable, filesystem-safe cache path.

        The first 24 hexadecimal SHA-256 characters avoid exposing query
        strings in filenames while making the same URL deterministic.
        ``None`` is returned when caching is disabled.
        """
        if not self.cache_dir:
            return None
        key = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
        return os.path.join(self.cache_dir, f"{key}.{suffix}")

    def _cache_valid(self, path: str) -> bool:
        """Return whether a cache file exists and satisfies refresh/TTL policy."""
        if self.refresh or not os.path.exists(path):
            return False
        if self.cache_ttl is None:
            return True
        return (time.time() - os.path.getmtime(path)) < self.cache_ttl

    def get_text(self, url: str, suffix: str = "txt") -> str:
        """Return a text response from cache or HTTP.

        Parameters
        ----------
        url
            Absolute SMHI endpoint URL.
        suffix
            Cache filename suffix identifying the payload representation.

        Returns
        -------
        str
            UTF-8 cached text or :attr:`requests.Response.text`.

        Raises
        ------
        IngestionError
            If all HTTP attempts fail.

        Notes
        -----
        Cache writes are atomic. Readers therefore observe either the previous
        complete payload or the new complete payload, never a partial write.
        """
        path = self._cache_path(url, suffix)
        if path and self._cache_valid(path):
            log.debug("cache hit: %s", url)
            with open(path, "r", encoding="utf-8") as fh:
                return fh.read()
        log.debug("GET %s", url)
        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
        except requests.RequestException as exc:  # pragma: no cover - network
            raise IngestionError(f"request failed: {url}: {exc}") from exc
        text = resp.text
        if path:
            tmp_path = None
            try:
                with tempfile.NamedTemporaryFile(
                    "w",
                    encoding="utf-8",
                    dir=os.path.dirname(path),
                    prefix=".smhi2epw-",
                    delete=False,
                ) as fh:
                    tmp_path = fh.name
                    fh.write(text)
                os.replace(tmp_path, path)
            finally:
                if tmp_path and os.path.exists(tmp_path):
                    os.unlink(tmp_path)
        return text

    def get_json(self, url: str) -> object:
        """Fetch and decode JSON, repairing one malformed cache entry.

        A cached payload that cannot be decoded is deleted and fetched once
        more. A second malformed response raises :class:`IngestionError`
        instead of entering an unbounded retry loop.
        """
        try:
            return json.loads(self.get_text(url, suffix="json"))
        except json.JSONDecodeError:
            # A process may have been interrupted while writing an older cache
            # entry. Remove it and retry the endpoint exactly once.
            path = self._cache_path(url, "json")
            if path and os.path.exists(path) and not self.refresh:
                try:
                    os.unlink(path)
                    return json.loads(self.get_text(url, suffix="json"))
                except (OSError, json.JSONDecodeError) as exc:
                    raise IngestionError(f"invalid JSON response: {url}") from exc
            raise IngestionError(f"invalid JSON response: {url}")


# --------------------------------------------------------------------------- #
# metobs station metadata
# --------------------------------------------------------------------------- #
def _select_position(positions: list, year: int) -> dict:
    """Pick the station position record valid during ``year``.

    Parameters
    ----------
    positions
        SMHI position records with millisecond ``from`` and ``to`` bounds.
    year
        Year whose July midpoint selects the historically valid location.

    Returns
    -------
    dict
        Matching position, or the most recent record as a documented fallback.

    Raises
    ------
    IngestionError
        If the station exposes no position records.
    """
    if not positions:
        raise IngestionError("no position metadata for station")
    mid_ms = int(datetime(year, 7, 1, tzinfo=timezone.utc).timestamp() * 1000)
    covering = [p for p in positions if p.get("from", 0) <= mid_ms <= p.get("to", 0)]
    if covering:
        return covering[0]
    return max(positions, key=lambda p: p.get("to", 0))


def _clean_station_name(title: object, station_id: int) -> str:
    """Extract a tidy station name from a metobs parameter-station title.

    Titles look like ``"Lufttemperatur - Göteborg A: Välj tidsutsnitt"``; the
    station name is the segment between the parameter prefix (" - ") and the
    trailing ": ..." instruction.

    Examples
    --------
    >>> _clean_station_name("Lufttemperatur - Göteborg A: Välj", 71420)
    'Göteborg A'
    >>> _clean_station_name(None, 71420)
    'Station 71420'
    """
    if not title:
        return f"Station {station_id}"
    text = str(title).strip()
    if " - " in text:
        text = text.split(" - ", 1)[1]
    if ":" in text:
        text = text.split(":", 1)[0]
    text = text.strip()
    return text or f"Station {station_id}"


def get_station_metadata(
    station_id: int, client: CachedClient, year: Optional[int] = None
) -> StationMeta:
    """Resolve a station's name, coordinates and elevation from metobs.

    Parameters
    ----------
    station_id
        SMHI MetObs station identifier.
    client
        Cache-aware transport used for the metadata request.
    year
        Optional historical year used to select the correct position record.

    Returns
    -------
    StationMeta
        Cleaned station identity and year-aware coordinates/elevation.

    Raises
    ------
    IngestionError
        If the payload shape or position metadata is unusable.

    Notes
    -----
    The SMHI ``key`` field is not assumed to be a WMO number. Missing genuine
    WMO metadata is represented by the EPW fallback ``"999999"``.
    """
    url = f"{C.METOBS_BASE}/parameter/1/station/{station_id}.json"
    payload = client.get_json(url)
    if not isinstance(payload, dict):
        raise IngestionError(f"unexpected station payload for {station_id}")

    positions = payload.get("position") or []
    if year is not None:
        pos = _select_position(positions, year)
    elif positions:
        pos = max(positions, key=lambda p: p.get("to", 0))
    else:
        raise IngestionError(f"no position metadata for station {station_id}")

    # The metobs station payload exposes the human-readable name as 'title'.
    raw_name = payload.get("name") or payload.get("title")
    name = _clean_station_name(raw_name, int(station_id))
    return StationMeta(
        station_id=int(station_id),
        name=name,
        latitude=float(pos["latitude"]),
        longitude=float(pos["longitude"]),
        elevation=float(pos.get("height", 0.0) or 0.0),
        # The MetObs ``key`` is an SMHI station ID, not a WMO identifier.
        wmo_id=str(payload.get("wmo") or "999999"),
    )


# --------------------------------------------------------------------------- #
# Nearest-station resolver
# --------------------------------------------------------------------------- #
def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return great-circle distance in kilometres between two coordinates.

    Examples
    --------
    >>> round(_haversine_km(57.7, 12.0, 59.3, 18.1))
    396
    """
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def _stations_for_parameter(
    param: int, client: CachedClient
) -> Dict[int, Tuple[float, float, int, int]]:
    """List stations exposing one MetObs parameter.

    Malformed individual entries are ignored so one bad metadata record does
    not make every station undiscoverable. A non-dictionary response yields an
    empty mapping for the caller to handle.
    """
    url = f"{C.METOBS_BASE}/parameter/{param}.json"
    payload = client.get_json(url)
    out: Dict[int, Tuple[float, float, int, int]] = {}
    if not isinstance(payload, dict):
        return out
    for st in payload.get("station", []):
        try:
            sid = int(st["key"])
            out[sid] = (
                float(st["latitude"]),
                float(st["longitude"]),
                int(st.get("from", 0)),
                int(st.get("to", 0)),
            )
        except (KeyError, TypeError, ValueError):
            continue
    return out


def _year_bounds_ms(year: int) -> Tuple[int, int]:
    """Return inclusive UTC millisecond bounds for a calendar year.

    Examples
    --------
    >>> start, end = _year_bounds_ms(2020)
    >>> end > start
    True
    """
    start = datetime(year, 1, 1, tzinfo=timezone.utc)
    end = datetime(year + 1, 1, 1, tzinfo=timezone.utc)
    return int(start.timestamp() * 1000), int(end.timestamp() * 1000) - 1


def _covers_year(record: Tuple[float, float, int, int], year: int) -> bool:
    """Return whether a station metadata record covers every instant of a year."""
    start_ms, end_ms = _year_bounds_ms(year)
    return record[2] <= start_ms and record[3] >= end_ms


def find_nearest_station(
    lat: float, lon: float, year: int, client: CachedClient
) -> StationMeta:
    """Find the nearest metobs station carrying all required parameters in ``year``.

    Parameters
    ----------
    lat, lon
        Requested point in decimal degrees.
    year
        Calendar year that every required parameter must fully cover.
    client
        Cache-aware metadata transport.

    Returns
    -------
    StationMeta
        Closest qualifying station with year-aware metadata.

    Raises
    ------
    IngestionError
        If station lists are unavailable or no station covers all required
        temperature, humidity, pressure, speed, and direction records.

    Notes
    -----
    No arbitrary candidate-count cutoff is applied: all stations are ranked
    and examined until a full-year match is found.
    """
    required = list(C.METOBS_REQUIRED_PARAMETERS)
    base = _stations_for_parameter(required[0], client)
    if not base:
        raise IngestionError("could not list metobs stations")

    other = {p: _stations_for_parameter(p, client) for p in required[1:]}

    ranked = sorted(
        base.items(), key=lambda kv: _haversine_km(lat, lon, kv[1][0], kv[1][1])
    )
    for sid, base_record in ranked:
        slat, slon, _, _ = base_record
        if not _covers_year(base_record, year):
            continue
        ok = True
        for p in required[1:]:
            rec = other.get(p, {}).get(sid)
            if rec is None or not _covers_year(rec, year):
                ok = False
                break
        if ok:
            log.info(
                "nearest station: %s @ %.4f,%.4f (%.1f km)",
                sid,
                slat,
                slon,
                _haversine_km(lat, lon, slat, slon),
            )
            return get_station_metadata(sid, client, year=year)

    raise IngestionError(
        f"no metobs station near {lat:.4f},{lon:.4f} covers all required "
        f"parameters for {year}"
    )


def find_nearest_radiation_station(
    lat: float, lon: float, year: int, client: CachedClient
) -> Optional[Tuple[int, float]]:
    """Return ``(station_id, distance_km)`` for the nearest Sol (pyranometer) station.

    Parameters
    ----------
    lat, lon
        Solar query point in decimal degrees.
    year
        Full year that measured GHI must cover.
    client
        Cache-aware metadata transport.

    Returns
    -------
    tuple of int and float or None
        Station ID and distance in kilometres, or ``None`` when automatic
        measured radiation is unavailable. Distance policy is applied later by
        :func:`smhi2epw.compiler.compile_epw`.
    """
    url = f"{C.METOBS_BASE}/parameter/{C.METOBS_RADIATION_PARAMETER}.json"
    try:
        payload = client.get_json(url)
    except Exception:  # pragma: no cover - network
        return None
    if not isinstance(payload, dict):
        return None
    start_ms, end_ms = _year_bounds_ms(year)
    candidates = [
        s
        for s in payload.get("station", [])
        if s.get("from", 0) <= start_ms and s.get("to", 0) >= end_ms
    ]
    if not candidates:
        return None
    nearest = min(
        candidates,
        key=lambda s: _haversine_km(
            lat, lon, float(s["latitude"]), float(s["longitude"])
        ),
    )
    dist = _haversine_km(
        lat, lon, float(nearest["latitude"]), float(nearest["longitude"])
    )
    log.info(
        "nearest radiation station: %s (%s) @ %.1f km",
        nearest["key"],
        nearest.get("name", "?"),
        dist,
    )
    return int(nearest["key"]), dist


def radiation_station_distance(
    station_id: int, lat: float, lon: float, year: int, client: CachedClient
) -> Optional[float]:
    """Return distance to a full-year explicit radiation station.

    ``None`` means the station is absent from parameter 11 metadata or fails to
    cover the full requested year; the compiler treats that as a hard error for
    an explicitly requested station.
    """
    stations = _stations_for_parameter(C.METOBS_RADIATION_PARAMETER, client)
    record = stations.get(station_id)
    if record is None or not _covers_year(record, year):
        return None
    return _haversine_km(lat, lon, record[0], record[1])


# --------------------------------------------------------------------------- #
# metobs observation parsing
# --------------------------------------------------------------------------- #
def _parse_metobs_csv(
    text: str,
    column: str,
    window: Tuple[pd.Timestamp, pd.Timestamp],
    accepted_quality: Optional[set] = None,
) -> pd.Series:
    """Parse a corrected-archive CSV into a UTC-indexed series.

    Parameters
    ----------
    text
        Corrected-archive semicolon-delimited response, including preamble.
    column
        Canonical output series name.
    window
        Inclusive UTC start/end timestamps retained from the response.
    accepted_quality
        Accepted SMHI quality codes; defaults to ``{"G", "Y"}``.

    Returns
    -------
    pandas.Series
        Sorted, duplicate-free, timezone-aware observations. Rejected quality
        values remain ``NaN`` so processing diagnostics see the gap.

    Raises
    ------
    IngestionError
        If no data header or value column can be identified.

    Notes
    -----
    Decimal commas are accepted. Duplicate timestamps keep the final published
    value, matching corrected-archive semantics.
    """
    if accepted_quality is None:
        accepted_quality = C.METOBS_ACCEPTED_QUALITY

    lines = text.splitlines()
    header_idx = None
    for i, line in enumerate(lines):
        first = line.split(";", 1)[0].strip().lower()
        if first in ("datum", "from", "från"):
            header_idx = i
            break
    if header_idx is None:
        raise IngestionError(f"could not locate data header for '{column}'")

    block = "\n".join(lines[header_idx:])
    df = pd.read_csv(io.StringIO(block), sep=";", dtype=str, engine="python")
    df.columns = [c.strip() for c in df.columns]

    date_col = df.columns[0]
    time_col = df.columns[1] if len(df.columns) > 1 else None
    value_col = df.columns[2] if len(df.columns) > 2 else None
    if value_col is None:
        raise IngestionError(f"unexpected metobs layout for '{column}'")

    ts_text = df[date_col].str.strip()
    if time_col is not None and df[time_col].notna().any():
        ts_text = ts_text + " " + df[time_col].str.strip()
    ts = pd.to_datetime(ts_text, utc=True, errors="coerce")

    values = pd.to_numeric(
        df[value_col].str.replace(",", ".", regex=False), errors="coerce"
    )

    # Honor the quality column ('Kvalitet'), typically immediately after value.
    quality_col = None
    for cand in df.columns[3:]:
        if cand.strip().lower().startswith("kvalit"):
            quality_col = cand
            break
    if quality_col is None and len(df.columns) > 3:
        quality_col = df.columns[3]
    if quality_col is not None:
        flags = df[quality_col].astype(str).str.strip().str.upper()
        values = values.where(flags.isin({q.upper() for q in accepted_quality}))

    series = pd.Series(values.to_numpy(), index=ts, name=column)
    series = series[series.index.notna()]
    start, end = window
    series = series[(series.index >= start) & (series.index <= end)]
    series = series[~series.index.duplicated(keep="last")].sort_index()
    return series


def fetch_metobs_parameter(
    station_id: int,
    param: int,
    column: str,
    window: Tuple[pd.Timestamp, pd.Timestamp],
    client: CachedClient,
    accepted_quality: Optional[set] = None,
) -> pd.Series:
    """Fetch one station parameter from the corrected MetObs archive.

    Parameters mirror :func:`_parse_metobs_csv`; ``param`` and ``station_id``
    form the endpoint URL. The returned series is hourly UTC where supplied by
    SMHI, but final resampling and grid alignment occur in :func:`ingest`.
    """
    url = (
        f"{C.METOBS_BASE}/parameter/{param}/station/{station_id}"
        f"/period/{C.METOBS_PERIOD}/data.csv"
    )
    text = client.get_text(url, suffix="csv")
    return _parse_metobs_csv(text, column, window, accepted_quality)


# --------------------------------------------------------------------------- #
# STRÅNG solar parsing
# --------------------------------------------------------------------------- #
def fetch_strang_parameter(
    lat: float,
    lon: float,
    param: int,
    column: str,
    window: Tuple[pd.Timestamp, pd.Timestamp],
    client: CachedClient,
) -> pd.Series:
    """Fetch one STRÅNG irradiance parameter for a point and UTC window.

    Parameters
    ----------
    lat, lon
        Requested solar coordinates in decimal degrees.
    param
        STRÅNG parameter ID, such as 117 for GHI.
    column
        Canonical series name.
    window
        Inclusive UTC start and end timestamps.
    client
        Cache-aware JSON transport.

    Returns
    -------
    pandas.Series
        Sorted UTC irradiance values in W/m². STRÅNG's ``-999`` sentinel is
        converted to ``NaN``.

    Raises
    ------
    IngestionError
        If the endpoint does not return the expected list payload.
    """
    start_ts, end_ts = window
    start = start_ts.strftime("%Y-%m-%dT%H:%M:%S")
    end = end_ts.strftime("%Y-%m-%dT%H:%M:%S")
    url = (
        f"{C.STRANG_BASE}/geotype/point/lon/{lon:.6f}/lat/{lat:.6f}"
        f"/parameter/{param}/data.json?from={start}&to={end}&interval=hourly"
    )
    payload = client.get_json(url)
    if not isinstance(payload, list):
        raise IngestionError(f"unexpected STRÅNG payload for parameter {param}")

    records = [(r["date_time"], r.get("value")) for r in payload if "date_time" in r]
    if not records:
        return pd.Series(dtype=float, name=column)

    times = pd.to_datetime([r[0] for r in records], utc=True, errors="coerce")
    values = pd.to_numeric([r[1] for r in records], errors="coerce")
    series = pd.Series(values, index=times, name=column)
    # STRÅNG encodes missing values as -999; treat them as gaps to be imputed.
    series = series.where(series > -990.0)
    series = series[series.index.notna()]
    series = series[(series.index >= start_ts) & (series.index <= end_ts)]
    series = series[~series.index.duplicated(keep="last")].sort_index()
    return series


# --------------------------------------------------------------------------- #
# Multi-threaded dual-endpoint query manager
# --------------------------------------------------------------------------- #
def ingest(
    meta: StationMeta,
    year: int,
    client: CachedClient,
    max_workers: int = 8,
    utc_offset: float = 0.0,
    accepted_quality: Optional[set] = None,
    radiation_station_id: Optional[int] = None,
    solar_latitude: Optional[float] = None,
    solar_longitude: Optional[float] = None,
    radiation_required: bool = False,
) -> pd.DataFrame:
    """Query both endpoints in parallel and return a UTC-indexed DataFrame.

    Parameters
    ----------
    meta
        Station supplying required meteorological observations.
    year
        Actual meteorological year.
    client
        Cache-aware SMHI transport.
    max_workers
        Maximum concurrent parameter requests.
    utc_offset
        Whole-hour LST offset used only to size the year-boundary buffer.
    accepted_quality
        Optional override for usable MetObs quality flags.
    radiation_station_id
        Optional Sol station supplying measured GHI.
    solar_latitude, solar_longitude
        Requested STRÅNG point; station coordinates are fallbacks when absent.
    radiation_required
        Make measured-GHI failure fatal for an explicit radiation station.

    Returns
    -------
    pandas.DataFrame
        Continuous hourly UTC frame spanning the year plus boundary buffer.

    Raises
    ------
    IngestionError
        If a required source request or payload fails.

    Notes
    -----
    Requests run concurrently but columns are assembled in deterministic
    canonical order. Optional cloud and automatically selected GHI failures are
    represented as missing columns. STRÅNG point values are instantaneous at
    the full hour, so adjacent samples are averaged to represent the preceding
    EPW interval.

    Before 2018 only full-year GHI is requested because direct parameters begin
    partway through 2017; downstream processing uses Erbs decomposition.
    """
    buffer_hours = int(math.ceil(abs(utc_offset))) + 1
    grid_start = datetime(year, 1, 1, tzinfo=timezone.utc)
    grid_end = datetime(year, 12, 31, 23, 0, 0, tzinfo=timezone.utc)
    win_start = pd.Timestamp(grid_start) - pd.Timedelta(hours=buffer_hours)
    win_end = pd.Timestamp(grid_end) + pd.Timedelta(hours=buffer_hours)
    window = (win_start, win_end)

    solar_lat = meta.latitude if solar_latitude is None else solar_latitude
    solar_lon = meta.longitude if solar_longitude is None else solar_longitude

    # Direct/beam STRÅNG params (118, 121) are only available from Apr 18 2017,
    # so 2018 is the first complete AMY that can use them.
    if year < C.STRANG_DIRECT_AVAILABLE_YEAR:
        log.warning(
            "year %d pre-dates STRÅNG direct/beam parameters (available from "
            "Apr 2017); DNI and DHI will be estimated via Erbs decomposition "
            "on STRÅNG GHI only",
            year,
        )
    strang_params = (
        C.STRANG_PARAMETERS
        if year >= C.STRANG_DIRECT_AVAILABLE_YEAR
        else C.STRANG_GHI_ONLY_PARAMETERS
    )

    tasks = {}
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        for param, column in C.METOBS_PARAMETERS.items():
            tasks[
                pool.submit(
                    fetch_metobs_parameter,
                    meta.station_id,
                    param,
                    column,
                    window,
                    client,
                    accepted_quality,
                )
            ] = (column, param in C.METOBS_REQUIRED_PARAMETERS)
        # Optionally fetch measured GHI from a dedicated Sol (pyranometer) station.
        if radiation_station_id is not None:
            tasks[
                pool.submit(
                    fetch_metobs_parameter,
                    radiation_station_id,
                    C.METOBS_RADIATION_PARAMETER,
                    C.METOBS_RADIATION_COLUMN,
                    window,
                    client,
                    accepted_quality,
                )
            ] = (C.METOBS_RADIATION_COLUMN, radiation_required)
        for param, column in strang_params.items():
            tasks[
                pool.submit(
                    fetch_strang_parameter,
                    solar_lat,
                    solar_lon,
                    param,
                    column,
                    window,
                    client,
                )
            ] = (column, True)

        collected: Dict[str, pd.Series] = {}
        for future in as_completed(tasks):
            column, required = tasks[future]
            try:
                collected[column] = future.result()
            except Exception as exc:
                if required:
                    raise
                log.warning("optional source '%s' unavailable: %s", column, exc)
                collected[column] = pd.Series(dtype=float, name=column)

    # Continuous hourly UTC grid spanning the year plus the boundary buffer.
    grid = pd.date_range(start=win_start, end=win_end, freq="h", tz="UTC")

    frame = pd.DataFrame(index=grid)
    ordered = (
        list(C.METOBS_PARAMETERS.values())
        + ([C.METOBS_RADIATION_COLUMN] if radiation_station_id is not None else [])
        + list(strang_params.values())
    )
    for column in ordered:
        series = collected.get(column, pd.Series(dtype=float, name=column))
        if not series.empty:
            series = series.resample("h").mean()
        frame[column] = series.reindex(grid)

    # STRÅNG values are instantaneous at the full hour; EPW expects the mean
    # over the *preceding* hour.  Average adjacent samples: EPW[t] = (t-1 + t) / 2.
    for col in C.STRANG_PARAMETERS.values():
        if col in frame.columns:
            frame[col] = (frame[col] + frame[col].shift(1)) / 2

    return frame
