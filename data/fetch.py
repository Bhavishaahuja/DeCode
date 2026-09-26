"""Download + text extraction for each `fetch.kind` in sources.yaml.

Each fetcher returns a FetchResult: the extracted text, page offsets if known, and the concrete
url/title/license actually used. Everything downloaded is cached under data/raw/ so rebuilds are offline.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import sys
import time
from dataclasses import dataclass, field
from urllib.parse import quote

import requests

from . import config

CONTACT = os.environ.get("STRATUM_CONTACT_EMAIL", "")
UA = f"StratumDataBot/0.1 (archaeology research index{'; mailto:' + CONTACT if CONTACT else ''})"
TIMEOUT = 60


class TooLarge(Exception):
    pass


class FetchError(Exception):
    pass


@dataclass
class FetchResult:
    text: str
    url: str
    title: str | None = None
    license: str | None = None          # overrides the sources.yaml license only when the upstream states one (OpenAlex)
    page_starts: list[int] = field(default_factory=list)  # char offset where each page starts (1-based page = index+1)
    extra: dict = field(default_factory=dict)


_session = None


def session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers["User-Agent"] = UA
    return _session


def _cache_path(url: str, ext: str) -> "os.PathLike":
    config.RAW_DIR.mkdir(parents=True, exist_ok=True)
    return config.RAW_DIR / (hashlib.sha1(url.encode()).hexdigest()[:16] + ext)


def get_bytes(url: str, ext: str = ".bin", allow_large: bool = False, offline: bool = False, params=None) -> bytes:
    """GET with an on-disk cache and a hard size limit (config.MAX_DOWNLOAD_BYTES)."""
    full = requests.Request("GET", url, params=params).prepare().url
    path = _cache_path(full, ext)
    if path.exists():
        return path.read_bytes()
    if offline:
        raise FetchError(f"not cached (offline): {full}")
    for attempt in range(3):
        try:
            with session().get(full, stream=True, timeout=TIMEOUT, allow_redirects=True) as r:
                if r.status_code == 429 or r.status_code >= 500:
                    time.sleep(2 ** attempt * 2)
                    continue
                if r.status_code != 200:
                    raise FetchError(f"HTTP {r.status_code} for {full}")
                size = int(r.headers.get("Content-Length") or 0)
                if size > config.MAX_DOWNLOAD_BYTES and not allow_large:
                    raise TooLarge(f"{full} is {size / 1e6:.0f} MB (> {config.MAX_DOWNLOAD_BYTES / 1e6:.0f} MB). "
                                   "Ask before downloading; rerun with --allow-large to proceed.")
                buf = io.BytesIO()
                for chunk in r.iter_content(1 << 16):
                    buf.write(chunk)
                    if buf.tell() > config.MAX_DOWNLOAD_BYTES and not allow_large:
                        raise TooLarge(f"{full} exceeded {config.MAX_DOWNLOAD_BYTES / 1e6:.0f} MB while streaming.")
                data = buf.getvalue()
                path.write_bytes(data)
                return data
        except (requests.ConnectionError, requests.Timeout) as e:
            if attempt == 2:
                raise FetchError(f"{type(e).__name__} for {full}") from e
            time.sleep(2 ** attempt * 2)
    raise FetchError(f"gave up on {full}")


def get_json(url: str, params=None, **kw):
    return json.loads(get_bytes(url, ".json", params=params, **kw))


# ---------------------------------------------------------------------------------------------
# Extractors

def pdf_to_pages(data: bytes) -> list[str]:
    try:
        from pypdf import PdfReader
    except ImportError as e:
        raise FetchError("pypdf is required for PDFs (pip install pypdf)") from e
    reader = PdfReader(io.BytesIO(data))
    pages = []
    for p in reader.pages:
        try:
            pages.append(p.extract_text() or "")
        except Exception:
            pages.append("")
    return pages


def join_pages(pages: list[str]) -> tuple[str, list[int]]:
    from .textproc import clean_text
    text, starts = "", []
    for p in pages:
        starts.append(len(text))
        text += clean_text(p) + "\n\n"
    return text, starts


def html_to_text(html: bytes | str) -> str:
    try:
        import trafilatura
        out = trafilatura.extract(html if isinstance(html, str) else html.decode("utf-8", "replace"),
                                  include_comments=False, include_tables=False, favor_recall=True)
        if out and len(out) > 500:
            return out
    except ImportError:
        pass
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, "lxml" if _has_lxml() else "html.parser")
    for t in soup(["script", "style", "nav", "header", "footer", "aside", "form", "noscript"]):
        t.decompose()
    main = soup.find("main") or soup.find("article") or soup.body or soup
    return "\n\n".join(el.get_text(" ", strip=True) for el in main.find_all(["h1", "h2", "h3", "h4", "p", "li", "td", "blockquote"])
                       if el.get_text(strip=True))


def _has_lxml() -> bool:
    try:
        import lxml  # noqa: F401
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------------------------
# Fetchers by kind

WIKI_API = "https://en.wikipedia.org/w/api.php"


def fetch_wikipedia(spec: dict, **kw) -> FetchResult:
    page = spec["page"]

    def query(title):
        return get_json(WIKI_API, params={"action": "query", "prop": "extracts|info|revisions", "explaintext": 1,
                                          "exsectionformat": "wiki", "redirects": 1, "titles": title, "inprop": "url",
                                          "rvprop": "ids", "format": "json", "formatversion": 2}, **kw)

    data = query(page)
    p = data["query"]["pages"][0]
    if p.get("missing") or not p.get("extract"):
        s = get_json(WIKI_API, params={"action": "query", "list": "search", "srsearch": page, "srlimit": 3,
                                       "format": "json", "formatversion": 2}, **kw)
        want = {w for w in re.findall(r"[a-z]{4,}", page.lower())}
        for hit in s["query"]["search"]:
            if want & set(re.findall(r"[a-z]{4,}", hit["title"].lower())):
                p = query(hit["title"])["query"]["pages"][0]
                break
        else:
            raise FetchError(f"no Wikipedia article for {page!r}")
        if p.get("missing") or not p.get("extract"):
            raise FetchError(f"no Wikipedia article for {page!r}")
    revid = (p.get("revisions") or [{}])[0].get("revid")
    url = f"https://en.wikipedia.org/w/index.php?title={quote(p['title'].replace(' ', '_'))}&oldid={revid}" if revid else p["fullurl"]
    return FetchResult(text=p["extract"], url=url, title=f"{p['title']} (Wikipedia)", extra={"revid": revid})


def fetch_archive_search(spec: dict, allow_large=False, **kw) -> FetchResult:
    q = f"({spec['query']}) AND mediatype:texts"
    res = get_json("https://archive.org/advancedsearch.php",
                   params={"q": q, "fl[]": ["identifier", "title", "year", "volume", "date"], "rows": 50, "output": "json",
                           "sort[]": "downloads desc"}, **kw)
    docs = res.get("response", {}).get("docs", [])
    title_rx = re.compile(spec["title_regex"], re.I) if spec.get("title_regex") else None
    cands = list(spec.get("prefer", []))
    for d in docs:
        label = " ".join(str(d.get(k, "")) for k in ("title", "volume", "year", "date"))
        if title_rx is None or title_rx.search(label) or title_rx.search(d["identifier"]):
            cands.append(d["identifier"])
    seen = set()
    for ident in cands:
        if ident in seen:
            continue
        seen.add(ident)
        try:
            meta = get_json(f"https://archive.org/metadata/{ident}", **kw)
        except FetchError:
            continue
        files = meta.get("files", [])
        txt = [f for f in files if f.get("name", "").endswith("_djvu.txt")]
        if not txt:
            continue
        f = max(txt, key=lambda f: int(f.get("size", 0) or 0))
        if int(f.get("size", 0) or 0) > config.MAX_DOWNLOAD_BYTES and not allow_large:
            raise TooLarge(f"archive.org/{ident}/{f['name']} is {int(f['size']) / 1e6:.0f} MB; ask first (--allow-large).")
        raw = get_bytes(f"https://archive.org/download/{ident}/{quote(f['name'])}", ".txt", allow_large=allow_large, **kw)
        text = raw.decode("utf-8", "replace")
        md = meta.get("metadata", {})
        title = md.get("title")
        if isinstance(title, list):
            title = title[0]
        pages = text.split("\f")
        if len(pages) > 1:
            text, starts = join_pages(pages)
        else:
            starts = []
        return FetchResult(text=text, url=f"https://archive.org/details/{ident}", title=title, page_starts=starts,
                           extra={"archive_id": ident, "archive_rights": md.get("possible-copyright-status") or md.get("rights"),
                                  "archive_year": md.get("year") or md.get("date")})
    raise FetchError(f"no archive.org text for query {spec['query']!r} (tried {len(seen)} items)")


def fetch_gutenberg_search(spec: dict, **kw) -> FetchResult:
    res = get_json("https://gutendex.com/books", params={"search": spec["query"]}, **kw)
    rx = re.compile(spec["title_regex"], re.I) if spec.get("title_regex") else None
    for book in res.get("results", []):
        if rx and not rx.search(book["title"]):
            continue
        fmts = book.get("formats", {})
        url = next((u for k, u in fmts.items() if k.startswith("text/plain") and not u.endswith(".zip")), None)
        if not url:
            continue
        text = get_bytes(url, ".txt", **kw).decode("utf-8", "replace")
        m1 = re.search(r"\*\*\* ?START OF (THE|THIS) PROJECT GUTENBERG.*?\*\*\*", text)
        m2 = re.search(r"\*\*\* ?END OF (THE|THIS) PROJECT GUTENBERG", text)
        text = text[m1.end() if m1 else 0: m2.start() if m2 else len(text)]
        return FetchResult(text=text, url=f"https://www.gutenberg.org/ebooks/{book['id']}", title=book["title"])
    raise FetchError(f"no Gutenberg book for {spec['query']!r}")


def fetch_url(spec: dict, **kw) -> FetchResult:
    url = spec["url"]
    fmt = spec.get("format") or ("pdf" if url.lower().endswith(".pdf") else "html")
    data = get_bytes(url, "." + fmt, **kw)
    if fmt == "pdf" or data[:5] == b"%PDF-":
        text, starts = join_pages(pdf_to_pages(data))
        return FetchResult(text=text, url=url, page_starts=starts)
    return FetchResult(text=html_to_text(data), url=url)


def fetch_wikidata_place(spec: dict, **kw) -> FetchResult:
    s = get_json("https://www.wikidata.org/w/api.php", params={"action": "wbsearchentities", "search": spec["label"],
                                                               "language": "en", "limit": 1, "format": "json"}, **kw)
    if not s.get("search"):
        raise FetchError(f"no Wikidata entity for {spec['label']!r}")
    qid = s["search"][0]["id"]
    ent = get_json(f"https://www.wikidata.org/wiki/Special:EntityData/{qid}.json", **kw)["entities"][qid]
    claims = ent.get("claims", {})

    def vals(prop):
        out = []
        for c in claims.get(prop, []):
            dv = c.get("mainsnak", {}).get("datavalue", {}).get("value")
            if dv is not None:
                out.append(dv)
        return out

    ref_ids = sorted({v["id"] for p in ("P17", "P31", "P1435", "P361", "P131", "P138") for v in vals(p) if isinstance(v, dict) and "id" in v})
    labels = {}
    if ref_ids:
        lab = get_json("https://www.wikidata.org/w/api.php", params={"action": "wbgetentities", "ids": "|".join(ref_ids[:50]),
                                                                    "props": "labels", "languages": "en", "format": "json"}, **kw)
        labels = {k: v.get("labels", {}).get("en", {}).get("value", k) for k, v in lab.get("entities", {}).items()}
    name = ent.get("labels", {}).get("en", {}).get("value", spec["label"])
    lines = [f"{name}: {ent.get('descriptions', {}).get('en', {}).get('value', '')}."]
    aliases = [a["value"] for a in ent.get("aliases", {}).get("en", [])]
    if aliases:
        lines.append("Also known as: " + ", ".join(aliases) + ".")
    for prop, label in (("P31", "Instance of"), ("P17", "Country"), ("P131", "Located in"), ("P361", "Part of"),
                        ("P1435", "Heritage designation"), ("P138", "Named after")):
        v = [labels.get(x["id"], x["id"]) for x in vals(prop) if isinstance(x, dict) and "id" in x]
        if v:
            lines.append(f"{label}: {', '.join(v)}.")
    for c in vals("P625"):
        lines.append(f"Coordinates: {c['latitude']:.5f} N, {c['longitude']:.5f} E.")
    for t in vals("P571"):
        lines.append(f"Inception (Wikidata): {t.get('time', '')}.")
    text = "\n".join(lines)
    url = f"https://www.wikidata.org/wiki/{qid}"
    pleiades = vals("P1584")
    if pleiades:
        try:
            pl = get_json(f"https://pleiades.stoa.org/places/{pleiades[0]}/json", **kw)
            details = html_to_text(pl.get("details") or "") if pl.get("details") else ""
            names = ", ".join(sorted({n.get("romanized") or n.get("title", "") for n in pl.get("names", []) if n}))
            text += (f"\n\nPleiades place {pleiades[0]} ({pl.get('title', '')}): {pl.get('description', '')}\n"
                     f"Ancient names: {names}.\n{details}")
            url += f" ; https://pleiades.stoa.org/places/{pleiades[0]}"
        except FetchError as e:
            print(f"  [warn] Pleiades {pleiades[0]}: {e}", file=sys.stderr)
    return FetchResult(text=text, url=url, title=f"{name}: Wikidata {qid}" + (f" + Pleiades {pleiades[0]}" if pleiades else ""))


FETCHERS = {
    "wikipedia": fetch_wikipedia,
    "archive_search": fetch_archive_search,
    "gutenberg_search": fetch_gutenberg_search,
    "url": fetch_url,
    "wikidata_place": fetch_wikidata_place,
}


# ---------------------------------------------------------------------------------------------
# OpenAlex discovery -> open-access full text

def _abstract(inv: dict | None) -> str:
    if not inv:
        return ""
    pos = sorted((i, w) for w, idxs in inv.items() for i in idxs)
    return " ".join(w for _, w in pos)


def openalex_candidates(query: str, per_page: int = 25, **kw) -> list[dict]:
    params = {"search": query, "filter": "is_oa:true", "per-page": per_page,
              "select": "id,doi,title,publication_year,best_oa_location,primary_location,ids,abstract_inverted_index,type,open_access"}
    if CONTACT:
        params["mailto"] = CONTACT
    return get_json("https://api.openalex.org/works", params=params, **kw).get("results", [])


def fetch_openalex_work(work: dict, **kw) -> FetchResult:
    """Full text via Europe PMC (if in PMC), else the OA PDF, else the OA landing page."""
    loc = work.get("best_oa_location") or {}
    pmcid = (work.get("ids") or {}).get("pmcid")
    errors = []
    if pmcid:
        pmc = pmcid.rstrip("/").split("/")[-1]
        pmc = pmc if pmc.upper().startswith("PMC") else "PMC" + pmc
        try:
            xml = get_bytes(f"https://www.ebi.ac.uk/europepmc/webservices/rest/{pmc}/fullTextXML", ".xml", **kw)
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(xml, "xml" if _has_lxml() else "html.parser")
            for t in soup.find_all(["ref-list", "table-wrap", "fig", "back", "supplementary-material"]):
                t.decompose()
            body = soup.find("body")
            if body:
                paras = [el.get_text(" ", strip=True) for el in body.find_all(["title", "p"])]
                text = "\n\n".join(p for p in paras if p)
                if len(text) > 3000:
                    return FetchResult(text=text, url=f"https://europepmc.org/article/PMC/{pmc}")
        except (FetchError, TooLarge) as e:
            errors.append(str(e))
    for url in filter(None, [loc.get("pdf_url"), (work.get("primary_location") or {}).get("pdf_url")]):
        try:
            data = get_bytes(url, ".pdf", **kw)
            if data[:5] == b"%PDF-":
                text, starts = join_pages(pdf_to_pages(data))
                if len(text) > 3000:
                    return FetchResult(text=text, url=url, page_starts=starts)
            else:
                text = html_to_text(data)
                if len(text) > 3000:
                    return FetchResult(text=text, url=url)
        except (FetchError, TooLarge) as e:
            errors.append(str(e))
    landing = loc.get("landing_page_url")
    if landing:
        try:
            text = html_to_text(get_bytes(landing, ".html", **kw))
            if len(text) > 5000:
                return FetchResult(text=text, url=landing)
        except FetchError as e:
            errors.append(str(e))
    raise FetchError("; ".join(errors) or "no usable open-access full text")
