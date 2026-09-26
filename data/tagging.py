"""Tag passages with period and system_tags.

1. Keyword rules (systems.yaml): >=1 strong pattern or >=2 distinct weak patterns -> tag.
2. Optional LLM pass (claude-sonnet-5) only for passages the rules left untagged. Batched, truncated and
   cached in data/llm_tags.json so a rerun never pays twice.

CLI:  python -m data.tagging --llm [--max 400]      (re-tags data/passages.jsonl in place)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from functools import lru_cache

from . import config

LLM_CACHE = config.DATA_DIR / "llm_tags.json"


@lru_cache(maxsize=1)
def _compiled():
    out = {}
    for sid, spec in config.load_systems().items():
        wrap = lambda p: re.compile(rf"(?<![\w-])(?:{p})(?![\w-])", re.I)
        out[sid] = ([wrap(p) for p in spec.get("strong", [])], [wrap(p) for p in spec.get("weak", [])])
    return out


def keyword_tags(text: str) -> list[str]:
    tags = []
    for sid, (strong, weak) in _compiled().items():
        if any(r.search(text) for r in strong) or sum(1 for r in weak if r.search(text)) >= 2:
            tags.append(sid)
    return tags


def system_scores(text: str) -> dict[str, int]:
    """Number of distinct matching patterns per system (strong count double). Handy for debugging rules."""
    return {sid: 2 * sum(1 for r in s if r.search(text)) + sum(1 for r in w if r.search(text))
            for sid, (s, w) in _compiled().items()}


def period_for(text: str, site: str, source_period: str | None = None) -> str:
    for pattern, label in config.PERIOD_RULES.get(site, []):
        if re.search(pattern, text, re.I):
            return label
    return source_period or config.SITES[site]["default_period"]


# ---------------------------------------------------------------------------------------------
# LLM pass

_PROMPT = """You label archaeology passages with engineering systems for a retrieval index.

Allowed system ids (use only these):
{systems}

For each passage, return the ids that the passage gives real evidence about (0-3 ids). If it gives evidence
about none of them (e.g. a biography, a museum history, or a list of references), return [].

Reply with a single JSON object only, mapping passage id -> list of ids. No prose.

Passages:
{passages}"""


def _load_cache() -> dict[str, list[str]]:
    if LLM_CACHE.exists():
        return json.loads(LLM_CACHE.read_text())
    return {}


def llm_tag(passages: list[dict], max_passages: int = 400, batch_size: int = 20, chars: int = 1200,
            model: str = config.LLM_TAG_MODEL) -> int:
    """Fill system_tags for untagged passages in place. Returns how many passages got >=1 tag."""
    cache = _load_cache()
    todo = [p for p in passages if not p["system_tags"]]
    for p in todo:
        if p["id"] in cache:
            p["system_tags"] = cache[p["id"]]
    todo = [p for p in todo if p["id"] not in cache][:max_passages]
    if not todo:
        return 0
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("[tagging] ANTHROPIC_API_KEY not set; skipping LLM pass", file=sys.stderr)
        return 0
    try:
        import anthropic
    except ImportError:
        print("[tagging] `anthropic` not installed; skipping LLM pass", file=sys.stderr)
        return 0

    client = anthropic.Anthropic()
    systems = config.load_systems()
    sys_desc = "\n".join(f"- {sid}: {spec['description']}" for sid, spec in systems.items())
    valid = set(systems)
    n_tagged, in_tok, out_tok = 0, 0, 0
    for b in range(0, len(todo), batch_size):
        batch = todo[b:b + batch_size]
        body = "\n\n".join(f"[{p['id']}] (site: {p['site']})\n{p['text'][:chars]}" for p in batch)
        try:
            msg = client.messages.create(model=model, max_tokens=1500,
                                         messages=[{"role": "user", "content": _PROMPT.format(systems=sys_desc, passages=body)}])
        except Exception as e:  # keep going; the rules already ran
            print(f"[tagging] LLM batch failed: {e}", file=sys.stderr)
            continue
        in_tok += msg.usage.input_tokens
        out_tok += msg.usage.output_tokens
        raw = "".join(getattr(c, "text", "") for c in msg.content)
        m = re.search(r"\{.*\}", raw, re.S)
        try:
            result = json.loads(m.group(0)) if m else {}
        except json.JSONDecodeError:
            result = {}
        for p in batch:
            tags = [t for t in result.get(p["id"], []) if t in valid][:3]
            cache[p["id"]] = tags
            p["system_tags"] = tags
            n_tagged += bool(tags)
        LLM_CACHE.write_text(json.dumps(cache, indent=0))
    print(f"[tagging] LLM pass: {len(todo)} passages, {n_tagged} tagged, {in_tok} in / {out_tok} out tokens", file=sys.stderr)
    return n_tagged


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--llm", action="store_true", help="run the LLM pass on untagged passages")
    ap.add_argument("--max", type=int, default=400, help="max passages sent to the LLM (cost cap)")
    args = ap.parse_args(argv)
    passages = [json.loads(l) for l in config.PASSAGES_JSONL.read_text(encoding="utf-8").splitlines() if l.strip()]
    for p in passages:  # re-run the rules so edits to systems.yaml take effect
        p["system_tags"] = keyword_tags(p["text"])
    if args.llm:
        llm_tag(passages, max_passages=args.max)
    with config.PASSAGES_JSONL.open("w", encoding="utf-8") as f:
        for p in passages:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    untagged = sum(1 for p in passages if not p["system_tags"])
    print(f"[tagging] {len(passages)} passages, {untagged} without system tags")


if __name__ == "__main__":
    main()
