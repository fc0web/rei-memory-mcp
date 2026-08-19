"""Type definitions for rei-memory-mcp.

Kept as plain dataclass / TypedDict to avoid pulling in pydantic;
tools return plain dicts to MCP which serialise via JSON.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, TypedDict

Tier = Literal["proven", "hypothesis", "speculative"]
"""Three-layer taxonomy. Required on every theory at ingestion time.

Reason: the epidemic-hygiene discipline is enforced at schema level, not
by human attention. A theory without a tier cannot be ingested.
"""

LinkKind = Literal["depends", "contradicts", "generalizes", "related"]


@dataclass(frozen=True)
class Theory:
    """In-memory representation of a theory row (used by ingest / retrieve)."""

    id: str
    title: str
    body: str
    tier: Tier
    step: int | None
    created_at: str
    updated_at: str
    source: str | None
    immutable: bool


class SearchResult(TypedDict):
    """One row returned by seed_search."""

    id: str
    title: str
    tier: str
    step: int | None
    snippet: str
    score: float


class SearchResponse(TypedDict):
    total: int
    results: list[SearchResult]


class LinkedTheory(TypedDict):
    id: str
    title: str


class GetResponse(TypedDict, total=False):
    id: str
    title: str
    body: str
    tier: str
    step: int | None
    created_at: str
    updated_at: str
    source: str | None
    immutable: bool
    links: dict[str, list[LinkedTheory]]
    # error case
    error: str


class StepBucket(TypedDict):
    step: int | None
    count: int
    tiers: dict[str, int]


class StepsResponse(TypedDict):
    steps: list[StepBucket]
    total_theories: int
