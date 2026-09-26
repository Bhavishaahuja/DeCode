"""Acceptance checks for the Stratum data layer.

    python -m data.test_search        # prints PASS/FAIL per check, exit code 1 on any failure
    pytest data/test_search.py        # same checks under pytest
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict

import yaml

from . import config
from .search import search_evidence

DEV2_SYSTEMS = ["transport_lifting", "materials", "workforce", "water_sanitation", "quality_control"]


def _passages():
    return [json.loads(l) for l in config.PASSAGES_JSONL.read_text(encoding="utf-8").splitlines() if l.strip()]


def _top_has(hits, n, site=None, tags=()):
    for h in hits[:n]:
        if (site is None or h["site"] == site) and (not tags or set(tags) & set(h["system_tags"])):
            return True
    return False


def _show(hits, n=3):
    return " | ".join(f"{h['id']} {h['system_tags']} {h['score']}" for h in hits[:n])


# 1 -------------------------------------------------------------------------------------------
def test_schema_and_ordering():
    hits = search_evidence("how were the pyramid blocks cut and moved", k=5)
    assert 0 < len(hits) <= 5, f"expected 1..5 hits, got {len(hits)}"
    for h in hits:
        missing = [k for k in config.PASSAGE_KEYS + ["score"] if k not in h]
        assert not missing, f"{h.get('id')} missing keys {missing}"
        assert isinstance(h["score"], float) and isinstance(h["system_tags"], list)
        assert h["site"] in config.SITES and set(h["system_tags"]) <= set(config.system_ids())
    scores = [h["score"] for h in hits]
    assert scores == sorted(scores, reverse=True), f"not sorted: {scores}"
    assert search_evidence("", k=5) == [] and search_evidence("pyramid", k=0) == []


# 2 -------------------------------------------------------------------------------------------
def test_volume_and_licenses():
    ps = _passages()
    per_site = Counter(p["site"] for p in ps)
    low = {s: per_site[s] for s in config.SITES if per_site[s] < config.MIN_PASSAGES_PER_SITE}
    assert not low, f"sites below {config.MIN_PASSAGES_PER_SITE} passages: {low}"
    assert all(p.get("license") for p in ps), "some passages have no license"
    resolved = yaml.safe_load(config.RESOLVED_YAML.read_text(encoding="utf-8"))["sources"]
    by_id = {r["id"]: r for r in resolved}
    orphans = {p["source_id"] for p in ps} - set(by_id)
    assert not orphans, f"passages whose source isn't in sources.resolved.yaml: {sorted(orphans)[:5]}"
    no_lic = [r["id"] for r in resolved if not r.get("license") or not r.get("url")]
    assert not no_lic, f"resolved sources without license/url: {no_lic}"
    assert len({p["id"] for p in ps}) == len(ps), "duplicate passage ids"


# 3 -------------------------------------------------------------------------------------------
def test_dev2_system_coverage():
    cov = defaultdict(Counter)
    for p in _passages():
        for t in p["system_tags"]:
            cov[p["site"]][t] += 1
    gaps = {s: [t for t in DEV2_SYSTEMS if cov[s][t] < 3] for s in config.SITES}
    gaps = {s: g for s, g in gaps.items() if g}
    assert not gaps, f"sites with <3 passages for a must-have system: {gaps}"


# 4 -------------------------------------------------------------------------------------------
def test_site_filter_and_aliases():
    for site, alias in [("ur", "ur"), ("mohenjo_daro", "Mohenjo-daro"), ("qin_mausoleum", "Terracotta Army"), ("giza", "Giza")]:
        hits = search_evidence("brick construction", site=alias, k=8)
        assert hits, f"no hits for site={alias!r}"
        assert all(h["site"] == site for h in hits), f"site filter leaked for {alias!r}: {[h['site'] for h in hits]}"


# 5 -------------------------------------------------------------------------------------------
def test_system_filter_and_aliases():
    for sys_id, alias in [("water_sanitation", "water"), ("quality_control", "QA"), ("workforce", "workforce")]:
        hits = search_evidence("construction of the monument", system=alias, k=8)
        assert hits, f"no hits for system={alias!r}"
        assert all(sys_id in h["system_tags"] for h in hits), f"system filter leaked for {alias!r}"
    hits = search_evidence("drains", site="mohenjo_daro", system="water_sanitation", k=5)
    assert hits and all(h["site"] == "mohenjo_daro" and "water_sanitation" in h["system_tags"] for h in hits)


# 6 -------------------------------------------------------------------------------------------
def test_giza_sledge_wet_sand():
    hits = search_evidence("Giza ramp sledge wet sand", k=8)
    assert _top_has(hits, 3, "giza", ["transport_lifting"]), f"no Giza transport_lifting in top 3: {_show(hits)}"


# 7 -------------------------------------------------------------------------------------------
def test_mohenjo_drains():
    hits = search_evidence("Mohenjo-daro drains", k=8)
    assert _top_has(hits, 3, "mohenjo_daro", ["water_sanitation"]), f"no Mohenjo-daro water_sanitation in top 3: {_show(hits)}"


# 8 -------------------------------------------------------------------------------------------
def test_ur_ziggurat_materials():
    hits = search_evidence("ziggurat of Ur baked brick and bitumen", k=8)
    assert _top_has(hits, 3, "ur", ["materials"]), f"no Ur materials passage in top 3: {_show(hits)}"


# 9 -------------------------------------------------------------------------------------------
def test_qin_terracotta_production():
    hits = search_evidence("terracotta warriors production workshops inscribed names of craftsmen", k=8)
    assert _top_has(hits, 3, "qin_mausoleum", ["quality_control", "workforce", "administration_records"]), \
        f"no Qin QA/workforce passage in top 3: {_show(hits)}"


# 10 ------------------------------------------------------------------------------------------
def test_giza_workforce():
    hits = search_evidence("pyramid builders workers settlement bakeries rations", site="giza", k=8)
    assert _top_has(hits, 3, "giza", ["workforce", "logistics_supply"]), f"no Giza workforce passage in top 3: {_show(hits)}"


CHECKS = [v for k, v in list(globals().items()) if k.startswith("test_") and callable(v)]


def main() -> int:
    failed = 0
    for fn in CHECKS:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {fn.__name__}: {e}")
        except Exception as e:
            failed += 1
            print(f"ERROR {fn.__name__}: {type(e).__name__}: {e}")
    print(f"\n{len(CHECKS) - failed}/{len(CHECKS)} checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
