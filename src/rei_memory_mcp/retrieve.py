"""Retrieval implementations for seed_get and seed_list_steps.

Both are read-only against ``theories`` / ``theory_links``.
"""

from __future__ import annotations

import sqlite3
from collections import defaultdict

from .models import GetResponse, LinkedTheory, StepBucket, StepsResponse

LINK_KINDS = ("depends", "contradicts", "generalizes", "related")


def get_theory(
    conn: sqlite3.Connection,
    theory_id: str,
    include_links: bool = True,
) -> GetResponse:
    """Return the full theory record + link fan-out.

    Non-existent ID returns ``{"error": "not_found", "id": theory_id}``
    instead of raising, per spec.
    """
    row = conn.execute(
        "SELECT id, title, body, tier, step, created_at, updated_at, source, immutable "
        "FROM theories WHERE id = ?",
        (theory_id,),
    ).fetchone()
    if row is None:
        return {"error": "not_found", "id": theory_id}

    resp: GetResponse = {
        "id": row["id"],
        "title": row["title"],
        "body": row["body"],
        "tier": row["tier"],
        "step": row["step"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
        "source": row["source"],
        "immutable": bool(row["immutable"]),
    }

    if include_links:
        resp["links"] = _fetch_links(conn, theory_id)

    return resp


def _fetch_links(
    conn: sqlite3.Connection, theory_id: str
) -> dict[str, list[LinkedTheory]]:
    """Fan-out links grouped by kind. Title lookup joins theories."""
    grouped: dict[str, list[LinkedTheory]] = {k: [] for k in LINK_KINDS}
    rows = conn.execute(
        """
        SELECT tl.kind AS kind, tl.to_id AS to_id, COALESCE(t.title, '') AS title
        FROM theory_links tl
        LEFT JOIN theories t ON t.id = tl.to_id
        WHERE tl.from_id = ?
        ORDER BY tl.kind, tl.to_id
        """,
        (theory_id,),
    ).fetchall()
    for r in rows:
        kind = r["kind"]
        if kind not in grouped:
            # unknown kind (shouldn't happen given CHECK constraint) — skip
            continue
        grouped[kind].append({"id": r["to_id"], "title": r["title"]})
    return grouped


def list_steps(
    conn: sqlite3.Connection,
    step_min: int | None = None,
    step_max: int | None = None,
) -> StepsResponse:
    """Return per-STEP count + tier distribution.

    Note: SEED_KERNEL as of 2026-08-19 has step embedded in axiom body for
    only ~3.1% of theories (52 / 1,677). The remaining ~96.9% appear under
    ``step=None`` bucket. This is a known coverage limitation, not a bug.
    """
    where: list[str] = []
    params: list[int] = []
    if step_min is not None:
        where.append("step >= ?")
        params.append(step_min)
    if step_max is not None:
        where.append("step <= ?")
        params.append(step_max)
    where_clause = ("WHERE " + " AND ".join(where)) if where else ""

    rows = conn.execute(
        f"""
        SELECT step, tier, COUNT(*) AS n
        FROM theories
        {where_clause}
        GROUP BY step, tier
        ORDER BY step IS NULL, step, tier
        """,
        params,
    ).fetchall()

    # aggregate: {step: {tier: count}}
    step_map: dict[int | None, dict[str, int]] = defaultdict(
        lambda: {"proven": 0, "hypothesis": 0, "speculative": 0}
    )
    for r in rows:
        step_map[r["step"]][r["tier"]] = int(r["n"])

    buckets: list[StepBucket] = []
    # keep insertion order (Python 3.7+ defaultdict preserves)
    for step, tiers in step_map.items():
        total = sum(tiers.values())
        buckets.append({"step": step, "count": total, "tiers": tiers})

    total_theories = conn.execute(
        f"SELECT COUNT(*) AS n FROM theories {where_clause}", params
    ).fetchone()["n"]

    return {"steps": buckets, "total_theories": int(total_theories)}


__all__ = ["get_theory", "list_steps"]
