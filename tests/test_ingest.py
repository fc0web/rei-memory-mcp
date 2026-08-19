"""Ingest validation tests — each spec rule must abort the run loudly."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ingest import IngestError, ingest, validate_row


@pytest.fixture
def valid_row():
    return {
        "id": "T-9001",
        "title": "テスト理論",
        "body": "テスト用の本文",
        "tier": "hypothesis",
        "step": None,
        "created_at": "2026-08-19T00:00:00Z",
        "updated_at": "2026-08-19T00:00:00Z",
        "source": "test",
        "immutable": 0,
    }


def _write_jsonl(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "input.jsonl"
    with p.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return p


def test_valid_row_passes(valid_row):
    validate_row(valid_row, lineno=1)  # no exception


def test_bad_id_format_still_accepted(valid_row):
    """id shape is permissive (spec-tightening 2026-08-19): slug allowed."""
    valid_row["id"] = "dfumt-anything-slug"
    validate_row(valid_row, lineno=1)  # no exception


def test_missing_id_raises(valid_row):
    del valid_row["id"]
    with pytest.raises(IngestError, match="id must be"):
        validate_row(valid_row, lineno=1)


def test_empty_id_raises(valid_row):
    valid_row["id"] = ""
    with pytest.raises(IngestError, match="id must be"):
        validate_row(valid_row, lineno=1)


def test_invalid_tier_raises(valid_row):
    """Rule 2: tier must be one of the three."""
    valid_row["tier"] = "unknown"
    with pytest.raises(IngestError, match="tier must be"):
        validate_row(valid_row, lineno=1)


def test_missing_tier_raises(valid_row):
    del valid_row["tier"]
    with pytest.raises(IngestError, match="tier must be"):
        validate_row(valid_row, lineno=1)


def test_empty_body_raises(valid_row):
    """Rule 3: body must be non-empty."""
    valid_row["body"] = ""
    with pytest.raises(IngestError, match="body must be"):
        validate_row(valid_row, lineno=1)


def test_whitespace_body_raises(valid_row):
    """body='   ' should also be rejected."""
    valid_row["body"] = "   \n\t  "
    with pytest.raises(IngestError, match="body must be"):
        validate_row(valid_row, lineno=1)


def test_immutable_overwrite_raises(tmp_path, valid_row):
    """Rule 4: overwriting immutable=1 record is rejected."""
    # First ingest: insert with immutable=1
    valid_row["immutable"] = 1
    p1 = _write_jsonl(tmp_path, [valid_row])
    stats = ingest(p1, tmp_path / "test.db")
    assert stats.inserted == 1

    # Second ingest: try to overwrite with different body
    valid_row["body"] = "改変された本文"
    valid_row["immutable"] = 0  # even trying to unset immutable
    p2 = _write_jsonl(tmp_path, [valid_row])
    with pytest.raises(IngestError, match="immutable"):
        ingest(p2, tmp_path / "test.db")


def test_valid_ingest_end_to_end(tmp_path, valid_row):
    p = _write_jsonl(tmp_path, [valid_row])
    db = tmp_path / "test.db"
    stats = ingest(p, db)
    assert stats.inserted == 1
    assert stats.updated == 0
    assert stats.total_seen == 1


def test_re_ingest_updates_mutable_row(tmp_path, valid_row):
    """Same id + immutable=0 should update on re-ingest, not error."""
    p1 = _write_jsonl(tmp_path, [valid_row])
    db = tmp_path / "test.db"
    ingest(p1, db)

    valid_row["body"] = "改訂本文"
    p2 = _write_jsonl(tmp_path, [valid_row])
    stats = ingest(p2, db)
    assert stats.updated == 1
    assert stats.inserted == 0


def test_first_bad_row_aborts_whole_run(tmp_path, valid_row):
    """Silent skip is forbidden — one bad row must fail the whole run."""
    bad = dict(valid_row)
    bad["id"] = "T-9002"
    bad["tier"] = "??unknown??"
    good_after = dict(valid_row)
    good_after["id"] = "T-9003"

    p = _write_jsonl(tmp_path, [valid_row, bad, good_after])
    db = tmp_path / "test.db"
    with pytest.raises(IngestError):
        ingest(p, db)

    # Because ingest is one transaction, none of the rows should be committed
    from rei_memory_mcp.db import open_db
    conn = open_db(db)
    try:
        n = conn.execute("SELECT COUNT(*) FROM theories").fetchone()[0]
        # The `with conn:` context manager rolls back on exception, so 0 rows
        assert n == 0
    finally:
        conn.close()


def test_invalid_json_line_raises(tmp_path):
    p = tmp_path / "bad.jsonl"
    p.write_text('{"id":"T-1","title":"x","body":"y","tier":"proven",\n', encoding="utf-8")
    with pytest.raises(IngestError, match="invalid JSON"):
        ingest(p, tmp_path / "bad.db")


def test_missing_created_at_raises(valid_row):
    del valid_row["created_at"]
    with pytest.raises(IngestError, match="created_at"):
        validate_row(valid_row, lineno=1)
