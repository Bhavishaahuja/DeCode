"""Hand-split my own sources into passages until Dev 1's index lands.

Reads claims/handsplit/sources.yaml, splits each PDF or text file into
300 to 500 token passages (Contract 1), rule-tags them with the taxonomy
keywords, and writes claims/handsplit/passages.jsonl.

Usage:
    python -m claims.split              # all sources
    python -m claims.split --source giza-petrie1883
"""

import argparse
import re
from pathlib import Path

import yaml

from claims.common import (
    CLAIMS_DIR, HANDSPLIT_PASSAGES, SITES, SOURCE_TYPES,
    load_taxonomy, read_jsonl, write_jsonl,
)

SOURCES_YAML = CLAIMS_DIR / "handsplit" / "sources.yaml"
FILES_DIR = CLAIMS_DIR / "handsplit" / "files"

# roughly 1.33 tokens per English word, so 225 to 375 words is about 300 to 500 tokens
TARGET_WORDS = 280
MAX_WORDS = 375
MIN_WORDS = 60  # tiny leftovers get glued onto the previous passage


def read_pages(path):
    """Return a list of page texts. PDFs use pypdf, text files split on form feeds."""
    path = Path(path)
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        pages = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")
        return pages
    text = path.read_text(encoding="utf-8", errors="replace")
    # archive.org _djvu.txt files use form feeds between pages
    return text.split("\f")


def clean_page(text):
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        # drop lines that are just a page number or roman numeral
        if re.fullmatch(r"[\divxlcIVXLC\.\s]{1,8}", stripped):
            continue
        lines.append(stripped)
    text = "\n".join(lines)
    # join words broken across lines: "exca-\nvation" becomes "excavation"
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    # keep paragraph breaks, flatten everything else
    text = re.sub(r"\n{2,}", "<PARA>", text)
    text = re.sub(r"\s+", " ", text)
    text = text.replace("<PARA>", "\n\n")
    return text.strip()


def split_into_chunks(pages, page_offset):
    """Group paragraphs into passages, remembering which page each passage starts on."""
    chunks = []
    current_words = []
    current_page = None

    for page_index, page_text in enumerate(pages):
        printed_page = page_index + 1 - page_offset
        paragraphs = [p for p in clean_page(page_text).split("\n\n") if p.strip()]
        for paragraph in paragraphs:
            words = paragraph.split()
            # a giant paragraph gets cut into sentence-ish pieces first
            while len(words) > MAX_WORDS:
                cut = MAX_WORDS
                for i in range(MAX_WORDS - 1, TARGET_WORDS // 2, -1):
                    if words[i].endswith((".", ";", ":")):
                        cut = i + 1
                        break
                if current_words:
                    chunks.append((current_page, current_words))
                    current_words = []
                chunks.append((printed_page, words[:cut]))
                words = words[cut:]
            if not words:
                continue
            if current_words and len(current_words) + len(words) > MAX_WORDS:
                chunks.append((current_page, current_words))
                current_words = []
            if not current_words:
                current_page = printed_page
            current_words = current_words + words
            if len(current_words) >= TARGET_WORDS:
                chunks.append((current_page, current_words))
                current_words = []

    if current_words:
        if chunks and len(current_words) < MIN_WORDS:
            last_page, last_words = chunks[-1]
            chunks[-1] = (last_page, last_words + current_words)
        else:
            chunks.append((current_page, current_words))
    return chunks


def build_keyword_patterns(taxonomy):
    patterns = {}
    for system_id, info in taxonomy["systems"].items():
        words = info["keywords"]["ancient"] + info["keywords"]["modern"]
        compiled = []
        for word in words:
            compiled.append(re.compile(r"\b" + re.escape(word.lower()) + r"\b"))
        patterns[system_id] = compiled
    return patterns


def tag_systems(text, patterns, min_hits=2, max_tags=3):
    lowered = text.lower()
    scores = []
    for system_id, compiled in patterns.items():
        hits = 0
        for pattern in compiled:
            hits += len(pattern.findall(lowered))
        if hits >= min_hits:
            scores.append((hits, system_id))
    scores.sort(reverse=True)
    tags = []
    for hits, system_id in scores[:max_tags]:
        tags.append(system_id)
    return tags


def check_source(source):
    problems = []
    for field in ["source_id", "site", "file", "title", "author", "year", "url", "license", "source_type"]:
        if not source.get(field):
            problems.append(f"missing {field}")
    if source.get("site") not in SITES:
        problems.append(f"bad site {source.get('site')}")
    if source.get("source_type") not in SOURCE_TYPES:
        problems.append(f"bad source_type {source.get('source_type')}")
    if source.get("reuse_allowed") is not True:
        problems.append("reuse_allowed is not true, skipping (check the license first)")
    if source.get("source_id") and not source["source_id"].startswith(f"{source.get('site')}-"):
        problems.append("source_id should start with the site id")
    return problems


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", help="only split this source_id")
    args = parser.parse_args()

    with open(SOURCES_YAML, encoding="utf-8") as f:
        sources = yaml.safe_load(f).get("sources") or []

    patterns = build_keyword_patterns(load_taxonomy())

    # keep passages from sources we're not re-splitting this run
    kept = []
    for row in read_jsonl(HANDSPLIT_PASSAGES):
        if args.source and row["source_id"] != args.source:
            kept.append(row)
    all_passages = kept

    for source in sources:
        if args.source and source.get("source_id") != args.source:
            continue
        problems = check_source(source)
        if problems:
            print(f"SKIP {source.get('source_id')}: {'; '.join(problems)}")
            continue
        path = FILES_DIR / source["file"]
        if not path.exists():
            print(f"SKIP {source['source_id']}: file not found at {path}")
            continue

        pages = read_pages(path)
        chunks = split_into_chunks(pages, source.get("page_offset", 0))
        tagged_count = 0
        for n, (page, words) in enumerate(chunks, start=1):
            text = " ".join(words)
            tags = tag_systems(text, patterns)
            if tags:
                tagged_count += 1
            locator = None
            if source.get("has_pages", True) and page is not None and page > 0:
                locator = f"p. {page}"
            all_passages.append({
                "passage_id": f"{source['source_id']}-{n:04d}",
                "source_id": source["source_id"],
                "site": source["site"],
                "title": source["title"],
                "author": source["author"],
                "year": source["year"],
                "url": source["url"],
                "license": source["license"],
                "source_type": source["source_type"],
                "period": source.get("period"),
                "locator": locator,
                "text": text,
                "system_tags": tags,
                "tagged_by": "rules" if tags else "none",
            })
        print(f"{source['source_id']}: {len(pages)} pages, {len(chunks)} passages, {tagged_count} tagged")

    write_jsonl(HANDSPLIT_PASSAGES, all_passages)
    print(f"wrote {len(all_passages)} passages to {HANDSPLIT_PASSAGES}")


if __name__ == "__main__":
    main()
