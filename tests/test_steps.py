"""seed_list_steps tests — tier distribution aggregation."""

from __future__ import annotations

from rei_memory_mcp.retrieve import list_steps


def test_total_theories_matches_seed(seed):
    r = list_steps(seed)
    # conftest inserts 5 rows
    assert r["total_theories"] == 5


def test_bucket_counts_sum_to_total(seed):
    r = list_steps(seed)
    counted = sum(b["count"] for b in r["steps"])
    assert counted == r["total_theories"]


def test_none_step_bucket_present(seed):
    """Two theories in the fixture have step=None (T-300, invented-*)."""
    r = list_steps(seed)
    none_buckets = [b for b in r["steps"] if b["step"] is None]
    assert len(none_buckets) == 1
    assert none_buckets[0]["count"] == 2


def test_tier_distribution_present(seed):
    r = list_steps(seed)
    for b in r["steps"]:
        assert set(b["tiers"].keys()) == {"proven", "hypothesis", "speculative"}


def test_specific_step_bucket(seed):
    """T-100 has step=100 tier=proven."""
    r = list_steps(seed)
    step100 = next(b for b in r["steps"] if b["step"] == 100)
    assert step100["count"] == 1
    assert step100["tiers"]["proven"] == 1
    assert step100["tiers"]["hypothesis"] == 0
    assert step100["tiers"]["speculative"] == 0


def test_none_bucket_tier_split(seed):
    """T-300 (hypothesis) + invented-* (speculative) — both step=None."""
    r = list_steps(seed)
    none_bucket = next(b for b in r["steps"] if b["step"] is None)
    assert none_bucket["tiers"]["hypothesis"] == 1
    assert none_bucket["tiers"]["speculative"] == 1
    assert none_bucket["tiers"]["proven"] == 0


def test_step_min_filter(seed):
    r = list_steps(seed, step_min=50)
    # excludes step=42 (dfumt-self) and step=None (2 rows) is *kept* because
    # NULL comparisons return NULL == FALSE; step_min filters exclude nulls.
    # Verify by comparing to no-filter result.
    for b in r["steps"]:
        if b["step"] is not None:
            assert b["step"] >= 50


def test_step_max_filter(seed):
    r = list_steps(seed, step_max=150)
    for b in r["steps"]:
        if b["step"] is not None:
            assert b["step"] <= 150


def test_step_range_narrow(seed):
    """step_min=100 step_max=150 → only T-100 (step=100)."""
    r = list_steps(seed, step_min=100, step_max=150)
    non_null = [b for b in r["steps"] if b["step"] is not None]
    assert len(non_null) == 1
    assert non_null[0]["step"] == 100
    assert non_null[0]["count"] == 1


def test_empty_range_zero_total(seed):
    """A range with no rows returns total_theories=0."""
    r = list_steps(seed, step_min=9000, step_max=9999)
    non_null = [b for b in r["steps"] if b["step"] is not None]
    assert non_null == []
    assert r["total_theories"] == 0
