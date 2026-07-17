#!/usr/bin/env python3
"""Minimal smhi2epw example: compile a real Gothenburg 2021 EPW.

This hits the live SMHI MetObs + STRÅNG endpoints, so it requires network
access. Run it with:

    python examples/gothenburg_2021.py
"""

from smhi2epw import compile_epw
from smhi2epw.compiler import EPWConfig

result = compile_epw(EPWConfig(
    year=2021,
    output_path="gothenburg_2021.epw",
    station_id=71420,          # Göteborg A
    city="Gothenburg",
    latitude=57.7156,          # STRÅNG solar query point
    longitude=11.9924,
    utc_offset=1.0,            # Local Standard Time (DST ignored)
))

print(f"Wrote {result.rows} rows to {result.output_path}")
print(f"Interpolated {result.interpolated_fraction:.2%} of samples")
print(f"Cloud data available: {result.report.cloud_available}")
