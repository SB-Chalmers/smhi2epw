Troubleshooting
===============

``No module named smhi2epw``
----------------------------

Activate the environment in which the package was installed. In a notebook,
print ``sys.executable`` and select that interpreter as the kernel.

No qualifying station
---------------------

Automatic selection requires one station to cover the full year for every
required observed parameter. Try a nearby coordinate, inspect SMHI station
availability, or select a known station explicitly. Do not work around this by
merging unrelated stations silently.

Required gap exceeds 48 hours
-----------------------------

The source record is incomplete beyond the supported scientific method. Choose
another full-year station or another year. Optional cloud data may remain
missing, but temperature, humidity, pressure, wind, and required solar cannot.

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
