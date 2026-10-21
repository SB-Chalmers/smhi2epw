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

import csv
import json
import math
import os
import tempfile
from hashlib import sha256
from pathlib import Path


def stage_fwg_epw(source: Path, destination: Path, *, yearless_period: bool) -> None:
    """Copy a validated EPW, adapting only the current engine's period header.

    FWG Engine 1.1 rejects actual-year dates in DATA PERIODS. Its staged input
    uses month/day dates; every data record and the original file are preserved.
    """
    with source.open(encoding="utf-8-sig", newline="") as incoming:
        header = [incoming.readline() for _ in range(8)]
        if yearless_period:
            fields = next(csv.reader([header[7]]))
            fields[-2:] = ["/".join(value.split("/")[:2]) for value in fields[-2:]]
            header[7] = ",".join(fields) + "\n"
        with destination.open("x", encoding="utf-8", newline="") as outgoing:
            outgoing.writelines(header)
            for line in incoming:
                outgoing.write(line)


def restore_epw_calendar(source: Path, generated: Path) -> None:
    """Restore source calendar labels only when generated intervals match.

    FWG labels rows with a future period year. Require identical month/day/hour
    sequences and record counts before restoring source years, minute convention
    and calendar headers. Reject missing, shifted or reordered intervals rather
    than assigning weather to a different hour. Operates only on staged output.
    """
    with source.open(encoding="utf-8-sig", newline="") as handle:
        source_header = [handle.readline() for _ in range(8)]
        source_rows = list(csv.reader(handle))
    with generated.open(encoding="utf-8-sig", newline="") as handle:
        header = [handle.readline() for _ in range(8)]
        rows = list(csv.reader(handle))
    if len(rows) != len(source_rows):
        raise ValueError("FWG output record count differs from the source calendar")
    for original, row in zip(source_rows, rows):
        if (
            len(row) != 35
            or tuple(map(int, original[1:4])) != tuple(map(int, row[1:4]))
            or int(row[4]) not in (0, 60)
        ):
            raise ValueError("FWG output intervals differ from the source calendar")
        row[0], row[4] = original[0], original[4]
    header[4], header[7] = source_header[4], source_header[7]
    with generated.open("w", encoding="utf-8", newline="") as handle:
        handle.writelines(header)
        csv.writer(handle, lineterminator="\n").writerows(rows)


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
