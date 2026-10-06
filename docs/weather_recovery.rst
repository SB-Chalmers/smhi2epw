Missing-weather recovery and audit trail
========================================

Policy and defaults
-------------------

``EPWConfig.weather_policy="automatic"`` is the default. The compiler aims to
return a complete requested-year EPW while retaining usable observations and
making reconstruction visible. Supported requests are completed calendar years
from 1999 onward. Required meteorological variables follow this order:

1. Accepted-quality primary observations.
2. Interpolation for gaps up to three hours, circularly for wind direction.
3. Assessed same-year nearby observations for longer gaps or unfillable short
   wind gaps.
4. Bounded daily-profile reconstruction for remaining gaps up to 48 hours.
5. Same-year ERA5 at the requested coordinates, supplied through Open-Meteo.

Solar recovery remains donor-free: usable primary radiation, bounded solar
filling or GHI decomposition, then same-year ERA5 for unresolved GHI.

``weather_policy="strict"`` retains source and gap failures instead of enabling
reanalysis. In strict mode, ``metobs_gap_fallback=True`` permits assessed donors;
its default remains ``False``. Automatic policy already enables donors and does
not require this legacy flag. Donor-enabled strict mode uses the same
meteorological precedence through daily profiles, with no ERA5 stage. Without
that flag, strict mode uses primary observations and bounded temporal filling.
Both modes preserve valid primary observations. Invalid or nonfinite inputs
become missing cells in automatic recovery.

Temporal filling remains bounded. Scalar gaps of at most three hours use
endpoint interpolation; a single endpoint permits a constant boundary estimate.
After assessed donors are tried, remaining gaps of up to 48 hours use
endpoint-adjusted daily profiles, searching independently on each side within
seven days. Usable sides receive equal weight; one side is sufficient. Profiles
can include earlier reconstructions. Wind direction uses sine/cosine components.
Solar gaps use day-aware profiles without donor transfer. Longer gaps are filled
from another source, never by extending interpolation.

The frozen sensitivity campaign covered 17 weather-years, six regions and
six building profiles. For its 3--12-hour gaps, the largest group-level 95th
percentile annual-load error was 0.893%. Four week-long seasonal solar gaps
reached 12.728% at the 95th percentile for annual sensible cooling. In its
48-hour event-centred meteorology cases, the winning peak moved more than
24 hours in 13/41 heating and 14/44 cooling cases. Annual energy and event timing
therefore need separate checks.

These results compare reconstructions with the campaign's own reference weather;
4,146 automatic comparisons are not 4,146 independent climate samples. Both
reference and candidate used the same solar finalizer, so a shared error can
cancel in a paired comparison. The original campaign is frozen at source commit
5930c07, before the low-sun and historical-DNI corrections. It supports the
reported conditional comparisons, not site-weather accuracy or national error
bounds. Regenerated references and targeted paired runs are needed when the
solar method changes. The archived completeness evidence below is a separate
generation check, not additional validation of sensitivity results.

Automatic station selection prefers full coverage but can use a partial station.
Source failures are reported while other requests continue. If station discovery
fails, supplied coordinates allow reanalysis recovery. Supplying only a station
ID still requires enough metadata to resolve a target location. Invalid
configuration, unknown coordinates, incomplete future years, unavailable weather
from every source, unrecoverable physical inconsistencies and filesystem errors
remain explicit failures. "Complete" does not mean inventing weather when no
usable source exists.

Nearby-observation assessment
-----------------------------

Donors are searched within ``gap_fallback_max_distance_km`` (default 75 km).
At most ``gap_fallback_max_stations`` candidates (default three in total) are
attempted, ordered by distance and station ID. Metadata is resolved for the
parameter being borrowed; a donor need not have temperature or all five required
variables. Year-specific positions are checked against the radius again.
Only same-hour SMHI observations with accepted quality grades G or Y are used.
Invalid donor values and transport failures are recorded and skipped.

For each gap and variable, assess original paired primary/donor observations
within 30 days on either side. Reconstructed primary values are excluded.
Validate on three complete, distinct UTC overlap days: the earliest, middle and
latest. Each fit excludes its test day and the adjacent days, and requires at
least 168 paired training hours spanning seven dates. Insufficient overlap
rejects a donor rather than treating its proximity as evidence of accuracy.

Scalar candidates are raw transfer and a median primary-minus-donor offset.
Select an offset only if held-out mean absolute error (MAE) improves by at least
10 percent, then refit on all eligible overlap. Wind direction uses shortest-arc
errors and raw transfer only. The selected candidate must satisfy these default
MAE ceilings in source units:

===================== ====================
Variable              Maximum held-out MAE
===================== ====================
Temperature           3 degrees Celsius
Relative humidity     15 percentage points
Wind speed            3 m/s
Wind direction        45 degrees
Sea-level QFF         5 hPa
===================== ====================

These are engineering defaults, not scientifically established accuracy
thresholds. Corrected values outside physical bounds are ignored. Remaining
gaps proceed to another eligible donor, then bounded daily profiles where
possible, and ERA5 in automatic mode. Entirely
missing variables cannot be calibrated against that year's primary record and
therefore normally require reanalysis. No ML, wind rotation, multi-variable
prediction or future-climate morphing is applied.

Primary and donor subhourly winds share circular hourly averaging. A cancelling
direction vector remains missing. Donor solar data is never copied; solar
recovery remains tied to the requested coordinates.

ERA5 recovery and physical consistency
--------------------------------------

Automatic policy uses the `Open-Meteo Historical Weather API
<https://open-meteo.com/en/docs/historical-weather-api>`_ with ERA5 selected
explicitly, UTC timestamps and the buffered requested-year window. The adapter
checks units, array lengths, calendar coverage and usable values. Returned grid
coordinates, elevation, model and response fingerprints accompany the report.

Temperature, humidity, wind and surface pressure recover unresolved required
hours. Missing cloud cover is filled from ERA5 only where ERA5 actually replaces
required meteorology or GHI. Usable existing cloud values and all other hours
remain unchanged; fetching ERA5 only to resolve metadata does not add clouds.
``reanalysis_filled_hours`` includes ``cloud_cover`` when these optional
replacements are used. SMHI parameter 9 is sea-level QFF and requires the inverse
SMHI reduction; ERA5 surface pressure is used directly after unit conversion,
without a second
reduction. See :doc:`provenance` for elevation assumptions.

Reanalysis radiation already represents the preceding-hour mean and is not
averaged again like instantaneous STRÅNG samples. Solar replacements use complete
component groups; when only usable GHI is available, the existing Erbs method
derives DNI/DHI. Missing direct/diffuse solar components alone do not request
ERA5 when existing GHI can be decomposed. Dew point and longwave radiation are
derived from the final meteorological inputs.

Hourly solar inputs outside 0--2,000 W/m² are treated as missing before recovery.
This is a broad engineering plausibility guard, not a validated local solar
threshold or a limit on plausible heatwave temperatures.

Final checks require complete ordered hours, finite required values, physical
ranges, dew point consistent with dry bulb, nonnegative solar fields, solar
closure and the existing extraterrestrial DNI cap. Positive solar data during
fully dark intervals is treated as inconsistent. Darkness checks use interval
geometry so sunrise and sunset hours are not mistaken for complete darkness.
Reconstructed humidity, wind and cloud estimates obey representable limits;
valid observations are not clipped merely because they are unusual.

When ERA5 is fetched, ``reanalysis_metadata["overlap"]`` compares it against
available original primary observations. It records paired-hour counts, mean
difference and mean absolute difference; wind direction uses shortest angular
arcs. Pressure comparisons use Pa after original QFF is converted to target
surface pressure with original valid temperature. Substantial disagreement
produces a warning rather than rejecting the fallback or suppressing an event.
These comparisons are descriptive and do not provide independent validation.

Abrupt changes at source boundaries also generate warnings.
Boundary warning thresholds are 10 degrees Celsius for temperature, 40
percentage points for humidity, 15 m/s for wind speed and 1,000 Pa for surface
pressure. They trigger review, not automatic rejection of extreme weather.
Usable primary extremes are preserved, and another year is never substituted.
Reconstruction may change a missing event's peak intensity, timing or duration;
these checks cannot guarantee heatwave preservation or building-site accuracy.
Review source extent and uncertainty when extremes matter.

Usage
-----

Python::

    from smhi2epw import EPWConfig, compile_epw

    result = compile_epw(EPWConfig(
        year=2018,
        output_path="weather-2018.epw",  # parent directory must exist
        latitude=59.3,
        longitude=18.0,
        weather_policy="automatic",  # default; also enables assessed donors
        gap_fallback_max_distance_km=75.0,
        gap_fallback_max_stations=3,
    ))
    print(result.report.warnings)
    print(result.report.required_reconstructed_fraction)
    print(result.report.gap_fallback_sources)
    # Default audit sidecar: weather-2018.epw.json

CLI::

    smhi2epw 2018 weather-2018.epw --lat 59.3 --lon 18.0 \
      --gap-fallback-max-distance-km 75 --gap-fallback-max-stations 3

For strict compilation with optional assessed donors::

    smhi2epw 2018 weather-2018.epw --lat 59.3 --lon 18.0 \
      --weather-policy strict --metobs-gap-fallback --provenance weather-2018.json

Settings are validated before requests. Explicit ``provenance_path`` (CLI
``--provenance``) overrides the automatic ``OUTPUT.epw.json`` destination.
Strict mode creates no sidecar unless one is requested. The output and sidecar
paths must differ and their parent directories must exist.

Diagnostics and reproducibility
-------------------------------

Review ``ProcessingReport.warnings`` and the sidecar alongside the EPW. They
record source failures, rejected donors, insufficient overlap, corrected or
reanalysis-filled hours, and source-boundary concerns. ``weather_classification``
is ``observation_based``, ``mixed_reconstructed`` or ``reanalysis_only``.
Reconstruction of any required meteorological variable or solar GHI makes a
result mixed; routine physical darkness zeros do not. Reanalysis-only requires
all required meteorological hours from ERA5 and solar GHI from ERA5 or physical
darkness. ``solar_source`` separately identifies the radiation path.
``source_fractions`` maps required meteorological variables and GHI to shares
of exported hours using primary, temporal, donor, reanalysis and physical source
tags. It does not currently describe optional cloud cover; its recovered-hour
count is included in ``reanalysis_filled_hours``.
``reanalysis_filled_hours`` and ``reanalysis_metadata`` describe the extent,
provider details and original-observation comparisons of ERA5 use.
EPW comments retain fallback attribution and a quality summary when the EPW is
copied without its sidecar.

Recovery diagnostics include:

* ``primary_missing_hours`` and ``invalid_observation_hours`` by required
  variable before recovery;
* ``cross_station_filled_hours`` and ``gap_fallback_sources`` with donor IDs,
  locations, distances, selected methods, offsets and filled UTC intervals;
* ``gap_fallback_attempts`` including rejected candidates, assessment status,
  overlap period, held-out errors and metadata/parameter errors;
* ``linear_filled_hours``, ``diurnal_filled_hours``, ``max_gap_hours`` and
  ``bounded_filled_hours`` for temporal reconstruction;
* ``required_reconstructed_fraction``: missing/invalid primary cells divided
  by all cells in the five required meteorological variables on the ingestion
  grid, including calendar boundary hours.

The existing ``interpolated_fraction`` reports temporal filling across processed
columns. It is not the fraction of all reconstruction; donor and reanalysis
estimates must also be reviewed. Donor held-out errors measure agreement with
primary observations during overlap, not independent site validation or an
accuracy guarantee for the outage.

The atomic JSON sidecar records configuration, result/report, EPW SHA-256,
package version, source-code fingerprints and UTF-8 response hashes. Live and
cached payloads follow the same receipt contract. Receipts are scoped per
compilation even when a client is reused; unrelated earlier requests are
excluded. Custom clients without scoped response receipts are marked incomplete.

Receipt writing occurs after successful EPW export. Automatic policy returns
the valid EPW with a ``provenance_write_failed`` warning when a sidecar filesystem
failure prevents saving the receipt; strict policy retains a reported error.
Neither case establishes a saved audit trail. EPW replacement remains atomic and follows successful
validation of headers, 35-field rows, physical values and annual cardinality.
Preserve old artifacts and regenerate when changing reconstruction policy,
pressure conversion or source payloads.

Service access and limitations
------------------------------

The packaged adapter uses Open-Meteo's public noncommercial endpoint. Check the
current `service access and limits <https://open-meteo.com/en/pricing>`_ before
batch or commercial use; the package does not configure a paid API key or a
customer endpoint. Responses are cached to avoid unnecessary repeat requests.
Attribute Open-Meteo and Copernicus Climate Change Service ERA5 in studies using
this fallback. Model weather is not an independent local observation and can
underrepresent microclimates or extreme intensity.

Historical replay evidence
--------------------------

The earlier opt-in, raw-donor policy (commit ``4861f9e``) was exercised on
5 October 2026 when the EPSM national-cohort workflow replayed its 53 failed
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
artifacts, not package source. These artifacts describe the earlier recovery
policy and do not validate the automatic ERA5 fallback or donor assessment
introduced here. Regenerated
receipts will have new code and configuration identities.

Historical regression verification: 97 offline smhi2epw tests passed, four
skipped and four live-network tests were deselected. Coverage includes a complete recovered
8,760-hour EPW, a 49-hour donor-filled gap, radius enforcement, circular winds,
invalid configuration before requests, preserving valid observations and the
48-hour temporal ceiling. The EPSM workflow suite passed 236 tests with one
skip. Live donor retrieval was exercised by the separate replay, not the
network-marked test suite.

Current national completion run
--------------------------------

On 5 October 2026 the frozen automatic policy at ``5930c07`` completed all
128 requested municipality/year jobs from 2017--2024. The preceding national
run at ``4861f9e`` completed 124 of the same 128 jobs using opt-in raw donors
without ERA5. The original temporal-only run completed 32 of 85 jobs; preparation
changes expanded the later denominator. The separate 52-of-53 replay above
uses another denominator and the earlier policy.

The current 128 EPWs were independently rechecked on 6 October: hashes matched
both recorded receipts, ordered calendars and 35-field rows were correct, and
required exported values passed finite/range and dew-point checks. There are
112 common-year and 16 leap-year files, totaling 1,121,664 exported hours.
Historical v1/v2 EPWs and their per-job receipts are no longer available locally;
their retained status manifests support the earlier counts.

All current files are ``mixed_reconstructed``. Donors supply meteorology in
101 jobs, ERA5 in 35, and temporal filling in 126; these groups overlap.
Twenty-five jobs exceed 5% reconstructed required meteorological cells on the
buffered ingestion grid, ranging from 0.0114% to 100% across all jobs. This
fraction excludes solar and differs from exported-hour source fractions.
Five percent is descriptive, not an acceptance threshold. The run checks
completion and export usability, not local weather accuracy or event preservation.

The portable :download:`completion evidence summary
<../examples/data/completeness_2026-10-05.json>` includes definitions, source
commits, artifact hashes, warning counts and the audit checks. Its original
artifact directory is
``epsm_workflows/output/national-mf-se02-random-baseline-2026-10-05-v3-weather-shadow``;
the status, quality summary, runtime manifest, verification and per-job weather
and source receipts retain the full audit trail. Large EPWs and raw caches are
not distributed with the examples. Notebook 08 reads the summary offline.
