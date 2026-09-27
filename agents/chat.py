"""Picks which pipeline answers a /chat request.

    DECODE_MODE=auto   (default) Claude pipeline when ANTHROPIC_API_KEY is set, otherwise the rules
    DECODE_MODE=llm    always try the Claude pipeline first
    DECODE_MODE=rules  always use the rule-based pipeline (fast, free, no API key needed)

If the Claude pipeline throws, or produces something that breaks Contract 4, the request falls back
to the rule-based pipeline, so the chat always answers. The trace says when that happened.
"""
from __future__ import annotations

import os
import time
from typing import Any

from agents.contract import validate_chat_response
from agents.pipeline import run_pipeline


def llm_enabled() -> bool:
    mode = os.getenv("DECODE_MODE", "auto").strip().lower()
    if mode == "rules":
        return False
    if mode == "llm":
        return True
    return bool(os.getenv("ANTHROPIC_API_KEY"))


def answer(message: str, history: list[dict] | None, site: str | None, tools: Any,
           llm=None, record_sink: list | None = None) -> dict:
    """Contract 4 response for one chat turn. record_sink (a list) collects the internal record, for eval."""
    history = history or []
    reason = None
    if llm_enabled() or llm is not None:
        from agents.llm_pipeline import LLMPipeline, ToolBridge

        started = time.time()
        try:
            response, record = LLMPipeline(tools=ToolBridge(tools), llm=llm).run(message, history, site)
            problems = validate_chat_response(response)
            if not problems:
                if record_sink is not None:
                    record_sink.append(record)
                return response
            reason = "contract check failed: " + "; ".join(problems[:3])
        except Exception as err:  # anything at all, the rules pipeline still answers
            reason = f"{type(err).__name__}: {str(err)[:160]}"
        fallback_ms = int((time.time() - started) * 1000)
    response = run_pipeline(message, history, site, tools)
    if reason:
        response["trace"].insert(0, {"layer": "fallback", "ms": fallback_ms,
                                     "summary": f"Claude pipeline unavailable ({reason}), answered with the rules pipeline"})
        response["critic"]["flags"].append("Answered by the rule-based fallback pipeline.")
        response["critic"]["passed"] = False
    if record_sink is not None:
        record_sink.append({"response": response, "fallback_reason": reason})
    return response
