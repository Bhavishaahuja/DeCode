"""Shared bits for the claims pipeline: paths, loaders, and the claim validator.

Every script (extract, dedupe, review, validate) checks claims through
validate_claim() here, so the rules only live in one place.
"""

import json
import re
from pathlib import Path

import yaml

CLAIMS_DIR = Path(__file__).resolve().parent
REPO_ROOT = CLAIMS_DIR.parent

TAXONOMY_PATH = CLAIMS_DIR / "taxonomy.yaml"
HANDSPLIT_PASSAGES = CLAIMS_DIR / "handsplit" / "passages.jsonl"
DEV1_PASSAGES = REPO_ROOT / "data" / "passages.jsonl"
DRAFT_PATH = CLAIMS_DIR / "draft" / "claims.jsonl"
DEDUPED_PATH = CLAIMS_DIR / "draft" / "claims_deduped.jsonl"
DECISIONS_PATH = CLAIMS_DIR / "draft" / "decisions.jsonl"
VERIFIED_PATH = CLAIMS_DIR / "verified" / "claims.jsonl"

SITES = ["giza", "uruk", "mohenjo", "qin"]
GRADES = ["attested", "debated", "inferred"]
SOURCE_TYPES = ["excavation_report", "primary_text", "scholarship", "reference", "dataset"]

# the systems every site must cover before we call the claim set done
REQUIRED_SYSTEMS = ["transport_lifting", "materials_supply", "workforce", "water_sanitation", "quality_control"]

CLAIM_FIELDS = [
    "claim_id", "site", "system", "statement", "quote", "grade", "sources",
    "modern_equivalent", "lesson", "status", "reviewed_by",
]
SOURCE_FIELDS = ["source_id", "passage_id", "title", "url", "locator"]

# fields a draft may carry on top of the contract, review.py strips them on accept
DRAFT_EXTRA_FIELDS = ["grade_reason", "grade_conflict", "merged_from"]

MAX_QUOTE_WORDS = 40
VERIFIED_ID_PATTERN = re.compile(r"^(giza|uruk|mohenjo|qin)-([a-z_]+)-(\d{3})$")
BANNED_DASHES = ["\u2014", "\u2013"]  # em dash, en dash


def load_taxonomy():
    with open(TAXONOMY_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def system_ids():
    return list(load_taxonomy()["systems"].keys())


def read_jsonl(path):
    rows = []
    path = Path(path)
    if not path.exists():
        return rows
    with open(path, encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as err:
                raise ValueError(f"{path}:{line_no} is not valid JSON ({err})")
    return rows


def write_jsonl(path, rows):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def append_jsonl(path, row):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # if someone hand-edited the file and dropped the last newline, add it back
    # so the new row doesn't get glued onto the previous one
    needs_newline = False
    if path.exists() and path.stat().st_size > 0:
        with open(path, "rb") as f:
            f.seek(-1, 2)
            needs_newline = f.read(1) != b"\n"
    with open(path, "a", encoding="utf-8") as f:
        if needs_newline:
            f.write("\n")
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_passages():
    """All passages we can cite, keyed by passage_id.

    Dev 1's data/passages.jsonl wins, and my hand-split set fills in anything
    Dev 1 hasn't ingested (the contract allows both before hour 8).
    """
    passages = {}
    for row in read_jsonl(HANDSPLIT_PASSAGES):
        passages[row["passage_id"]] = row
    for row in read_jsonl(DEV1_PASSAGES):
        passages[row["passage_id"]] = row
    return passages


def squash_spaces(text):
    # PDFs love random line breaks and double spaces, so compare with whitespace collapsed.
    # This is the only loosening of "verbatim" we allow.
    return re.sub(r"\s+", " ", text or "").strip()


def quote_in_passage(quote, passage_text):
    return squash_spaces(quote) in squash_spaces(passage_text)


def word_count(text):
    return len((text or "").split())


def source_from_passage(passage):
    """Build a claim source straight from the passage. The model never writes sources."""
    return {
        "source_id": passage["source_id"],
        "passage_id": passage["passage_id"],
        "title": passage.get("title"),
        "url": passage.get("url"),
        "locator": passage.get("locator"),
    }


def validate_claim(claim, passages, systems=None, verified=False):
    """Return a list of problems. Empty list means the claim is good.

    verified=True applies the stricter rules for claims/verified/claims.jsonl:
    exact contract fields only, status verified, reviewer set, final id format.
    """
    problems = []
    if systems is None:
        systems = system_ids()

    allowed = set(CLAIM_FIELDS)
    if not verified:
        allowed = allowed | set(DRAFT_EXTRA_FIELDS)

    for field in CLAIM_FIELDS:
        if field not in claim:
            problems.append(f"missing field: {field}")
    for field in claim:
        if field not in allowed:
            problems.append(f"unexpected field: {field}")
    if problems and any(p.startswith("missing") for p in problems):
        return problems

    if claim["site"] not in SITES:
        problems.append(f"bad site: {claim['site']}")
    if claim["system"] not in systems:
        problems.append(f"bad system: {claim['system']}")
    if claim["grade"] not in GRADES:
        problems.append(f"bad grade: {claim['grade']}")

    for field in ["statement", "quote", "modern_equivalent", "lesson"]:
        value = claim.get(field)
        if not isinstance(value, str) or not value.strip():
            problems.append(f"empty {field}")
            continue
        for dash in BANNED_DASHES:
            if dash in value and field != "quote":
                # quotes are verbatim so a dash in the source is fine, everything else is ours
                problems.append(f"{field} contains an em or en dash")
                break

    if word_count(claim.get("quote")) > MAX_QUOTE_WORDS:
        problems.append(f"quote is {word_count(claim['quote'])} words, max {MAX_QUOTE_WORDS}")

    sources = claim.get("sources")
    if not isinstance(sources, list) or len(sources) == 0:
        problems.append("needs at least 1 source")
    else:
        for i, source in enumerate(sources):
            for field in SOURCE_FIELDS:
                if field not in source:
                    problems.append(f"source {i} missing {field}")
            passage = passages.get(source.get("passage_id"))
            if passage is None:
                problems.append(f"source {i} passage_id not found: {source.get('passage_id')}")
                continue
            if passage["source_id"] != source.get("source_id"):
                problems.append(f"source {i} source_id does not match its passage")
            if passage["site"] != claim["site"]:
                problems.append(f"source {i} passage is from site {passage['site']}")
        # the quote has to sit in the first source's passage, word for word
        first = passages.get(sources[0].get("passage_id"))
        if first is not None and not quote_in_passage(claim.get("quote", ""), first["text"]):
            problems.append("quote not found verbatim in the first source's passage")

    if verified:
        if claim["status"] != "verified":
            problems.append("status must be verified")
        if not claim.get("reviewed_by"):
            problems.append("reviewed_by is empty")
        match = VERIFIED_ID_PATTERN.match(claim["claim_id"])
        if not match:
            problems.append(f"claim_id format should be site-system-NNN, got {claim['claim_id']}")
        elif match.group(1) != claim["site"] or match.group(2) != claim["system"]:
            problems.append("claim_id site or system does not match the claim")

    return problems
