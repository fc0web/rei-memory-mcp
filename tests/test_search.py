"""seed_search tests — trigram Japanese behaviour + filters."""

from __future__ import annotations

import pytest

from rei_memory_mcp.search import search


def test_japanese_query_hits(seed):
    """Trigram tokenizer must find Japanese phrases of >= 3 chars."""
    r = search(seed, "七値論理")
    assert r["total"] >= 1
    ids = [x["id"] for x in r["results"]]
    assert "T-100" in ids, f"expected T-100 in {ids}"


def test_japanese_query_hits_平和公理(seed):
    r = search(seed, "平和公理")
    assert r["total"] >= 1
    assert any(x["id"] == "T-200" for x in r["results"])


def test_katakana_query_hits(seed):
    """Katakana (also passes trigram)."""
    r = search(seed, "キャンセル")
    assert r["total"] >= 1
    assert any("zero-ext" in x["id"] for x in r["results"])


def test_snippet_includes_markers(seed):
    """FTS snippet() should surround the match with [ and ]."""
    r = search(seed, "七値論理")
    assert r["total"] >= 1
    snippet = r["results"][0]["snippet"]
    assert "[" in snippet and "]" in snippet


def test_score_is_float(seed):
    r = search(seed, "螺旋上")  # 3+ chars required for trigram
    assert r["total"] >= 1
    assert isinstance(r["results"][0]["score"], float)


def test_two_char_japanese_returns_empty(seed):
    """Documented limitation: trigram cannot match 2-char Japanese fragments."""
    r = search(seed, "螺旋")
    assert r["total"] == 0


def test_tier_filter_proven_only(seed):
    """tier=proven should exclude hypothesis + speculative entries."""
    r_all = search(seed, "定式化")
    r_pv = search(seed, "定式化", tier="proven")
    assert all(x["tier"] == "proven" for x in r_pv["results"])
    # T-100 (proven) is in the corpus so we should get at least 1
    assert r_pv["total"] >= 1
    assert r_pv["total"] <= r_all["total"]


def test_tier_filter_speculative(seed):
    r = search(seed, "zero_extension", tier="speculative")
    assert r["total"] >= 1
    assert all(x["tier"] == "speculative" for x in r["results"])


def test_invalid_tier_raises(seed):
    with pytest.raises(ValueError, match="tier must be one of"):
        search(seed, "any", tier="proovn")


def test_step_range_filter(seed):
    """step_min / step_max should narrow to the range."""
    r = search(seed, "七値論理", step_min=50, step_max=150)
    assert r["total"] >= 1
    for x in r["results"]:
        assert x["step"] is None or (50 <= x["step"] <= 150)


def test_step_range_excludes(seed):
    """Query hits a row outside the range — should be excluded."""
    # T-200 (step=200) matches '平和公理' but is outside 0..150
    r = search(seed, "平和公理", step_max=150)
    assert not any(x["id"] == "T-200" for x in r["results"])


def test_limit(seed):
    r = search(seed, "の", limit=2)
    # trigram of 1-char query returns nothing (needs >= 3); use safer query
    r = search(seed, "seed-kernel", limit=2)
    # Regardless, limit must bound the returned list length
    assert len(r["results"]) <= 2


def test_full_body_not_returned(seed):
    """Spec: full body is not returned by seed_search (token save)."""
    r = search(seed, "七値論理")
    assert r["total"] >= 1
    # 'body' should not be a key in any result row
    for x in r["results"]:
        assert "body" not in x


def test_zero_hit_query(seed):
    """Non-matching query returns total=0, empty results."""
    r = search(seed, "この文字列は絶対にヒットしない架空語ザブトン")
    assert r["total"] == 0
    assert r["results"] == []
