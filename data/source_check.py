"""Stage 1 of the Decode flow: decide whether a source can be used, before ingest touches it.

    python -m data.source_check              # check every source in sources.yaml and print the verdicts
    python -m data.source_check --offline    # same, but skip robots.txt lookups

This sits on top of Chad's SourceRegistry (data/source_registry.py), which reads what we
already know from sources.yaml, sources.resolved.yaml and ingest logs. The rule:

    switched off in sources.yaml -> skip (with the note as the reason)
    registry says valid          -> use it
    registry says invalid        -> skip it
    registry says unknown        -> check license, access and robots.txt now

Decisions are saved by ingest into sources.resolved.yaml: used sources under `sources`,
skipped ones under `listed_but_not_ingested` with a `reason`. That's the same file the
registry reads, so there's no second data layer.
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from dataclasses import dataclass

import yaml

from . import config
from .corpus_models import SourceStatus
from .source_registry import SourceRegistry

# Licenses that allow reuse for this project, matched case-insensitively.
REUSE_OK_PATTERNS = [
    r"public domain",
    r"\bcc0\b",
    r"\bcc[ -]by\b",                     # CC BY, CC BY-SA, CC BY-NC, CC BY-ND and friends
    r"free for non-commercial use with attribution",
    r"project gutenberg",
]

# Anything that says reuse isn't allowed. Checked first, so it wins.
REUSE_BLOCKED_PATTERNS = [
    r"in copyright",
    r"all rights reserved",
    r"login required",
    r"no reuse",
    r"not licensed",
]

# Fetch kinds that go through an official API instead of scraping pages, so the site terms are
# respected by design and robots.txt isn't the gate.
API_KINDS = {"wikipedia", "archive_search", "gutenberg_search", "wikidata_place"}


@dataclass
class Verdict:
    use: bool                 # True = go ahead and ingest
    status: SourceStatus      # valid | invalid | unknown
    reason: str


def license_verdict(license_text: str | None) -> tuple[bool, str]:
    """(ok, reason) for a license string. Empty or unrecognised licenses are not ok."""
    text = (license_text or "").strip().lower()
    if not text:
        return False, "no license recorded"
    for pattern in REUSE_BLOCKED_PATTERNS:
        if re.search(pattern, text):
            return False, f"license forbids reuse: {license_text}"
    for pattern in REUSE_OK_PATTERNS:
        if re.search(pattern, text):
            return True, f"license allows reuse: {license_text}"
    return False, f"license not recognised as reusable: {license_text}"


def check_unknown(src: dict, offline: bool = False) -> Verdict:
    """Fresh check for a source the registry doesn't know yet."""
    ok, why = license_verdict(src.get("license"))
    if not ok:
        return Verdict(False, SourceStatus.INVALID, why)

    kind = (src.get("fetch") or {}).get("kind")
    if kind is None:
        return Verdict(False, SourceStatus.INVALID, "no fetch method, nothing to ingest")
    if kind in API_KINDS:
        return Verdict(True, SourceStatus.VALID, f"{why}; fetched through the official API")
    if kind == "url":
        if offline:
            return Verdict(False, SourceStatus.UNKNOWN, "robots.txt not checked yet (offline)")
        from . import fetch
        target = src["fetch"]["url"]
        allowed = fetch.robots_allowed(target)
        if allowed is None:
            return Verdict(False, SourceStatus.UNKNOWN, "couldn't reach robots.txt, try again online")
        if not allowed:
            return Verdict(False, SourceStatus.INVALID, f"robots.txt disallows {target}")
        return Verdict(True, SourceStatus.VALID, f"{why}; robots.txt allows it")
    return Verdict(False, SourceStatus.INVALID, f"unknown fetch kind {kind!r}")


def decide(src: dict, registry: SourceRegistry, offline: bool = False) -> Verdict:
    """The stage 1 gate ingest calls for every sources.yaml entry."""
    if src.get("enabled") is False:
        return Verdict(False, SourceStatus.INVALID, f"switched off in sources.yaml: {src.get('note') or 'no note'}")

    known = registry.status(src["id"])
    if known == SourceStatus.VALID:
        return Verdict(True, SourceStatus.VALID, "known valid (already ingested before)")
    if known == SourceStatus.INVALID:
        record = registry.get_by_id(src["id"])
        return Verdict(False, SourceStatus.INVALID, f"known invalid: {record.validation_reason}")
    return check_unknown(src, offline=offline)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--offline", action="store_true", help="skip robots.txt checks")
    args = parser.parse_args(argv)

    registry = SourceRegistry()
    sources = yaml.safe_load(config.SOURCES_YAML.read_text(encoding="utf-8"))["sources"]
    counts = Counter()
    for src in sources:
        verdict = decide(src, registry, offline=args.offline)
        counts[verdict.status.value] += 1
        if not verdict.use:
            print(f"  {verdict.status.value:8} {src['site']:8} {src['id']}: {verdict.reason}")
    print(f"\n{dict(counts)} across {len(sources)} sources in {config.SOURCES_YAML.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
