"""seed_get tests — retrieval, not-found handling, link fan-out."""

from __future__ import annotations

from rei_memory_mcp.retrieve import get_theory


def test_get_existing_returns_full_record(seed):
    r = get_theory(seed, "T-100")
    assert "error" not in r
    assert r["id"] == "T-100"
    assert r["title"] == "七値論理の初期定式化"
    assert "七値論理" in r["body"]
    assert r["tier"] == "proven"
    assert r["step"] == 100
    assert r["immutable"] is False
    assert isinstance(r["links"], dict)


def test_get_immutable_flag(seed):
    r = get_theory(seed, "T-200")
    assert r["immutable"] is True


def test_get_missing_returns_error_dict(seed):
    """Non-existent ID must NOT raise — must return {"error": "not_found", ...}."""
    r = get_theory(seed, "T-nonexistent-999999")
    assert r == {"error": "not_found", "id": "T-nonexistent-999999"}


def test_get_include_links_default_true(seed):
    r = get_theory(seed, "T-100")
    assert "links" in r
    kinds = r["links"].keys()
    for k in ("depends", "contradicts", "generalizes", "related"):
        assert k in kinds


def test_get_links_depends(seed):
    """T-100 depends on T-200 per conftest fixture."""
    r = get_theory(seed, "T-100")
    dep_ids = [x["id"] for x in r["links"]["depends"]]
    assert "T-200" in dep_ids
    dep_titles = {x["id"]: x["title"] for x in r["links"]["depends"]}
    assert dep_titles["T-200"] == "平和公理 #196 は不変である"


def test_get_links_contradicts(seed):
    """invented-* contradicts T-100."""
    r = get_theory(seed, "invented-20260420-zero-ext")
    ids = [x["id"] for x in r["links"]["contradicts"]]
    assert "T-100" in ids


def test_get_links_generalizes(seed):
    """T-200 generalizes dfumt-self."""
    r = get_theory(seed, "T-200")
    ids = [x["id"] for x in r["links"]["generalizes"]]
    assert "dfumt-self" in ids


def test_get_links_related(seed):
    r = get_theory(seed, "T-100")
    ids = [x["id"] for x in r["links"]["related"]]
    assert "T-300" in ids


def test_get_include_links_false(seed):
    r = get_theory(seed, "T-100", include_links=False)
    assert "links" not in r


def test_get_isolated_theory_has_empty_link_groups(seed):
    """A theory with no outgoing links gets empty lists (not missing keys)."""
    r = get_theory(seed, "T-300")
    for k in ("depends", "contradicts", "generalizes", "related"):
        assert r["links"][k] == []


def test_get_link_target_missing_title_ok(seed):
    """If a link points to an unknown target, title comes back empty (LEFT JOIN)."""
    seed.execute(
        "INSERT INTO theory_links (from_id, to_id, kind) VALUES ('T-300', 'ghost-id', 'depends')"
    )
    seed.commit()
    r = get_theory(seed, "T-300")
    deps = r["links"]["depends"]
    assert any(x["id"] == "ghost-id" for x in deps)
    ghost = next(x for x in deps if x["id"] == "ghost-id")
    assert ghost["title"] == ""
