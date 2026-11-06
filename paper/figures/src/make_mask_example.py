"""Derive example outage positions with the campaign's own sampler.

Runs epsm_workflows archive/2026-10-14 campaign_design.generate_panels on a
fully observed Stockholm 2021 calendar (the frozen references allow <= 1 %
missing cells, so real positions can differ slightly). Writes
data/mask_example.json, which fig_c_masking.py reads.

    python make_mask_example.py /path/to/epsm_workflows
"""

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

root = Path(sys.argv[1])
path = root / "archive/2026-10-14/examples/weather_imputation_sensitivity/campaign_design.py"
spec = importlib.util.spec_from_file_location("campaign_design", path)
cd = importlib.util.module_from_spec(spec)
sys.modules["campaign_design"] = cd
spec.loader.exec_module(cd)

year = 2021
index = pd.date_range(f"{year - 1}-12-31 00:00", f"{year + 1}-01-01 23:00", freq="h", tz="UTC")
cols = sorted({c for v in cd._SCOPES.values() for c in v})
originals = pd.DataFrame(np.ones((len(index), len(cols))), index=index, columns=cols)
out = []
for scope in ("meteorology", "solar"):
    for p in cd.generate_panels(originals, "stockholm", year, scopes=(scope,)):
        out.append({
            "scope": scope, "seed": p.seed, "hours": p.duration_hours if hasattr(p, "duration_hours") else None,
            "status": p.status if hasattr(p, "status") else None,
            "blocks": [[b.start_utc.isoformat(), b.end_utc.isoformat(), b.season] for b in p.blocks],
        })
Path(__file__).resolve().parents[1].joinpath("data/mask_example.json").write_text(json.dumps(out, indent=1))
print(len(out))
