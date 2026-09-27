"""Acceptance checks for the DeCode data layer.

    python -m data.test_search        # prints PASS/FAIL per check, exit code 1 on any failure
    pytest data/test_search.py        # same checks under pytest

Two groups: Chad's artifact checks (the committed files are well formed and consumable) and the
contract and search checks (Contract 1 fields, registry, and that search finds the right evidence).
These need a built data/passages.jsonl (python -m data.build --small, or make data).
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict

import yaml

from . import config
from .corpus_models import SourceStatus
from .search import search_evidence
from .source_registry import SourceRegistry

CONTRACT_SITES = ["giza", "uruk", "mohenjo", "qin"]
CONTRACT_SYSTEMS = ["site_setout", "materials_supply", "transport_lifting", "water_sanitation", "structure_form",
                    "finishes", "workforce", "quality_control", "project_controls"]
# the systems Dev 2 needs covered at every site (claims/common.py REQUIRED_SYSTEMS)
DEV2_SYSTEMS = ["transport_lifting", "materials_supply", "workforce", "water_sanitation", "quality_control"]


def _passages():
    return [json.loads(l) for l in config.PASSAGES_JSONL.read_text(encoding="utf-8").splitlines() if l.strip()]


def _top_has(hits, n, site=None, tags=()):
    for h in hits[:n]:
        if (site is None or h["site"] == site) and (not tags or set(tags) & set(h["system_tags"])):
            return True
    return False


def _show(hits, n=3):
    return " | ".join(f"{h['passage_id']} {h['system_tags']} {h['score']}" for h in hits[:n])


def _resolved_payload():
    assert config.RESOLVED_YAML.exists(), f"{config.RESOLVED_YAML} does not exist"
    payload = yaml.safe_load(config.RESOLVED_YAML.read_text(encoding="utf-8")) or {}
    assert isinstance(payload, dict), "sources.resolved.yaml must contain a mapping"
    assert isinstance(payload.get("sources"), list), "sources.resolved.yaml needs a 'sources' list"
    assert isinstance(payload.get("listed_but_not_ingested"), list), \
        "sources.resolved.yaml needs a 'listed_but_not_ingested' list"
    return payload


# Chad's artifact checks ----------------------------------------------------------------------
def test_passages_file_is_valid_jsonl():
    assert config.PASSAGES_JSONL.exists(), f"{config.PASSAGES_JSONL} does not exist"
    lines = config.PASSAGES_JSONL.read_text(encoding="utf-8").splitlines()
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AssertionError(f"invalid JSONL at line {line_number}: {exc}") from exc
        assert isinstance(row, dict), f"line {line_number} is not a JSON object"


def test_resolved_source_entries_are_valid():
    for source in _resolved_payload()["sources"]:
        assert isinstance(source, dict), "resolved source entry must be a mapping"
        for field in ("id", "site", "type", "title", "url", "license"):
            assert source.get(field), f"resolved source missing {field!r}: {source}"
        assert source["site"] in config.SITES, f"resolved source has unknown site {source['site']!r}"
        assert source["type"] in config.SOURCE_TYPES, f"resolved source has unknown type {source['type']!r}"


def test_listed_not_ingested_entries_are_valid():
    for source in _resolved_payload()["listed_but_not_ingested"]:
        assert isinstance(source, dict), "listed-but-not-ingested entry must be a mapping"
        assert source.get("id"), "listed-but-not-ingested source is missing 'id'"


def test_passage_sources_exist():
    resolved_ids = {source["id"] for source in _resolved_payload()["sources"]}
    orphaned = {p["source_id"] for p in _passages() if p["source_id"] not in resolved_ids}
    assert not orphaned, f"passages reference unresolved sources: {sorted(orphaned)[:5]}"


# 1 -------------------------------------------------------------------------------------------
def test_ids_match_the_contract():
    assert list(config.SITES) == CONTRACT_SITES, f"config.SITES is {list(config.SITES)}"
    assert config.system_ids() == CONTRACT_SYSTEMS, f"systems.yaml ids are {config.system_ids()}"
    taxonomy = config.DATA_DIR.parent / "claims" / "taxonomy.yaml"
    if taxonomy.exists():
        dev2 = list(yaml.safe_load(taxonomy.read_text(encoding="utf-8"))["systems"])
        assert dev2 == CONTRACT_SYSTEMS, f"claims/taxonomy.yaml drifted from the contract: {dev2}"


# 2 -------------------------------------------------------------------------------------------
def test_passages_follow_contract_1():
    ps = _passages()
    assert ps, "passages.jsonl is empty"
    for p in ps:
        missing = [k for k in config.PASSAGE_KEYS if k not in p]
        assert not missing, f"{p.get('passage_id')} missing keys {missing}"
        assert "score" not in p, f"{p['passage_id']} has a score in the jsonl file"
        assert p["site"] in CONTRACT_SITES, f"{p['passage_id']} has site {p['site']!r}"
        assert p["source_type"] in config.SOURCE_TYPES, f"{p['passage_id']} has source_type {p['source_type']!r}"
        assert p["tagged_by"] in config.TAGGED_BY, f"{p['passage_id']} has tagged_by {p['tagged_by']!r}"
        assert set(p["system_tags"]) <= set(CONTRACT_SYSTEMS), f"{p['passage_id']} has tags {p['system_tags']}"
        assert p["passage_id"].startswith(p["site"] + "-"), f"{p['passage_id']} doesn't start with its site"
        assert p["year"] is None or isinstance(p["year"], int)
        assert p["locator"] is None or isinstance(p["locator"], str)
    assert len({p["passage_id"] for p in ps}) == len(ps), "duplicate passage ids"


# 3 -------------------------------------------------------------------------------------------
def test_schema_and_ordering():
    hits = search_evidence("how were the pyramid blocks cut and moved", k=5)
    assert 0 < len(hits) <= 5, f"expected 1..5 hits, got {len(hits)}"
    for h in hits:
        missing = [k for k in config.PASSAGE_KEYS + ["score"] if k not in h]
        assert not missing, f"{h.get('passage_id')} missing keys {missing}"
        assert isinstance(h["score"], float) and isinstance(h["system_tags"], list)
    scores = [h["score"] for h in hits]
    assert scores == sorted(scores, reverse=True), f"not sorted: {scores}"
    assert search_evidence("", k=5) == [] and search_evidence("pyramid", k=0) == []


# 4 -------------------------------------------------------------------------------------------
def test_volume_and_licenses():
    ps = _passages()
    per_site = Counter(p["site"] for p in ps)
    low = {s: per_site[s] for s in CONTRACT_SITES if per_site[s] < config.MIN_PASSAGES_PER_SITE}
    assert not low, f"sites below {config.MIN_PASSAGES_PER_SITE} passages: {low}"
    assert all(p.get("license") for p in ps), "some passages have no license"
    resolved = yaml.safe_load(config.RESOLVED_YAML.read_text(encoding="utf-8"))["sources"]
    by_id = {r["id"]: r for r in resolved}
    orphans = {p["source_id"] for p in ps} - set(by_id)
    assert not orphans, f"passages whose source isn't in sources.resolved.yaml: {sorted(orphans)[:5]}"
    no_lic = [r["id"] for r in resolved if not r.get("license") or not r.get("url")]
    assert not no_lic, f"resolved sources without license/url: {no_lic}"


# 5 -------------------------------------------------------------------------------------------
def test_every_source_is_valid_in_the_registry():
    registry = SourceRegistry()
    problems = []
    for source_id in sorted({p["source_id"] for p in _passages()}):
        record = registry.get_by_id(source_id)
        if record is None:
            problems.append(f"{source_id}: not in registry")
        elif record.status != SourceStatus.VALID:
            problems.append(f"{source_id}: registry says {record.status.value}")
        elif not record.metadata.get("license"):
            problems.append(f"{source_id}: no license recorded")
    assert not problems, f"registry problems: {problems[:5]}"


# 6 -------------------------------------------------------------------------------------------
def test_dev2_system_coverage():
    cov = defaultdict(Counter)
    for p in _passages():
        for t in p["system_tags"]:
            cov[p["site"]][t] += 1
    gaps = {s: [t for t in DEV2_SYSTEMS if cov[s][t] < 3] for s in CONTRACT_SITES}
    gaps = {s: g for s, g in gaps.items() if g}
    assert not gaps, f"sites with <3 passages for a must-have system: {gaps}"


# 7 -------------------------------------------------------------------------------------------
def test_site_filter_and_aliases():
    for site, alias in [("uruk", "Warka"), ("mohenjo", "Mohenjo-daro"), ("qin", "Great Wall"), ("giza", "Giza")]:
        hits = search_evidence("brick and earth construction", site=alias, k=8)
        assert hits, f"no hits for site={alias!r}"
        assert all(h["site"] == site for h in hits), f"site filter leaked for {alias!r}: {[h['site'] for h in hits]}"


# 8 -------------------------------------------------------------------------------------------
def test_system_filter_and_aliases():
    for sys_id, alias in [("water_sanitation", "water"), ("quality_control", "QA"), ("materials_supply", "materials"),
                          ("project_controls", "records")]:
        hits = search_evidence("construction of the monument", system=alias, k=8)
        assert hits, f"no hits for system={alias!r}"
        assert all(sys_id in h["system_tags"] for h in hits), f"system filter leaked for {alias!r}"
    hits = search_evidence("drains", site="mohenjo", system="water_sanitation", k=5)
    assert hits and all(h["site"] == "mohenjo" and "water_sanitation" in h["system_tags"] for h in hits)


# 9 -------------------------------------------------------------------------------------------
def test_giza_sledge_wet_sand():
    hits = search_evidence("Giza ramp sledge wet sand", k=8)
    assert _top_has(hits, 3, "giza", ["transport_lifting"]), f"no Giza transport_lifting in top 3: {_show(hits)}"


# 10 ------------------------------------------------------------------------------------------
def test_mohenjo_drains():
    hits = search_evidence("Mohenjo-daro drains", k=8)
    assert _top_has(hits, 3, "mohenjo", ["water_sanitation"]), f"no Mohenjo-daro water_sanitation in top 3: {_show(hits)}"


# 11 ------------------------------------------------------------------------------------------
def test_uruk_eanna_building():
    hits = search_evidence("Uruk Eanna temple mudbrick cone mosaic", k=8)
    assert _top_has(hits, 3, "uruk", ["materials_supply", "finishes", "structure_form"]), \
        f"no Uruk building passage in top 3: {_show(hits)}"


# 12 ------------------------------------------------------------------------------------------
def test_uruk_rations_records():
    hits = search_evidence("beveled rim bowls rations proto-cuneiform accounts", site="uruk", k=8)
    assert _top_has(hits, 3, "uruk", ["workforce", "project_controls"]), f"no Uruk workforce/records in top 3: {_show(hits)}"


# 13 ------------------------------------------------------------------------------------------
def test_qin_wall_rammed_earth():
    hits = search_evidence("Qin Great Wall rammed earth Meng Tian", k=8)
    assert _top_has(hits, 3, "qin", ["materials_supply", "structure_form", "workforce"]), \
        f"no Qin wall passage in top 3: {_show(hits)}"


# 14 ------------------------------------------------------------------------------------------
def test_qin_straight_road():
    hits = search_evidence("Qin Straight Road Zhidao built for troops", site="qin", k=8)
    assert _top_has(hits, 3, "qin", ["transport_lifting"]), f"no Qin road passage in top 3: {_show(hits)}"


# 15 ------------------------------------------------------------------------------------------
def test_giza_workforce():
    hits = search_evidence("pyramid builders workers settlement bakeries rations", site="giza", k=8)
    assert _top_has(hits, 3, "giza", ["workforce", "materials_supply"]), f"no Giza workforce passage in top 3: {_show(hits)}"


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
