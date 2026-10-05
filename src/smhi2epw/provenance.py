"""Machine-readable AMY receipts; see docs/provenance.rst and SMHI archives.

Only payloads requested by this compilation are recorded. A hash covers the
UTF-8 response consumed by the parser, not unrelated files in a shared cache.
"""

import hashlib
import json
import os
import tempfile
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path


def write_provenance(config, result, client):
    """Atomically save configuration, used payload fingerprints and EPW quality.

    Custom clients without receipts remain usable, but their raw-response
    coverage is explicitly incomplete. Never manufacture source hashes.
    """
    from importlib.metadata import PackageNotFoundError, version

    try:
        package_version = version("smhi2epw")
    except PackageNotFoundError:
        package_version = "source-checkout"
    raw = getattr(client, "response_receipts", None)
    payload = {
        "schema_version": 1,
        "accessed_at_utc": datetime.now(timezone.utc).isoformat(),
        "package_version": package_version,
        "configuration": asdict(config),
        "result": asdict(result),
        "epw_sha256": hashlib.sha256(Path(result.output_path).read_bytes()).hexdigest(),
        "raw_response_receipts_complete": raw is not None,
        "raw_responses": sorted(
            (raw or {}).values(), key=lambda x: (x["url"], x["sha256"])
        ),
        "source_code_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(__file__).parent.glob("*.py"))
        },
    }
    target = Path(config.provenance_path)
    name = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", dir=target.parent, delete=False
        ) as handle:
            name = handle.name
            json.dump(payload, handle, indent=2, default=str, allow_nan=False)
            handle.write("\n")
        os.replace(name, target)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)
    return payload
