"""smhi2epw - Compile SMHI open data into EnergyPlus Weather (.epw) AMY files.

Public API
----------
- :func:`compile_epw`     : high-level one-call compiler (URL/file output).
- :class:`StationMeta`    : station metadata container.
- :class:`EPWConfig`      : compilation configuration.
- :class:`Smhi2EpwError`  : base exception for the package.
- :class:`DataGapError`   : raised when an unfillable observation gap is found.
"""

from .errors import DataGapError, IngestionError, Smhi2EpwError
from .compiler import EPWConfig, compile_epw
from .ingestion import StationMeta

__all__ = [
    "compile_epw",
    "EPWConfig",
    "StationMeta",
    "Smhi2EpwError",
    "DataGapError",
    "IngestionError",
    "__version__",
]

__version__ = "1.1.0"
