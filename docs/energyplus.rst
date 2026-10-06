EnergyPlus application and release validation
=============================================

The package creates weather inputs independently of any building-model package.
Notebook 09 runs a local AMY through a small single-zone EnergyPlus fixture with
a south-facing window and ideal loads. The shared runner uses the standard
library for process execution and SQLite output inspection; ``epsm_core`` is not
required. Delivered ideal-load energy is thermal energy, not purchased
electricity or evidence of calibrated equipment performance.

Engine installation
-------------------

The required study-compatible engine is **24.2.0 build 94a887817b**, from the
official `v24.2.0a bug-fix release
<https://github.com/NatLabRockies/EnergyPlus/releases/tag/v24.2.0a>`_. The original
and corrected builds both report version 24.2.0, so the build identifier matters.
Official release assets include Linux, macOS Intel/ARM, and Windows archives and
checksums. Keep the adjacent IDD and libraries with the executable.

On Ubuntu 24.04 x86_64, the repository installer downloads the official archive
and verifies its fixed SHA-256::

   bash scripts/install_energyplus.sh /tmp/smhi2epw-energyplus-24.2.0
   export ENERGYPLUS_EXE=/tmp/smhi2epw-energyplus-24.2.0/energyplus

For another platform, install the matching official archive and set
``ENERGYPLUS_EXE`` or add its directory to ``PATH``. The engine is optional for
ordinary compilation and EPW analysis, but engine tests fail when it is absent
or has the wrong build. The notebook never downloads the engine or weather.

Running the lesson
------------------

Run notebook 00 first or set ``SMHI2EPW_EPW_PATH`` to a local actual-year EPW.
Launch Jupyter from the checkout and open ``examples/09_run_energyplus.ipynb``.
Regenerate weather produced before the actual-year header fix: EnergyPlus's
strict actual-weather reader requires years in the ``DATA PERIODS`` date fields,
as well as leap-day and weekday headers. Keep original study files intact and
compile replacement inputs in a new directory.
When launching elsewhere, set ``SMHI2EPW_EXAMPLES_DIR`` to the checkout's
``examples`` directory so the notebook can find its shared model and runner.

The runner sets explicit actual-year run-period boundaries, disables daylight
saving, and inspects an hourly weather calendar. Leap years retain 29 February.
SQLite output excludes warmup from the reported hourly series. EnergyPlus
interpolates weather internally; compare its outputs using matching interval
semantics rather than assuming every reported value equals a raw EPW sample.
Retain the EPW receipt, model, engine version, error log, and SQLite database.

Required CI and publication gate
--------------------------------

``.github/workflows/ci.yml`` runs on pull requests, main/master pushes, release
tags, manual dispatches, and a weekly schedule. Release validation requires:

* the Python source/static matrix and minimum-dependency tests;
* distribution building and metadata checks;
* offline tests against the installed wheel, outside the source checkout;
* documentation and notebook validation;
* deterministic provider-to-EnergyPlus integration and execution of notebook 09.

The engine job uses Ubuntu 24.04 and the checksum-pinned engine. It installs the
same uploaded wheel used by the distribution tests, checks its import location,
and runs without live provider requests. Fixtures exercise common/leap calendars
and recovery paths. Tests require a complete intended calendar, finite requested
outputs and useful model response. Logs and executed notebook outputs are saved
as CI artifacts even when validation fails.

The runner rejects every engine warning, severe error and fatal error. There
are no warning exceptions for the current fixture. Any future unavoidable
exception must specify the exact message, engine/fixture scope, maximum
occurrence count, and a reason tied to a feature the fixture does not use.
A broad warning suppression is not an acceptance rule. Weather-recovery
warnings remain separately visible in the EPW receipt.

The ``release-gate`` job requires every validation job to succeed; skipped or
missing engine validation cannot pass it. On a ``v*`` tag, the same workflow then
publishes the validated distributions to GitHub Releases and PyPI and deploys the
built documentation site. The tag must match the wheel's version. Configure
branch protection to require ``release-gate`` if passing validation must also be
enforced before merging.

PyPI needs a one-time trusted-publisher entry for this repository before the
first upload: project ``smhi2epw``, owner ``SB-Chalmers``, repository
``smhi2epw``, workflow ``ci.yml``, and no GitHub environment. Add it from the
PyPI project's Publishing settings using the
`PyPI trusted-publisher guide <https://docs.pypi.org/trusted-publishers/>`_.
This lets GitHub Actions publish with short-lived OIDC credentials instead of a
stored API token.

Live provider tests and the live getting-started notebook run only on schedule
or manual dispatch. Their purpose is to check current service behavior; they
are separate from reproducible release acceptance.

These checks establish that generated weather can drive the shared consumer
fixture. They do not establish building-site weather accuracy, preservation of
reconstructed extremes, archetype qualification, or building calibration.

Observed warning case
---------------------

Recorded live checks before the pvlib implementation found no warnings for
Gothenburg 2016 and 2023. The 2020 file completed with no severe errors but
produced two ``PsyPsatFnTemp`` warnings
from ``PsyTwbFnTdbWPb``, despite valid weather inputs. They persisted at twelve
timesteps per hour. The tutorial's strict validator rejected that recorded file.

The reported negative temperatures are internal wet-bulb trial values, not EPW
dry-bulb values; see the `EnergyPlus psychrometric implementation
<https://raw.githubusercontent.com/NREL/EnergyPlus/v24.2.0/src/EnergyPlus/Psychrometrics.cc>`_.
This does not justify changing valid input weather or accepting the warnings
for cooling analysis. Engine completion alone does not establish acceptance.
