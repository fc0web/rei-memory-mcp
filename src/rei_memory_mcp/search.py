"""Full-text search implementation for seed_search.

FTS5 trigram tokenizer requires queries of >= 3 characters for meaningful
matches against Japanese text; the caller is expected to handle short-query
UX. Very short queries are still executed (they may match Latin substrings)
but Japanese hits will be missing.
"""

from __future__ import annotations

import sqlite3
from typing import Any

from .models import SearchResponse, SearchResult, Tier

VALID_TIERS = ("proven", "hypothesis", "speculative")


def _escape_fts_query(query: str) -> str:
    """Wrap the query in double quotes so FTS5 treats it as a single phrase.

    Any embedded double quotes are doubled per FTS5 quoting rules.
    This keeps operator characters like ``AND``, ``OR``, ``NEAR``, ``*`` etc.
    from being interpreted, which matches the natural-language expectation
    of ``seed_search("平和公理")``.
    """
    escaped = query.replace('"', '""')
    return f'"{escaped}"'


def search(
    conn: sqlite3.Connection,
    query: str,
    tier: str | None = None,
    step_min: int | None = None,
    step_max: int | None = None,
    limit: int = 20,
) -> SearchResponse:
    """Run FTS5 search over (title, body) and return top-N by bm25.

    Filters (tier, step_min, step_max) apply after the FTS match join.

    Raises:
        ValueError: if ``tier`` is not one of VALID_TIERS.
    """
    if tier is not None and tier not in VALID_TIERS:
        raise ValueError(f"tier must be one of {VALID_TIERS}, got {tier!r}")
    if limit <= 0:
        limit = 20

    fts_q = _escape_fts_query(query)

    sql_where: list[str] = ["theories_fts MATCH ?"]
    params: list[Any] = [fts_q]

    if tier is not None:
        sql_where.append("t.tier = ?")
        params.append(tier)
    if step_min is not None:
        sql_where.append("t.step >= ?")
        params.append(step_min)
    if step_max is not None:
        sql_where.append("t.step <= ?")
        params.append(step_max)

    where_clause = " AND ".join(sql_where)

    # bm25() returns a lower-is-better score; we surface it as-is and let
    # the client interpret. Sorting by rank (== bm25) puts best matches first.
    sql = f"""
        SELECT
            t.id             AS id,
            t.title          AS title,
            t.tier           AS tier,
            t.step           AS step,
            snippet(theories_fts, 2, '[', ']', ' ... ', 32) AS snippet,
            bm25(theories_fts) AS score
        FROM theories_fts
        JOIN theories t ON t.id = theories_fts.id
        WHERE {where_clause}
        ORDER BY score
        LIMIT ?
    """
    params.append(limit)

    rows = list(conn.execute(sql, params))

    # total = count matching FTS + filters (no snippet, no limit)
    count_sql = f"""
        SELECT COUNT(*) AS n
        FROM theories_fts
        JOIN theories t ON t.id = theories_fts.id
        WHERE {where_clause}
    """
    total = conn.execute(count_sql, params[:-1]).fetchone()["n"]

    results: list[SearchResult] = [
        {
            "id": r["id"],
            "title": r["title"],
            "tier": r["tier"],
            "step": r["step"],
            "snippet": r["snippet"],
            "score": float(r["score"]),
        }
        for r in rows
    ]

    return {"total": int(total), "results": results}


__all__ = ["search", "VALID_TIERS"]
