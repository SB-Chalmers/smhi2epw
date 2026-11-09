# Unreleased

- Automatic mode: solar outages longer than 3 hours go to the next source
  (STRÅNG for a measured-GHI outage, otherwise ERA5) instead of daily profiles.
  Their length is measured before fully dark hours are zeroed; previously night
  split a week-long outage into daytime pieces that were each filled by
  repeating a nearby day, so ERA5 was never reached.
- Automatic mode: general-weather outages longer than 48 hours skip assessed
  donors and go to ERA5. Strict mode keeps donors at any length.
- Both limits are set in `constants.py`; see `docs/weather_recovery.rst`.

# Release 1.3.0 — batch weather and morphing

Generate AMY batches across locations and years with retained artifact and
provenance manifests. Optional SSP/RCP morphing uses the existing providers and
Future Weather Generator integration. Source calendars remain distinct from
future climate periods; missing tools and damaged outputs fail explicitly.
See the [morphing guide](docs/morphing.rst) for prerequisites and scientific limits.

# Release 1.2.0 — 15 October 2026

Weather acquisition, station selection, cache/recovery decisions and EPW publication. Library compilation no longer configures an output handler automatically.

Libraries emit through Python's standard logging without configuring output.
Instrumented operations accept optional keyword-only `log_context`; identifiers
stay separate from scientific inputs, saved models and cache keys. INFO shows
major stages; DEBUG adds decisions and timing. Standalone commands support
`--log-level`, including `OFF`, where the package provides a command.

The EPSM application configures the combined stderr and optional DEBUG JSONL
output with `configure_logging`; `enabled=False` disables both destinations.
Existing callers and supported older collaborator signatures remain supported.
No new mandatory dependency is introduced by the logging implementation.

The coordinated release was requested for manual review and local validation
because GitHub refused to start several hosted jobs due to account billing.
Hosted checks that did not run are not counted as passes. See the
[coordinated verification record](https://github.com/SB-Chalmers/epsm_development/blob/main/docs/logging-verification.md)
for exact tested revisions, executed checks and remaining limitations.
