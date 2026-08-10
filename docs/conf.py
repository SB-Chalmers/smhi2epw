"""Sphinx configuration for the smhi2epw documentation site."""

from __future__ import annotations

from importlib.metadata import version as metadata_version

project = "smhi2epw"
author = "smhi2epw contributors"
release = metadata_version("smhi2epw")
version = release

extensions = [
    "nbsphinx",
    "nbsphinx_link",
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.doctest",
    "sphinx.ext.intersphinx",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "**/.ipynb_checkpoints"]
autosummary_generate = True
autodoc_typehints = "description"
autodoc_member_order = "bysource"
napoleon_google_docstring = False
napoleon_numpy_docstring = True
napoleon_use_param = True
napoleon_use_rtype = True
nbsphinx_execute = "never"
doctest_test_doctest_blocks = "default"
doctest_global_setup = """
import numpy as np
import pandas as pd
import requests

from smhi2epw.cli import build_parser
from smhi2epw.export import *
from smhi2epw.export import _fmt_float, _fmt_int
from smhi2epw.ingestion import *
from smhi2epw.ingestion import _clean_station_name, _haversine_km, _year_bounds_ms
from smhi2epw.processing import *
from smhi2epw.processing import (
    _fill_wind_direction,
    _gap_runs,
    _linear_estimate,
    _max_gap_length,
)
from smhi2epw.solar import *
"""

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "numpy": ("https://numpy.org/doc/stable", None),
    "pandas": ("https://pandas.pydata.org/docs", None),
    "requests": ("https://requests.readthedocs.io/en/latest", None),
}

html_theme = "sphinx_rtd_theme"
html_theme_options = {
    "collapse_navigation": False,
    "navigation_depth": 4,
}
html_static_path: list[str] = []
