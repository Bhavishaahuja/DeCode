"""Decode map: a tree of transforms per site that points claim extraction at the right passages.

    python -m claims.decode_map --site mohenjo --system finishes      build the map (a few API calls)
    python -m claims.decode_map --site mohenjo --show                 print a saved map, no API calls
    python -m claims.extract --from-map claims/decode/mohenjo.json --limit 10
                                                                      extract drafts from the mapped passages

How it works. This runs Chad's decode code (data/decode.py, tools/decode_ai.py) with a few guard rails:
  1. Core pass: Claude reads a spread of the site's passages and names the root transforms (big themes),
     each tied to the passage ids that support it.
  2. Child pass: for each root, Claude re-reads only that root's passages and names more specific
     transforms under it. Children of one level run in parallel, and depth and counts are capped.
  3. The tree is saved to claims/decode/<site>.json (plus a readable .md). Its passage ids are what
     extract.py --from-map uses, instead of taking passages in file order.

Nothing here is a claim. Every node is an unreviewed reading. Claims still come out of extract.py
and only become verified through review.py, same as before.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from claims.common import load_passages
from data.decode import TransformExtract, TransformGraph, TransformLink, TransformRecord

CLAIMS_DIR = Path(__file__).resolve().parent
MAP_DIR = CLAIMS_DIR / "decode"
SITES = ["giza", "uruk", "mohenjo", "qin"]
SITE_NAMES = {"giza": "Giza", "uruk": "Uruk", "mohenjo": "Mohenjo-daro", "qin": "the Qin walls and roads"}

# Added after Chad's system prompt so the decode stays inside Stratum's rules.
STRATUM_RULES = """

STRATUM RULES (these apply to everything above)

You are decoding the evidence for {site_name}, an ancient megaproject, the way a building contractor would read it.
A transform is an ancient building practice that a modern builder could learn from: how they set out, sourced,
moved, built, finished, organised, checked or managed the work.

1. Only use the passages supplied. Every transform must cite the passage ids that directly support it. Never cite
   a passage id that wasn't supplied.
2. Stay on the site. Skip passages about other sites, and skip jewellery, seals, pottery or art unless they show
   how the build was organised or checked.
3. Fringe ideas (aliens, lost civilizations, ancient power plants and similar) are never transforms.
4. One plain sentence per transform, 25 words or fewer. No numbers unless the cited passage states them.
5. Core mode: at most {max_roots} root transforms, the broadest useful themes. Child mode: at most
   {max_children} children, each narrower than its parent, or none if the evidence doesn't go deeper.
6. Never use em dashes or en dashes. Use commas, periods or parentheses.
"""


# ---------------------------------------------------------------------------------------------
# Picking the corpus

def pick_passages(passages: dict, site: str, system: str | None, max_passages: int) -> list[dict]:
    """Round-robin across sources, so one long book can't crowd out the rest (the round 3 problem)."""
    by_source: dict[str, list[dict]] = {}
    for p in passages.values():
        if p.get("site") != site:
            continue
        if system and system not in (p.get("system_tags") or []):
            continue
        if not system and not p.get("system_tags"):
            continue  # untagged passages are usually off topic
        by_source.setdefault(p["source_id"], []).append(p)

    picked = []
    round_number = 0
    while len(picked) < max_passages:
        added = False
        for source_id in sorted(by_source):
            rows = by_source[source_id]
            if round_number < len(rows):
                picked.append(rows[round_number])
                added = True
                if len(picked) >= max_passages:
                    break
        if not added:
            break
        round_number += 1
    return picked


# ---------------------------------------------------------------------------------------------
# A forgiving wrapper around Chad's evaluator
#
# tools/decode_ai.py raises (and loses the whole pass) if the model cites one passage id that wasn't
# supplied. This wrapper makes the same call with Chad's prompt, tool and message builder, but just
# drops the bad ids, and drops a transform only if none of its ids are real. Retries once on a failure.

class SafeEvaluator:
    def __init__(self, evaluator):
        self.inner = evaluator

    def core(self, passages):
        return self._evaluate("core", passages, None)

    def child(self, parent, passages):
        return self._evaluate("child", passages, parent)

    def _evaluate(self, mode, passages, parent):
        from tools import decode_ai
        passage_map = {p["passage_id"]: p for p in passages}
        last_error = None
        for _ in range(2):
            try:
                response = self.inner.client.messages.create(
                    model=self.inner.model, max_tokens=4000, system=self.inner.system_prompt,
                    tools=[decode_ai._transform_tool()], tool_choice={"type": "tool", "name": "record_transforms"},
                    messages=[{"role": "user", "content": decode_ai._build_user_message(mode, passages, parent)}])
                raw_rows = decode_ai._tool_output(response)
                break
            except Exception as err:
                last_error = err
        else:
            raise last_error

        out = []
        for raw in raw_rows:
            if not isinstance(raw, dict):
                continue
            text = str(raw.get("text") or "").strip()
            ids = [pid for pid in (raw.get("evidence_passage_ids") or []) if pid in passage_map]
            if not text or not ids:
                continue
            temp_id = str(raw.get("transform_id") or "x")
            links = tuple(TransformLink(transform_id=temp_id, source_id=passage_map[pid]["source_id"],
                                        site_id=passage_map[pid]["site"], passage_id=pid,
                                        locator=passage_map[pid].get("locator")) for pid in ids)
            out.append(TransformExtract(transform_id=temp_id, text=text, evidence=links))
        return out


# ---------------------------------------------------------------------------------------------
# Running the decode with stable ids and caps

def renumber(extracts, prefix: str, limit: int) -> list[TransformExtract]:
    """The model's own ids can collide and crash the graph, so we assign ours: giza-t01, giza-t01-02 ..."""
    out = []
    for i, extract in enumerate(list(extracts)[:limit], start=1):
        new_id = f"{prefix}{i:02d}"
        links = tuple(TransformLink(transform_id=new_id, source_id=link.source_id, site_id=link.site_id,
                                    passage_id=link.passage_id, locator=link.locator) for link in extract.evidence)
        out.append(TransformExtract(transform_id=new_id, text=extract.text, evidence=links))
    return out


def linked_passages(graph: TransformGraph, node: TransformRecord, corpus: list[dict]) -> list[dict]:
    ids = {link.passage_id for link in graph.links_for(node.transform_id) if link.passage_id}
    return [p for p in corpus if p["passage_id"] in ids]


def build_map(evaluator, site: str, corpus: list[dict], depth: int, max_roots: int, max_children: int,
              workers: int = 4, log=print) -> TransformGraph:
    graph = TransformGraph()

    log(f"core pass over {len(corpus)} passages ...")
    for extract in renumber(evaluator.core(corpus), f"{site}-t", max_roots):
        graph.add_core_transform(extract.transform_id, extract.text)
        for link in extract.evidence:
            graph.add_link(link)
    level = [t for t in graph.transforms.values() if t.depth == 0]
    log(f"  {len(level)} root transforms")

    for current_depth in range(1, depth + 1):
        jobs = []
        for node in level:
            evidence = linked_passages(graph, node, corpus)
            if evidence:
                jobs.append((node, evidence))
        if not jobs:
            break
        log(f"child pass, depth {current_depth}: {len(jobs)} nodes in parallel ...")

        def run(job):
            node, evidence = job
            try:
                return node, evaluator.child(node, evidence), None
            except Exception as err:  # one bad branch shouldn't sink the whole map
                return node, [], err

        next_level = []
        with ThreadPoolExecutor(max_workers=workers) as pool:
            results = list(pool.map(run, jobs))
        for node, extracts, err in results:  # graph writes stay on this thread
            if err:
                log(f"  {node.transform_id}: skipped ({type(err).__name__}: {str(err)[:100]})")
                continue
            for extract in renumber(extracts, f"{node.transform_id}-", max_children):
                child = graph.add_derived_transform(extract.transform_id, extract.text, node.transform_id)
                for link in extract.evidence:
                    graph.add_link(link)
                next_level.append(child)
        log(f"  {len(next_level)} transforms at depth {current_depth}")
        level = next_level
    return graph


# ---------------------------------------------------------------------------------------------
# Saving and showing

def graph_to_json(graph: TransformGraph, site: str, system: str | None, corpus: list[dict], params: dict,
                  model: str) -> dict:
    passages_by_id = {p["passage_id"]: p for p in corpus}
    nodes = []
    for t in sorted(graph.transforms.values(), key=lambda t: t.transform_id):
        ids = []
        for link in graph.links_for(t.transform_id):
            if link.passage_id and link.passage_id not in ids:
                ids.append(link.passage_id)
        sources = []
        for pid in ids:
            p = passages_by_id.get(pid, {})
            where = p.get("title", "")
            if p.get("locator"):
                where += f", {p['locator']}"
            if where not in sources:
                sources.append(where)
        children = [c.transform_id for c in graph.transforms.values() if c.parent_transform_id == t.transform_id]
        nodes.append({"id": t.transform_id, "text": t.text, "parent": t.parent_transform_id, "root": t.root_transform_id,
                      "depth": t.depth, "is_leaf": not children, "passage_ids": ids, "sources": sources,
                      "status": "unreviewed"})
    return {"site": site, "system": system, "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "model": model, "params": params, "corpus_passage_ids": [p["passage_id"] for p in corpus],
            "transforms": nodes}


def map_to_markdown(doc: dict) -> str:
    title = SITE_NAMES[doc["site"]] + (f", {doc['system']}" if doc.get("system") else "")
    lines = [f"# Decode map: {title}", "",
             f"Built {doc['built_at']} with {doc['model']} from {len(doc['corpus_passage_ids'])} passages. "
             "Every node is an unreviewed reading, not a claim.", ""]
    for node in doc["transforms"]:
        indent = "  " * node["depth"]
        lines.append(f"{indent}- **{node['id']}** {node['text']}")
        if node["sources"]:
            lines.append(f"{indent}  ({'; '.join(node['sources'][:3])})")
    return "\n".join(lines) + "\n"


def mapped_passage_ids(doc: dict, node_id: str | None = None, leaves_only: bool = False) -> list[str]:
    """Passage ids in tree order, optionally under one node. extract.py --from-map uses this."""
    ids = []
    for node in doc["transforms"]:
        if node_id and not (node["id"] == node_id or node["id"].startswith(node_id + "-")):
            continue
        if leaves_only and not node["is_leaf"]:
            continue
        for pid in node["passage_ids"]:
            if pid not in ids:
                ids.append(pid)
    return ids


def map_path(site: str, system: str | None) -> Path:
    return MAP_DIR / (f"{site}-{system}.json" if system else f"{site}.json")


def show(doc: dict) -> None:
    print(map_to_markdown(doc))
    print(f"{len(doc['transforms'])} transforms, {len(mapped_passage_ids(doc))} mapped passages")


# ---------------------------------------------------------------------------------------------

def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--site", required=True, choices=SITES)
    parser.add_argument("--system", help="only passages tagged with this system, e.g. finishes")
    parser.add_argument("--max-passages", type=int, default=60, help="passages in the core pass (default 60)")
    parser.add_argument("--depth", type=int, default=1, help="child levels under the roots (default 1)")
    parser.add_argument("--max-roots", type=int, default=5)
    parser.add_argument("--max-children", type=int, default=3)
    parser.add_argument("--show", action="store_true", help="print the saved map and exit, no API calls")
    args = parser.parse_args(argv)

    path = map_path(args.site, args.system)
    if args.show:
        if not path.exists():
            print(f"no map yet at {path}")
            return 1
        show(json.loads(path.read_text(encoding="utf-8")))
        return 0

    load_dotenv()
    if not os.getenv("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set (put it in .env)")

    corpus = pick_passages(load_passages(), args.site, args.system, args.max_passages)
    if not corpus:
        sys.exit(f"no tagged passages for site={args.site} system={args.system}")
    sources = len({p["source_id"] for p in corpus})
    print(f"{len(corpus)} passages from {sources} sources")

    from tools.decode_ai import MODEL, create_anthropic_decode_evaluator
    evaluator = create_anthropic_decode_evaluator()
    evaluator.system_prompt += STRATUM_RULES.format(site_name=SITE_NAMES[args.site], max_roots=args.max_roots,
                                                    max_children=args.max_children)

    graph = build_map(SafeEvaluator(evaluator), args.site, corpus, depth=args.depth, max_roots=args.max_roots,
                      max_children=args.max_children)
    params = {"max_passages": args.max_passages, "depth": args.depth, "max_roots": args.max_roots,
              "max_children": args.max_children}
    doc = graph_to_json(graph, args.site, args.system, corpus, params, MODEL)

    MAP_DIR.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    path.with_suffix(".md").write_text(map_to_markdown(doc), encoding="utf-8")
    print()
    show(doc)
    print(f"\nsaved {path} and {path.with_suffix('.md').name}")
    print(f"next: python -m claims.extract --from-map {path.relative_to(CLAIMS_DIR.parent).as_posix()} --limit 10")
    return 0


if __name__ == "__main__":
    sys.exit(main())
