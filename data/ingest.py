"""Download -> extract -> clean -> chunk -> tag -> data/passages.jsonl (+ data/sources.resolved.yaml).

    python -m data.ingest                      # everything (uses the cache in data/raw/ when present)
    python -m data.ingest --sites giza,uruk    # subset (contract ids: giza, uruk, mohenjo, qin)
    python -m data.ingest --offline            # cache only, no network
    python -m data.ingest --no-discovery       # curated sources only (skip OpenAlex)
    python -m data.ingest --allow-large        # permit single downloads > 500 MB (ask first!)

Every source goes through the stage 1 gate first (data/source_check.py on top of Chad's SourceRegistry):
known valid gets used, known invalid gets skipped, unknown gets checked (license, access, robots.txt).
The answer is saved in sources.resolved.yaml: used sources under `sources`, skipped ones under
`listed_but_not_ingested` with a `reason`.

Passages follow Contract 1 in CLAUDE.md. char_start / char_end (extras) are offsets into
data/text/<source_id>.txt (the cleaned text). Dev 2's hand-split passages in claims/handsplit/passages.jsonl
are merged in as-is so their passage_ids stay stable.
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
from .corpus_models import SourceStatus
from .source_check import decide, license_verdict
from .source_registry import SourceRegistry

MIN_CHUNK_TOKENS = 60
MIN_OCR_QUALITY = 0.6
MAX_SOURCES_PER_SITE = 60

TODAY_YEAR = dt.date.today().year


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


_WIKI_HEADING = re.compile(r"^\s*=+\s*(.*?)\s*=+\s*$", re.M)


def _section_starts(raw: str, clean: str) -> list[tuple[int, str]]:
    """Where each wiki-style section heading ended up in the cleaned text, as (offset, heading)."""
    out = []
    cursor = 0
    for heading in _WIKI_HEADING.findall(raw):
        heading = heading.strip()
        if not heading:
            continue
        pos = clean.find(heading, cursor)
        if pos < 0:
            continue
        out.append((pos, heading))
        cursor = pos + len(heading)
    return out


def _locator(page: int | None, char_start: int, sections: list[tuple[int, str]]) -> str | None:
    """Contract 1 locator: "p. 42" when we know the page, else the section heading, else None."""
    if page:
        return f"p. {page}"
    current = None
    for pos, heading in sections:
        if pos <= char_start:
            current = heading
        else:
            break
    return f"section: {current}" if current else None


def _year_for(src: dict) -> int | None:
    """Publication year if we have one. Living web pages (Wikipedia, Wikidata) get the retrieval year."""
    year = src.get("year")
    if year is not None:
        try:
            return int(str(year)[:4])
        except ValueError:
            return None
    kind = (src.get("fetch") or {}).get("kind")
    if kind in ("wikipedia", "wikidata_place"):
        return TODAY_YEAR
    return None


def process_source(src: dict, res: fetch.FetchResult) -> tuple[str, list[dict]]:
    """Clean + filter + chunk one fetched source. Returns (clean_text, passages)."""
    site = src["site"]
    if site not in config.SITES:
        raise ValueError(f"{src['id']}: site {site!r} is not a contract site id {list(config.SITES)}")
    source_type = config.contract_source_type(src["type"])
    raw = res.text
    text = raw if res.page_starts else textproc.clean_text(raw)
    text = textproc.cut_tail_sections(text)
    if src.get("keep_regex"):
        text = textproc.keep_matching(text, src["keep_regex"])
    sections = [] if res.page_starts else _section_starts(raw, text)
    year = _year_for(src)
    passages = []
    for i, ch in enumerate(textproc.chunk_text(text)):
        if textproc.count_tokens(ch.text) < MIN_CHUNK_TOKENS or textproc.ocr_quality(ch.text) < MIN_OCR_QUALITY:
            continue
        page = _page_for(ch.text, raw, res.page_starts)
        tags = tagging.keyword_tags(ch.text)
        passages.append({
            "passage_id": f"{site}-{src['id']}-{i:04d}",
            "source_id": src["id"],
            "site": site,
            "title": src["title"],
            "author": src.get("author"),
            "year": year,
            "url": src["url"],
            "license": src["license"],
            "source_type": source_type,
            "period": tagging.period_for(ch.text, site, src.get("period")),
            "locator": _locator(page, ch.char_start, sections),
            "text": ch.text,
            "system_tags": tags,
            "tagged_by": "rules" if tags else "none",
            # extras (allowed by the contract, never replace a required field)
            "page": page,
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
    is_wiki = (src.get("fetch") or {}).get("kind") == "wikipedia"
    if res.title and not is_wiki and not src.get("keep_title"):
        src.setdefault("upstream_title", res.title)
    if res.title and is_wiki:
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
    resolved["type"] = config.contract_source_type(resolved["type"])
    for k in ("author", "period", "year", "note", "upstream_title", "doi"):
        if src.get(k):
            resolved[k] = src[k]
    resolved.update({"retrieved": dt.date.today().isoformat(), "n_passages": len(passages)})
    for k, v in res.extra.items():
        if v:
            resolved[k] = v
    log(f"  [ok] {src['id']}: {len(passages)} passages")
    return resolved, passages


def _openalex_authors(work: dict) -> str | None:
    names = []
    for a in work.get("authorships") or []:
        name = (a.get("author") or {}).get("display_name")
        if name:
            names.append(name)
    if not names:
        return None
    if len(names) > 3:
        return ", ".join(names[:3]) + " et al."
    return ", ".join(names)


def discover_openalex(site: str, spec: dict, allowed: set[str], have_urls: set[str], budget: int, args, registry: SourceRegistry):
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
            wid = w["id"].rsplit("/", 1)[-1].lower()
            if wid in seen:
                continue
            seen.add(wid)
            lic = ((w.get("best_oa_location") or {}).get("license") or "").lower()
            title = w.get("title") or ""
            abstract = fetch._abstract(w.get("abstract_inverted_index"))
            doi = w.get("doi")
            if lic not in allowed or not must.search(title + " " + abstract) or (doi and doi in have_urls):
                continue
            if registry.status(f"oa_{wid}") == SourceStatus.INVALID:
                log(f"  [registry: invalid] oa_{wid}, skipped")
                continue
            src = {"id": f"oa_{wid}", "site": site, "type": "scholarship",
                   "title": f"{title} ({w.get('publication_year')})", "url": doi or w["id"],
                   "license": f"{lic.upper().replace('CC-', 'CC ').replace('-', ' ')} (OpenAlex: {lic})",
                   "author": _openalex_authors(w), "year": w.get("publication_year"),
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
    registry = SourceRegistry()

    bad_sites = sorted({s["site"] for s in cfg["sources"]} - set(config.SITES))
    if bad_sites:
        raise SystemExit(f"sources.yaml uses site ids that aren't in the contract: {bad_sites}")

    listed_off = []
    for s in cfg["sources"]:
        if s["site"] not in sites:
            continue
        # Stage 1 of the Decode flow: known valid -> use, known invalid -> skip, unknown -> check
        verdict = decide(s, registry, offline=args.offline)
        if not verdict.use:
            log(f"[{s['site']}] {s['id']}: skipped ({verdict.reason})")
            listed_off.append({**s, "reason": verdict.reason})
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
            for r_src, r_pass in discover_openalex(site, spec, allowed, have, budget, args, registry):
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

    # Dev 2's hand-split passages go in as-is (their passage_ids are already cited by claims).
    passages += load_handsplit(sites, {p["passage_id"] for p in passages}, resolved)

    # Merge with passages for sites not rebuilt this run (old-schema rows without passage_id are dropped).
    if args.sites and config.PASSAGES_JSONL.exists():
        keep = [json.loads(l) for l in config.PASSAGES_JSONL.read_text(encoding="utf-8").splitlines() if l.strip()]
        passages = [p for p in keep if "passage_id" in p and p["site"] not in sites] + passages
        if config.RESOLVED_YAML.exists():
            old_file = yaml.safe_load(config.RESOLVED_YAML.read_text(encoding="utf-8")) or {}
            resolved = [r for r in old_file.get("sources", []) if r["site"] not in sites] + resolved
            old_skipped = [r for r in old_file.get("listed_but_not_ingested", []) if r.get("site") not in sites]
        else:
            old_skipped = []
    else:
        old_skipped = []

    with config.PASSAGES_JSONL.open("w", encoding="utf-8") as f:
        for p in passages:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    skipped = old_skipped + [{k: s[k] for k in ("id", "site", "title", "url", "license", "note", "reason") if k in s}
                             for s in listed_off]
    config.RESOLVED_YAML.write_text(
        "# Generated by `python -m data.ingest`: every source actually ingested, with the concrete url and license used.\n"
        + yaml.safe_dump({"generated": dt.datetime.now().isoformat(timespec="seconds"), "sources": resolved,
                          "listed_but_not_ingested": skipped}, sort_keys=False, allow_unicode=True, width=180),
        encoding="utf-8")
    report(passages, resolved)


def load_handsplit(sites: list[str], taken: set[str], resolved: list[dict]) -> list[dict]:
    """Pull in claims/handsplit/passages.jsonl for the sites being built, if Dev 2 has any."""
    if not config.HANDSPLIT_PASSAGES.exists():
        return []
    hand_sources = {}
    if config.HANDSPLIT_SOURCES.exists():
        for src in (yaml.safe_load(config.HANDSPLIT_SOURCES.read_text(encoding="utf-8")) or {}).get("sources") or []:
            hand_sources[src["source_id"]] = src
    out = []
    counted = set()
    for line in config.HANDSPLIT_PASSAGES.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        p = json.loads(line)
        if p.get("site") not in sites or p.get("passage_id") in taken:
            continue
        src = hand_sources.get(p["source_id"])
        if src is None:
            log(f"  [handsplit] {p['passage_id']}: source {p['source_id']} not in claims/handsplit/sources.yaml, skipped")
            continue
        license_ok, _ = license_verdict(src.get("license"))
        if src.get("reuse_allowed") is not True or not license_ok:
            log(f"  [handsplit] {p['passage_id']}: source {p['source_id']} not cleared for reuse, skipped")
            continue
        p.pop("score", None)
        p.setdefault("tagged_by", "rules" if p.get("system_tags") else "none")
        out.append(p)
        if p["source_id"] not in counted:
            counted.add(p["source_id"])
            resolved.append({"id": p["source_id"], "site": p["site"], "type": p["source_type"], "title": p["title"],
                             "url": p["url"], "license": p["license"], "author": p.get("author"), "year": p.get("year"),
                             "note": "hand-split by Dev 2 (claims/handsplit)"})
    if out:
        log(f"[handsplit] merged {len(out)} passages from {len(counted)} Dev 2 sources")
    return out


def report(passages: list[dict], resolved: list[dict]):
    by_site = Counter(p["site"] for p in passages)
    srcs = Counter(r["site"] for r in resolved)
    tags = defaultdict(Counter)
    for p in passages:
        for t in p["system_tags"]:
            tags[p["site"]][t] += 1
    print("\nsite       sources  passages  untagged  top systems")
    for site in config.SITES:
        n = by_site[site]
        un = sum(1 for p in passages if p["site"] == site and not p["system_tags"])
        top = ", ".join(f"{t}:{c}" for t, c in tags[site].most_common(5))
        flag = "" if n >= config.MIN_PASSAGES_PER_SITE else f"   <-- below {config.MIN_PASSAGES_PER_SITE}"
        print(f"{site:10} {srcs[site]:7}  {n:8}  {un:8}  {top}{flag}")
    missing_lic = [p["passage_id"] for p in passages if not p.get("license")]
    print(f"\n{len(passages)} passages from {len(resolved)} sources; passages without license: {len(missing_lic)}")


if __name__ == "__main__":
    main()
