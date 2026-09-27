"""Stratum tool API (Contract 3 in CLAUDE.md), served on :8001.

    uvicorn tools.app:app --port 8001 --reload      (or: make tools)
    python -m tools.app --export                    rewrite tools/openapi_tools.json from the models below

Every endpoint is POST, JSON in and out. Errors come back as 4xx with {"detail": "..."}.
The chat agents call these so that every number in an answer comes from a tool, never from the model.

Tool name   -> endpoint
search_evidence -> POST /tools/search_evidence
get_claims      -> POST /tools/claims
estimate        -> POST /tools/estimate
haul_force      -> POST /tools/haul_force
carbon          -> POST /tools/carbon

Extras (not tools, handy for the web app): GET /tools/presets, GET /health
"""
from __future__ import annotations

import csv
import json
import math
import sys
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

TOOLS_DIR = Path(__file__).resolve().parent
REPO_ROOT = TOOLS_DIR.parent
PRESETS_PATH = TOOLS_DIR / "presets.json"
CARBON_CSV = TOOLS_DIR / "data" / "carbon_factors.csv"
OPENAPI_TOOLS_PATH = TOOLS_DIR / "openapi_tools.json"
VERIFIED_CLAIMS = REPO_ROOT / "claims" / "verified" / "claims.jsonl"
EXAMPLES_DIR = REPO_ROOT / "contracts" / "examples"

GRAVITY = 9.81
SITES = ["giza", "uruk", "mohenjo", "qin"]

TOOL_ENDPOINTS = {
    "search_evidence": "/tools/search_evidence",
    "get_claims": "/tools/claims",
    "estimate": "/tools/estimate",
    "haul_force": "/tools/haul_force",
    "carbon": "/tools/carbon",
}

# a few friendly names people (and models) use for the materials in the csv
MATERIAL_ALIASES = {
    "brick": "clay_brick",
    "bricks": "clay_brick",
    "fired brick": "clay_brick",
    "fired_brick": "clay_brick",
    "baked brick": "clay_brick",
    "baked_brick": "clay_brick",
    "burnt brick": "clay_brick",
    "clay brick": "clay_brick",
    "rammed earth": "rammed_earth",
    "hangtu": "rammed_earth",
    "tamped earth": "rammed_earth",
}


# ---------------------------------------------------------------------------------------------
# Request models. The descriptions double as the tool descriptions the agents see.

class SearchEvidenceIn(BaseModel):
    """Search the evidence index for passages about an ancient site. Returns cited passages with a relevance score."""
    query: str = Field(..., min_length=1, description="What to look for, in plain English, e.g. 'ramp sledge wet sand'")
    site: Optional[str] = Field(None, description="Site id: giza, uruk, mohenjo or qin. Leave null to search all sites.")
    system: Optional[str] = Field(None, description="One of the 9 system ids, e.g. transport_lifting. Leave null for all.")
    k: int = Field(8, ge=1, le=25, description="How many passages to return")


class ClaimsIn(BaseModel):
    """Get verified, graded claims (ancient practice, modern equivalent, lesson, evidence grade) for a site and system."""
    site: Optional[str] = Field(None, description="Site id: giza, uruk, mohenjo or qin. Null returns every site.")
    system: Optional[str] = Field(None, description="One of the 9 system ids. Null returns every system.")


class EstimateIn(BaseModel):
    """Estimate duration and labour for a build: years, people and person-days from quantity, crews and rates."""
    quantity: float = Field(..., gt=0, description="How much gets built, e.g. 2300000 blocks")
    unit: str = Field("units", description="What quantity counts, e.g. 'stone blocks'")
    crews: float = Field(..., gt=0, description="Number of crews working in parallel")
    crew_size: float = Field(..., gt=0, description="People per crew")
    rate_per_crew_day: float = Field(..., gt=0, description="Units one crew completes per working day")
    days_per_year: float = Field(..., gt=0, le=366, description="Working days per year")


class HaulForceIn(BaseModel):
    """Force needed to drag a load on a sledge up a slope, and how many people that takes."""
    mass_kg: float = Field(..., gt=0, description="Mass of the load in kg")
    slope_deg: float = Field(0, ge=0, lt=90, description="Slope of the ramp in degrees, 0 for flat ground")
    friction_coeff: float = Field(..., ge=0, le=2, description="Sliding friction coefficient (assumed), e.g. 0.3 for a sledge on wetted sand")
    pull_per_person_n: float = Field(..., gt=0, description="Sustained pull one person manages, in newtons (assumed), e.g. 400")


class CarbonIn(BaseModel):
    """Embodied carbon (cradle to gate) for a volume of material, using ICE Database factors."""
    material: str = Field(..., min_length=1, description="Material name, e.g. limestone, granite, clay_brick, rammed_earth")
    volume_m3: float = Field(..., gt=0, description="Volume in cubic metres")


TOOL_MODELS = {
    "search_evidence": SearchEvidenceIn,
    "get_claims": ClaimsIn,
    "estimate": EstimateIn,
    "haul_force": HaulForceIn,
    "carbon": CarbonIn,
}


# ---------------------------------------------------------------------------------------------
# Data loading (small files, so we just read them when asked)

def load_carbon_factors() -> dict[str, dict]:
    factors = {}
    with open(CARBON_CSV, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            factors[row["material"]] = {
                "kgco2e_per_kg": float(row["kgco2e_per_kg"]),
                "density_kg_per_m3": float(row["density_kg_per_m3"]),
                "kgco2e_per_m3": float(row["kgco2e_per_m3"]),
                "source": row["source"],
            }
    return factors


def load_presets() -> dict:
    presets = json.loads(PRESETS_PATH.read_text(encoding="utf-8"))
    return {site: preset for site, preset in presets.items() if not site.startswith("_")}


def load_verified_claims() -> tuple[list[dict], bool]:
    """(claims, is_fallback). Falls back to the contract example until real claims land."""
    claims = []
    if VERIFIED_CLAIMS.exists():
        for line in VERIFIED_CLAIMS.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            claim = json.loads(line)
            # the chat may only cite verified claims, so drafts never leave this endpoint
            if claim.get("status") == "verified":
                claims.append(claim)
    if claims:
        return claims, False
    example = json.loads((EXAMPLES_DIR / "claim.json").read_text(encoding="utf-8"))
    return [example], True


def normalize_material(name: str) -> str:
    key = name.strip().lower()
    if key in MATERIAL_ALIASES:
        return MATERIAL_ALIASES[key]
    return key.replace(" ", "_").replace("-", "_")


# ---------------------------------------------------------------------------------------------
# The maths. Plain functions so tests and agents can use them without HTTP.

def run_estimate(req: EstimateIn) -> dict:
    daily_output = req.crews * req.rate_per_crew_day
    years = req.quantity / (daily_output * req.days_per_year)
    people = req.crews * req.crew_size
    person_days = people * req.days_per_year * years
    return {
        "years": round(years, 2),
        "people": _tidy_number(people),
        "person_days": int(round(person_days)),
        "assumptions": [
            f"Rate of {_tidy_number(req.rate_per_crew_day)} {req.unit} per crew-day is assumed",
            f"{_tidy_number(req.days_per_year)} working days per year is assumed",
            f"Crews of {_tidy_number(req.crew_size)} people working in parallel with no downtime between tasks",
            "Straight-line estimate: no ramp-up, weather losses or sequencing constraints",
        ],
    }


def run_haul_force(req: HaulForceIn) -> dict:
    theta = math.radians(req.slope_deg)
    force = req.mass_kg * GRAVITY * (math.sin(theta) + req.friction_coeff * math.cos(theta))
    # round first so float noise (18.000000001) doesn't add a phantom person
    people_needed = math.ceil(round(force / req.pull_per_person_n, 9))
    return {
        "force_n": round(force, 1),
        "force_kn": round(force / 1000, 2),
        "people_needed": people_needed,
        "assumptions": [
            f"Friction coefficient of {req.friction_coeff} is assumed",
            f"Sustained pull of {_tidy_number(req.pull_per_person_n)} N per person is assumed",
            f"g = {GRAVITY} m/s2, steady pull with no acceleration and no rope losses",
        ],
    }


def run_carbon(req: CarbonIn) -> dict | None:
    factors = load_carbon_factors()
    material = normalize_material(req.material)
    factor = factors.get(material)
    if factor is None:
        return None
    return {
        "material": material,
        "volume_m3": req.volume_m3,
        "kgco2e": round(req.volume_m3 * factor["kgco2e_per_m3"], 1),
        "factor_kgco2e_per_m3": factor["kgco2e_per_m3"],
        "source": factor["source"],
        "assumptions": [
            f"{factor['kgco2e_per_kg']} kgCO2e per kg x {_tidy_number(factor['density_kg_per_m3'])} kg/m3 density",
            "Cradle to gate only (A1 to A3): no transport, construction or end of life",
            "Modern industrial factor applied to the material, not a reconstruction of ancient production",
        ],
    }


def run_search(req: SearchEvidenceIn) -> list[dict]:
    from data.search import search_evidence
    return search_evidence(req.query, site=req.site, system=req.system, k=req.k)


def run_claims(req: ClaimsIn) -> tuple[list[dict], bool]:
    claims, is_fallback = load_verified_claims()
    out = []
    for claim in claims:
        if req.site and claim.get("site") != req.site.strip().lower():
            continue
        if req.system and claim.get("system") != req.system.strip().lower():
            continue
        out.append(claim)
    return out, is_fallback


def _tidy_number(value: float):
    """2.0 -> 2, 0.5 -> 0.5, so assumption text reads naturally."""
    if float(value).is_integer():
        return int(value)
    return value


# ---------------------------------------------------------------------------------------------
# App

@asynccontextmanager
async def lifespan(app):
    # the first search loads the vector index and embedding model, which takes 30 s or more.
    # Do it in the background at startup so the first /chat doesn't time out waiting for it.
    def warm():
        try:
            run_search(SearchEvidenceIn(query="warm up", k=1))
        except Exception as err:
            print(f"[tools] search warm-up failed: {type(err).__name__}: {err}", file=sys.stderr)

    threading.Thread(target=warm, daemon=True).start()
    yield


app = FastAPI(title="Stratum tools", version="1.0", lifespan=lifespan)

# the web app and the agents run on other ports, so let them in
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError):
    # Contract 3 wants {"detail": "..."} as a string, not FastAPI's list of error objects
    problems = []
    for err in exc.errors():
        where = ".".join(str(part) for part in err.get("loc", []) if part != "body")
        problems.append(f"{where}: {err.get('msg')}" if where else err.get("msg", "invalid input"))
    return JSONResponse(status_code=422, content={"detail": "; ".join(problems) or "invalid input"})


@app.get("/health")
def health():
    return {"ok": True}


@app.get("/tools/presets")
def presets():
    return load_presets()


@app.post("/tools/search_evidence")
def search_evidence_endpoint(req: SearchEvidenceIn):
    try:
        results = run_search(req)
    except ValueError as err:  # unknown site or system
        return JSONResponse(status_code=400, content={"detail": str(err)})
    except FileNotFoundError as err:  # no passages.jsonl built yet
        return JSONResponse(status_code=503, content={"detail": str(err)})
    return {"results": results}


@app.post("/tools/claims")
def claims_endpoint(req: ClaimsIn):
    if req.site and req.site.strip().lower() not in SITES:
        return JSONResponse(status_code=400, content={"detail": f"unknown site {req.site!r}, use one of {SITES}"})
    claims, is_fallback = run_claims(req)
    response = JSONResponse(content={"claims": claims})
    if is_fallback:
        # no verified claims yet, so this is the contract example. The header says so without breaking the shape.
        response.headers["X-Stratum-Fallback"] = "contracts/examples/claim.json"
    return response


@app.post("/tools/estimate")
def estimate_endpoint(req: EstimateIn):
    return run_estimate(req)


@app.post("/tools/haul_force")
def haul_force_endpoint(req: HaulForceIn):
    return run_haul_force(req)


@app.post("/tools/carbon")
def carbon_endpoint(req: CarbonIn):
    result = run_carbon(req)
    if result is None:
        known = sorted(load_carbon_factors())
        return JSONResponse(status_code=404, content={"detail": "unknown material", "known_materials": known})
    return result


# ---------------------------------------------------------------------------------------------
# Tool definitions for the agents (Anthropic tool-use format)

def anthropic_tools() -> list[dict]:
    tools = []
    for name, model in TOOL_MODELS.items():
        schema = model.model_json_schema()
        schema.pop("title", None)
        description = schema.pop("description", "") or ""
        for prop in schema.get("properties", {}).values():
            prop.pop("title", None)
            # pydantic writes Optional[str] as anyOf [str, null]; flatten it so every model reads it easily
            if "anyOf" in prop:
                kinds = [part.get("type") for part in prop["anyOf"] if part.get("type") != "null"]
                if len(kinds) == 1:
                    prop.pop("anyOf")
                    prop["type"] = [kinds[0], "null"]
        if name == "carbon":
            description += " Known materials: " + ", ".join(sorted(load_carbon_factors())) + "."
        tools.append({"name": name, "description": description, "input_schema": schema})
    return tools


def export_tools() -> None:
    OPENAPI_TOOLS_PATH.write_text(json.dumps(anthropic_tools(), indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(TOOL_MODELS)} tool definitions to {OPENAPI_TOOLS_PATH}")


if __name__ == "__main__":
    if "--export" in sys.argv:
        export_tools()
    else:
        print(__doc__)
