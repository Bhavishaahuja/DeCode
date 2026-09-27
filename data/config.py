"""Shared constants for the DeCode data layer: sites, periods, systems, paths, and the PASSAGE schema."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import TypedDict

import yaml

DATA_DIR = Path(__file__).resolve().parent
RAW_DIR = DATA_DIR / "raw"                 # downloaded originals (git-ignored)
TEXT_DIR = DATA_DIR / "text"               # extracted plain text, one file per source (git-ignored)
INDEX_DIR = DATA_DIR / "index"             # persistent Chroma collection (committed, small)
SOURCES_YAML = DATA_DIR / "sources.yaml"   # hand-curated source list
RESOLVED_YAML = DATA_DIR / "sources.resolved.yaml"  # every concrete source actually ingested (title/url/license)
PASSAGES_JSONL = DATA_DIR / "passages.jsonl"
SYSTEMS_YAML = DATA_DIR / "systems.yaml"
HANDSPLIT_DIR = DATA_DIR.parent / "claims" / "handsplit"   # Dev 2's hand-split sources, merged in by ingest
HANDSPLIT_PASSAGES = HANDSPLIT_DIR / "passages.jsonl"
HANDSPLIT_SOURCES = HANDSPLIT_DIR / "sources.yaml"

COLLECTION = "decode_passages"
EMBED_MODEL = "BAAI/bge-small-en-v1.5"
# bge v1.5 recommends this prefix on *queries only* (not on passages).
QUERY_INSTRUCTION = "Represent this sentence for searching relevant passages: "
LLM_TAG_MODEL = "claude-sonnet-5"

# Chunking, measured in tokens of the embedding model's tokenizer when available (else ~words * 1.3).
CHUNK_TARGET_TOKENS = 400
CHUNK_MIN_TOKENS = 300
CHUNK_MAX_TOKENS = 500
CHUNK_OVERLAP_TOKENS = 60

MAX_DOWNLOAD_BYTES = 500 * 1024 * 1024     # ask a human before anything bigger (see ingest --allow-large)
MIN_PASSAGES_PER_SITE = 300

# ---------------------------------------------------------------------------------------------
# Sites. Contract ids (CLAUDE.md): giza, uruk, mohenjo, qin. Stored data only ever uses these.
# Aliases are accepted as search input by search_evidence(site=...), never stored.
SITES: dict[str, dict] = {
    "giza": {
        "name": "Giza pyramid complex",
        "aliases": ["giza", "gizeh", "great pyramid", "pyramids of giza", "khufu"],
        "default_period": "Old Kingdom, Dynasty 4 (c. 2600-2500 BCE)",
    },
    "uruk": {
        "name": "Uruk (Warka)",
        "aliases": ["uruk", "warka", "erech", "unug", "eanna", "white temple", "anu ziggurat"],
        "default_period": "Uruk period (c. 4000-3100 BCE)",
    },
    "mohenjo": {
        "name": "Mohenjo-daro",
        "aliases": ["mohenjo-daro", "mohenjo daro", "mohenjo_daro", "mohenjodaro", "moenjodaro", "indus", "harappan"],
        "default_period": "Mature Harappan (c. 2600-1900 BCE)",
    },
    "qin": {
        "name": "Qin walls and roads",
        "aliases": ["qin", "qin walls", "qin roads", "qin great wall", "great wall", "straight road", "zhidao",
                    "qin dynasty", "qin shi huang", "meng tian"],
        "default_period": "Qin dynasty (221-206 BCE)",
    },
}

# Period rules: first matching regex wins; otherwise the source's period, otherwise the site default.
PERIOD_RULES: dict[str, list[tuple[str, str]]] = {
    "giza": [
        (r"\b(old kingdom|fourth dynasty|4th dynasty|dynasty 4|khufu|cheops|khafre|chephren|menkaure|mycerinus|sneferu|snofru)\b",
         "Old Kingdom, Dynasty 4 (c. 2600-2500 BCE)"),
        (r"\b(fifth dynasty|5th dynasty|sixth dynasty|6th dynasty)\b", "Old Kingdom, Dynasties 5-6 (c. 2500-2180 BCE)"),
        (r"\b(new kingdom|eighteenth dynasty|18th dynasty|thutmose|amenhotep)\b", "New Kingdom (c. 1550-1070 BCE)"),
        (r"\b(saite|26th dynasty|late period)\b", "Late Period (c. 664-332 BCE)"),
        (r"\b(ptolemaic|roman period|greco-roman)\b", "Graeco-Roman (332 BCE-395 CE)"),
    ],
    "uruk": [
        (r"\b(ubaid)\b", "Ubaid period (c. 5500-4000 BCE)"),
        (r"\b(jemdet nasr)\b", "Jemdet Nasr period (c. 3100-2900 BCE)"),
        (r"\b(early dynastic|gilgamesh|enmerkar|lugalbanda)\b", "Early Dynastic (c. 2900-2350 BCE)"),
        (r"\b(ur iii|third dynasty of ur|ur-nammu|ur-namma|shulgi)\b", "Ur III (c. 2112-2004 BCE)"),
        (r"\b(neo-babylonian|nebuchadnezzar|achaemenid)\b", "Neo-Babylonian / Achaemenid (c. 626-330 BCE)"),
        (r"\b(seleucid|parthian|bit resh)\b", "Seleucid / Parthian (c. 312 BCE-224 CE)"),
        (r"\b(uruk period|late uruk|middle uruk|early uruk|eanna|anu ziggurat|white temple|proto-cuneiform|beveled[- ]rim|bevelled[- ]rim)\b",
         "Uruk period (c. 4000-3100 BCE)"),
    ],
    "mohenjo": [
        (r"\b(early harappan|kot diji|pre-harappan)\b", "Early Harappan (c. 3200-2600 BCE)"),
        (r"\b(late harappan|post-urban|decline|cemetery h)\b", "Late Harappan (c. 1900-1300 BCE)"),
        (r"\b(mature harappan|urban phase|harappan civili[sz]ation|indus civili[sz]ation)\b", "Mature Harappan (c. 2600-1900 BCE)"),
    ],
    "qin": [
        (r"\b(warring states|qin state|state of qin|duke xiao|shang yang|zhao wall|yan wall|dujiangyan|zhengguo)\b",
         "Warring States (475-221 BCE)"),
        (r"\b(qin shi ?huang|first emperor|qin dynasty|meng tian|straight road|zhidao|lingqu|ying zheng)\b",
         "Qin dynasty (221-206 BCE)"),
        (r"\b(han dynasty|western han|sima qian|shiji)\b", "Western Han (206 BCE-9 CE) account"),
        (r"\b(ming dynasty|ming wall)\b", "Ming dynasty (1368-1644 CE), later rebuild"),
    ],
}

# Source types from Contract 1. Anything older in sources.yaml gets mapped through SOURCE_TYPE_MAP.
SOURCE_TYPES = ["excavation_report", "primary_text", "scholarship", "reference", "dataset"]
SOURCE_TYPE_MAP = {
    "excavation_report": "excavation_report",
    "primary_text": "primary_text",
    "scholarship": "scholarship",
    "reference": "reference",
    "dataset": "dataset",
    # older labels, just in case one sneaks back in
    "book": "scholarship",
    "journal_article": "scholarship",
    "thesis": "scholarship",
    "encyclopedia": "reference",
    "place_record": "reference",
}

TAGGED_BY = ["rules", "llm", "none"]


def contract_source_type(raw_type: str) -> str:
    """Map whatever sources.yaml says to one of the 5 contract source types."""
    mapped = SOURCE_TYPE_MAP.get((raw_type or "").strip().lower())
    if mapped is None:
        raise ValueError(f"Unknown source type {raw_type!r}. Use one of {SOURCE_TYPES}")
    return mapped


# ---------------------------------------------------------------------------------------------
class Passage(TypedDict):
    """Contract 1 (CLAUDE.md). One line per passage in passages.jsonl.

    search_evidence() returns these plus "score": float. score never goes in the jsonl file.
    Every field is required; author, year and locator may be None.
    """
    passage_id: str      # "<site>-<source_id>-<0000>", stable across rebuilds of the same source
    source_id: str       # key into the source registry and sources.resolved.yaml
    site: str            # one of SITES (giza, uruk, mohenjo, qin)
    title: str           # source title
    author: str | None   # source author, "Wikipedia contributors" for Wikipedia
    year: int | None     # publication year (retrieval year for living web pages)
    url: str             # canonical source URL (for citation)
    license: str         # license string exactly as recorded for the source
    source_type: str     # excavation_report | primary_text | scholarship | reference | dataset
    period: str          # human-readable period label
    locator: str | None  # "p. 42" or "section: Construction", else None
    text: str            # 300-500 tokens of cleaned text
    system_tags: list[str]  # subset of the 9 systems (may be empty)
    tagged_by: str       # rules | llm | none


# Extra fields we keep on top of the contract (allowed, they never replace a required one).
PASSAGE_EXTRA_KEYS = ["page", "char_start", "char_end"]

PASSAGE_KEYS = list(Passage.__annotations__)


@lru_cache(maxsize=1)
def load_systems() -> dict[str, dict]:
    return yaml.safe_load(SYSTEMS_YAML.read_text(encoding="utf-8"))["systems"]


def system_ids() -> list[str]:
    return list(load_systems())


def _norm(s: str) -> str:
    return re.sub(r"[\s\-]+", "_", s.strip().lower())


def resolve_site(site: str | None) -> str | None:
    """Map 'Mohenjo-daro', 'Warka', 'Great Wall' ... to a contract site id. None passes through."""
    if site is None:
        return None
    key = _norm(site)
    for slug, info in SITES.items():
        if key == slug or key in {_norm(a) for a in info["aliases"]}:
            return slug
    raise ValueError(f"Unknown site {site!r}. Known: {sorted(SITES)}")


def resolve_system(system: str | None) -> str | None:
    """Map 'QA', 'water', 'transport_lifting' ... to a canonical system id. None passes through."""
    if system is None:
        return None
    key = _norm(system)
    for sid, info in load_systems().items():
        if key == sid or key in {_norm(a) for a in info.get("aliases", [])}:
            return sid
    raise ValueError(f"Unknown system {system!r}. Known: {system_ids()}")
