# File: src/smhi2epw/io.py
# Purpose: Safely read and publish weather workflow artifacts.
# SPDX-License-Identifier: MIT
# Copyright (c) 2026 smhi2epw contributors
# License: See LICENSE at the project root.
# Author: OpenAI Codex, implementing the requested smhi2epw feature.
# Created/modified: 2026-10-21. Changelog: Add atomic artifact publication.
"""Read strict JSON and publish complete weather artifacts without clobbering.

Paths are explicit and relative to the caller's working directory. Callers
create parent directories. Publication uses a hard link to enforce refusal of
existing destinations, including concurrent writers. These are single-file
operations, not transactions across weather and receipts.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
from hashlib import sha256
from pathlib import Path


def file_sha256(path: Path) -> str:
    """Read a file in bounded blocks and return its SHA-256 identity."""
    digest = sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def publish_file(staged: Path, destination: Path) -> None:
    """Publish a complete staged file on the same filesystem without overwrite.

    Raises FileExistsError if any writer already owns the destination. The
    staged file remains available; callers remove it when staging ends.
    Unsupported hard links fail explicitly without a direct-write fallback.
    """
    os.link(staged, destination)


def write_json(path: Path, payload: dict, *, overwrite: bool = False) -> None:
    """Stage UTF-8 JSON and atomically publish it in an existing directory.

    Nonfinite numbers fail before publication. The default refuses replacement
    even during a writer race; overwrite=True explicitly replaces a progress
    receipt. Temporary files are removed after success or failure.
    """
    content = json.dumps(payload, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(
            "w", dir=path.parent, encoding="utf-8", delete=False
        ) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        if overwrite:
            temporary.replace(path)
        else:
            publish_file(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _unique_fields(pairs: list[tuple[str, object]]) -> dict:
    """Reject duplicate JSON fields rather than choosing a winning value."""
    result: dict = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _finite_float(value: str) -> float:
    """Reject nonfinite JSON numbers, including ordinary decimal overflow."""
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("nonfinite JSON numbers are not supported")
    return number


def read_json(path: Path) -> object:
    """Read UTF-8 JSON without duplicate fields or nonfinite numeric extensions.

    Returns decoded values without an open file handle. Format-specific
    validation belongs to the owning operation. Invalid encoding, JSON and
    unavailable paths raise their original UnicodeError, ValueError or OSError.
    """
    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_unique_fields,
        parse_constant=_finite_float,
        parse_float=_finite_float,
    )
