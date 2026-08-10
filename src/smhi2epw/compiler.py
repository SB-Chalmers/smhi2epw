"""High-level compiler orchestrating ingestion, processing and export."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

import pandas as pd

from . import constants as C
from . import export, processing
from .errors import IngestionError
from .ingestion import (
    CachedClient,
    StationMeta,
    find_nearest_radiation_station,
    find_nearest_station,
    get_station_metadata,
    ingest,
)

log = logging.getLogger("smhi2epw")


@dataclass
class EPWConfig:
    """Configuration for an EPW compilation run."""

    year: int
    output_path: str
    station_id: Optional[int] = None
    city: str = "Unknown"
    region: str = "SE"
    country: str = "SWE"
    utc_offset: float = 1.0  # Local Standard Time offset (DST ignored).
    cache_dir: Optional[str] = ".smhi_cache"
    max_workers: int = 8
    # Optional explicit coordinates; used to resolve the nearest station when
    # no station id is given, and as the STRÅNG solar query point.
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    refresh: bool = False
    cache_ttl: Optional[float] = None
    # Optional Sol (pyranometer) station for measured GHI + Erbs decomposition.
    # Set to False to force STRÅNG-only solar; None triggers auto-discovery.
    radiation_station_id: Optional[int] = None
    radiation_station_auto: bool = True


@dataclass
class CompileResult:
    """Summary returned by :func:`compile_epw`."""

    output_path: str
    rows: int
    station: StationMeta
    interpolated_fraction: float
    coordinate_distance_km: float
    report: processing.ProcessingReport = field(default=None)


def _configure_logging() -> None:
    if not logging.getLogger("smhi2epw").handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("[smhi2epw] %(message)s"))
        log.addHandler(handler)
        log.setLevel(logging.INFO)


def compile_epw(config: EPWConfig, client: Optional[CachedClient] = None) -> CompileResult:
    """Fetch, process and write an EPW file as described by ``config``.

    Returns a :class:`CompileResult` with validation diagnostics. A summary is
    also emitted to the ``smhi2epw`` logger.
    """
    _configure_logging()

    if config.year < C.STRANG_MIN_YEAR:
        raise IngestionError(
            f"STRÅNG solar data is only available from {C.STRANG_MIN_YEAR}; "
            f"requested year {config.year} is out of range"
        )

    client = client or CachedClient(
        cache_dir=config.cache_dir,
        refresh=config.refresh,
        cache_ttl=config.cache_ttl,
    )

    # 1. Resolve station metadata / coordinates.
    if config.station_id is not None:
        meta = get_station_metadata(config.station_id, client, year=config.year)
    elif config.latitude is not None and config.longitude is not None:
        meta = find_nearest_station(
            config.latitude, config.longitude, config.year, client
        )
    else:
        raise IngestionError(
            "either a station id or both latitude and longitude must be provided"
        )

    if config.latitude is not None and config.longitude is not None:
        request_lat, request_lon = config.latitude, config.longitude
    else:
        request_lat, request_lon = meta.latitude, meta.longitude
    distance = meta.distance_km(request_lat, request_lon)

    # STRÅNG is optimised for Sweden; accuracy degrades outside it (Lundström 2012 §3.1.1).
    _SE_LAT = (55.0, 69.5)
    _SE_LON = (10.0, 24.5)
    if not (_SE_LAT[0] <= request_lat <= _SE_LAT[1] and _SE_LON[0] <= request_lon <= _SE_LON[1]):
        log.warning(
            "solar query point (%.4f, %.4f) is outside Sweden; STRÅNG accuracy "
            "may be significantly reduced (hourly GHI RMSD up to 30-40%% for "
            "coastal/Atlantic/high-altitude/Baltic locations)",
            request_lat, request_lon,
        )

    log.info(
        "station %s (%s) @ %.4f,%.4f; solar query point %.4f,%.4f (%.2f km)",
        meta.station_id,
        meta.name,
        meta.latitude,
        meta.longitude,
        request_lat,
        request_lon,
        distance,
    )

    # 2. Resolve radiation (Sol) station for measured GHI + Erbs decomposition.
    rad_station_id: Optional[int] = config.radiation_station_id
    if rad_station_id is None and config.radiation_station_auto:
        result = find_nearest_radiation_station(
            request_lat, request_lon, config.year, client
        )
        if result is not None:
            rad_station_id, rad_dist = result
            log.info(
                "radiation station %s selected (%.1f km); "
                "will use measured GHI + STRÅNG beam decomposition",
                rad_station_id, rad_dist,
            )
        else:
            log.info("no Sol radiation station found; falling back to STRÅNG solar")
    elif rad_station_id is not None:
        log.info("using configured radiation station %s", rad_station_id)

    # 3. Ingest both endpoints (multi-threaded) onto a continuous UTC grid.
    frame = ingest(
        meta,
        config.year,
        client,
        max_workers=config.max_workers,
        utc_offset=config.utc_offset,
        radiation_station_id=rad_station_id,
    )
    log.info("ingested %d UTC hours for %d", len(frame), config.year)

    # 4. Process: impute, convert, derive dew point / IR / DNI.
    report = processing.process(frame, request_lat, request_lon)
    log.info(
        "interpolated %.3f%% of observation samples",
        report.total_interpolated_fraction * 100.0,
    )
    if report.missing_columns:
        log.warning("optional columns missing/sparse: %s", ", ".join(report.missing_columns))
    log.info(
        "solar source: %s; cloud data %s; clamped %d sub-horizon DNI hours; "
        "max solar energy-balance residual %.1f W/m^2",
        report.solar_source,
        "available" if report.cloud_available else "unavailable",
        report.clamped_dni_hours,
        report.energy_balance_max_residual,
    )

    # 5. Shift UTC -> LST and write the EPW.
    lst_frame = export.shift_to_lst(frame, config.year, config.utc_offset)
    header = export.build_header(
        city=config.city,
        region=config.region,
        country=config.country,
        wmo_id=meta.wmo_id,
        latitude=meta.latitude,
        longitude=meta.longitude,
        time_zone=config.utc_offset,
        elevation=meta.elevation,
    )
    rows = export.write_epw(config.output_path, header, lst_frame, config.year)
    log.info("wrote %d rows -> %s (validated)", rows, config.output_path)

    return CompileResult(
        output_path=config.output_path,
        rows=rows,
        station=meta,
        interpolated_fraction=report.total_interpolated_fraction,
        coordinate_distance_km=distance,
        report=report,
    )
