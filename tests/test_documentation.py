"""Documentation coverage and notebook-quality tests."""

from __future__ import annotations

import ast
import importlib.util
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from smhi2epw.export import build_header, expected_rows, write_epw

ROOT = Path(__file__).parents[1]
SOURCE = ROOT / "src" / "smhi2epw"
EXAMPLES = ROOT / "examples"

EXPECTED_NOTEBOOKS = [
    "00_getting_started.ipynb",
    "01_inspect_an_epw.ipynb",
    "02_compare_locations.ipynb",
    "03_compare_years.ipynb",
    "04_identify_heatwaves.ipynb",
    "05_compare_amy_to_tmy.ipynb",
    "06_data_quality_and_gap_filling.ipynb",
    "07_solar_components.ipynb",
    "08_batch_generation.ipynb",
    "09_run_energyplus.ipynb",
]


def _source_symbols(path: Path):
    """Yield documentable modules, classes, functions, and methods."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    yield path.name, tree
    for node in ast.walk(tree):
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            yield f"{path.name}:{node.lineno}:{node.name}", node


def test_every_source_symbol_has_a_substantive_docstring():
    missing = []
    too_short = []
    for path in sorted(SOURCE.glob("*.py")):
        for label, node in _source_symbols(path):
            docstring = ast.get_docstring(node)
            if not docstring:
                missing.append(label)
            elif len(docstring.split()) < 5:
                too_short.append(label)
    assert not missing, f"missing docstrings: {missing}"
    assert not too_short, (
        f"docstrings are too short to teach their contract: {too_short}"
    )


def test_numbered_notebook_curriculum_is_complete():
    actual = sorted(path.name for path in EXAMPLES.glob("*.ipynb"))
    assert actual == EXPECTED_NOTEBOOKS
    assert (EXAMPLES / "README.md").is_file()
    assert not list(EXAMPLES.glob("*.py")), "tutorials are intentionally notebook-only"


@pytest.mark.parametrize("name", EXPECTED_NOTEBOOKS)
def test_notebook_metadata_content_and_code_syntax(name):
    path = EXAMPLES / name
    notebook = json.loads(path.read_text(encoding="utf-8"))
    assert notebook["nbformat"] == 4

    policy = notebook["metadata"]["smhi2epw"]
    assert policy["execution_mode"] in {
        "offline",
        "live",
        "prerequisite",
        "external-data",
    }
    assert isinstance(policy["requires_network"], bool)
    assert isinstance(policy["requires_tmy"], bool)

    markdown = "\n".join(
        "".join(cell.get("source", []))
        for cell in notebook["cells"]
        if cell["cell_type"] == "markdown"
    )
    lowered = markdown.lower()
    for phrase in (
        "learning objectives",
        "expected runtime",
        "key takeaways",
        "try it",
    ):
        assert phrase in lowered, f"{name} is missing '{phrase}'"

    all_source = "\n".join(
        "".join(cell.get("source", [])) for cell in notebook["cells"]
    )
    forbidden = [r"/Users/", r"/home/[^/]+/", r"[A-Za-z]:\\Users\\", r"api[_-]?key\s*="]
    assert not any(
        re.search(pattern, all_source, re.IGNORECASE) for pattern in forbidden
    )

    tags = {
        tag
        for cell in notebook["cells"]
        for tag in cell.get("metadata", {}).get("tags", [])
    }
    if policy["requires_network"]:
        assert "requires-network" in tags
    if policy["requires_tmy"]:
        assert "requires-tmy" in tags
    if policy.get("requires_energyplus", False):
        assert "requires-energyplus" in tags

    for cell_number, cell in enumerate(notebook["cells"], start=1):
        if cell["cell_type"] != "code":
            continue
        assert cell.get("execution_count") is None
        assert cell.get("outputs") == []
        source = "".join(cell.get("source", []))
        ast.parse(source, filename=f"{name}:cell-{cell_number}")


@pytest.mark.skipif(
    importlib.util.find_spec("nbclient") is None
    or importlib.util.find_spec("nbformat") is None,
    reason="tutorial extras are not installed",
)
@pytest.mark.parametrize(
    "name",
    [
        "06_data_quality_and_gap_filling.ipynb",
        "07_solar_components.ipynb",
    ],
)
def test_self_contained_offline_notebooks_execute(name, tmp_path):
    """Execute notebooks that promise to need neither network nor prior files."""
    import nbformat
    from nbclient import NotebookClient

    notebook = nbformat.read(EXAMPLES / name, as_version=4)
    client = NotebookClient(
        notebook,
        timeout=120,
        kernel_name="python3",
        resources={"metadata": {"path": str(tmp_path)}},
    )
    client.execute()


def _write_notebook_epw(path: Path, year: int, temperature_offset: float) -> None:
    """Create a deterministic full-year EPW fixture for notebook execution."""
    count = expected_rows(year)
    index = pd.date_range(f"{year}-01-01 01:00", periods=count, freq="h")
    cycle = np.sin(np.arange(count) * 2 * np.pi / 24)
    dry_bulb = temperature_offset + 8 * cycle
    frame = pd.DataFrame(
        {
            "dry_bulb": dry_bulb,
            "dew_point": dry_bulb - 4,
            "relative_humidity": 70,
            "pressure": 101325,
            "etrh": 500,
            "etrn": 1367,
            "horizontal_ir": 300,
            "ghi": np.clip(500 * cycle, 0, None),
            "dni": np.clip(600 * cycle, 0, None),
            "dhi": np.clip(150 * cycle, 0, None),
            "wind_direction": 180,
            "wind_speed": 3,
            "sky_cover": 5,
        },
        index=index,
    )
    header = build_header(
        "Gothenburg", "VG", "SWE", "999999", 57.7, 12.0, 1, 3, year, 71420
    )
    write_epw(str(path), header, frame, year)


@pytest.mark.skipif(
    importlib.util.find_spec("nbclient") is None
    or importlib.util.find_spec("nbformat") is None,
    reason="tutorial extras are not installed",
)
def test_epw_inspection_notebook_executes_with_prior_output(tmp_path, monkeypatch):
    """Execute the inspection lesson with a generated prerequisite EPW."""
    import nbformat
    from nbclient import NotebookClient

    epw_path = tmp_path / "gothenburg_2023.epw"
    _write_notebook_epw(epw_path, 2023, 10.0)
    monkeypatch.setenv("SMHI2EPW_EPW_PATH", str(epw_path))
    notebook = nbformat.read(EXAMPLES / "01_inspect_an_epw.ipynb", as_version=4)
    NotebookClient(
        notebook,
        timeout=120,
        kernel_name="python3",
        resources={"metadata": {"path": str(tmp_path)}},
    ).execute()


@pytest.mark.skipif(
    importlib.util.find_spec("nbclient") is None
    or importlib.util.find_spec("nbformat") is None,
    reason="tutorial extras are not installed",
)
def test_amy_tmy_notebook_executes_with_local_override(tmp_path, monkeypatch):
    """Exercise the comparison notebook without contacting OneBuilding."""
    import nbformat
    from nbclient import NotebookClient

    amy_path = tmp_path / "amy.epw"
    tmy_path = tmp_path / "tmy.epw"
    _write_notebook_epw(amy_path, 2023, 10.0)
    _write_notebook_epw(tmy_path, 2021, 8.0)
    monkeypatch.setenv("SMHI2EPW_AMY_PATH", str(amy_path))
    monkeypatch.setenv("SMHI2EPW_TMY_PATH", str(tmy_path))

    notebook = nbformat.read(EXAMPLES / "05_compare_amy_to_tmy.ipynb", as_version=4)
    NotebookClient(
        notebook,
        timeout=120,
        kernel_name="python3",
        resources={"metadata": {"path": str(tmp_path)}},
    ).execute()
