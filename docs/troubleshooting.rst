Troubleshooting
===============

``No module named smhi2epw``
----------------------------

Activate the environment in which the package was installed. In a notebook,
print ``sys.executable`` and select that interpreter as the kernel.

No qualifying station
---------------------

Automatic weather policy prefers full coverage but can select a partial station
or proceed with same-year reanalysis when coordinates are available. Review the
reported source failure and reanalysis warnings. Strict policy requires a
qualifying station; inspect SMHI availability or select a known station
explicitly. A station-only request cannot proceed if no metadata resolves its
coordinates; provide the intended latitude and longitude in that case.

Required gap exceeds 48 hours
-----------------------------

Temporal filling stops at 48 hours. Automatic policy attempts assessed donors
and then same-year ERA5 for longer gaps. If recovery still fails, inspect which
sources were unavailable or physically unusable, then retry source access or
choose another station. Strict mode requires adequate permitted source coverage;
``--metobs-gap-fallback`` allows assessed donors without enabling reanalysis.
Do not substitute another year's weather for an actual-year request.

Reanalysis unavailable or quota exceeded
----------------------------------------

Automatic mode requires Open-Meteo access only when primary weather and donors
cannot complete the year. Retain the cache and avoid repeated refreshes in batch
work. Check provider service limits and noncommercial access requirements. The
packaged adapter does not configure a commercial customer endpoint or API key.
A future year or a recent, incomplete archive cannot be filled with a different
year and remains an explicit failure.

EPW exists but provenance writing failed
----------------------------------------

The EPW is validated and atomically written before the sidecar. Automatic
policy returns that valid EPW with a ``provenance_write_failed`` warning if a
later sidecar filesystem error prevents saving provenance; strict policy reports
an error. Check that the sidecar parent exists, that its path differs from the
EPW and that it is writable, then rerun with cached source data. Do not treat
a missing sidecar as a verified audit trail.

Fractional UTC offset rejected
------------------------------

The source is hourly and the release targets Nordic whole-hour standard time.
Fractional shifting would require an explicit resampling method and is rejected
instead of silently producing missing rows.

Stale or malformed cache
------------------------

Malformed JSON is removed and fetched once automatically. Use ``refresh=True``
or CLI ``--refresh`` when SMHI has legitimately revised an otherwise valid
cached response. Disabling the cache is useful for tests but discouraged for
normal repeated work.

TMY comparison cannot download or find a file
---------------------------------------------

Notebook 05 downloads the explicitly linked OneBuilding Gothenburg TMYx ZIP on
its first run, extracts only the EPW member, and caches it below
``examples/output/onebuilding_tmyx``. Confirm that the OneBuilding host is
reachable and delete an incomplete ``.epw.part`` file before retrying. For
offline use, point ``SMHI2EPW_TMY_PATH`` to a lawfully obtained local EPW.
Paths should be created with :class:`pathlib.Path`, not copied from another
user's computer.
