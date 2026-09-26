"""Hybrid evidence search for Stratum.

    from data.search import search_evidence
    hits = search_evidence("Giza ramp sledge wet sand", site="giza", system="transport_lifting", k=8)
    # -> list of PASSAGE dicts (see data/config.py::Passage) + "score" (0..1, higher is better), best first.

site   accepts contract ids or aliases: "giza", "uruk", "Warka", "Mohenjo-daro", "qin", "Great Wall", ...
system accepts ids or aliases:  "transport_lifting", "water", "QA", "workforce", "materials", "finishes", ...

Results always carry the contract ids (giza, uruk, mohenjo, qin and the 9 systems).

Scoring = 0.65 * cosine similarity (bge-small-en-v1.5, Chroma) + 0.35 * BM25 (normalised to the best hit),
computed over the union of the top vector and BM25 candidates after filtering. If chromadb /
sentence-transformers / the index are missing, it falls back to BM25-only and warns once.
"""
from __future__ import annotations

import json
import math
import re
import sys
import threading
from collections import Counter, defaultdict

from . import config

VEC_WEIGHT = 0.65
BM25_WEIGHT = 0.35
CANDIDATES = 50

__all__ = ["search_evidence", "get_passage", "list_sites", "list_systems"]

# ---------------------------------------------------------------------------------------------
# BM25 (no external dependency)

_STOP = set("""a an and are as at be been but by for from had has have he her his i in into is it its of on or our
she that the their them there these they this those to was were which who will with within without you your
not no than then so such can could would should may might also very over under about after before between""".split())


def _stem(w: str) -> str:
    for suf in ("ations", "ation", "ings", "ing", "ies", "ied", "ed", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[: -len(suf)] + ("y" if suf in ("ies", "ied") else "")
    return w


def tokenize(text: str) -> list[str]:
    return [_stem(w) for w in re.findall(r"[a-z0-9]+", text.lower().replace("-", " ")) if w not in _STOP and len(w) > 1]


class BM25:
    def __init__(self, docs: list[list[str]], k1: float = 1.4, b: float = 0.75):
        self.k1, self.b = k1, b
        self.n = len(docs)
        self.len = [len(d) for d in docs]
        self.avg = sum(self.len) / max(1, self.n)
        self.post: dict[str, list[tuple[int, int]]] = defaultdict(list)
        for i, d in enumerate(docs):
            for t, c in Counter(d).items():
                self.post[t].append((i, c))
        self.idf = {t: math.log(1 + (self.n - len(p) + 0.5) / (len(p) + 0.5)) for t, p in self.post.items()}

    def scores(self, query: str, allowed: set[int] | None = None) -> dict[int, float]:
        out: dict[int, float] = defaultdict(float)
        for t in set(tokenize(query)):
            idf = self.idf.get(t)
            if idf is None:
                continue
            for i, tf in self.post[t]:
                if allowed is not None and i not in allowed:
                    continue
                out[i] += idf * tf * (self.k1 + 1) / (tf + self.k1 * (1 - self.b + self.b * self.len[i] / self.avg))
        return out


# ---------------------------------------------------------------------------------------------
# Store (lazy, process-wide)

class _Store:
    def __init__(self):
        if not config.PASSAGES_JSONL.exists():
            raise FileNotFoundError(f"{config.PASSAGES_JSONL} not found. Run `python -m data.build` first.")
        self.passages = [json.loads(l) for l in config.PASSAGES_JSONL.read_text(encoding="utf-8").splitlines() if l.strip()]
        self.by_id = {p["passage_id"]: i for i, p in enumerate(self.passages)}
        self.by_site = defaultdict(set)
        self.by_system = defaultdict(set)
        for i, p in enumerate(self.passages):
            self.by_site[p["site"]].add(i)
            for t in p["system_tags"]:
                self.by_system[t].add(i)
        self.bm25 = BM25([tokenize(p["title"] + " " + p["text"]) for p in self.passages])
        self.col = None
        self.model = None
        self.mode = "bm25"
        try:
            import chromadb
            from sentence_transformers import SentenceTransformer

            if not (config.INDEX_DIR / "manifest.json").exists():
                raise FileNotFoundError("no index; run `python -m data.index`")
            manifest = json.loads((config.INDEX_DIR / "manifest.json").read_text())
            self.col = chromadb.PersistentClient(path=str(config.INDEX_DIR)).get_collection(config.COLLECTION)
            if manifest.get("n_passages") != len(self.passages):
                print(f"[search] warning: index has {manifest.get('n_passages')} passages but passages.jsonl has "
                      f"{len(self.passages)}; rebuild with `python -m data.index`", file=sys.stderr)
            self.model = SentenceTransformer(manifest.get("model", config.EMBED_MODEL))
            self.mode = "hybrid"
        except Exception as e:  # ImportError, missing index, ...
            print(f"[search] vector search unavailable ({type(e).__name__}: {e}); using BM25 only", file=sys.stderr)

    def embed_query(self, q: str) -> list[float]:
        return self.model.encode([config.QUERY_INSTRUCTION + q], normalize_embeddings=True)[0].tolist()


_store: _Store | None = None
_lock = threading.Lock()


def _get_store() -> _Store:
    global _store
    if _store is None:
        with _lock:
            if _store is None:
                _store = _Store()
    return _store


def reload() -> None:
    """Drop the cached store (after a rebuild in the same process)."""
    global _store
    _store = None


# ---------------------------------------------------------------------------------------------

def search_evidence(query: str, site: str | None = None, system: str | None = None, k: int = 8) -> list[dict]:
    """Return up to k PASSAGE dicts (plus "score") most relevant to `query`, optionally filtered by site and system."""
    if not query or not query.strip() or k <= 0:
        return []
    st = _get_store()
    site_id = config.resolve_site(site)
    sys_id = config.resolve_system(system)

    allowed: set[int] | None = None
    if site_id:
        allowed = set(st.by_site.get(site_id, ()))
    if sys_id:
        s = st.by_system.get(sys_id, set())
        allowed = set(s) if allowed is None else allowed & s
    if allowed is not None and not allowed:
        return []

    bm = st.bm25.scores(query, allowed)
    bm_top = sorted(bm, key=bm.get, reverse=True)[:CANDIDATES]
    bm_max = max(bm.values(), default=0.0) or 1.0

    vec: dict[int, float] = {}
    if st.mode == "hybrid":
        where = {}
        conds = []
        if site_id:
            conds.append({"site": site_id})
        if sys_id:
            conds.append({f"sys_{sys_id}": True})
        if len(conds) == 1:
            where = conds[0]
        elif conds:
            where = {"$and": conds}
        qv = st.embed_query(query)
        n = min(CANDIDATES, len(allowed) if allowed is not None else len(st.passages))
        res = st.col.query(query_embeddings=[qv], n_results=n, where=where or None, include=["distances"])
        for pid, dist in zip(res["ids"][0], res["distances"][0]):
            if pid in st.by_id:
                vec[st.by_id[pid]] = 1.0 - dist
        # Exact cosine for BM25-only candidates so every candidate gets both signals.
        missing = [i for i in bm_top if i not in vec]
        if missing:
            got = st.col.get(ids=[st.passages[i]["passage_id"] for i in missing], include=["embeddings"])
            for pid, emb in zip(got["ids"], got["embeddings"]):
                vec[st.by_id[pid]] = float(sum(a * b for a, b in zip(qv, emb)))

    cands = set(bm_top) | set(vec)
    scored = []
    for i in cands:
        b = bm.get(i, 0.0) / bm_max
        s = VEC_WEIGHT * max(0.0, vec.get(i, 0.0)) + BM25_WEIGHT * b if st.mode == "hybrid" else b
        scored.append((s, i))
    scored.sort(reverse=True)
    out = []
    for s, i in scored[:k]:
        p = dict(st.passages[i])
        p["system_tags"] = list(p["system_tags"])
        p["score"] = round(float(s), 4)
        out.append(p)
    return out


def get_passage(passage_id: str) -> dict | None:
    st = _get_store()
    i = st.by_id.get(passage_id)
    return dict(st.passages[i]) if i is not None else None


def list_sites() -> list[str]:
    return list(config.SITES)


def list_systems() -> list[str]:
    return config.system_ids()


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="search the Stratum evidence index")
    ap.add_argument("query")
    ap.add_argument("--site")
    ap.add_argument("--system")
    ap.add_argument("-k", type=int, default=5)
    a = ap.parse_args()
    for h in search_evidence(a.query, a.site, a.system, a.k):
        print(f"{h['score']:.3f}  {h['passage_id']}  [{', '.join(h['system_tags'])}]  {h['title']}\n       {h['text'][:220]}...\n")
