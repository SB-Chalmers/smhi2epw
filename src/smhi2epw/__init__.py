"""smhi2epw - Compile SMHI open data into EnergyPlus Weather (.epw) AMY files.

Public API
----------
- :func:`compile_epw`     : high-level one-call compiler (URL/file output).
- :class:`StationMeta`    : station metadata container.
- :class:`EPWConfig`      : compilation configuration.
- :class:`Smhi2EpwError`  : base exception for the package.
- :class:`DataGapError`   : raised when an unfillable observation gap is found.
"""

from importlib.metadata import PackageNotFoundError, version

from .compiler import EPWConfig, compile_epw
from .errors import DataGapError, IngestionError, Smhi2EpwError, ValidationError
from .ingestion import StationMeta

__all__ = [
    "compile_epw",
    "EPWConfig",
    "StationMeta",
    "Smhi2EpwError",
    "DataGapError",
    "IngestionError",
    "ValidationError",
    "__version__",
]

try:
    __version__ = version("smhi2epw")
except PackageNotFoundError:  # pragma: no cover - source tree without installation
    __version__ = "0+unknown"
