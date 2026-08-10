"""High-level compiler orchestrating ingestion, processing and export."""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Optional

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
    radiation_station_distance,
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
    # Optional Sol (pyranometer) station for measured GHI. None permits
    # auto-discovery when radiation_station_auto is enabled.
    radiation_station_id: Optional[int] = None
    radiation_station_auto: bool = True
    radiation_station_max_distance_km: Optional[float] = 50.0


@dataclass
class CompileResult:
    """Summary returned by :func:`compile_epw`."""

    output_path: str
    rows: int
    station: StationMeta
    interpolated_fraction: float
    coordinate_distance_km: float
    report: processing.ProcessingReport
    radiation_station_id: Optional[int] = None
    radiation_station_distance_km: Optional[float] = None


def _validate_config(config: EPWConfig) -> None:
    """Reject invalid or unsupported configuration before network access."""
    if not isinstance(config.year, int) or isinstance(config.year, bool):
        raise IngestionError("year must be an integer")
    if config.year < C.STRANG_MIN_YEAR:
        raise IngestionError(
            f"STRÅNG solar data is only available from {C.STRANG_MIN_YEAR}; "
            f"requested year {config.year} is out of range"
        )
    if config.station_id is not None and config.station_id <= 0:
        raise IngestionError("station id must be positive")
    if config.radiation_station_id is not None and config.radiation_station_id <= 0:
        raise IngestionError("radiation station id must be positive")
    if config.max_workers <= 0:
        raise IngestionError("max_workers must be positive")
    if config.cache_ttl is not None and config.cache_ttl < 0:
        raise IngestionError("cache_ttl must be nonnegative")
    if (
        config.radiation_station_max_distance_km is not None
        and config.radiation_station_max_distance_km < 0
    ):
        raise IngestionError("radiation station maximum distance must be nonnegative")

    has_lat = config.latitude is not None
    has_lon = config.longitude is not None
    if has_lat != has_lon:
        raise IngestionError("latitude and longitude must be provided together")
    if not has_lat and config.station_id is None:
        raise IngestionError(
            "either a station id or both latitude and longitude must be provided"
        )
    if has_lat:
        assert config.latitude is not None and config.longitude is not None
        if not math.isfinite(config.latitude) or not -90.0 <= config.latitude <= 90.0:
            raise IngestionError("latitude must be finite and between -90 and 90")
        if (
            not math.isfinite(config.longitude)
            or not -180.0 <= config.longitude <= 180.0
        ):
            raise IngestionError("longitude must be finite and between -180 and 180")
    if not math.isfinite(config.utc_offset) or not -12.0 <= config.utc_offset <= 14.0:
        raise IngestionError("utc_offset must be finite and between -12 and 14 hours")
    if not float(config.utc_offset).is_integer():
        raise IngestionError(
            "fractional UTC offsets are not supported; use a whole-hour Local Standard Time offset"
        )


def _configure_logging() -> None:
    if not logging.getLogger("smhi2epw").handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("[smhi2epw] %(message)s"))
        log.addHandler(handler)
        log.setLevel(logging.INFO)


def compile_epw(
    config: EPWConfig, client: Optional[CachedClient] = None
) -> CompileResult:
    """Fetch, process and write an EPW file as described by ``config``.

    Returns a :class:`CompileResult` with validation diagnostics. A summary is
    also emitted to the ``smhi2epw`` logger.
    """
    _configure_logging()
    _validate_config(config)

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
    else:  # guarded by _validate_config
        raise AssertionError("unreachable station configuration")

    if config.latitude is not None and config.longitude is not None:
        request_lat, request_lon = config.latitude, config.longitude
    else:
        request_lat, request_lon = meta.latitude, meta.longitude
    distance = meta.distance_km(request_lat, request_lon)

    # STRÅNG is optimised for Sweden; accuracy degrades outside it (Lundström 2012 §3.1.1).
    _SE_LAT = (55.0, 69.5)
    _SE_LON = (10.0, 24.5)
    if not (
        _SE_LAT[0] <= request_lat <= _SE_LAT[1]
        and _SE_LON[0] <= request_lon <= _SE_LON[1]
    ):
        log.warning(
            "solar query point (%.4f, %.4f) is outside Sweden; STRÅNG accuracy "
            "may be significantly reduced (hourly GHI RMSD up to 30-40%% for "
            "coastal/Atlantic/high-altitude/Baltic locations)",
            request_lat,
            request_lon,
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

    # 2. Resolve a radiation (Sol) station for measured GHI.
    rad_station_id: Optional[int] = config.radiation_station_id
    rad_dist: Optional[float] = None
    radiation_required = rad_station_id is not None
    if rad_station_id is None and config.radiation_station_auto:
        result = find_nearest_radiation_station(
            request_lat, request_lon, config.year, client
        )
        if result is not None:
            rad_station_id, rad_dist = result
            max_distance = config.radiation_station_max_distance_km
            if max_distance is not None and rad_dist > max_distance:
                log.info(
                    "nearest radiation station %s is %.1f km away (limit %.1f km); "
                    "using STRÅNG solar",
                    rad_station_id,
                    rad_dist,
                    max_distance,
                )
                rad_station_id = None
                rad_dist = None
            else:
                log.info(
                    "radiation station %s selected (%.1f km); "
                    "will use measured GHI + STRÅNG partitioning",
                    rad_station_id,
                    rad_dist,
                )
        else:
            log.info("no Sol radiation station found; falling back to STRÅNG solar")
    elif rad_station_id is not None:
        rad_dist = radiation_station_distance(
            rad_station_id, request_lat, request_lon, config.year, client
        )
        if rad_dist is None:
            raise IngestionError(
                f"configured radiation station {rad_station_id} does not cover {config.year}"
            )
        log.info(
            "using configured radiation station %s (%.1f km)",
            rad_station_id,
            rad_dist,
        )

    # 3. Ingest both endpoints (multi-threaded) onto a continuous UTC grid.
    frame = ingest(
        meta,
        config.year,
        client,
        max_workers=config.max_workers,
        utc_offset=config.utc_offset,
        radiation_station_id=rad_station_id,
        solar_latitude=request_lat,
        solar_longitude=request_lon,
        radiation_required=radiation_required,
    )
    log.info("ingested %d UTC hours for %d", len(frame), config.year)

    # 4. Process: impute, convert, derive dew point / IR / DNI.
    report = processing.process(
        frame,
        request_lat,
        request_lon,
        measured_required=radiation_required,
    )
    log.info(
        "interpolated %.3f%% of observation samples",
        report.total_interpolated_fraction * 100.0,
    )
    if report.missing_columns:
        log.warning(
            "optional columns missing/sparse: %s", ", ".join(report.missing_columns)
        )
    log.info(
        "solar source: %s; observed cloud data %s; clamped %d DNI hours; "
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
        latitude=request_lat,
        longitude=request_lon,
        time_zone=config.utc_offset,
        elevation=meta.elevation,
        year=config.year,
        station_id=meta.station_id,
    )
    rows = export.write_epw(config.output_path, header, lst_frame, config.year)
    log.info("wrote %d rows -> %s (validated)", rows, config.output_path)

    strang_res = next(
        label for cutoff, label in C.STRANG_RESOLUTION_BY_YEAR if config.year >= cutoff
    )
    log.info("STRÅNG spatial resolution for %d: %s", config.year, strang_res)

    return CompileResult(
        output_path=config.output_path,
        rows=rows,
        station=meta,
        interpolated_fraction=report.total_interpolated_fraction,
        coordinate_distance_km=distance,
        report=report,
        radiation_station_id=rad_station_id,
        radiation_station_distance_km=rad_dist,
    )
