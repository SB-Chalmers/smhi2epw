Missing-weather recovery and audit trail
=======================================

Policy and defaults
-------------------

The compiler preserves a continuous hourly UTC grid, including the boundary
hours needed to export a complete Local Standard Time calendar. It does not
silently replace missing meteorology with EnergyPlus defaults.

* Scalar gaps of at most three hours use endpoint interpolation. At a calendar
  boundary, one available endpoint permits a constant one-sided estimate.
* Gaps of four through 48 hours use endpoint-adjusted daily profiles. The
  nearest complete 24-hour reference is searched independently on either side
  within seven days. Available sides are blended equally; one usable side is
  sufficient. Profiles are taken from the working series, which can contain
  earlier reconstructions.
* Longer gaps are never filled by temporal interpolation. Entirely missing
  required variables also fail unless the opt-in observation fallback supplies
  sufficient recorded observations.
* Reconstructed relative humidity, wind speed and cloud cover are bounded to
  0--100 percent, 0--40 m/s and 0--8 octas respectively. Valid source observations
  are not clipped. Direction interpolation uses sine/cosine components.

``EPWConfig.metobs_gap_fallback`` defaults to ``False``. Enabling it validates
primary required meteorological observations and treats nonfinite or
out-of-range cells as missing. The representable bounds are temperature
-70--70 degrees Celsius, humidity 0--100 percent, sea-level pressure
310--1200 hPa, wind speed 0--40 m/s and direction 0--360 degrees. These bounds
are representability checks, not a complete meteorological quality model.

Nearby-observation fallback
---------------------------

After identifying gaps that the temporal policy cannot reconstruct, the
compiler searches stations with metadata coverage for the requested year and
needed parameter. A donor need not supply all five required variables.
Candidates are ranked by distance to the requested point, then station ID.
At most ``gap_fallback_max_stations`` candidates (default three in total) are
attempted within ``gap_fallback_max_distance_km`` (default 75 km). Year-specific
positions are checked against the radius again after metadata resolution.

Only same-hour, accepted-quality SMHI observations (G or Y) replace missing
primary cells. Donor observations outside the representable bounds are ignored.
Subhourly donor observations are averaged hourly; wind directions use circular
averages and a cancelling vector is left missing. Existing valid primary values
are retained. After each donor, remaining gaps are reassessed using the same
48-hour temporal limit. Transport errors for a donor parameter are recorded and
other eligible candidates may still be attempted. Uncovered gaps still fail.

No donor solar radiation is copied. STRANG queries and solar geometry remain at
the requested location. Parameter 9 remains sea-level QFF until processing
converts it into pressure at the resolved target elevation using the inverse
SMHI reduction. See :doc:`provenance` for pressure assumptions.

Usage
-----

Python::

    from smhi2epw import EPWConfig, compile_epw

    result = compile_epw(EPWConfig(
        year=2018,
        output_path="weather-2018.epw",  # parent directory must exist
        latitude=59.3,
        longitude=18.0,
        metobs_gap_fallback=True,
        gap_fallback_max_distance_km=75.0,
        gap_fallback_max_stations=3,
        provenance_path="weather-2018.json",
    ))
    print(result.report.required_reconstructed_fraction)
    print(result.report.gap_fallback_sources)

CLI::

    smhi2epw 2018 weather-2018.epw --lat 59.3 --lon 18.0 \
      --metobs-gap-fallback --gap-fallback-max-distance-km 75 \
      --gap-fallback-max-stations 3 --provenance weather-2018.json

Fallback settings are validated before network access. Disabling fallback
retains strict station-only behavior; the improved temporal reconstruction and
bounds on reconstructed values still apply.

Diagnostics and reproducibility
-------------------------------

``ProcessingReport`` records:

* ``primary_missing_hours`` and ``invalid_observation_hours`` by required
  variable, before any recovery, when fallback is enabled;
* ``cross_station_filled_hours`` by variable, and ``gap_fallback_sources`` with
  donor IDs, coordinates, distances, filled counts and inclusive UTC intervals;
* ``gap_fallback_attempts`` including donor metadata/parameter errors;
* donor/primary overlap counts, mean differences and mean absolute differences
  in each variable's source units (angular differences use the shortest arc);
* ``linear_filled_hours``, ``diurnal_filled_hours``, ``max_gap_hours`` and
  ``bounded_filled_hours`` for subsequent temporal filling;
* ``required_reconstructed_fraction``: the pre-recovery missing/invalid cell
  count divided by all cells in the five required meteorological variables on
  the ingestion grid, including calendar boundary hours. This field is populated
  by the opt-in recovery path and remains zero when that path is disabled.

The existing ``interpolated_fraction`` measures subsequent temporal filling
across processed columns; it excludes cells already supplied by donors and
must not be interpreted as the total amount of weather reconstruction.
Overlap differences are descriptive comparisons against primary observations,
not independent held-out validation or a bias correction. No-overlap statistics
are explicitly null, including when a primary variable is entirely absent.

``provenance_path`` writes a separate atomic JSON receipt with configuration,
result/report, EPW SHA-256, package version, source-code fingerprints and hashes
of UTF-8 API responses consumed by the parser. Cached and fetched payloads are
both recorded. Custom clients without receipts are marked incomplete. Receipt
writing happens after successful EPW export; a failed compilation has no normal
success receipt, and a receipt-write failure can leave a valid EPW on disk.

Actual-year export also validates leap-day and weekday headers before replacing
an output file. Leap years use 8,784 rows and permit February 29; ordinary years
use 8,760 rows. Preserve old artifacts and generate a fresh EPW when changing
pressure conversion, reconstruction policy or source data.

Evidence and limitations
------------------------

On 5 October 2026, the EPSM national-cohort workflow replayed its 53 failed
municipality/year weather jobs in a separate artifact directory, retaining
cached primary observations and fetching needed donor archives. Of these:

* 52 produced EPWs passing export and EPSM calendar validation;
* nine recovered without donors, and 43 used nearby recorded observations;
* 19 reconstructed more than five percent of required meteorological cells;
* all 32 previously successful EPWs retained their original SHA-256 values;
* the remaining job, municipality 2101/year 2018, retained an 86-hour pressure
  gap on 15--19 October UTC after its only eligible donor within 75 km was used.

Five percent is a reporting aid, not a validated acceptance threshold. Some
recovered jobs substitute entire variables, and one substitutes all primary
meteorological inputs. Donor wind differences can be substantial. A complete,
range-valid EPW establishes neither local weather accuracy nor archetype
qualification. Review replacement extent, distance, overlap and site exposure;
consider weather sensitivity before calibrating heavily reconstructed cases.
No annual building simulations or calibration were rerun in this replay.

The workflow artifact directory ``output/weather-robustness-2026-10-05-v1``
contains status, source manifest/snapshot, per-job receipts, failure diagnostics,
replay script and an HTML report. Large generated EPWs and raw caches are local
artifacts, not package source. The replay source hashes precede documentation
and formatting added for this commit; regenerated receipts will have new hashes.

Regression verification: 97 offline smhi2epw tests passed, four skipped and four
live-network tests were deselected. Coverage includes a complete recovered
8,760-hour EPW, a 49-hour donor-filled gap, radius enforcement, circular winds,
invalid configuration before requests, preserving valid observations and the
48-hour temporal ceiling. The EPSM workflow suite passed 236 tests with one
skip. Live donor retrieval was exercised by the separate replay, not the
network-marked test suite.
