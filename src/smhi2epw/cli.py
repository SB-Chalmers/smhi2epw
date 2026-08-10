"""Command-line interface for smhi2epw."""

from __future__ import annotations

import argparse
import sys

from .compiler import EPWConfig, compile_epw
from .errors import Smhi2EpwError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="smhi2epw",
        description="Compile SMHI MetObs + STRÅNG data into an EnergyPlus .epw file.",
    )
    parser.add_argument("year", type=int, help="target year (AMY)")
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
        help="latitude for nearest-station search and STRÅNG solar query",
    )
    parser.add_argument(
        "--lon",
        "--longitude",
        dest="longitude",
        type=float,
        default=None,
        help="longitude for nearest-station search and STRÅNG solar query",
    )
    parser.add_argument(
        "--cache-dir",
        default=".smhi_cache",
        help="directory for cached payloads ('' disables caching)",
    )
    parser.add_argument(
        "--refresh",
        action="store_true",
        help="ignore cached payloads and re-fetch from the SMHI endpoints",
    )
    parser.add_argument("--max-workers", type=int, default=8)
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
        help="disable auto-discovery of radiation station; use STRÅNG solar only",
    )
    parser.add_argument(
        "--radiation-station-max-distance",
        type=float,
        default=50.0,
        metavar="KM",
        help=("maximum distance for auto-selected pyranometer data (default 50 km)"),
    )
    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.station is None and (args.latitude is None or args.longitude is None):
        parser.error(
            "provide --station, or both --lat and --lon for nearest-station search"
        )
    config = EPWConfig(
        station_id=args.station,
        year=args.year,
        output_path=args.output,
        city=args.city,
        region=args.region,
        country=args.country,
        utc_offset=args.utc_offset,
        cache_dir=args.cache_dir or None,
        max_workers=args.max_workers,
        latitude=args.latitude,
        longitude=args.longitude,
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
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
