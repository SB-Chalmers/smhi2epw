"""Compile SMHI open data into EnergyPlus Weather Actual Meteorological Years.

The top-level namespace contains the stable entry points needed by most users.
Lower-level ingestion, processing, solar, and export modules remain available
for teaching and advanced quality-control workflows.

Public API
----------
- :func:`compile_epw`: high-level one-call compiler.
- :func:`read_epw`: load an AMY or TMY into pandas.
- :class:`EPWConfig`: compilation configuration.
- :class:`StationMeta`: station metadata container.
- :class:`Smhi2EpwError`: common expected-error boundary.

Examples
--------
>>> from smhi2epw import EPWConfig, compile_epw, read_epw
>>> config = EPWConfig(2023, "gothenburg.epw", station_id=71420)
>>> result = compile_epw(config)  # doctest: +SKIP
>>> weather = read_epw(result.output_path)  # doctest: +SKIP
"""

from importlib.metadata import PackageNotFoundError, version

from .compiler import EPWConfig, compile_epw
from .errors import DataGapError, IngestionError, Smhi2EpwError, ValidationError
from .ingestion import StationMeta
from .reader import EPW_COLUMNS, read_epw

__all__ = [
    "compile_epw",
    "EPWConfig",
    "StationMeta",
    "Smhi2EpwError",
    "DataGapError",
    "IngestionError",
    "ValidationError",
    "read_epw",
    "EPW_COLUMNS",
    "__version__",
]

try:
    __version__ = version("smhi2epw")
except PackageNotFoundError:  # pragma: no cover - source tree without installation
    __version__ = "0+unknown"
