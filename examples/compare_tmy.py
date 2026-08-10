#!/usr/bin/env python3
"""Compare a smhi2epw AMY against a OneBuilding TMYx for Gothenburg.

This script reads the pre-generated ``gothenburg_2021.epw`` (AMY) and the
nearest OneBuilding TMYx (``SWE_VG_Goteborg.025130_TMYx.2007-2021.epw``)
and prints a side-by-side statistical comparison of the key EPW variables.

Run it after gothenburg_2021.py has produced its output:

    python examples/gothenburg_2021.py   # first run if not done yet
    python examples/compare_tmy.py
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

# --------------------------------------------------------------------------- #
# EPW column definitions (35 fields, 1-based as in the spec)
# --------------------------------------------------------------------------- #
EPW_COLS = [
    "year",
    "month",
    "day",
    "hour",
    "minute",
    "flags",
    "dry_bulb",  #  7 (°C, tenths)
    "dew_point",  #  8 (°C, tenths)
    "relative_humidity",  #  9 (%)
    "pressure",  # 10 (Pa)
    "etrh",  # 11 (Wh/m²)
    "etrn",  # 12 (Wh/m²)
    "horizontal_ir",  # 13 (Wh/m²)
    "ghi",  # 14 (Wh/m²)
    "dni",  # 15 (Wh/m²)
    "dhi",  # 16 (Wh/m²)
    "global_illum",  # 17
    "direct_illum",  # 18
    "diffuse_illum",  # 19
    "zenith_lum",  # 20
    "wind_dir",  # 21 (°)
    "wind_speed",  # 22 (m/s, tenths)
    "total_sky_cover",  # 23 (tenths)
    "opaque_sky_cover",  # 24 (tenths)
    "visibility",  # 25
    "ceiling_height",  # 26
    "weather_obs",  # 27
    "weather_codes",  # 28
    "precip_water",  # 29
    "aerosol_opt_depth",  # 30
    "snow_depth",  # 31
    "days_since_snow",  # 32
    "albedo",  # 33
    "liquid_precip",  # 34
    "liquid_precip_qty",  # 35
]


def load_epw(path: Path) -> pd.DataFrame:
    """Read an EPW file, skip 8 header lines, return a labelled DataFrame."""
    df = pd.read_csv(
        path,
        skiprows=8,
        header=None,
        names=EPW_COLS,
        na_values=["9999", "99999", "999999", "9999999", "999", "99", "0.999"],
    )
    # Numeric conversions (EPW stores floats as float strings, ints as ints).
    for col in EPW_COLS[6:]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def _missing_pct(series: pd.Series, missing_tokens: tuple) -> float:
    """Fraction of values equal to a missing token."""
    return float((series.isin(missing_tokens)).sum() / max(len(series), 1) * 100)


def _describe(df: pd.DataFrame, col: str, missing_tokens=(9999, 99999)) -> dict:
    s = df[col].replace(missing_tokens, np.nan).dropna()
    return {
        "n": len(s),
        "mean": s.mean(),
        "std": s.std(),
        "p10": s.quantile(0.10),
        "p50": s.quantile(0.50),
        "p90": s.quantile(0.90),
        "missing%": _missing_pct(df[col], missing_tokens),
    }


def _row(label, a, b, fmt=".1f"):
    diff = a["mean"] - b["mean"]
    sign = "+" if diff >= 0 else ""
    return (
        f"  {label:<28}"
        f"  {a['mean']:{fmt}}  ±{a['std']:{fmt}}"
        f"  {b['mean']:{fmt}}  ±{b['std']:{fmt}}"
        f"  {sign}{diff:{fmt}}"
    )


def compare(amy_path: Path, tmy_path: Path) -> None:
    amy = load_epw(amy_path)
    tmy = load_epw(tmy_path)

    print()
    print("=" * 78)
    print(f"  AMY  : {amy_path.name}")
    print(f"  TMYx : {tmy_path.name}")
    print("=" * 78)
    print(
        f"  {'Variable':<28}  {'AMY mean  ±std':>18}  {'TMY mean  ±std':>18}  {'Δ mean':>8}"
    )
    print("-" * 78)

    # --- Temperature ---
    a = _describe(amy, "dry_bulb")
    b = _describe(tmy, "dry_bulb")
    print(_row("Dry-bulb temp (°C)", a, b))

    a = _describe(amy, "dew_point")
    b = _describe(tmy, "dew_point")
    print(_row("Dew-point temp (°C)", a, b))

    # --- Humidity ---
    a = _describe(amy, "relative_humidity", (999,))
    b = _describe(tmy, "relative_humidity", (999,))
    print(_row("Relative humidity (%)", a, b, ".1f"))

    # --- Pressure ---
    a = _describe(amy, "pressure", (999999,))
    b = _describe(tmy, "pressure", (999999,))
    print(_row("Pressure (Pa)", a, b, ".0f"))

    print()

    # --- Solar ---
    a = _describe(amy, "ghi", (9999,))
    b = _describe(tmy, "ghi", (9999,))
    print(_row("GHI (W/m²)", a, b))

    a = _describe(amy, "dni", (9999,))
    b = _describe(tmy, "dni", (9999,))
    print(_row("DNI (W/m²)", a, b))

    a = _describe(amy, "dhi", (9999,))
    b = _describe(tmy, "dhi", (9999,))
    print(_row("DHI (W/m²)", a, b))

    a = _describe(amy, "horizontal_ir", (9999,))
    b = _describe(tmy, "horizontal_ir", (9999,))
    print(_row("Horizontal IR (W/m²)", a, b))

    a = _describe(amy, "etrn", (9999,))
    b = _describe(tmy, "etrn", (9999,))
    print(_row("Extraterr. normal (W/m²)", a, b))

    print()

    # --- Wind ---
    a = _describe(amy, "wind_speed", (999,))
    b = _describe(tmy, "wind_speed", (999,))
    print(_row("Wind speed (m/s)", a, b, ".2f"))

    a = _describe(amy, "wind_dir", (999,))
    b = _describe(tmy, "wind_dir", (999,))
    print(_row("Wind direction (°)", a, b, ".1f"))

    print()

    # --- Annual totals (solar, heating/cooling degree-days) ---
    print("  Annual totals / degree-days:")

    def annual_kwh(df, col, missing):
        return df[col].replace(missing, np.nan).sum() / 1000.0

    amy_ghi = annual_kwh(amy, "ghi", 9999)
    tmy_ghi = annual_kwh(tmy, "ghi", 9999)
    print(
        f"    GHI annual sum (kWh/m²)  : AMY {amy_ghi:7.1f}   TMY {tmy_ghi:7.1f}"
        f"   Δ {amy_ghi - tmy_ghi:+.1f}"
    )

    amy_dni = annual_kwh(amy, "dni", 9999)
    tmy_dni = annual_kwh(tmy, "dni", 9999)
    print(
        f"    DNI annual sum (kWh/m²)  : AMY {amy_dni:7.1f}   TMY {tmy_dni:7.1f}"
        f"   Δ {amy_dni - tmy_dni:+.1f}"
    )

    def hdd(df, base=18.0):
        t = df["dry_bulb"].replace(9999, np.nan)
        return float((base - t).clip(lower=0).sum())

    def cdd(df, base=22.0):
        t = df["dry_bulb"].replace(9999, np.nan)
        return float((t - base).clip(lower=0).sum())

    ah = hdd(amy)
    th = hdd(tmy)
    ac = cdd(amy)
    tc = cdd(tmy)
    print(
        f"    HDD18 (°C·h)             : AMY {ah:7.0f}   TMY {th:7.0f}"
        f"   Δ {ah - th:+.0f}"
    )
    print(
        f"    CDD22 (°C·h)             : AMY {ac:7.0f}   TMY {tc:7.0f}"
        f"   Δ {ac - tc:+.0f}"
    )

    print()

    # --- Monthly mean dry-bulb ---
    print("  Monthly mean dry-bulb (°C):")
    print(f"    {'Month':<8}", end="")
    for m in range(1, 13):
        print(f"  {pd.Timestamp(2021, m, 1).strftime('%b'):>5}", end="")
    print()
    for label, df in (("AMY  ", amy), ("TMYx ", tmy)):
        print(f"    {label:<8}", end="")
        for m in range(1, 13):
            v = df.loc[df["month"] == m, "dry_bulb"].replace(9999, np.nan).mean()
            print(f"  {v:5.1f}", end="")
        print()
    print("-" * 78)


if __name__ == "__main__":
    here = Path(__file__).parent
    amy = here.parent / "gothenburg_2021.epw"
    tmy = Path(
        "/Users/ssanjay/GitHub/ParametricBuildingGenerator/epw/"
        "SWE_VG_Goteborg.025130_TMYx.2007-2021.epw"
    )

    if not amy.exists():
        print(f"AMY file not found: {amy}")
        print("Run  python examples/gothenburg_2021.py  first.")
        raise SystemExit(1)
    if not tmy.exists():
        print(f"TMY file not found: {tmy}")
        raise SystemExit(1)

    compare(amy, tmy)
