"""Expose the high-level compiler as the ``smhi2epw`` shell command.

The CLI is intentionally a thin adapter: :func:`build_parser` owns argument
spelling and help text, while :func:`main` translates parsed values into an
:class:`~smhi2epw.compiler.EPWConfig`.  Scientific work remains in the package
modules, so CLI and Python users receive identical results.
"""

from __future__ import annotations

import argparse
import sys

from .compiler import EPWConfig, compile_epw
from .errors import Smhi2EpwError


def build_parser() -> argparse.ArgumentParser:
    """Construct the command-line argument parser.

    Returns
    -------
    argparse.ArgumentParser
        Parser for station selection, target coordinates, caching, radiation
        selection, and Local Standard Time settings.

    Examples
    --------
    >>> parser = build_parser()
    >>> args = parser.parse_args(["2023", "out.epw", "--station", "71420"])
    >>> (args.year, args.station)
    (2023, 71420)
    """
    parser = argparse.ArgumentParser(
        prog="smhi2epw",
        description="Compile requested-year SMHI weather with ERA5 recovery into an EnergyPlus .epw file.",
    )
    parser.add_argument("year", type=int, help="completed target year from 1999 (AMY)")
    parser.add_argument("output", help="output .epw file path")
    parser.add_argument(
        "--station",
        type=int,
        default=None,
        help="SMHI metobs station id (omit to auto-select nearest via --lat/--lon)",
    )
    parser.add_argument("--city", default="Unknown")
    parser.add_argument("--region", default="SE")
    parser.add_argument("--country", default="SWE")
    parser.add_argument(
        "--utc-offset",
        type=float,
        default=1.0,
        help="Local Standard Time offset in hours (DST ignored; default 1.0)",
    )
    parser.add_argument(
        "--lat",
        "--latitude",
        dest="latitude",
        type=float,
        default=None,
        help="target latitude for station search, solar geometry and ERA5",
    )
    parser.add_argument(
        "--lon",
        "--longitude",
        dest="longitude",
        type=float,
        default=None,
        help="target longitude for station search, solar geometry and ERA5",
    )
    parser.add_argument(
        "--cache-dir",
        default=".smhi_cache",
        help="directory for cached payloads ('' disables caching)",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="ignore cached payloads and re-fetch requested source responses",
    )
    parser.add_argument("--max-workers", type=int, default=8)
    parser.add_argument(
        "--weather-policy",
        choices=("automatic", "strict"),
        default="automatic",
        help="automatic recovery with same-year ERA5 fallback (default) or strict source requirements",
    )
    parser.add_argument(
        "--target-elevation-m",
        type=float,
        default=None,
        help="target elevation for EPW and pressure (default: station or ERA5 height)",
    )
    parser.add_argument(
        "--radiation-station",
        type=int,
        default=None,
        dest="radiation_station_id",
        help=(
            "MetObs Sol (pyranometer) station id for measured GHI "
            "(auto-discovered by default)"
        ),
    )
    parser.add_argument(
        "--no-radiation",
        action="store_true",
        help="disable automatic pyranometer discovery; retain other solar sources",
    )
    parser.add_argument(
        "--radiation-station-max-distance",
        type=float,
        default=50.0,
        metavar="KM",
        help=("maximum distance for auto-selected pyranometer data (default 50 km)"),
    )
    parser.add_argument(
        "--provenance",
        help="JSON receipt path (automatic default: OUTPUT.epw.json)",
    )
    parser.add_argument(
        "--metobs-gap-fallback",
        action="store_true",
        help="enable assessed donors in strict mode; already enabled in automatic mode",
    )
    parser.add_argument("--gap-fallback-max-distance-km", type=float, default=75.0)
    parser.add_argument("--gap-fallback-max-stations", type=int, default=3)
    return parser


def main(argv=None) -> int:
    """Run the command-line compiler and return a process exit code.

    Parameters
    ----------
    argv
        Optional argument sequence without the program name. ``None`` reads
        :data:`sys.argv`, matching normal console-script behavior.

    Returns
    -------
    int
        ``0`` after a successful write or ``1`` for a handled package error.
        Invalid argparse syntax raises :class:`SystemExit` with code ``2``.

    Examples
    --------
    Programmatic callers can test help without starting a subprocess::

        main(["--help"])  # raises SystemExit(0)

    A real compilation contacts SMHI and writes the requested path::

        main(["2023", "out.epw", "--station", "71420"])  # doctest: +SKIP
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.station is None and (args.latitude is None or args.longitude is None):
        parser.error(
            "provide --station, or both --lat and --lon for nearest-station search"
        )
    config = EPWConfig(
        station_id=args.station,
        weather_policy=args.weather_policy,
        metobs_gap_fallback=args.metobs_gap_fallback,
        gap_fallback_max_distance_km=args.gap_fallback_max_distance_km,
        gap_fallback_max_stations=args.gap_fallback_max_stations,
        year=args.year,
        provenance_path=args.provenance,
        output_path=args.output,
        city=args.city,
        region=args.region,
        country=args.country,
        utc_offset=args.utc_offset,
        cache_dir=args.cache_dir or None,
        max_workers=args.max_workers,
        latitude=args.latitude,
        longitude=args.longitude,
        target_elevation_m=args.target_elevation_m,
        refresh=args.refresh,
        radiation_station_id=args.radiation_station_id,
        radiation_station_auto=not args.no_radiation,
        radiation_station_max_distance_km=args.radiation_station_max_distance,
    )
    try:
        result = compile_epw(config)
    except Smhi2EpwError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(
        f"OK: {result.rows} rows -> {result.output_path} "
        f"({result.interpolated_fraction * 100:.2f}% interpolated, "
        f"solar={result.report.solar_source})"
    )
    warnings = getattr(result.report, "warnings", [])
    classification = getattr(
        result.report, "weather_classification", "observation_based"
    )
    print(f"Weather: {classification}; {len(warnings)} warning(s)")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
