"""Extract 0 to 3 draft claims per passage with claude-sonnet-5.

The model only writes statement, quote, grade, system, modern_equivalent,
lesson and grade_reason. Sources are always copied from the passage by this
script, so the model can't invent one. Every claim is validated before it
lands in claims/draft/claims.jsonl.

Usage:
    python -m claims.extract --site giza --limit 20     # quick test run
    python -m claims.extract                             # everything not done yet
    python -m claims.extract --redo                      # ignore the done list
    python -m claims.extract --site qin --system workforce --per-source 2 --limit 10
"""

import argparse
import json
import hashlib
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv

from claims.common import (
    CLAIMS_DIR, DRAFT_PATH, SITES,
    append_jsonl, load_passages, load_taxonomy, read_jsonl,
    source_from_passage, validate_claim,
)

MODEL = "claude-sonnet-5"
PROMPT_PATH = CLAIMS_DIR / "prompts" / "extract.md"
DONE_PATH = CLAIMS_DIR / "draft" / "extracted_passages.txt"
REJECTS_PATH = CLAIMS_DIR / "draft" / "rejected_by_validator.jsonl"

SITE_NAMES = {
    "giza": "Giza (the pyramids and related works at Giza, Egypt)",
    "uruk": "Uruk (Warka, southern Iraq)",
    "mohenjo": "Mohenjo-daro (Indus Valley, Sindh, Pakistan)",
    "qin": "the Qin walls and roads (Qin state and dynasty, China, including the Straight Road)",
}

write_lock = threading.Lock()


def build_tool(systems):
    return {
        "name": "record_claims",
        "description": "Record 0 to 3 claims extracted from the passage.",
        "input_schema": {
            "type": "object",
            "properties": {
                "claims": {
                    "type": "array",
                    "maxItems": 3,
                    "items": {
                        "type": "object",
                        "properties": {
                            "system": {"type": "string", "enum": systems},
                            "statement": {"type": "string"},
                            "quote": {"type": "string"},
                            "grade": {"type": "string", "enum": ["attested", "debated", "inferred"]},
                            "grade_reason": {"type": "string"},
                            "modern_equivalent": {"type": "string"},
                            "lesson": {"type": "string"},
                        },
                        "required": ["system", "statement", "quote", "grade", "grade_reason",
                                     "modern_equivalent", "lesson"],
                    },
                }
            },
            "required": ["claims"],
        },
    }


def systems_block(taxonomy):
    lines = []
    for system_id, info in taxonomy["systems"].items():
        definition = " ".join(info["definition"].split())
        lines.append(f"- {system_id} ({info['name']}): {definition}")
    return "\n".join(lines)


def build_user_message(passage):
    # give the model the metadata it needs to grade, then the text
    return (
        f"Site: {passage['site']}\n"
        f"Source: {passage['title']} by {passage['author']} ({passage['year']})\n"
        f"Source type: {passage['source_type']}\n"
        f"Period covered: {passage.get('period') or 'unknown'}\n"
        f"Locator: {passage.get('locator') or 'none'}\n"
        f"Rule-based system tags (hints only, may be wrong): {', '.join(passage.get('system_tags') or []) or 'none'}\n"
        f"\n<passage>\n{passage['text']}\n</passage>"
    )


def draft_id(site, system, passage_id, statement):
    digest = hashlib.sha1(f"{passage_id}|{statement}".encode("utf-8")).hexdigest()[:8]
    return f"{site}-{system}-d{digest}"


def call_model(client, system_prompt, tool, passage):
    response = client.messages.create(
        model=MODEL,
        max_tokens=1500,
        system=system_prompt,
        tools=[tool],
        tool_choice={"type": "tool", "name": "record_claims"},
        messages=[{"role": "user", "content": build_user_message(passage)}],
    )
    for block in response.content:
        if block.type == "tool_use" and block.name == "record_claims":
            claims = block.input.get("claims") or []
            # every so often the model sends the list as a JSON string instead of a real list
            if isinstance(claims, str):
                try:
                    claims = json.loads(claims)
                except json.JSONDecodeError:
                    return []
            if isinstance(claims, dict):
                claims = [claims]
            if not isinstance(claims, list):
                return []
            return claims
    return []


def to_draft_claims(raw_claims, passage, passages, systems):
    """Turn model output into draft claims. Returns (good, rejected)."""
    good = []
    rejected = []
    for raw in raw_claims[:3]:
        if not isinstance(raw, dict):
            continue  # skip anything that isn't a proper claim object
        statement = (raw.get("statement") or "").strip()
        system = raw.get("system")
        claim = {
            "claim_id": draft_id(passage["site"], system, passage["passage_id"], statement),
            "site": passage["site"],
            "system": system,
            "statement": statement,
            "quote": (raw.get("quote") or "").strip().strip('"').strip("\u201c\u201d"),
            "grade": raw.get("grade"),
            "sources": [source_from_passage(passage)],
            "modern_equivalent": (raw.get("modern_equivalent") or "").strip(),
            "lesson": (raw.get("lesson") or "").strip(),
            "status": "draft",
            "reviewed_by": None,
            "grade_reason": (raw.get("grade_reason") or "").strip(),
        }
        problems = validate_claim(claim, passages, systems=systems, verified=False)
        if problems:
            rejected.append({"claim": claim, "problems": problems})
        else:
            good.append(claim)
    return good, rejected


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", choices=SITES)
    parser.add_argument("--system", help="only passages rule-tagged with this system")
    parser.add_argument("--source", help="only this source_id")
    parser.add_argument("--limit", type=int, help="stop after this many passages")
    parser.add_argument("--per-source", type=int, help="take at most this many passages from any one source")
    parser.add_argument("--only-tagged", action="store_true", help="skip passages with no system tags")
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--redo", action="store_true", help="re-run passages already extracted")
    parser.add_argument("--from-map", help="only passages in this decode map, in tree order (claims/decode/<site>.json)")
    parser.add_argument("--node", help="with --from-map: only passages under this transform id, e.g. mohenjo-t02")
    args = parser.parse_args()

    map_order = None
    if args.from_map:
        from claims.decode_map import mapped_passage_ids
        with open(args.from_map, encoding="utf-8") as f:
            decode_doc = json.load(f)
        map_order = {pid: i for i, pid in enumerate(mapped_passage_ids(decode_doc, args.node))}
        if not map_order:
            sys.exit(f"no passages in {args.from_map}" + (f" under {args.node}" if args.node else ""))

    load_dotenv()
    if not os.getenv("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set (put it in .env)")

    import anthropic
    client = anthropic.Anthropic(max_retries=4)

    taxonomy = load_taxonomy()
    systems = list(taxonomy["systems"].keys())
    template = PROMPT_PATH.read_text(encoding="utf-8")
    tool = build_tool(systems)
    passages = load_passages()

    done = set()
    if DONE_PATH.exists() and not args.redo:
        done = set(DONE_PATH.read_text(encoding="utf-8").split())

    todo = []
    taken_per_source = {}
    for passage in passages.values():
        if passage["passage_id"] in done:
            continue
        if map_order is not None and passage["passage_id"] not in map_order:
            continue
        if args.site and passage["site"] != args.site:
            continue
        if args.source and passage["source_id"] != args.source:
            continue
        if args.system and args.system not in (passage.get("system_tags") or []):
            continue
        if args.only_tagged and not passage.get("system_tags"):
            continue
        # spread the run across sources instead of draining the first one in the file
        source_id = passage["source_id"]
        if args.per_source and taken_per_source.get(source_id, 0) >= args.per_source:
            continue
        taken_per_source[source_id] = taken_per_source.get(source_id, 0) + 1
        todo.append(passage)
    if map_order is not None:
        todo.sort(key=lambda p: map_order[p["passage_id"]])  # follow the tree, not the file
    if args.limit:
        todo = todo[:args.limit]

    print(f"{len(todo)} passages to extract ({len(done)} already done)")
    existing_ids = set()
    for row in read_jsonl(DRAFT_PATH):
        existing_ids.add(row["claim_id"])

    counts = {"claims": 0, "rejected": 0, "errors": 0}

    def work(passage):
        system_prompt = (template
                         .replace("{site_name}", SITE_NAMES[passage["site"]])
                         .replace("{systems_block}", systems_block(taxonomy)))
        raw = call_model(client, system_prompt, tool, passage)
        return passage, to_draft_claims(raw, passage, passages, systems)

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = []
        for passage in todo:
            futures.append(pool.submit(work, passage))
        for future in as_completed(futures):
            try:
                passage, (good, rejected) = future.result()
            except Exception as err:  # keep going, one bad call shouldn't kill the run
                counts["errors"] += 1
                print(f"  error: {err}")
                continue
            with write_lock:
                for claim in good:
                    if claim["claim_id"] in existing_ids:
                        continue
                    existing_ids.add(claim["claim_id"])
                    append_jsonl(DRAFT_PATH, claim)
                    counts["claims"] += 1
                for row in rejected:
                    append_jsonl(REJECTS_PATH, row)
                    counts["rejected"] += 1
                with open(DONE_PATH, "a", encoding="utf-8") as f:
                    f.write(passage["passage_id"] + "\n")
            print(f"  {passage['passage_id']}: {len(good)} kept, {len(rejected)} rejected")

    print(f"done: {counts['claims']} draft claims, {counts['rejected']} failed validation "
          f"(see {REJECTS_PATH.name}), {counts['errors']} API errors")


if __name__ == "__main__":
    main()
