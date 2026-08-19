"""Immutability protection tests.

Phase 1 is read-only from the MCP tool surface, but ingest MUST honour
immutable=1 records — that is the schema-level guard for Peace Axiom #196
and similar永久理論.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ingest import IngestError, ingest


def _write_jsonl(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "input.jsonl"
    with p.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return p


def _base_row(theory_id: str, **overrides) -> dict:
    row = {
        "id": theory_id,
        "title": "永久理論",
        "body": "この理論は永久に保持される。",
        "tier": "proven",
        "step": None,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
        "source": "seed-kernel",
        "immutable": 1,
    }
    row.update(overrides)
    return row


def test_immutable_record_survives_body_overwrite_attempt(tmp_path):
    r_original = _base_row("T-196")
    p = _write_jsonl(tmp_path, [r_original])
    db = tmp_path / "im.db"
    ingest(p, db)

    r_attempt = _base_row(
        "T-196", body="改変を試みる本文", title="改変タイトル"
    )
    p2 = _write_jsonl(tmp_path, [r_attempt])
    with pytest.raises(IngestError):
        ingest(p2, db)

    # Row should remain in original state
    from rei_memory_mcp.db import open_db
    conn = open_db(db)
    try:
        row = conn.execute(
            "SELECT title, body FROM theories WHERE id = 'T-196'"
        ).fetchone()
        assert row["title"] == "永久理論"
        assert "永久に保持" in row["body"]
    finally:
        conn.close()


def test_immutable_survives_tier_downgrade_attempt(tmp_path):
    r_original = _base_row("T-196")
    p = _write_jsonl(tmp_path, [r_original])
    db = tmp_path / "im.db"
    ingest(p, db)

    r_attempt = _base_row("T-196", tier="speculative")
    p2 = _write_jsonl(tmp_path, [r_attempt])
    with pytest.raises(IngestError):
        ingest(p2, db)

    from rei_memory_mcp.db import open_db
    conn = open_db(db)
    try:
        row = conn.execute(
            "SELECT tier FROM theories WHERE id = 'T-196'"
        ).fetchone()
        assert row["tier"] == "proven"
    finally:
        conn.close()


def test_mutable_record_updates_freely(tmp_path):
    """Non-immutable rows should update on re-ingest without error."""
    r = _base_row("T-3000", immutable=0)
    p = _write_jsonl(tmp_path, [r])
    db = tmp_path / "im.db"
    ingest(p, db)

    r2 = _base_row("T-3000", immutable=0, body="更新後")
    p2 = _write_jsonl(tmp_path, [r2])
    stats = ingest(p2, db)
    assert stats.updated == 1

    from rei_memory_mcp.db import open_db
    conn = open_db(db)
    try:
        row = conn.execute(
            "SELECT body FROM theories WHERE id = 'T-3000'"
        ).fetchone()
        assert row["body"] == "更新後"
    finally:
        conn.close()


def test_immutable_boolean_true_accepted(tmp_path):
    """JSON `true` should be treated as immutable (=1)."""
    r = _base_row("T-4000", immutable=True)
    p = _write_jsonl(tmp_path, [r])
    db = tmp_path / "im.db"
    ingest(p, db)

    r_attempt = _base_row("T-4000", body="overwrite")
    p2 = _write_jsonl(tmp_path, [r_attempt])
    with pytest.raises(IngestError):
        ingest(p2, db)
