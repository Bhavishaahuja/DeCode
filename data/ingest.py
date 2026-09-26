"""Download -> extract -> clean -> chunk -> tag -> data/passages.jsonl (+ data/sources.resolved.yaml).

    python -m data.ingest                      # everything (uses the cache in data/raw/ when present)
    python -m data.ingest --sites giza,ur      # subset
    python -m data.ingest --offline            # cache only, no network
    python -m data.ingest --no-discovery       # curated sources only (skip OpenAlex)
    python -m data.ingest --allow-large        # permit single downloads > 500 MB (ask first!)

char_start / char_end in each passage are offsets into data/text/<source_id>.txt (the cleaned text).
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict

import yaml

from . import config, fetch, tagging, textproc

MIN_CHUNK_TOKENS = 60
MIN_OCR_QUALITY = 0.6
MAX_SOURCES_PER_SITE = 60

OPENALEX_TYPE = {"article": "journal_article", "review": "journal_article", "book-chapter": "book", "book": "book",
                 "preprint": "journal_article", "dissertation": "thesis"}


def log(*a):
    print(*a, file=sys.stderr, flush=True)


def load_sources() -> dict:
    return yaml.safe_load(config.SOURCES_YAML.read_text(encoding="utf-8"))


def _page_for(chunk_text: str, raw_text: str, page_starts: list[int]) -> int | None:
    if not page_starts:
        return None
    probe = chunk_text[:80]
    pos = raw_text.find(probe)
    if pos < 0:
        return None
    page = 0
    for i, s in enumerate(page_starts):
        if s <= pos:
            page = i
        else:
            break
    return page + 1


def process_source(src: dict, res: fetch.FetchResult) -> tuple[str, list[dict]]:
    """Clean + filter + chunk one fetched source. Returns (clean_text, passages)."""
    site = src["site"]
    raw = res.text
    text = raw if res.page_starts else textproc.clean_text(raw)
    text = textproc.cut_tail_sections(text)
    if src.get("keep_regex"):
        text = textproc.keep_matching(text, src["keep_regex"])
    passages = []
    for i, ch in enumerate(textproc.chunk_text(text)):
        if textproc.count_tokens(ch.text) < MIN_CHUNK_TOKENS or textproc.ocr_quality(ch.text) < MIN_OCR_QUALITY:
            continue
        passages.append({
            "id": f"{site}-{src['id']}-{i:04d}",
            "text": ch.text,
            "site": site,
            "period": tagging.period_for(ch.text, site, src.get("period")),
            "system_tags": tagging.keyword_tags(ch.text),
            "source_id": src["id"],
            "title": src["title"],
            "url": src["url"],
            "license": src["license"],
            "source_type": src["type"],
            "page": _page_for(ch.text, raw, res.page_starts),
            "char_start": ch.char_start,
            "char_end": ch.char_end,
        })
    return text, passages


def ingest_one(src: dict, args) -> tuple[dict, list[dict]] | None:
    kind = src["fetch"]["kind"]
    try:
        res = fetch.FETCHERS[kind](src["fetch"], offline=args.offline, allow_large=args.allow_large)
    except fetch.TooLarge as e:
        log(f"  [ASK FIRST] {src['id']}: {e}")
        return None
    except (fetch.FetchError, KeyError, ValueError) as e:
        log(f"  [skip] {src['id']}: {e}")
        return None
    except Exception as e:  # never let one source kill the build
        log(f"  [skip] {src['id']}: {type(e).__name__}: {e}")
        return None
    return finish(src, res)


def finish(src: dict, res: fetch.FetchResult) -> tuple[dict, list[dict]] | None:
    src = dict(src)
    src["url"] = res.url or src["url"]
    if res.title and src["type"] != "encyclopedia" and not src.get("keep_title"):
        src.setdefault("upstream_title", res.title)
    if res.title and src["type"] == "encyclopedia":
        src["title"] = res.title
    if res.license:
        src["license"] = res.license
    text, passages = process_source(src, res)
    if not passages:
        log(f"  [skip] {src['id']}: no usable passages after cleaning/filtering")
        return None
    config.TEXT_DIR.mkdir(parents=True, exist_ok=True)
    (config.TEXT_DIR / f"{src['id']}.txt").write_text(text, encoding="utf-8")
    resolved = {k: src[k] for k in ("id", "site", "type", "title", "url", "license") if k in src}
    for k in ("period", "year", "note", "upstream_title", "doi"):
        if src.get(k):
            resolved[k] = src[k]
    resolved.update({"retrieved": dt.date.today().isoformat(), "n_passages": len(passages)})
    for k, v in res.extra.items():
        if v:
            resolved[k] = v
    log(f"  [ok] {src['id']}: {len(passages)} passages")
    return resolved, passages


def discover_openalex(site: str, spec: dict, allowed: set[str], have_urls: set[str], budget: int, args):
    must = re.compile(spec["must_match"], re.I)
    seen, out = set(), []
    for q in spec["queries"]:
        if len(out) >= budget:
            break
        try:
            works = fetch.openalex_candidates(q, offline=args.offline)
        except fetch.FetchError as e:
            log(f"  [openalex] {q!r}: {e}")
            continue
        for w in works:
            if len(out) >= budget:
                break
            wid = w["id"].rsplit("/", 1)[-1]
            if wid in seen:
                continue
            seen.add(wid)
            lic = ((w.get("best_oa_location") or {}).get("license") or "").lower()
            title = w.get("title") or ""
            abstract = fetch._abstract(w.get("abstract_inverted_index"))
            doi = w.get("doi")
            if lic not in allowed or not must.search(title + " " + abstract) or (doi and doi in have_urls):
                continue
            src = {"id": f"oa_{wid}", "site": site, "type": OPENALEX_TYPE.get(w.get("type"), "journal_article"),
                   "title": f"{title} ({w.get('publication_year')})", "url": doi or w["id"],
                   "license": f"{lic.upper().replace('CC-', 'CC ').replace('-', ' ')} (OpenAlex: {lic})",
                   "doi": doi, "keep_title": True}
            try:
                res = fetch.fetch_openalex_work(w, offline=args.offline)
            except (fetch.FetchError, fetch.TooLarge) as e:
                log(f"  [skip] {src['id']}: {str(e)[:160]}")
                continue
            except Exception as e:
                log(f"  [skip] {src['id']}: {type(e).__name__}: {e}")
                continue
            if len(must.findall(res.text)) < 3:
                log(f"  [skip] {src['id']}: fetched text doesn't look like the paper (paywall/cookie page?)")
                continue
            res.extra["fulltext_url"] = res.url
            res.url = doi or res.url  # cite the DOI; where the text came from is kept as fulltext_url
            r = finish(src, res)
            if r:
                out.append(r)
                if doi:
                    have_urls.add(doi)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sites", help="comma-separated site slugs (default: all)")
    ap.add_argument("--offline", action="store_true", help="use data/raw cache only")
    ap.add_argument("--no-discovery", action="store_true", help="skip OpenAlex discovery")
    ap.add_argument("--allow-large", action="store_true", help="allow single downloads > 500 MB")
    args = ap.parse_args(argv)

    cfg = load_sources()
    sites = [config.resolve_site(s) for s in args.sites.split(",")] if args.sites else list(config.SITES)
    resolved, passages = [], []
    per_site_sources = Counter()

    listed_off = [s for s in cfg["sources"] if s.get("enabled") is False and s["site"] in sites]
    for s in cfg["sources"]:
        if s["site"] not in sites or s.get("enabled") is False or "fetch" not in s:
            continue
        if per_site_sources[s["site"]] >= MAX_SOURCES_PER_SITE:
            continue
        log(f"[{s['site']}] {s['id']} ({s['fetch']['kind']})")
        r = ingest_one(s, args)
        if r:
            resolved.append(r[0])
            passages.extend(r[1])
            per_site_sources[s["site"]] += 1

    if not args.no_discovery:
        oa = cfg.get("discovery", {}).get("openalex", {})
        allowed = set(oa.get("licenses_allowed", []))
        have = {r["url"] for r in resolved}
        for site in sites:
            spec = oa.get("queries", {}).get(site)
            if not spec:
                continue
            budget = min(spec.get("max_sources", 20), MAX_SOURCES_PER_SITE - per_site_sources[site])
            log(f"[{site}] OpenAlex discovery (up to {budget} works)")
            for r_src, r_pass in discover_openalex(site, spec, allowed, have, budget, args):
                resolved.append(r_src)
                passages.extend(r_pass)
                per_site_sources[site] += 1

    # Drop exact duplicate passages (e.g. the same paragraph in two Wikipedia articles).
    seen, unique = set(), []
    for p in passages:
        h = hashlib.sha1(re.sub(r"\W+", " ", p["text"].lower()).encode()).hexdigest()
        if h not in seen:
            seen.add(h)
            unique.append(p)
    passages = unique

    # Merge with passages for sites not rebuilt this run.
    if args.sites and config.PASSAGES_JSONL.exists():
        keep = [json.loads(l) for l in config.PASSAGES_JSONL.read_text(encoding="utf-8").splitlines() if l.strip()]
        passages = [p for p in keep if p["site"] not in sites] + passages
        if config.RESOLVED_YAML.exists():
            old = yaml.safe_load(config.RESOLVED_YAML.read_text(encoding="utf-8")).get("sources", [])
            resolved = [r for r in old if r["site"] not in sites] + resolved

    with config.PASSAGES_JSONL.open("w", encoding="utf-8") as f:
        for p in passages:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    skipped = [{k: s[k] for k in ("id", "site", "title", "url", "license", "note") if k in s} for s in listed_off]
    config.RESOLVED_YAML.write_text(
        "# Generated by `python -m data.ingest`: every source actually ingested, with the concrete url and license used.\n"
        + yaml.safe_dump({"generated": dt.datetime.now().isoformat(timespec="seconds"), "sources": resolved,
                          "listed_but_not_ingested": skipped}, sort_keys=False, allow_unicode=True, width=180),
        encoding="utf-8")
    report(passages, resolved)


def report(passages: list[dict], resolved: list[dict]):
    by_site = Counter(p["site"] for p in passages)
    srcs = Counter(r["site"] for r in resolved)
    tags = defaultdict(Counter)
    for p in passages:
        for t in p["system_tags"]:
            tags[p["site"]][t] += 1
    print("\nsite            sources  passages  untagged  top systems")
    for site in config.SITES:
        n = by_site[site]
        un = sum(1 for p in passages if p["site"] == site and not p["system_tags"])
        top = ", ".join(f"{t}:{c}" for t, c in tags[site].most_common(5))
        flag = "" if n >= config.MIN_PASSAGES_PER_SITE else f"   <-- below {config.MIN_PASSAGES_PER_SITE}"
        print(f"{site:15} {srcs[site]:7}  {n:8}  {un:8}  {top}{flag}")
    missing_lic = [p["id"] for p in passages if not p.get("license")]
    print(f"\n{len(passages)} passages from {len(resolved)} sources; passages without license: {len(missing_lic)}")


if __name__ == "__main__":
    main()
