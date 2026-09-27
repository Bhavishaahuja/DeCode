import os
from unittest.mock import patch

from fastapi.testclient import TestClient

from agents.pipeline import run_pipeline, route


class FakeTools:
    def __init__(self, claims=None, evidence=None, presets=None):
        self.claims = claims or []
        self.evidence = evidence or []
        self.presets = presets or {}
        self.estimate_calls = []

    def get_claims(self, site=None, system=None):
        claims = [claim for claim in self.claims
                  if (not site or claim.get("site") == site)
                  and (not system or claim.get("system") == system)]
        return {"claims": claims, "_fallback": False}

    def search_evidence(self, **_kwargs):
        return {"results": self.evidence}

    def get_presets(self):
        return self.presets

    def estimate(self, **values):
        self.estimate_calls.append(values)
        return {"years": 20.18 if values["crews"] == 190 else 4.79,
                "people": values["crews"] * values["crew_size"], "person_days": 23000000}

    def haul_force(self, **values):
        self.haul_force_input = values
        return {"force_kn": 7.36 if values["slope_deg"] == 0 else 11.5,
                "people_needed": 19 if values["slope_deg"] == 0 else 29,
                "assumptions": ["Friction coefficient of 0.3 is assumed",
                                "Sustained pull of 400 N per person is assumed"]}

    def carbon(self, **values):
        self.carbon_inputs = getattr(self, "carbon_inputs", []) + [values]
        return {"material": values["material"], "kgco2e": 196200,
                "source": "ICE Database v3", "assumptions": ["density assumption used"]}

    def close(self):
        pass


def giza_preset():
    return {
        "unit": "stone blocks", "quantity": 2300000, "quantity_tag": "attested",
        "ancient": {"crews": 190, "crew_size": 20, "rate_per_crew_day": 2, "days_per_year": 300,
                    "crew_label": "Hauling crews", "rate_label": "Blocks per crew-day", "tag": "assumed"},
        "modern": {"crews": 20, "crew_size": 6, "rate_per_crew_day": 80, "days_per_year": 300,
                   "crew_label": "Crane crews", "rate_label": "Blocks per crane-day", "tag": "assumed"},
    }


def test_router_uses_site_hint_and_recognizes_estimate():
    result = route("How long with modern cranes?", site_hint="giza")
    assert result["intent"] == "estimate"
    assert result["sites"] == ["giza"]
    assert result["clarifying_question"] is None


def test_router_clarifies_unknown_site_and_detects_fringe():
    result = route("Did aliens build the pyramids?")
    assert result["intent"] == "fringe"
    assert result["sites"] == ["giza"]  # "the pyramids" means Giza (demo question)
    assert result["clarifying_question"] is None
    assert route("How did they move the stones?")["clarifying_question"]


def test_router_recognizes_site_comparisons_fringe_variants_and_global_carbon():
    comparison = route("Compare work standards at Giza and Mohenjo-daro")
    assert comparison["sites"] == ["giza", "mohenjo"]
    assert comparison["intent"] == "compare"
    assert "quality_control" in comparison["systems"]
    assert route("Was Mohenjo-daro destroyed by an ancient nuclear blast?", site_hint="mohenjo")["intent"] == "fringe"
    carbon = route("What is embodied carbon for 1000 cubic meters of limestone?")
    assert carbon["calculation"] == "carbon"
    assert carbon["clarifying_question"] is None


def test_haul_force_request_uses_tool_and_preserves_assumptions():
    tools = FakeTools()
    response = run_pipeline(
        "How many people to drag a 2.5 tonne block on flat wet sand, friction 0.3 and 400 N of pull per person?",
        [], "giza", tools,
    )
    assert tools.haul_force_input == {
        "mass_kg": 2500.0, "slope_deg": 0, "friction_coeff": 0.3, "pull_per_person_n": 400.0,
    }
    assert "19 people" in response["answer_md"]
    assert "Assumptions" in response["answer_md"]
    assert response["critic"]["passed"]


def test_carbon_comparison_works_without_a_site_hint():
    tools = FakeTools()
    response = run_pipeline(
        "What is the embodied carbon of 1000 cubic meters of limestone compared with fired brick?",
        [], None, tools,
    )
    assert len(tools.carbon_inputs) == 2
    assert {item["material"] for item in tools.carbon_inputs} == {"limestone", "fired brick"}
    assert "ICE Database" in response["answer_md"]
    assert response["clarifying_question"] is None


def test_multi_site_comparison_cites_both_sites():
    claims = [
        {"claim_id": "giza-quality-001", "site": "giza", "system": "quality_control",
         "statement": "Giza claim.", "grade": "attested", "status": "verified",
         "sources": [{"source_id": "giza-source", "title": "Giza source", "url": "https://example.test/giza"}]},
        {"claim_id": "mohenjo-quality-001", "site": "mohenjo", "system": "quality_control",
         "statement": "Mohenjo claim.", "grade": "debated", "status": "verified",
         "sources": [{"source_id": "mohenjo-source", "title": "Mohenjo source", "url": "https://example.test/mohenjo"}]},
    ]
    response = run_pipeline("Compare work standards at Giza and Mohenjo-daro", [], None,
                            FakeTools(claims=claims))
    assert len(response["citations"]) == 2
    assert "Giza: Giza claim.[^1]" in response["answer_md"]
    assert "Mohenjo-daro: Mohenjo claim.[^2]" in response["answer_md"]
    assert {card["site"] for card in response["cards"]} == {"giza", "mohenjo"}


def test_estimate_calls_tool_for_both_scenarios_and_returns_contract_shape():
    tools = FakeTools(presets={"giza": giza_preset()})
    response = run_pipeline("How long would Giza take with modern cranes?", [], None, tools)
    assert len(tools.estimate_calls) == 2
    assert response["intent"] == "estimate"
    assert response["cards"][0]["type"] == "estimator"
    assert "20.18 years" in response["answer_md"]
    assert "4.79 years" in response["answer_md"]
    assert set(response) == {"answer_md", "intent", "sites", "systems", "clarifying_question",
                             "citations", "cards", "critic", "trace"}


def test_contract_fallback_claim_is_not_cited_or_presented():
    class FallbackTools(FakeTools):
        def get_claims(self, site=None, system=None):
            return {"claims": [{"claim_id": "placeholder", "status": "verified",
                                "statement": "placeholder claim", "sources": []}], "_fallback": True}

    response = run_pipeline("Explain Giza construction", [], None,
                            FallbackTools(evidence=[{"title": "Source record"}]))
    assert response["citations"] == []
    assert "placeholder claim" not in response["answer_md"]
    assert response["critic"]["passed"] is False
    assert response["cards"] == []


def test_missing_site_returns_one_question_and_no_cards():
    response = run_pipeline("How did they build it?", [], None, FakeTools())
    assert response["clarifying_question"]
    assert response["cards"] == []


def test_chat_endpoint_returns_contract_response():
    from agents import server

    fake_tools = FakeTools(presets={"giza": giza_preset()})
    # rules mode, so the test never calls the real Claude API even when .env has a key
    with patch("agents.server.ToolsClient", return_value=fake_tools), patch.dict(os.environ, {"STRATUM_MODE": "rules"}):
        response = TestClient(server.app).post(
            "/chat", json={"message": "How long would Giza take with modern cranes?", "site": "giza"}
        )
    assert response.status_code == 200
    body = response.json()
    assert body["intent"] == "estimate"
    assert body["cards"][0]["type"] == "estimator"
    assert set(body) == {"answer_md", "intent", "sites", "systems", "clarifying_question",
                         "citations", "cards", "critic", "trace"}