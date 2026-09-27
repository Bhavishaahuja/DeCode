"""Checks that a /chat response matches Contract 4 in CLAUDE.md.

    from agents.contract import validate_chat_response
    problems = validate_chat_response(response)   # [] means it's valid

Used by the server (before a response goes out), by eval, and by the tests.
"""
from __future__ import annotations

SITES = ["giza", "uruk", "mohenjo", "qin"]
SYSTEMS = ["site_setout", "materials_supply", "transport_lifting", "water_sanitation", "structure_form",
           "finishes", "workforce", "quality_control", "project_controls"]
INTENTS = ["explain", "compare", "estimate", "playbook", "fringe"]
GRADES = ["attested", "debated", "inferred"]
TOP_KEYS = ["answer_md", "intent", "sites", "systems", "clarifying_question", "citations", "cards", "critic", "trace"]
CITATION_KEYS = ["n", "claim_id", "source_id", "title", "url", "locator", "grade"]
TEARDOWN_ROW_KEYS = ["system", "grade", "ancient", "evidence", "modern", "lesson", "claim_ids"]
ERA_KEYS = ["crews", "crew_size", "rate_per_crew_day", "days_per_year", "crew_label", "rate_label", "tag"]
RESULT_KEYS = ["years", "people", "person_days"]
BANNED_DASHES = ["\u2014", "\u2013"]


def validate_chat_response(resp: dict) -> list[str]:
    problems = []
    if not isinstance(resp, dict):
        return ["response is not an object"]

    for key in TOP_KEYS:
        if key not in resp:
            problems.append(f"missing key {key}")
    if problems:
        return problems

    if not isinstance(resp["answer_md"], str):
        problems.append("answer_md must be a string")
    elif any(dash in resp["answer_md"] for dash in BANNED_DASHES):
        problems.append("answer_md contains an em or en dash")
    if resp["intent"] not in INTENTS:
        problems.append(f"intent {resp['intent']!r} not in {INTENTS}")
    if not isinstance(resp["sites"], list) or not set(resp["sites"]) <= set(SITES):
        problems.append(f"sites must be a subset of {SITES}")
    if not isinstance(resp["systems"], list) or not set(resp["systems"]) <= set(SYSTEMS):
        problems.append("systems must use the 9 system ids")

    question = resp["clarifying_question"]
    if question is not None:
        if not isinstance(question, str) or not question.strip():
            problems.append("clarifying_question must be null or a non-empty string")
        if resp["cards"]:
            problems.append("cards must be empty when asking a clarifying question")

    problems += _check_citations(resp["citations"])
    problems += _check_cards(resp["cards"])

    critic = resp["critic"]
    if not isinstance(critic, dict) or not {"passed", "flags", "retries"} <= set(critic):
        problems.append("critic needs passed, flags, retries")
    elif not isinstance(critic["passed"], bool) or not isinstance(critic["flags"], list):
        problems.append("critic.passed must be a bool and critic.flags a list")

    if not isinstance(resp["trace"], list):
        problems.append("trace must be a list")
    else:
        for step in resp["trace"]:
            if not isinstance(step, dict) or not {"layer", "ms", "summary"} <= set(step):
                problems.append("each trace step needs layer, ms, summary")
                break
    return problems


def _check_citations(citations) -> list[str]:
    if not isinstance(citations, list):
        return ["citations must be a list"]
    problems = []
    seen = set()
    for c in citations:
        missing = [k for k in CITATION_KEYS if k not in c]
        if missing:
            problems.append(f"citation missing {missing}")
            continue
        if not isinstance(c["n"], int) or c["n"] in seen:
            problems.append(f"citation n {c['n']!r} must be a unique int")
        seen.add(c["n"])
        if c["grade"] not in GRADES:
            problems.append(f"citation {c['n']} has grade {c['grade']!r}")
    return problems


def _check_cards(cards) -> list[str]:
    if not isinstance(cards, list):
        return ["cards must be a list"]
    problems = []
    for card in cards:
        kind = card.get("type")
        if card.get("site") not in SITES:
            problems.append(f"{kind} card has site {card.get('site')!r}")
        if kind == "teardown":
            for row in card.get("rows", []):
                missing = [k for k in TEARDOWN_ROW_KEYS if k not in row]
                if missing:
                    problems.append(f"teardown row missing {missing}")
                elif row["system"] not in SYSTEMS or row["grade"] not in GRADES:
                    problems.append(f"teardown row has bad system or grade: {row['system']}, {row['grade']}")
        elif kind == "estimator":
            preset = card.get("preset", {})
            for key in ("unit", "quantity", "quantity_tag", "ancient", "modern"):
                if key not in preset:
                    problems.append(f"estimator preset missing {key}")
            for era in ("ancient", "modern"):
                missing = [k for k in ERA_KEYS if k not in preset.get(era, {})]
                if missing:
                    problems.append(f"estimator preset.{era} missing {missing}")
                missing = [k for k in RESULT_KEYS if k not in card.get("result", {}).get(era, {})]
                if missing:
                    problems.append(f"estimator result.{era} missing {missing}")
        elif kind == "sequence":
            for key in ("span", "unit", "rows"):
                if key not in card:
                    problems.append(f"sequence card missing {key}")
        else:
            problems.append(f"unknown card type {kind!r}")
    return problems
