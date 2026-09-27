"""Tests for the tool API.  pytest tools/tests"""
import json

import pytest
from fastapi.testclient import TestClient

from tools import app as tools_app

client = TestClient(tools_app.app)


def post(path, body):
    return client.post(path, json=body)


# estimate --------------------------------------------------------------------------------------
def test_estimate_matches_contract_example():
    r = post("/tools/estimate", {"quantity": 2300000, "unit": "stone blocks", "crews": 190, "crew_size": 20,
                                 "rate_per_crew_day": 2, "days_per_year": 300})
    assert r.status_code == 200
    body = r.json()
    assert body["years"] == 20.18
    assert body["people"] == 3800
    assert body["person_days"] == 23000000
    assert any("assumed" in a for a in body["assumptions"])


def test_giza_presets_give_about_20_and_5_years():
    presets = client.get("/tools/presets").json()
    giza = presets["giza"]
    years = {}
    for era in ("ancient", "modern"):
        p = giza[era]
        r = post("/tools/estimate", {"quantity": giza["quantity"], "unit": giza["unit"], "crews": p["crews"],
                                     "crew_size": p["crew_size"], "rate_per_crew_day": p["rate_per_crew_day"],
                                     "days_per_year": p["days_per_year"]})
        years[era] = r.json()["years"]
    assert years["ancient"] == pytest.approx(20.2, abs=0.05)
    assert years["modern"] == pytest.approx(4.8, abs=0.05)


def test_every_preset_runs_and_modern_is_faster():
    presets = client.get("/tools/presets").json()
    assert set(presets) == {"giza", "uruk", "mohenjo", "qin"}
    for site, preset in presets.items():
        results = {}
        for era in ("ancient", "modern"):
            p = preset[era]
            body = {k: p[k] for k in ("crews", "crew_size", "rate_per_crew_day", "days_per_year")}
            body.update(quantity=preset["quantity"], unit=preset["unit"])
            r = post("/tools/estimate", body)
            assert r.status_code == 200, (site, r.text)
            results[era] = r.json()["years"]
        assert results["modern"] < results["ancient"], site


def test_estimate_rejects_zero_with_string_detail():
    r = post("/tools/estimate", {"quantity": 0, "crews": 1, "crew_size": 1, "rate_per_crew_day": 1, "days_per_year": 300})
    assert r.status_code == 422
    assert isinstance(r.json()["detail"], str)
    assert "quantity" in r.json()["detail"]


# haul_force ------------------------------------------------------------------------------------
def test_haul_force_matches_contract_example():
    r = post("/tools/haul_force", {"mass_kg": 2500, "slope_deg": 0, "friction_coeff": 0.3, "pull_per_person_n": 400})
    body = r.json()
    assert body["force_n"] == 7357.5
    assert body["force_kn"] == 7.36
    assert body["people_needed"] == 19
    text = " ".join(body["assumptions"])
    assert "Friction coefficient" in text and "per person is assumed" in text


def test_haul_force_on_a_slope_needs_more_people():
    flat = post("/tools/haul_force", {"mass_kg": 2500, "slope_deg": 0, "friction_coeff": 0.3, "pull_per_person_n": 400}).json()
    ramp = post("/tools/haul_force", {"mass_kg": 2500, "slope_deg": 10, "friction_coeff": 0.3, "pull_per_person_n": 400}).json()
    assert ramp["force_n"] > flat["force_n"]
    assert ramp["people_needed"] > flat["people_needed"]


def test_haul_force_exact_division_does_not_round_up():
    # 400 kg on flat ground, mu 1.0 -> 3924 N, at 392.4 N each is exactly 10 people
    r = post("/tools/haul_force", {"mass_kg": 400, "slope_deg": 0, "friction_coeff": 1.0, "pull_per_person_n": 392.4})
    assert r.json()["people_needed"] == 10


# carbon ----------------------------------------------------------------------------------------
def test_carbon_limestone_uses_ice_factor():
    r = post("/tools/carbon", {"material": "limestone", "volume_m3": 1000})
    body = r.json()
    assert r.status_code == 200
    assert body["factor_kgco2e_per_m3"] == pytest.approx(0.09 * 2180)
    assert body["kgco2e"] == pytest.approx(196200)
    assert "ICE" in body["source"]


def test_carbon_aliases():
    r = post("/tools/carbon", {"material": "Fired Brick", "volume_m3": 10})
    assert r.status_code == 200
    assert r.json()["material"] == "clay_brick"


def test_carbon_unknown_material_404():
    r = post("/tools/carbon", {"material": "unobtainium", "volume_m3": 1})
    assert r.status_code == 404
    body = r.json()
    assert body["detail"] == "unknown material"
    assert "limestone" in body["known_materials"]


def test_carbon_csv_math_is_consistent():
    for name, f in tools_app.load_carbon_factors().items():
        assert f["kgco2e_per_m3"] == pytest.approx(f["kgco2e_per_kg"] * f["density_kg_per_m3"], rel=1e-3), name


# claims ----------------------------------------------------------------------------------------
def test_claims_fall_back_to_example_when_nothing_verified(tmp_path, monkeypatch):
    monkeypatch.setattr(tools_app, "VERIFIED_CLAIMS", tmp_path / "missing.jsonl")
    r = post("/tools/claims", {"site": "giza", "system": "transport_lifting"})
    assert r.status_code == 200
    assert r.headers.get("X-DeCode-Fallback")
    assert r.json()["claims"][0]["claim_id"] == "giza-transport_lifting-003"


def test_claims_only_verified_and_filtered(tmp_path, monkeypatch):
    path = tmp_path / "claims.jsonl"
    rows = [
        {"claim_id": "giza-workforce-001", "site": "giza", "system": "workforce", "status": "verified"},
        {"claim_id": "giza-workforce-d123", "site": "giza", "system": "workforce", "status": "draft"},
        {"claim_id": "uruk-workforce-001", "site": "uruk", "system": "workforce", "status": "verified"},
    ]
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    monkeypatch.setattr(tools_app, "VERIFIED_CLAIMS", path)
    r = post("/tools/claims", {"site": "giza", "system": "workforce"})
    assert [c["claim_id"] for c in r.json()["claims"]] == ["giza-workforce-001"]
    assert "X-DeCode-Fallback" not in r.headers
    everything = post("/tools/claims", {}).json()["claims"]
    assert len(everything) == 2


def test_claims_unknown_site_400():
    r = post("/tools/claims", {"site": "atlantis"})
    assert r.status_code == 400


# search_evidence -------------------------------------------------------------------------------
def test_search_evidence_wraps_data_layer(monkeypatch):
    fake = [{"passage_id": "giza-x-0001", "score": 0.9}]
    monkeypatch.setattr(tools_app, "run_search", lambda req: fake)
    r = post("/tools/search_evidence", {"query": "ramp", "site": "giza", "system": None, "k": 8})
    assert r.json() == {"results": fake}


def test_search_evidence_bad_site_400(monkeypatch):
    def boom(req):
        raise ValueError("Unknown site 'atlantis'")
    monkeypatch.setattr(tools_app, "run_search", boom)
    r = post("/tools/search_evidence", {"query": "ramp", "site": "atlantis"})
    assert r.status_code == 400 and "atlantis" in r.json()["detail"]


def test_search_evidence_real_index_if_built():
    r = post("/tools/search_evidence", {"query": "ramp sledge wet sand", "site": "giza", "k": 3})
    if r.status_code == 503:
        pytest.skip("passages.jsonl not built")
    assert r.status_code == 200
    results = r.json()["results"]
    assert results and all(p["site"] == "giza" and "score" in p for p in results)


# tool definitions ------------------------------------------------------------------------------
def test_openapi_tools_file_is_current():
    on_disk = json.loads(tools_app.OPENAPI_TOOLS_PATH.read_text(encoding="utf-8"))
    assert on_disk == tools_app.anthropic_tools(), "run: python -m tools.app --export"
    assert [t["name"] for t in on_disk] == ["search_evidence", "get_claims", "estimate", "haul_force", "carbon"]
    for tool in on_disk:
        assert tool["description"] and tool["input_schema"]["type"] == "object"
