"""Orchestrate station discovery, ingestion, processing, and EPW export.

Most users interact with :func:`compile_epw` and :class:`EPWConfig` rather
than calling the lower-level modules directly.  The compiler deliberately
validates all local configuration before making a network request, resolves
the meteorological and optional radiation stations, asks :mod:`processing` to
derive the weather fields, and delegates the final atomic write to
:mod:`export`.
"""

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
    """Describe one Actual Meteorological Year compilation.

    Attributes
    ----------
    year
        Calendar year to compile. STRÅNG coverage begins in 1999.
    output_path
        Destination EPW path. Its parent directory must already exist.
    station_id
        Explicit SMHI MetObs station identifier. If omitted, ``latitude`` and
        ``longitude`` are used to locate the nearest station that covers the
        full year for every required parameter.
    city, region, country
        Human-readable EPW location fields. They must not contain commas or
        newlines; ``country`` is normally an ISO-style code such as ``"SWE"``.
    utc_offset
        Whole-hour offset from UTC to Local Standard Time. Daylight saving is
        intentionally ignored. Nordic locations normally use ``1.0``.
    cache_dir
        Directory for raw API responses, or ``None`` to disable caching.
    max_workers
        Positive number of concurrent parameter requests.
    latitude, longitude
        Optional requested coordinates in decimal degrees. When supplied,
        they control the STRÅNG query, solar geometry, and EPW location even
        if an explicit meteorological station is used.
    refresh
        Ignore otherwise valid cached responses when ``True``.
    cache_ttl
        Maximum cache age in seconds, or ``None`` for no age limit.
    radiation_station_id
        Explicit SMHI Sol station for measured GHI. Unlike automatic
        selection, an unusable explicit station causes compilation to fail.
    radiation_station_auto
        Discover a nearby full-year Sol station when no explicit ID is given.
    radiation_station_max_distance_km
        Maximum automatic Sol-station distance in kilometres. ``None``
        disables the radius; the default is 50 km.

    Examples
    --------
    Compile by station ID while evaluating solar radiation at the requested
    city-centre coordinates::

        config = EPWConfig(
            year=2023,
            output_path="gothenburg_2023.epw",
            station_id=71420,
            city="Gothenburg",
            latitude=57.7156,
            longitude=11.9924,
        )

    Notes
    -----
    Configuration is a plain dataclass. Validation occurs in
    :func:`compile_epw`, before the first network request.
    """

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
    """Summarize a completed compilation and its quality diagnostics.

    Attributes
    ----------
    output_path
        Path of the validated EPW file.
    rows
        Number of hourly rows written: 8760 or 8784.
    station
        Meteorological station used for observed parameters and elevation.
    interpolated_fraction
        Mean fraction of samples filled across processed input columns.
    coordinate_distance_km
        Distance from the meteorological station to the requested solar point.
    report
        Detailed filling, solar-source, cloud, and energy-closure diagnostics.
    radiation_station_id
        Selected Sol station identifier, if measured GHI was requested.
    radiation_station_distance_km
        Distance from that Sol station to the requested point, in kilometres.

    Examples
    --------
    The result is intended to be inspected rather than ignored::

        result = compile_epw(config)  # doctest: +SKIP
        print(result.rows, result.report.solar_source)  # doctest: +SKIP
    """

    output_path: str
    rows: int
    station: StationMeta
    interpolated_fraction: float
    coordinate_distance_km: float
    report: processing.ProcessingReport
    radiation_station_id: Optional[int] = None
    radiation_station_distance_km: Optional[float] = None


def _validate_config(config: EPWConfig) -> None:
    """Reject invalid or unsupported configuration before network access.

    Parameters
    ----------
    config
        Candidate compiler configuration.

    Raises
    ------
    IngestionError
        If identifiers, coordinates, worker/cache settings, year, or Local
        Standard Time offset cannot be represented safely by the pipeline.

    Notes
    -----
    This function runs before constructing :class:`CachedClient`; configuration
    mistakes therefore never trigger an SMHI request.
    """
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
    """Install a compact default package logger when the caller has not.

    Applications that configure the ``smhi2epw`` logger themselves keep full
    control: the helper only adds a handler when that logger has none. Calling
    it repeatedly is consequently idempotent.
    """
    if not logging.getLogger("smhi2epw").handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter("[smhi2epw] %(message)s"))
        log.addHandler(handler)
        log.setLevel(logging.INFO)


def compile_epw(
    config: EPWConfig, client: Optional[CachedClient] = None
) -> CompileResult:
    """Compile one year of SMHI weather into a validated EPW file.

    Parameters
    ----------
    config
        Location, year, cache, station-selection, and output settings.
    client
        Optional HTTP/cache client. Supplying a compatible test double makes
        the complete pipeline deterministic and offline.

    Returns
    -------
    CompileResult
        Output location, station choices, interpolation metrics, and solar
        quality diagnostics.

    Raises
    ------
    IngestionError
        If configuration, station coverage, HTTP access, or source payloads
        are invalid.
    DataGapError
        If a required observation gap cannot be filled under the 48-hour rule.
    ValidationError
        If the processed year cannot be represented as a strict EPW file.

    Notes
    -----
    Requested coordinates and station coordinates have different roles. The
    requested point drives STRÅNG, solar geometry, and the EPW header; the
    selected MetObs station supplies observed weather and elevation.

    The output is replaced atomically only after all 35 fields and all
    8760/8784 rows pass validation.

    Examples
    --------
    >>> from smhi2epw import EPWConfig, compile_epw
    >>> config = EPWConfig(2023, "gothenburg.epw", station_id=71420)
    >>> result = compile_epw(config)  # doctest: +SKIP
    >>> result.rows  # doctest: +SKIP
    8760

    See Also
    --------
    smhi2epw.read_epw
        Load the generated file for analysis.
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
