"""Shared pytest fixtures for rei-memory-mcp.

Uses in-memory SQLite so tests never touch disk.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Make src/ importable without installing the package
_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "src"))
sys.path.insert(0, str(_ROOT / "scripts"))

from rei_memory_mcp.db import init_schema, connect  # noqa: E402


@pytest.fixture
def db():
    """Fresh in-memory DB with schema applied."""
    conn = connect(":memory:")
    init_schema(conn)
    try:
        yield conn
    finally:
        conn.close()


@pytest.fixture
def seed(db):
    """Populate the in-memory DB with a fixed miniature theory set.

    Deliberately mixes:
    - Japanese and Latin text (for trigram tokenizer)
    - all three tiers
    - step present / absent
    - immutable / mutable
    - three id patterns (T-\\d+, invented-*, slug)
    - cross-referencing links of all four kinds
    """
    rows = [
        # (id, title, body, tier, step, created, updated, source, immutable)
        (
            "T-100",
            "七値論理の初期定式化",
            "七値論理は真偽以外に BOTH / NEITHER / INFINITY / ZERO を含む枠組み。",
            "proven",
            100,
            "2026-01-01T00:00:00Z",
            "2026-01-01T00:00:00Z",
            "seed-kernel",
            0,
        ),
        (
            "T-200",
            "平和公理 #196 は不変である",
            "平和公理 #196 は Rei-AIOS 全体で不変 TRUE として保持される。",
            "proven",
            200,
            "2026-02-01T00:00:00Z",
            "2026-02-01T00:00:00Z",
            "seed-kernel",
            1,  # immutable
        ),
        (
            "T-300",
            "螺旋数体系の仮説",
            "数は直線上ではなく螺旋上に配置されるという仮説 (SNST の初期形)。",
            "hypothesis",
            None,
            "2026-03-01T00:00:00Z",
            "2026-03-01T00:00:00Z",
            "seed-kernel",
            0,
        ),
        (
            "invented-20260420-zero-ext",
            "π×π⁻¹=1 キャンセル意味論",
            "zero_extension: π×π⁻¹=1 の消去が意味を保存する。",
            "speculative",
            None,
            "2026-04-20T00:00:00Z",
            "2026-04-20T00:00:00Z",
            "invention",
            0,
        ),
        (
            "dfumt-self",
            "SELF 演算子 ⟲",
            "SELF は自己参照点。ω(x) = x を満たす。",
            "hypothesis",
            42,
            "2026-05-01T00:00:00Z",
            "2026-05-01T00:00:00Z",
            "seed-kernel",
            0,
        ),
    ]
    db.executemany(
        """
        INSERT INTO theories
            (id, title, body, tier, step, created_at, updated_at, source, immutable)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    for r in rows:
        db.execute(
            "INSERT INTO theories_fts (id, title, body) VALUES (?, ?, ?)",
            (r[0], r[1], r[2]),
        )

    # Links — cover all four kinds
    links = [
        ("T-100", "T-200", "depends"),      # 平和公理に依存
        ("T-100", "T-300", "related"),
        ("T-200", "dfumt-self", "generalizes"),
        ("invented-20260420-zero-ext", "T-100", "contradicts"),
    ]
    db.executemany(
        "INSERT INTO theory_links (from_id, to_id, kind) VALUES (?, ?, ?)", links
    )
    db.commit()
    return db
