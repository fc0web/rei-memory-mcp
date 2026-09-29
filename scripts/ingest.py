"""Ingest SEED_KERNEL JSONL dump into a rei-memory-mcp SQLite DB.

Usage:
    python scripts/ingest.py \\
        --input  data/seed-kernel-dump.jsonl \\
        --db     data/seed_kernel.db

Validation rules (Phase 1 spec § 5):
    1. ``tier`` must be one of proven / hypothesis / speculative
    2. ``body`` must be non-empty
    3. ``immutable: true`` records may not be overwritten in the DB
    4. ``id`` shape is permissive — the SEED_KERNEL uses three patterns
       (T-\\d+, invented-*, slug) and all three are accepted (藤本さん
       2026-08-19 判断)

Validation failure raises ``IngestError`` and aborts the whole run;
silent skip is not permitted — a truncated ingest that "looks fine" is
worse than a loud failure.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

# Allow running as `python scripts/ingest.py` without install
_THIS = Path(__file__).resolve()
sys.path.insert(0, str(_THIS.parent.parent / "src"))

from rei_memory_mcp.db import open_db  # noqa: E402
from rei_memory_mcp.search import VALID_TIERS  # noqa: E402


class IngestError(Exception):
    """Raised when a row fails validation. Aborts the ingest run."""


@dataclass
class IngestStats:
    inserted: int = 0
    updated: int = 0
    skipped_immutable: int = 0
    total_seen: int = 0


def _iter_jsonl(path: Path) -> Iterator[dict]:
    with path.open("r", encoding="utf-8") as f:
        for lineno, raw in enumerate(f, start=1):
            raw = raw.strip()
            if not raw:
                continue
            try:
                yield json.loads(raw)
            except json.JSONDecodeError as e:
                raise IngestError(f"line {lineno}: invalid JSON: {e}") from e


def validate_row(row: dict, lineno: int) -> None:
    """Enforce ingest spec (Phase 1). Raises IngestError on any failure."""
    _id = row.get("id")
    if not isinstance(_id, str) or not _id:
        raise IngestError(f"line {lineno}: id must be a non-empty string")

    tier = row.get("tier")
    if tier not in VALID_TIERS:
        raise IngestError(
            f"line {lineno} (id={_id!r}): tier must be one of "
            f"{VALID_TIERS}, got {tier!r}"
        )

    body = row.get("body")
    if not isinstance(body, str) or not body.strip():
        raise IngestError(f"line {lineno} (id={_id!r}): body must be a non-empty string")

    title = row.get("title")
    if not isinstance(title, str) or not title:
        raise IngestError(f"line {lineno} (id={_id!r}): title must be a non-empty string")

    created = row.get("created_at")
    if not isinstance(created, str) or not created:
        raise IngestError(f"line {lineno} (id={_id!r}): created_at required")

    updated = row.get("updated_at")
    if not isinstance(updated, str) or not updated:
        raise IngestError(f"line {lineno} (id={_id!r}): updated_at required")

    step = row.get("step", None)
    if step is not None and not isinstance(step, int):
        raise IngestError(f"line {lineno} (id={_id!r}): step must be int or null")

    immutable = row.get("immutable", 0)
    if immutable not in (0, 1, True, False):
        raise IngestError(
            f"line {lineno} (id={_id!r}): immutable must be 0, 1, true, or false"
        )

    body_sha256 = row.get("body_sha256")
    if body_sha256 is not None:
        if not isinstance(body_sha256, str) or len(body_sha256) != 64:
            raise IngestError(
                f"line {lineno} (id={_id!r}): body_sha256 must be a 64-char hex string or omitted"
            )


def _existing_immutable(conn: sqlite3.Connection, theory_id: str) -> bool:
    r = conn.execute(
        "SELECT immutable FROM theories WHERE id = ?", (theory_id,)
    ).fetchone()
    if r is None:
        return False
    return bool(r["immutable"])


def _fts_replace(conn: sqlite3.Connection, row: dict) -> None:
    """Update FTS entry for a theory (delete-then-insert).

    We manage FTS explicitly (rather than content='theories') so that
    the JSONL round-trip stays simple and inspection stays direct.
    """
    conn.execute("DELETE FROM theories_fts WHERE id = ?", (row["id"],))
    conn.execute(
        "INSERT INTO theories_fts (id, title, body) VALUES (?, ?, ?)",
        (row["id"], row["title"], row["body"]),
    )


def _upsert(conn: sqlite3.Connection, row: dict, stats: IngestStats) -> None:
    theory_id = row["id"]
    if _existing_immutable(conn, theory_id):
        raise IngestError(
            f"id={theory_id!r} is marked immutable in DB and cannot be overwritten"
        )

    existing = conn.execute(
        "SELECT body, updated_at FROM theories WHERE id = ?", (theory_id,)
    ).fetchone()
    exists = existing is not None

    # Preserve updated_at when body has not changed since last ingest.
    # If the dump supplies body_sha256 and it matches sha256(existing_body),
    # discard the incoming updated_at so MAX(updated_at) reflects the actual
    # last content change rather than the dump generation time.
    if exists and isinstance(row.get("body_sha256"), str):
        existing_sha = hashlib.sha256(existing["body"].encode("utf-8")).hexdigest()
        if existing_sha == row["body_sha256"]:
            row = dict(row)
            row["updated_at"] = existing["updated_at"]

    immutable_int = 1 if row.get("immutable") in (1, True) else 0
    payload = (
        row["id"],
        row["title"],
        row["body"],
        row["tier"],
        row.get("step"),
        row["created_at"],
        row["updated_at"],
        row.get("source"),
        immutable_int,
    )
    conn.execute(
        """
        INSERT INTO theories
            (id, title, body, tier, step, created_at, updated_at, source, immutable)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            title = excluded.title,
            body = excluded.body,
            tier = excluded.tier,
            step = excluded.step,
            updated_at = excluded.updated_at,
            source = excluded.source,
            immutable = excluded.immutable
        """,
        payload,
    )
    _fts_replace(conn, row)

    if exists:
        stats.updated += 1
    else:
        stats.inserted += 1


def ingest(
    input_path: Path,
    db_path: Path,
    verbose: bool = False,
) -> IngestStats:
    """Run the ingest. Fails loudly on any validation error."""
    conn = open_db(db_path)
    stats = IngestStats()
    try:
        with conn:  # single transaction; rollback on exception
            for lineno, row in enumerate(_iter_jsonl(input_path), start=1):
                stats.total_seen += 1
                validate_row(row, lineno)
                _upsert(conn, row, stats)
                if verbose and stats.total_seen % 500 == 0:
                    print(f"  ... {stats.total_seen} rows", file=sys.stderr)
    finally:
        conn.close()
    return stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--input", required=True, type=Path, help="JSONL input path")
    ap.add_argument("--db", required=True, type=Path, help="SQLite output path")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)

    if not args.input.exists():
        print(f"ingest: input not found: {args.input}", file=sys.stderr)
        return 2

    args.db.parent.mkdir(parents=True, exist_ok=True)

    try:
        stats = ingest(args.input, args.db, verbose=args.verbose)
    except IngestError as e:
        print(f"ingest failed: {e}", file=sys.stderr)
        return 1

    print(
        f"ingest OK: inserted={stats.inserted} updated={stats.updated} "
        f"total_seen={stats.total_seen}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
