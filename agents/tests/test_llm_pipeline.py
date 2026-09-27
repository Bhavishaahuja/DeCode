"""Tests for the Claude pipeline (agents/llm_pipeline.py) with a scripted fake model, so no API calls."""
import json
import os
from types import SimpleNamespace
from unittest.mock import patch

from agents import chat
from agents.contract import validate_chat_response
from agents.llm_pipeline import LLMPipeline, ToolBridge, numbers_in, strip_dashes, unsourced_numbers
from agents.tests.test_pipeline import FakeTools, giza_preset

SLEDGE_CLAIM = {
    "claim_id": "giza-transport_lifting-001", "site": "giza", "system": "transport_lifting",
    "statement": "Blocks were dragged on wooden sledges.", "quote": "dragged on sledges", "grade": "attested",
    "sources": [{"source_id": "petrie1883", "passage_id": "giza-petrie1883-0001", "title": "Petrie",
                 "url": "https://example.test/petrie", "locator": "p. 1"}],
    "modern_equivalent": "Low-friction skid systems.", "lesson": "Cheap friction fixes beat horsepower.",
    "status": "verified", "reviewed_by": "bhavisha",
}


def text_reply(text):
    return SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text=text)])


def tool_reply(name, args, tool_id="t1"):
    return SimpleNamespace(stop_reason="tool_use",
                           content=[SimpleNamespace(type="tool_use", name=name, input=args, id=tool_id)])


class FakeLLM:
    """Answers by layer, recognised from the first line of the system prompt."""

    def __init__(self, script):
        self.script = script          # layer -> list of replies, used in order
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        first_line = kwargs["system"].strip().splitlines()[0]
        layer = next(name for name in self.script if f"the {name.capitalize()}," in first_line)
        self.calls.append((layer, kwargs))
        replies = self.script[layer]
        reply = replies.pop(0) if len(replies) > 1 else replies[0]
        return reply() if callable(reply) else reply


def explain_script(presenter_texts=None):
    presenter = [text_reply(t) for t in (presenter_texts or ["Blocks were dragged on wooden sledges[^1]."])]
    return {
        "router": [text_reply('{"intent": "explain", "sites": ["giza"], "systems": ["transport_lifting"], "clarifying_question": null}')],
        "archaeologist": [
            tool_reply("get_claims", {"site": "giza", "system": "transport_lifting"}),
            text_reply(json.dumps({"findings": [{"site": "giza", "system": "transport_lifting", "statement": "sledges",
                                                 "grade": "attested", "claim_id": "giza-transport_lifting-001",
                                                 "passage_id": None, "quote": "dragged on sledges", "grade_note": "x"}],
                                   "gaps": [], "fringe_check": None})),
        ],
        "engineer": [text_reply('{"system_map": [], "physics_checks": [], "risks": [], "gaps": []}')],
        "presenter": presenter,
        "critic": [text_reply('{"passed": true, "flags": []}')],
    }


def run(script, message="How did Giza move blocks?", site=None, tools=None):
    tools = tools or FakeTools(claims=[SLEDGE_CLAIM], presets={"giza": giza_preset()})
    pipeline = LLMPipeline(tools=ToolBridge(tools), llm=FakeLLM(script), write_logs=False)
    return pipeline.run(message, [], site)


def test_explain_answer_is_cited_and_valid():
    response, record = run(explain_script())
    assert validate_chat_response(response) == []
    assert response["intent"] == "explain"
    assert response["citations"][0]["claim_id"] == "giza-transport_lifting-001"
    assert response["citations"][0]["grade"] == "attested"
    assert "[^1]" in response["answer_md"]
    assert response["cards"][0]["type"] == "teardown"
    assert response["critic"] == {"passed": True, "flags": [], "retries": 0}
    layers = [step["layer"] for step in response["trace"]]
    assert layers[0] == "router" and "archaeologist" in layers and "critic" in layers


def test_unsourced_number_triggers_one_retry():
    response, _ = run(explain_script(["It took 999 workers[^1].", "Blocks were dragged on sledges[^1]."]))
    assert response["critic"]["retries"] == 1
    assert response["critic"]["passed"] is True
    assert "999" not in response["answer_md"]


def test_number_still_unsourced_after_retry_is_flagged():
    response, _ = run(explain_script(["It took 999 workers[^1].", "Still 999 workers[^1]."]))
    assert response["critic"]["passed"] is False
    assert any("999" in flag for flag in response["critic"]["flags"])


def test_estimate_builds_card_from_preset_and_numbers_pass():
    script = {
        "router": [text_reply('{"intent": "estimate", "sites": ["giza"], "systems": ["workforce"], "clarifying_question": null}')],
        "archaeologist": [text_reply('{"findings": [], "gaps": [], "fringe_check": null}')],
        "estimator": [text_reply('{"estimator_card_site": "giza", "summary": "", "assumptions": [], "notes": []}')],
        "presenter": [text_reply("About 20.18 years the ancient way and 4.79 years with cranes, with assumed crew rates.")],
        "critic": [text_reply('{"passed": true, "flags": []}')],
    }
    response, _ = run(script, "How long would Giza take with modern cranes?", site="giza")
    card = next(c for c in response["cards"] if c["type"] == "estimator")
    assert card["result"]["ancient"]["years"] == 20.18
    assert card["result"]["modern"]["years"] == 4.79
    assert response["critic"]["passed"] is True
    assert validate_chat_response(response) == []


def test_clarifying_question_returns_no_cards():
    script = {"router": [text_reply('{"intent": "explain", "sites": [], "systems": [], "clarifying_question": "Which site do you mean?"}')]}
    response, _ = run(script, "How did they move the stones?")
    assert response["clarifying_question"] == "Which site do you mean?"
    assert response["cards"] == [] and response["citations"] == []


def test_hallucinated_claim_ids_are_never_cited():
    script = explain_script(["Something[^1]."])
    script["archaeologist"][-1] = text_reply(json.dumps({"findings": [
        {"site": "giza", "system": "workforce", "statement": "made up", "grade": "attested",
         "claim_id": "giza-workforce-999", "passage_id": None, "quote": "", "grade_note": ""}], "gaps": [], "fringe_check": None}))
    response, _ = run(script)
    assert all(c["claim_id"] != "giza-workforce-999" for c in response["citations"])


def test_bridge_hides_the_contract_placeholder():
    class FallbackTools(FakeTools):
        def get_claims(self, site=None, system=None):
            return {"claims": [{"claim_id": "placeholder", "status": "verified"}], "_fallback": True}
    bridge = ToolBridge(FallbackTools())
    assert bridge.call("get_claims", {"site": "giza"})["claims"] == []


def test_chat_falls_back_to_rules_when_claude_breaks():
    class BrokenLLM:
        messages = None
    with patch.dict(os.environ, {"STRATUM_MODE": "llm"}):
        response = chat.answer("How long would Giza take with modern cranes?", [], "giza",
                               FakeTools(presets={"giza": giza_preset()}), llm=BrokenLLM())
    assert response["trace"][0]["layer"] == "fallback"
    assert response["cards"][0]["type"] == "estimator"
    assert validate_chat_response(response) == []


def test_number_helpers():
    assert [n[0] for n in numbers_in("2,300,000 blocks, 20.18 years[^3]")] == [2300000.0, 20.18]
    assert unsourced_numbers("about 20.2 years and 4.8 years", {20.18, 4.79}) == []
    assert unsourced_numbers("about 31 years", {20.18}) == ["31"]
    assert strip_dashes("2600\u20132500 BCE \u2014 roughly") == "2600 to 2500 BCE, roughly"


def test_agents_get_prefetched_evidence():
    script = explain_script()
    llm = FakeLLM(script)
    tools = FakeTools(claims=[SLEDGE_CLAIM], presets={"giza": giza_preset()})
    LLMPipeline(tools=ToolBridge(tools), llm=llm, write_logs=False).run("How did Giza move blocks?", [], None)
    archaeologist_input = next(kw for layer, kw in llm.calls if layer == "archaeologist")["messages"][0]["content"]
    assert "giza-transport_lifting-001" in archaeologist_input
    assert "VERIFIED CLAIMS" in archaeologist_input


def test_fringe_answer_always_says_not_supported():
    script = explain_script(["The pyramids were built by organised crews of Egyptian workers[^1]."])
    script["router"] = [text_reply('{"intent": "fringe", "sites": ["giza"], "systems": ["workforce"], "clarifying_question": null}')]
    response, _ = run(script, "Did aliens build the pyramids?")
    assert response["answer_md"].startswith("That idea is not supported by the evidence.")
