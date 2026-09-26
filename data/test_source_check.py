"""Tests for the stage 1 source gate (data/source_check.py).  pytest data/test_source_check.py"""
from datetime import datetime, timezone

import pytest
import yaml

from data.corpus_models import SourceStatus
from data.source_check import decide, license_verdict
from data.source_registry import SourceRegistry

NOW = datetime(2026, 9, 26, 20, 0, tzinfo=timezone.utc)


def yaml_source(**overrides):
    src = {
        "id": "wp_test_page",
        "site": "giza",
        "type": "reference",
        "title": "Test page (Wikipedia)",
        "url": "https://en.wikipedia.org/wiki/Test_page",
        "license": "CC BY-SA 4.0 (Wikipedia)",
        "author": "Wikipedia contributors",
        "fetch": {"kind": "wikipedia", "page": "Test page"},
    }
    src.update(overrides)
    return src


def make_registry(tmp_path, catalog, resolved=None, log_lines=()):
    sources_path = tmp_path / "sources.yaml"
    resolved_path = tmp_path / "resolved.yaml"
    sources_path.write_text(yaml.safe_dump({"sources": catalog}), encoding="utf-8")
    if resolved is not None:
        resolved_path.write_text(yaml.safe_dump({"sources": resolved, "listed_but_not_ingested": []}), encoding="utf-8")
    return SourceRegistry(sources_path=sources_path, resolved_path=resolved_path,
                          ingest_log_lines=log_lines, ingest_log_time=NOW)


@pytest.mark.parametrize("text, ok", [
    ("CC BY-SA 4.0 (Wikipedia)", True),
    ("Public domain (published 1883; author died 1942)", True),
    ("Wikidata CC0 1.0; Pleiades CC BY 3.0", True),
    ("ETCSL (Univ. of Oxford): free for non-commercial use with attribution", True),
    ("CC BY NC ND (OpenAlex: cc-by-nc-nd)", True),
    ("In copyright in the US until 2034", False),
    ("tDAR user agreement (login required)", False),
    ("", False),
    (None, False),
])
def test_license_verdict(text, ok):
    assert license_verdict(text)[0] is ok


def test_unknown_api_source_gets_checked_and_used(tmp_path):
    src = yaml_source()
    verdict = decide(src, make_registry(tmp_path, [src]))
    assert verdict.use and verdict.status == SourceStatus.VALID


def test_known_valid_source_is_used(tmp_path):
    src = yaml_source()
    resolved = [{"id": src["id"], "site": "giza", "title": src["title"], "url": src["url"],
                 "license": src["license"], "retrieved": "2026-09-26"}]
    verdict = decide(src, make_registry(tmp_path, [src], resolved=resolved))
    assert verdict.use and verdict.reason.startswith("known valid")


def test_known_invalid_source_is_skipped(tmp_path):
    src = yaml_source()
    registry = make_registry(tmp_path, [src], log_lines=["  [skip] wp_test_page: HTTP 404"])
    verdict = decide(src, registry)
    assert not verdict.use and verdict.status == SourceStatus.INVALID


def test_disabled_source_is_skipped_with_its_note(tmp_path):
    src = yaml_source(enabled=False, note="bulk download isn't licensed")
    verdict = decide(src, make_registry(tmp_path, [src]))
    assert not verdict.use and "bulk download" in verdict.reason


def test_blocked_license_is_skipped(tmp_path):
    src = yaml_source(license="In copyright until 2034")
    verdict = decide(src, make_registry(tmp_path, [src]))
    assert not verdict.use and "forbids reuse" in verdict.reason


def test_url_source_offline_stays_unknown(tmp_path):
    src = yaml_source(id="etcsl_test", license="ETCSL (Univ. of Oxford): free for non-commercial use with attribution",
                      fetch={"kind": "url", "url": "https://etcsl.orinst.ox.ac.uk/section1/tr1823.htm"})
    verdict = decide(src, make_registry(tmp_path, [src]), offline=True)
    assert not verdict.use and verdict.status == SourceStatus.UNKNOWN


def test_url_source_respects_robots(tmp_path, monkeypatch):
    from data import fetch
    src = yaml_source(id="blocked_page", fetch={"kind": "url", "url": "https://example.org/page.html"})
    monkeypatch.setattr(fetch, "robots_allowed", lambda url: False)
    verdict = decide(src, make_registry(tmp_path, [src]))
    assert not verdict.use and "robots.txt disallows" in verdict.reason
