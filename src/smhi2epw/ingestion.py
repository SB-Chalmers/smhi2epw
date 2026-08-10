"""Hybrid SMHI ingestion layer (metobs + STRÅNG) with local caching.

Provides a multi-threaded query manager that fetches station observations and
grid-modeled solar irradiance, returning UTC-indexed hourly ``pandas`` series.
"""

from __future__ import annotations

import hashlib
import io
import json
import logging
import math
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests
from requests.adapters import HTTPAdapter

try:  # urllib3 ships with requests; import defensively.
    from urllib3.util.retry import Retry
except Exception:  # pragma: no cover
    Retry = None

from . import constants as C
from .errors import IngestionError

log = logging.getLogger("smhi2epw")


# --------------------------------------------------------------------------- #
# Metadata container
# --------------------------------------------------------------------------- #
@dataclass
class StationMeta:
    """Geographic and identifying metadata for a metobs station."""

    station_id: int
    name: str
    latitude: float
    longitude: float
    elevation: float = 0.0
    wmo_id: str = "999999"

    def distance_km(self, lat: float, lon: float) -> float:
        """Great-circle distance (km) from the station to ``(lat, lon)``."""
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

    Caching makes recompilation idempotent and avoids redundant heavy queries
    against the SMHI open-data endpoints. Transient HTTP failures are retried
    with exponential backoff, and cached entries can optionally expire.
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
        self.cache_dir = cache_dir
        self.timeout = timeout
        self.session = session or self._build_session(max_retries)
        self.cache_ttl = cache_ttl  # seconds; None = never expire
        self.refresh = refresh       # force re-fetch, ignore cached entries
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)

    @staticmethod
    def _build_session(max_retries: int) -> requests.Session:
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
        if not self.cache_dir:
            return None
        key = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
        return os.path.join(self.cache_dir, f"{key}.{suffix}")

    def _cache_valid(self, path: str) -> bool:
        if self.refresh or not os.path.exists(path):
            return False
        if self.cache_ttl is None:
            return True
        return (time.time() - os.path.getmtime(path)) < self.cache_ttl

    def get_text(self, url: str, suffix: str = "txt") -> str:
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
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(text)
        return text

    def get_json(self, url: str) -> object:
        return json.loads(self.get_text(url, suffix="json"))


# --------------------------------------------------------------------------- #
# metobs station metadata
# --------------------------------------------------------------------------- #
def _select_position(positions: list, year: int) -> dict:
    """Pick the station position record valid during ``year``.

    Falls back to the most recent record if none of the intervals cover the
    requested year (e.g. for very old or future years).
    """
    if not positions:
        raise IngestionError("no position metadata for station")
    mid_ms = int(datetime(year, 7, 1, tzinfo=timezone.utc).timestamp() * 1000)
    covering = [
        p for p in positions
        if p.get("from", 0) <= mid_ms <= p.get("to", 0)
    ]
    if covering:
        return covering[0]
    return max(positions, key=lambda p: p.get("to", 0))


def _clean_station_name(title: object, station_id: int) -> str:
    """Extract a tidy station name from a metobs parameter-station title.

    Titles look like ``"Lufttemperatur - Göteborg A: Välj tidsutsnitt"``; the
    station name is the segment between the parameter prefix (" - ") and the
    trailing ": ..." instruction.
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

    When ``year`` is given, the position/elevation valid for that year is used;
    otherwise the most recent position is selected.
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
        wmo_id=str(payload.get("key", station_id)),
    )


# --------------------------------------------------------------------------- #
# Nearest-station resolver
# --------------------------------------------------------------------------- #
def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0088
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def _stations_for_parameter(param: int, client: CachedClient) -> Dict[int, Tuple[float, float, int, int]]:
    """Return ``{station_id: (lat, lon, from_ms, to_ms)}`` for a parameter."""
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


def find_nearest_station(
    lat: float, lon: float, year: int, client: CachedClient, max_candidates: int = 25
) -> StationMeta:
    """Find the nearest metobs station carrying all required parameters in ``year``.

    Stations are ranked by great-circle distance to ``(lat, lon)``; the closest
    one whose record covers ``year`` for every required parameter is returned.
    """
    required = list(C.METOBS_REQUIRED_PARAMETERS)
    base = _stations_for_parameter(required[0], client)
    if not base:
        raise IngestionError("could not list metobs stations")

    year_ms = int(datetime(year, 7, 1, tzinfo=timezone.utc).timestamp() * 1000)
    other = {p: _stations_for_parameter(p, client) for p in required[1:]}

    ranked = sorted(
        base.items(), key=lambda kv: _haversine_km(lat, lon, kv[1][0], kv[1][1])
    )
    for sid, (slat, slon, sfrom, sto) in ranked[:max_candidates]:
        if not (sfrom <= year_ms <= sto):
            continue
        ok = True
        for p in required[1:]:
            rec = other.get(p, {}).get(sid)
            if rec is None or not (rec[2] <= year_ms <= rec[3]):
                ok = False
                break
        if ok:
            log.info(
                "nearest station: %s @ %.4f,%.4f (%.1f km)",
                sid, slat, slon, _haversine_km(lat, lon, slat, slon),
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

    Returns ``None`` when no station covers ``year`` or the parameter list is
    unavailable (network failure, empty response, etc.).
    """
    url = f"{C.METOBS_BASE}/parameter/{C.METOBS_RADIATION_PARAMETER}.json"
    try:
        payload = client.get_json(url)
    except Exception:  # pragma: no cover - network
        return None
    if not isinstance(payload, dict):
        return None
    year_ms = int(datetime(year, 7, 1, tzinfo=timezone.utc).timestamp() * 1000)
    candidates = [
        s for s in payload.get("station", [])
        if s.get("from", 0) <= year_ms <= s.get("to", 0)
    ]
    if not candidates:
        return None
    nearest = min(
        candidates,
        key=lambda s: _haversine_km(lat, lon, float(s["latitude"]), float(s["longitude"])),
    )
    dist = _haversine_km(lat, lon, float(nearest["latitude"]), float(nearest["longitude"]))
    log.info(
        "nearest radiation station: %s (%s) @ %.1f km",
        nearest["key"], nearest.get("name", "?"), dist,
    )
    return int(nearest["key"]), dist


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

    Values whose quality flag is not in ``accepted_quality`` are dropped (set
    to NaN downstream) so they can be interpolated. Rows are restricted to the
    half-open ``[start, end]`` UTC window.
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
    """Fetch and parse a single metobs parameter for one station."""
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
    """Fetch a single STRÅNG parameter for one point/window as a UTC series."""
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
) -> pd.DataFrame:
    """Query both endpoints in parallel and return a UTC-indexed DataFrame.

    When ``radiation_station_id`` is given, MetObs parameter 11 (measured global
    radiation from a pyranometer "Sol" station) is fetched alongside the other
    parameters and stored as column ``ghi_measured``. The processing layer will
    then prefer Erbs decomposition over the STRÅNG modelled solar fields.
    """
    buffer_hours = int(math.ceil(abs(utc_offset))) + 1
    grid_start = datetime(year, 1, 1, tzinfo=timezone.utc)
    grid_end = datetime(year, 12, 31, 23, 0, 0, tzinfo=timezone.utc)
    win_start = pd.Timestamp(grid_start) - pd.Timedelta(hours=buffer_hours)
    win_end = pd.Timestamp(grid_end) + pd.Timedelta(hours=buffer_hours)
    window = (win_start, win_end)

    # Direct/beam STRÅNG params (118, 121) are only available from Apr 18 2017.
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
            tasks[pool.submit(
                fetch_metobs_parameter,
                meta.station_id, param, column, window, client, accepted_quality,
            )] = column
        # Optionally fetch measured GHI from a dedicated Sol (pyranometer) station.
        if radiation_station_id is not None:
            tasks[pool.submit(
                fetch_metobs_parameter,
                radiation_station_id,
                C.METOBS_RADIATION_PARAMETER,
                C.METOBS_RADIATION_COLUMN,
                window,
                client,
                accepted_quality,
            )] = C.METOBS_RADIATION_COLUMN
        for param, column in strang_params.items():
            tasks[pool.submit(
                fetch_strang_parameter,
                meta.latitude,
                meta.longitude,
                param,
                column,
                window,
                client,
            )] = column

        collected: Dict[str, pd.Series] = {}
        for future in as_completed(tasks):
            column = tasks[future]
            collected[column] = future.result()

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
