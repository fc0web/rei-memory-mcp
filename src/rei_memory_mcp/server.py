"""FastMCP entry point for rei-memory-mcp.

Registers three read-only tools:
- seed_search
- seed_get
- seed_list_steps

The DB path is picked from the ``REI_MEMORY_DB`` environment variable and
defaults to ``./data/seed_kernel.db`` relative to the working directory.
"""

from __future__ import annotations

import os
import sqlite3
from pathlib import Path

from .db import open_db
from .retrieve import get_theory, list_steps
from .search import search

DEFAULT_DB_PATH = "data/seed_kernel.db"


def _resolve_db_path() -> Path:
    p = os.environ.get("REI_MEMORY_DB", DEFAULT_DB_PATH)
    return Path(p).expanduser().resolve()


def _get_conn() -> sqlite3.Connection:
    """Open (and initialise) the DB on demand.

    A fresh connection per call keeps stdio-transport safety high — SQLite
    connections are not thread-safe for cross-thread reuse by default.
    """
    return open_db(_resolve_db_path())


def build_server():  # pragma: no cover — thin wiring
    """Construct the FastMCP server and register tools.

    Import is done lazily so tests that don't need MCP can import the
    other modules without ``mcp`` being installed.
    """
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("rei-memory-mcp")

    @mcp.tool()
    def seed_search(
        query: str,
        tier: str | None = None,
        step_min: int | None = None,
        step_max: int | None = None,
        limit: int = 20,
    ) -> dict:
        """Full-text search over SEED_KERNEL theories.

        ``query`` is treated as a single phrase (FTS5 quoted). For Japanese
        text, use queries of >= 3 characters; the trigram tokenizer cannot
        match shorter fragments.

        ``tier`` must be one of 'proven' / 'hypothesis' / 'speculative' if set.

        Returns a dict with ``total`` and ``results`` (id / title / tier /
        step / snippet / score). Full body is intentionally not returned —
        use ``seed_get(id)`` for the full text.
        """
        conn = _get_conn()
        try:
            return dict(search(conn, query, tier, step_min, step_max, limit))
        finally:
            conn.close()

    @mcp.tool()
    def seed_get(theory_id: str, include_links: bool = True) -> dict:
        """Fetch full theory body and its link fan-out.

        Returns ``{"error": "not_found", "id": ...}`` if the ID is unknown,
        rather than raising, so downstream tools can branch cleanly.
        """
        conn = _get_conn()
        try:
            return dict(get_theory(conn, theory_id, include_links))
        finally:
            conn.close()

    @mcp.tool()
    def seed_list_steps(
        step_min: int | None = None,
        step_max: int | None = None,
    ) -> dict:
        """Per-STEP count and tier distribution.

        Note: as of 2026-08-19 only about 3% of SEED_KERNEL theories
        embed a "STEP N" marker in their body; the remainder appear
        under the ``step: None`` bucket. Useful for identifying which
        STEPs have surfaced theories, not for exhaustive census.
        """
        conn = _get_conn()
        try:
            return dict(list_steps(conn, step_min, step_max))
        finally:
            conn.close()

    return mcp


def main() -> None:  # pragma: no cover — entry point
    """Console-script entry: run the stdio MCP server."""
    server = build_server()
    server.run()


if __name__ == "__main__":  # pragma: no cover
    main()
