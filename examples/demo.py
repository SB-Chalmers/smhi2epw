#!/usr/bin/env python3
"""smhi2epw feature demo (offline, no network required).

Runs the full compiler against a synthetic SMHI client that deliberately
contains the messy real-world conditions the library is built to handle:

  * a parameter-prefixed station title that needs cleaning,
  * multiple historical station positions (year-aware selection),
  * quality-flagged observations that must be discarded,
  * STRÅNG ``-999`` missing sentinels and a whole missing solar day,
  * total cloud cover driving sky-cover columns and the longwave IR model.

Run it with:

    python examples/demo.py
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

from smhi2epw import constants as C
from smhi2epw import processing, solar
from smhi2epw.compiler import EPWConfig, compile_epw
from smhi2epw.ingestion import (
    find_nearest_station,
    get_station_metadata,
)

YEAR = 2023  # non-leap -> 8760 rows
STATION_ID = 71420
LAT, LON = 57.7156, 11.9924


# --------------------------------------------------------------------------- #
# Synthetic SMHI client
# --------------------------------------------------------------------------- #
def _utc_grid(year: int) -> pd.DatetimeIndex:
    return pd.date_range(f"{year}-01-01", f"{year}-12-31 23:00", freq="h", tz="UTC")


def _metobs_csv(name: str, base: float, bad_quality_hours=(), seasonal=0.0) -> str:
    """Synthetic corrected-archive CSV with a trailing 'Kvalitet' column."""
    grid = _utc_grid(YEAR)
    lines = [
        "Stationsnamn;Stationsnummer",
        f"Synthetic;{STATION_ID}",
        "",
        f"Datum;Tid (UTC);{name};Kvalitet",
    ]
    for i, ts in enumerate(grid):
        val = base + np.sin(i / 24.0) + seasonal * np.sin(2 * np.pi * i / len(grid))
        quality = "B" if i in bad_quality_hours else "G"  # 'B' = unusable
        lines.append(
            f"{ts.strftime('%Y-%m-%d')};{ts.strftime('%H:%M:%S')};{val:.2f};{quality}"
        )
    return "\n".join(lines)


def _solar_components() -> dict[str, np.ndarray]:
    """Physically consistent GHI / DNI / beam-horizontal from real geometry.

    Built so that ``GHI - beam_horizontal = DHI >= 0`` and
    ``DNI * cos(zenith) = beam_horizontal`` hold at every hour, which keeps the
    pipeline's energy-balance residual near zero.
    """
    grid = _utc_grid(YEAR)
    _, cos_z = solar.solar_zenith(grid, LAT, LON)
    cos_z = np.clip(cos_z, 0.0, None)
    daylight = cos_z > C.COS_ZENITH_FLOOR

    ghi = np.where(daylight, 1100.0 * 0.75 * cos_z, 0.0)
    beam_h = 0.7 * ghi  # direct beam on the horizontal
    dni = np.where(daylight, beam_h / np.clip(cos_z, 1e-3, None), 0.0)
    return {"ghi": ghi, "dni": dni, "dirh": beam_h}


_SOLAR = _solar_components()


def _strang_json(component: str, missing_day: int | None = None) -> str:
    """Serialize one STRÅNG stream, with optional -999 sentinels for a day."""
    grid = _utc_grid(YEAR)
    values = _SOLAR[component]
    out = []
    for i, ts in enumerate(grid):
        if missing_day is not None and ts.dayofyear == missing_day:
            value = -999.0  # STRÅNG missing sentinel
        else:
            value = float(values[i])
        out.append({"date_time": ts.strftime("%Y-%m-%dT%H:%M:%SZ"), "value": value})
    return json.dumps(out)


class DemoClient:
    """Deterministic stand-in for :class:`CachedClient`."""

    # Hours (UTC) whose temperature carries an unusable quality flag.
    BAD_TEMP_HOURS = (10, 11, 12)
    MISSING_SOLAR_DAY = 200  # whole day of -999 in every STRÅNG stream

    def get_text(self, url: str, suffix: str = "txt") -> str:
        if "/parameter/1/" in url and "station" in url and url.endswith(".csv"):
            return _metobs_csv(
                "Lufttemperatur", 8.0, self.BAD_TEMP_HOURS, seasonal=10.0
            )
        if "/parameter/6/" in url:
            return _metobs_csv("Relativ Luftfuktighet", 75.0)
        if "/parameter/9/" in url:
            return _metobs_csv("Lufttryck", 1013.0)
        if "/parameter/4/" in url:
            return _metobs_csv("Vindhastighet", 4.0)
        if "/parameter/3/" in url:
            return _metobs_csv("Vindriktning", 200.0)
        if "/parameter/16/" in url:
            return _metobs_csv("Total molnmangd", 4.0)  # ~4 octas
        raise AssertionError(f"unexpected text url: {url}")

    def get_json(self, url: str):
        if url.endswith(f"/station/{STATION_ID}.json"):
            return {
                # Parameter-prefixed title, just like the live API.
                "title": "Lufttemperatur - Goteborg A: Valj tidsutsnitt",
                "key": "024640",
                "position": [
                    # Older, now-retired position (wrong for 2023).
                    {
                        "from": 0,
                        "to": 1262304000000,
                        "latitude": 57.70,
                        "longitude": 11.95,
                        "height": 5.0,
                    },
                    # Position valid during 2023.
                    {
                        "from": 1262304000000,
                        "to": 4102444800000,
                        "latitude": LAT,
                        "longitude": LON,
                        "height": 3.04,
                    },
                ],
            }
        if url.endswith("/parameter/1.json") or any(
            url.endswith(f"/parameter/{p}.json") for p in (3, 4, 6, 9)
        ):
            return {
                "station": [
                    {
                        "key": str(STATION_ID),
                        "latitude": LAT,
                        "longitude": LON,
                        "from": 0,
                        "to": 4102444800000,
                    },
                    {
                        "key": "99999",
                        "latitude": LAT + 4.0,
                        "longitude": LON + 4.0,
                        "from": 0,
                        "to": 4102444800000,
                    },
                ]
            }
        if "/parameter/117/" in url:
            return json.loads(_strang_json("ghi", self.MISSING_SOLAR_DAY))  # GHI
        if "/parameter/118/" in url:
            return json.loads(_strang_json("dni", self.MISSING_SOLAR_DAY))  # DNI
        if "/parameter/121/" in url:
            return json.loads(
                _strang_json("dirh", self.MISSING_SOLAR_DAY)
            )  # beam-horiz
        raise AssertionError(f"unexpected json url: {url}")


# --------------------------------------------------------------------------- #
# Pretty printing helpers
# --------------------------------------------------------------------------- #
def banner(title: str) -> None:
    print()
    print("=" * 70)
    print(f"  {title}")
    print("=" * 70)


# --------------------------------------------------------------------------- #
# Feature demonstrations
# --------------------------------------------------------------------------- #
def demo_station_metadata(client) -> None:
    banner("1. Station metadata: title cleaning + year-aware position")
    meta = get_station_metadata(STATION_ID, client, year=YEAR)
    print("  raw title  : 'Lufttemperatur - Goteborg A: Valj tidsutsnitt'")
    print(f"  clean name : {meta.name!r}")
    print(
        f"  position   : {meta.latitude:.4f}, {meta.longitude:.4f} "
        f"(elevation {meta.elevation:.2f} m)"
    )
    print("  -> the 2023-valid position was chosen over the retired one.")


def demo_nearest_station(client) -> None:
    banner("2. Nearest-station resolver (coordinates -> station)")
    meta = find_nearest_station(LAT, LON, YEAR, client)
    dist = meta.distance_km(LAT, LON)
    print(f"  query point : {LAT:.4f}, {LON:.4f}")
    print(f"  resolved    : station {meta.station_id} ({meta.name}) at {dist:.2f} km")
    print("  -> a far-away candidate station was rejected in favour of the closest.")


def demo_quality_and_solar_cleaning(client) -> None:
    banner("3. Quality flags + STRÅNG -999 sentinel cleaning")
    from smhi2epw.ingestion import ingest

    meta = get_station_metadata(STATION_ID, client, year=YEAR)
    frame = ingest(meta, YEAR, client, utc_offset=1.0)

    flagged = DemoClient.BAD_TEMP_HOURS
    flagged_ts = [pd.Timestamp(f"{YEAR}-01-01 {h:02d}:00", tz="UTC") for h in flagged]
    now_nan = [bool(np.isnan(frame.loc[ts, "dry_bulb"])) for ts in flagged_ts]
    print(f"  temperature hours {flagged} (UTC, Jan 1) carried a 'B' quality flag")
    print(f"    -> NaN before imputation: {now_nan}")

    sentinel_count = int((frame[["ghi", "dni", "dirh"]] <= -990).sum().sum())
    raw_min = float(np.nanmin(frame[["ghi", "dni", "dirh"]].to_numpy()))
    print(f"  STRÅNG -999 sentinels surviving ingestion : {sentinel_count}")
    print(
        f"  minimum solar value after cleaning        : {raw_min:.1f} (no -999 leakage)"
    )


def demo_processing(client) -> None:
    banner("4. Processing: derived physics + diurnal solar fill + QA report")
    from smhi2epw.ingestion import ingest

    meta = get_station_metadata(STATION_ID, client, year=YEAR)
    frame = ingest(meta, YEAR, client, utc_offset=1.0)
    report = processing.process(frame, meta.latitude, meta.longitude)

    print(
        "  derived columns added:",
        ", ".join(
            c
            for c in ("dew_point", "horizontal_ir", "dhi", "etrh", "etrn", "sky_cover")
            if c in frame.columns
        ),
    )
    print(f"  cloud data available        : {report.cloud_available}")
    print(
        f"  total interpolated fraction : "
        f"{report.total_interpolated_fraction * 100:.3f}%"
    )
    print(f"  physically clamped DNI hours: {report.clamped_dni_hours}")
    print(
        f"  max energy-balance residual : "
        f"{report.energy_balance_max_residual:.1f} W/m^2 (should be small)"
    )

    # Show that the fully-missing solar day was reconstructed, not left blank.
    day = DemoClient.MISSING_SOLAR_DAY
    mask = frame.index.dayofyear == day
    rebuilt_noon = float(frame.loc[mask, "ghi"].max())
    print(
        f"  GHI peak on the once-missing day {day}: {rebuilt_noon:.0f} W/m^2 "
        f"(rebuilt diurnally)"
    )


def demo_cloud_ir() -> None:
    banner("5. Cloud-aware longwave (horizontal IR)")
    dry = pd.Series([10.0])
    dew = pd.Series([6.0])
    clear = processing.horizontal_ir(dry, dew).iloc[0]
    overcast = processing.horizontal_ir(
        dry, dew, cloud_cover_tenths=pd.Series([10.0])
    ).iloc[0]
    print(f"  clear sky   : {clear:6.1f} W/m^2")
    print(f"  overcast    : {overcast:6.1f} W/m^2")
    print(f"  cloud uplift: {overcast - clear:+.1f} W/m^2 (EnergyPlus cloud term)")


def demo_extraterrestrial() -> None:
    banner("6. Extraterrestrial radiation (EPW columns 11/12)")
    idx = pd.date_range(f"{YEAR}-06-21 10:00", periods=1, freq="h", tz="UTC")
    _, cos_z = solar.solar_zenith(idx, LAT, LON)
    etrh, etrn = solar.extraterrestrial_radiation(idx, cos_z)
    print(f"  solstice mid-morning at {LAT:.2f},{LON:.2f}")
    print(f"  direct-normal (etrn): {etrn[0]:7.1f} W/m^2 (~ solar constant)")
    print(f"  horizontal   (etrh): {etrh[0]:7.1f} W/m^2")


def demo_compile() -> Path:
    banner("7. End-to-end compile -> validated EPW file")
    tmp = Path(tempfile.mkdtemp(prefix="smhi2epw_demo_"))
    out = tmp / "gothenburg_demo.epw"
    config = EPWConfig(
        year=YEAR,
        output_path=str(out),
        station_id=STATION_ID,
        city="Gothenburg",
        latitude=LAT,
        longitude=LON,
        utc_offset=1.0,
        cache_dir=None,
    )
    result = compile_epw(config, client=DemoClient())

    lines = out.read_text(encoding="utf-8").splitlines()
    print(f"  rows written        : {result.rows} (expected 8760)")
    print(f"  file lines          : {len(lines)} (8 header + data)")
    print(f"  header[0]           : {lines[0][:60]}...")
    midday = lines[8 + 24 * 120 + 12].split(",")  # ~ day 121, hour 13
    print(
        f"  sample row fields   : dry_bulb={midday[6]}  dew={midday[7]}  "
        f"etrn={midday[11]}  GHI={midday[13]}  sky_cover={midday[22]}"
    )
    print(f"  output file         : {out}")
    return out


def demo_required_vs_optional() -> None:
    banner("8. Imputation policy: required hard-abort vs optional soft")
    from smhi2epw.errors import DataGapError

    idx = _utc_grid(YEAR)
    frame = pd.DataFrame(
        {
            "dry_bulb": np.arange(len(idx), dtype=float),
            "cloud_cover": np.full(len(idx), 4.0),
        },
        index=idx,
    )
    # A 49-hour gap in an OPTIONAL column remains missing and is tolerated.
    frame.iloc[40:89, frame.columns.get_loc("cloud_cover")] = np.nan
    report = processing.impute(frame, ["dry_bulb"], optional=["cloud_cover"])
    print(
        f"  optional 49-h cloud gap tolerated; "
        f"cloud interp fraction = "
        f"{report.interpolated_fraction['cloud_cover'] * 100:.2f}%"
    )

    # The same gap in a REQUIRED column aborts because it exceeds 48 hours.
    frame2 = pd.DataFrame({"dry_bulb": np.arange(len(idx), dtype=float)}, index=idx)
    frame2.iloc[40:89, 0] = np.nan
    try:
        processing.impute(frame2, ["dry_bulb"])
        print("  required gap: NOT aborted (unexpected)")
    except DataGapError as exc:
        print(f"  required 49-h gap correctly rejected: {str(exc)[:55]}...")


def main() -> int:
    client = DemoClient()
    print("smhi2epw feature demo - synthetic data, no network calls")
    demo_station_metadata(client)
    demo_nearest_station(client)
    demo_quality_and_solar_cleaning(client)
    demo_processing(client)
    demo_cloud_ir()
    demo_extraterrestrial()
    out = demo_compile()
    demo_required_vs_optional()

    banner("Done")
    print(f"  A complete, validated EPW was written to:\n    {out}")
    print("  Open it in EnergyPlus / a text editor to inspect all 35 columns.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
