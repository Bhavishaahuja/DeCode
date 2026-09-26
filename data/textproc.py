"""Text cleaning, site filtering and token-aware chunking."""
from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from . import config

# ---------------------------------------------------------------------------------------------
# Token counting: use the embedding model's own tokenizer when installed, else a close approximation.

@lru_cache(maxsize=1)
def _tokenizer():
    try:
        from transformers import AutoTokenizer  # installed with sentence-transformers
        return AutoTokenizer.from_pretrained(config.EMBED_MODEL)
    except Exception:
        return None


_WORDISH = re.compile(r"\w+|[^\w\s]")


def count_tokens(text: str) -> int:
    tok = _tokenizer()
    if tok is not None:
        return len(tok.encode(text, add_special_tokens=False))
    # WordPiece splits ~15% of English words into more than one piece.
    return int(len(_WORDISH.findall(text)) * 1.15) + 1


# ---------------------------------------------------------------------------------------------
# Cleaning

_TAIL_SECTIONS = re.compile(
    r"^\s*(=+\s*)?(references|bibliography|works cited|literature cited|notes and references|see also|external links|"
    r"further reading|footnotes|citations|sources|acknowledg(e)?ments?|author contributions|competing interests|"
    r"conflicts? of interest|data availability( statement)?|funding)\s*(=+)?\s*$",
    re.I | re.M,
)


def cut_tail_sections(text: str, min_frac: float = 0.4) -> str:
    """Drop reference lists etc. Only cuts at a heading that appears after min_frac of the text."""
    cut = None
    for m in _TAIL_SECTIONS.finditer(text):
        if m.start() >= len(text) * min_frac:
            cut = m.start() if cut is None else min(cut, m.start())
    return text[:cut] if cut else text


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("­", "")
    text = re.sub(r"[​﻿]", "", text)
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)                  # de-hyphenate line breaks
    text = re.sub(r"^\s*(page )?\d{1,4}\s*$", "", text, flags=re.M | re.I)  # bare page numbers
    text = re.sub(r"^\s*=+\s*(.*?)\s*=+\s*$", r"\n\1\n", text, flags=re.M)  # wiki headings -> plain lines
    text = re.sub(r"\[\d+(,\s*\d+)*\]", "", text)                    # [12] style citation marks
    text = re.sub(r"[ \t]+", " ", text)
    # Join hard-wrapped lines inside paragraphs (OCR / PDF), keep blank-line paragraph breaks.
    text = re.sub(r"(?<![\n.:;!?])\n(?!\n)", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def ocr_quality(text: str) -> float:
    """Share of word tokens that look like real words (letters, 2+ chars, few digits). 0..1."""
    words = re.findall(r"\S+", text)
    if not words:
        return 0.0
    good = sum(1 for w in words if re.fullmatch(r"[A-Za-z][a-z'’\-]*[.,;:!?)\"]?", w))
    return good / len(words)


# ---------------------------------------------------------------------------------------------
# Site filter for general works: keep paragraphs that mention the site, plus `window` neighbours.

def keep_matching(text: str, pattern: str, window: int = 2) -> str:
    paras = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    rx = re.compile(pattern, re.I)
    hits = [i for i, p in enumerate(paras) if rx.search(p)]
    keep = set()
    for i in hits:
        keep.update(range(max(0, i - window), min(len(paras), i + window + 1)))
    return "\n\n".join(paras[i] for i in sorted(keep))


# ---------------------------------------------------------------------------------------------
# Chunking

@dataclass
class Chunk:
    text: str
    char_start: int
    char_end: int


_SENT_SPLIT = re.compile(r"(?<=[.!?])[\"')\]]?\s+(?=[\"'(\[]?[A-Z0-9])|\n\s*\n")


def _sentence_spans(text: str) -> list[tuple[int, int]]:
    spans, start = [], 0
    for m in _SENT_SPLIT.finditer(text):
        g = m.group(0)
        seg_end = m.start() + (len(g) - len(g.lstrip("\"')]")))  # keep a closing quote/bracket with its sentence
        if seg_end > start:
            spans.append((start, seg_end))
        start = m.end()
    if start < len(text):
        spans.append((start, len(text)))
    # Split very long "sentences" (tables, OCR run-ons) on word boundaries.
    out = []
    for s, e in spans:
        while e - s > 1800:
            cut = text.rfind(" ", s, s + 1500)
            cut = cut if cut > s else s + 1500
            out.append((s, cut))
            s = cut + 1
        if e > s:
            out.append((s, e))
    return [(s, e) for s, e in out if text[s:e].strip()]


def chunk_text(text: str, target: int = config.CHUNK_TARGET_TOKENS, max_tokens: int = config.CHUNK_MAX_TOKENS,
               overlap: int = config.CHUNK_OVERLAP_TOKENS, min_tokens: int = config.CHUNK_MIN_TOKENS) -> list[Chunk]:
    """Pack whole sentences into ~target-token chunks; each chunk starts with ~overlap tokens of the previous one."""
    spans = _sentence_spans(text)
    if not spans:
        return []
    ntok = [count_tokens(text[s:e]) for s, e in spans]
    chunks: list[Chunk] = []
    i = 0
    while i < len(spans):
        j, total = i, 0
        while j < len(spans) and (total + ntok[j] <= max_tokens or j == i):
            total += ntok[j]
            j += 1
            if total >= target:
                break
        s, e = spans[i][0], spans[j - 1][1]
        chunks.append(Chunk(text[s:e].strip(), s, e))
        if j >= len(spans):
            break
        # Step back to create ~overlap tokens of overlap, but always advance.
        k, back = j, 0
        while k - 1 > i and back + ntok[k - 1] <= overlap:
            k -= 1
            back += ntok[k]
        i = k if k > i else j
    # Merge a too-short final chunk into its predecessor when that stays under the max.
    if len(chunks) >= 2 and count_tokens(chunks[-1].text) < min_tokens // 2:
        a, b = chunks[-2], chunks[-1]
        merged = text[a.char_start:b.char_end].strip()
        if count_tokens(merged) <= max_tokens + overlap:
            chunks[-2:] = [Chunk(merged, a.char_start, b.char_end)]
    return chunks
