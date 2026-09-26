"""Shared constants for the Stratum data layer: sites, periods, systems, paths, and the PASSAGE schema."""
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

COLLECTION = "stratum_passages"
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
# Sites. Slugs are what goes in PASSAGE["site"]; aliases are accepted by search_evidence(site=...).
SITES: dict[str, dict] = {
    "giza": {
        "name": "Giza pyramid complex",
        "aliases": ["giza", "gizeh", "great pyramid", "pyramids of giza", "khufu"],
        "default_period": "Old Kingdom, Dynasty 4 (c. 2600-2500 BCE)",
    },
    "mohenjo_daro": {
        "name": "Mohenjo-daro",
        "aliases": ["mohenjo-daro", "mohenjo daro", "mohenjodaro", "moenjodaro", "indus", "harappan"],
        "default_period": "Mature Harappan (c. 2600-1900 BCE)",
    },
    "ur": {
        "name": "Ur (Tell el-Muqayyar)",
        "aliases": ["ur", "ur of the chaldees", "tell el-muqayyar", "ziggurat of ur"],
        "default_period": "Early Dynastic III to Ur III (c. 2600-2000 BCE)",
    },
    "qin_mausoleum": {
        "name": "Mausoleum of Qin Shi Huang (Lishan, Xi'an)",
        "aliases": ["qin", "qin mausoleum", "qin shi huang", "terracotta army", "lishan", "xi'an", "xian"],
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
    "mohenjo_daro": [
        (r"\b(early harappan|kot diji|pre-harappan)\b", "Early Harappan (c. 3200-2600 BCE)"),
        (r"\b(late harappan|post-urban|decline|cemetery h)\b", "Late Harappan (c. 1900-1300 BCE)"),
        (r"\b(mature harappan|urban phase|harappan civili[sz]ation|indus civili[sz]ation)\b", "Mature Harappan (c. 2600-1900 BCE)"),
    ],
    "ur": [
        (r"\b(ubaid)\b", "Ubaid period (c. 5500-4000 BCE)"),
        (r"\b(royal cemetery|royal tombs?|puabi|meskalamdug|early dynastic)\b", "Early Dynastic III (c. 2600-2350 BCE)"),
        (r"\b(akkadian|sargon)\b", "Akkadian (c. 2350-2150 BCE)"),
        (r"\b(ur iii|third dynasty of ur|ur-nammu|ur-namma|shulgi|šulgi|amar-sin|ibbi-sin)\b", "Ur III (c. 2112-2004 BCE)"),
        (r"\b(isin-larsa|old babylonian|larsa)\b", "Isin-Larsa / Old Babylonian (c. 2000-1600 BCE)"),
        (r"\b(nabonidus|nebuchadnezzar|neo-babylonian)\b", "Neo-Babylonian (c. 626-539 BCE)"),
    ],
    "qin_mausoleum": [
        (r"\b(warring states|qin state|duke xiao|shang yang)\b", "Warring States Qin (475-221 BCE)"),
        (r"\b(qin shi ?huang|first emperor|qin dynasty|terracotta|lishan|ying zheng)\b", "Qin dynasty (221-206 BCE)"),
        (r"\b(han dynasty|western han|sima qian|shiji)\b", "Western Han (206 BCE-9 CE) account"),
    ],
}

# ---------------------------------------------------------------------------------------------
class Passage(TypedDict):
    """One retrievable chunk of evidence. search_evidence() returns these plus "score": float."""
    id: str              # "<site>-<source_id>-<0000>", stable across rebuilds of the same source
    text: str            # 300-500 tokens of cleaned text
    site: str            # one of SITES
    period: str          # human-readable period label
    system_tags: list[str]  # subset of SYSTEMS (may be empty)
    source_id: str       # key into sources.resolved.yaml
    title: str           # source title
    url: str             # canonical source URL (for citation)
    license: str         # license string exactly as recorded for the source
    source_type: str     # excavation_report | journal_article | encyclopedia | primary_text | book | dataset | place_record
    page: int | None     # 1-based PDF page where the passage starts, if known
    char_start: int      # offset into the extracted text of the source
    char_end: int


PASSAGE_KEYS = list(Passage.__annotations__)


@lru_cache(maxsize=1)
def load_systems() -> dict[str, dict]:
    return yaml.safe_load(SYSTEMS_YAML.read_text(encoding="utf-8"))["systems"]


def system_ids() -> list[str]:
    return list(load_systems())


def _norm(s: str) -> str:
    return re.sub(r"[\s\-]+", "_", s.strip().lower())


def resolve_site(site: str | None) -> str | None:
    """Map 'Mohenjo-daro', 'mohenjo_daro', 'Terracotta Army' ... to a site slug. None passes through."""
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
