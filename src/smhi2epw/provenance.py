"""Machine-readable AMY receipts; see docs/provenance.rst and SMHI archives.

Only payloads requested by this compilation are recorded. A hash covers the
UTF-8 response consumed by the parser, not unrelated files in a shared cache.
"""

import hashlib
import json
import os
import tempfile
from contextlib import nullcontext
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def write_provenance(config: Any, result: Any, client: Any) -> dict[str, Any]:
    """Atomically save configuration, used payload fingerprints and EPW quality.

    Only clients explicitly providing compilation-scoped recording can claim
    complete raw-response coverage. Custom clients remain usable, but an
    unscoped lifetime collection is omitted to avoid unrelated requests.

    The UTF-8 JSON sidecar replaces an existing file only after serialization
    succeeds. Filesystem and serialization errors propagate to the caller,
    which determines whether to warn or fail under its weather policy. The
    already-written EPW is never modified by a sidecar failure.
    """
    from importlib.metadata import PackageNotFoundError, version

    try:
        package_version = version("smhi2epw")
    except PackageNotFoundError:
        package_version = "source-checkout"
    scoped = getattr(client, "response_receipts_scoped", False) is True
    raw = getattr(client, "response_receipts", None) if scoped else None
    receipts_complete = isinstance(raw, dict)
    with getattr(client, "_receipt_lock", nullcontext()):
        responses = [dict(receipt) for receipt in (raw or {}).values()]
    payload = {
        "schema_version": 1,
        "accessed_at_utc": datetime.now(timezone.utc).isoformat(),
        "package_version": package_version,
        "pvlib_version": version("pvlib"),
        "configuration": asdict(config),
        "result": asdict(result),
        "epw_sha256": hashlib.sha256(Path(result.output_path).read_bytes()).hexdigest(),
        "raw_response_receipts_complete": receipts_complete,
        "raw_response_receipts_incomplete_reason": (
            None if receipts_complete else "client lacks compilation-scoped recording"
        ),
        "raw_responses": sorted(responses, key=lambda x: (x["url"], x["sha256"])),
        "source_code_sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(Path(__file__).parent.glob("*.py"))
        },
    }
    target = Path(config.provenance_path)
    name = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", newline="\n", dir=target.parent, delete=False
        ) as handle:
            name = handle.name
            json.dump(
                payload,
                handle,
                indent=2,
                default=str,
                allow_nan=False,
                ensure_ascii=False,
            )
            handle.write("\n")
        os.replace(name, target)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)
    return payload
