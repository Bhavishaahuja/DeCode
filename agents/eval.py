"""Runs the eval questions (claims/eval/questions.jsonl) through the chat and scores them.

    python -m agents.eval                      # all 30, whichever pipeline STRATUM_MODE picks
    python -m agents.eval --mode rules         # rule-based pipeline only (free, fast)
    python -m agents.eval --mode llm           # Claude pipeline (needs ANTHROPIC_API_KEY)
    python -m agents.eval --ids q15,q26        # just these
    python -m agents.eval --category fringe

Uses the tools server on TOOLS_URL if it's running, otherwise runs the tools in-process.
Exit code 1 when the pass rate is under 80% (the definition of done in CLAUDE.md).
A full report goes to agents/logs/eval-<time>.json.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

from agents import chat
from agents.contract import validate_chat_response
from agents.llm_pipeline import numbers_in
from agents.tools_client import ToolsClient

REPO_ROOT = Path(__file__).resolve().parent.parent
QUESTIONS = REPO_ROOT / "claims" / "eval" / "questions.jsonl"
LOG_DIR = Path(__file__).resolve().parent / "logs"
PASS_MARK = 0.8


class RecordingToolsClient(ToolsClient):
    """Same client, but it also remembers every call so we can check required_tools."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.events: list[dict] = []

    def _write_log(self, event):
        self.events.append(event)
        super()._write_log(event)


def make_tools() -> RecordingToolsClient:
    url = os.getenv("TOOLS_URL", "http://localhost:8001")
    try:
        httpx.get(url.rstrip("/") + "/health", timeout=2).raise_for_status()
        return RecordingToolsClient(url)
    except httpx.HTTPError:
        # no tools server running, so talk to the FastAPI app directly
        from fastapi.testclient import TestClient

        from tools.app import app as tools_app
        client = RecordingToolsClient("http://testserver")
        client._http.close()
        client._http = TestClient(tools_app)
        return client


def check(question: dict, response: dict, tools_used: set[str]) -> list[str]:
    """Every problem with one answer. An empty list is a pass."""
    problems = []
    contract = validate_chat_response(response)
    if contract:
        problems.append("contract: " + "; ".join(contract[:3]))
        return problems

    answer = response["answer_md"].lower()
    asked = response["clarifying_question"] is not None
    if question["expect_clarifying"] != asked:
        problems.append("expected a clarifying question" if question["expect_clarifying"] else "asked a clarifying question it shouldn't have")
        return problems
    if asked:
        return problems

    if response["intent"] != question["expected_intent"]:
        problems.append(f"intent {response['intent']} (expected {question['expected_intent']})")
    missing_sites = set(question["expected_sites"]) - set(response["sites"])
    if missing_sites:
        problems.append(f"missing sites {sorted(missing_sites)}")
    expected_systems = question["expected_systems_any"]
    if expected_systems and not set(expected_systems) & set(response["systems"]):
        problems.append(f"systems {response['systems']} (expected any of {expected_systems})")
    if question["must_cite"] and not response["citations"]:
        problems.append("no citations")
    for tool in question["required_tools"]:
        if tool not in tools_used:
            problems.append(f"didn't call {tool}")

    # numbers can show up in the answer text or in a card
    shown = [value for value, _, _ in numbers_in(response["answer_md"])]
    for card in response["cards"]:
        shown += [value for value, _, _ in numbers_in(json.dumps(card))]
    for name, spec in (question.get("expected_numbers") or {}).items():
        target, tolerance = spec["value"], spec.get("tolerance", 0)
        if not any(abs(value - target) <= tolerance + 1e-9 for value in shown):
            problems.append(f"{name} {target} not shown")

    mentions = question["must_mention_any"]
    if mentions and not any(term.lower() in answer for term in mentions):
        problems.append(f"doesn't mention any of {mentions}")
    for term in question["must_not_mention"]:
        if term.lower() in answer:
            problems.append(f"mentions {term!r}")
    return problems


def run_one(question: dict) -> dict:
    tools = make_tools()
    started = time.time()
    try:
        response = chat.answer(question["question"], [], question.get("site_hint"), tools)
        tools_used = {event["tool"] for event in tools.events if "error" not in event}
        problems = check(question, response, tools_used)
    except Exception as err:
        response = None
        problems = [f"crashed: {type(err).__name__}: {err}"]
    finally:
        tools.close()
    fallback = bool(response and response["trace"] and response["trace"][0]["layer"] == "fallback")
    return {"id": question["id"], "category": question["category"], "question": question["question"],
            "passed": not problems, "problems": problems, "seconds": round(time.time() - started, 1),
            "fallback": fallback, "response": response}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--mode", choices=["auto", "llm", "rules"], help="overrides STRATUM_MODE")
    parser.add_argument("--ids", help="comma-separated question ids, e.g. q15,q26")
    parser.add_argument("--category", help="explain, compare, estimate, playbook or fringe")
    parser.add_argument("--workers", type=int, default=3, help="questions run at once (default 3)")
    args = parser.parse_args(argv)

    load_dotenv()
    if args.mode:
        os.environ["STRATUM_MODE"] = args.mode

    questions = [json.loads(line) for line in QUESTIONS.read_text(encoding="utf-8").splitlines() if line.strip()]
    if args.ids:
        wanted = set(args.ids.split(","))
        questions = [q for q in questions if q["id"] in wanted]
    if args.category:
        questions = [q for q in questions if q["category"] == args.category]
    if not questions:
        print("no questions matched")
        return 1

    mode = "Claude pipeline" if chat.llm_enabled() else "rules pipeline"
    print(f"running {len(questions)} questions with the {mode}\n")
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        results = list(pool.map(run_one, questions))

    for r in results:
        mark = "PASS" if r["passed"] else "FAIL"
        extra = "  (fallback)" if r["fallback"] else ""
        print(f"{mark}  {r['id']}  {r['category']:9} {r['seconds']:5}s{extra}  {r['question'][:60]}")
        for problem in r["problems"]:
            print(f"        - {problem}")

    passed = sum(1 for r in results if r["passed"])
    rate = passed / len(results)
    print(f"\n{passed}/{len(results)} passed ({rate:.0%}), target {PASS_MARK:.0%}")

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    report = LOG_DIR / f"eval-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    report.write_text(json.dumps({"mode": mode, "passed": passed, "total": len(results), "results": results},
                                 indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    print(f"full report: {report}")
    return 0 if rate >= PASS_MARK else 1


if __name__ == "__main__":
    sys.exit(main())
