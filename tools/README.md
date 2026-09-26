# tools: the Stratum tool API (port 8001)

Contract 3 in CLAUDE.md, examples in `contracts/examples/tool_responses.json`. Every number the chat shows comes from one of these endpoints, never from the model.

```powershell
python -m uvicorn tools.app:app --port 8001 --reload     # or: make tools
python -m pytest tools/tests                            # 18 tests
python -m tools.app --export                            # rewrite openapi_tools.json after changing a model
```

Then open http://localhost:8001/docs to try every endpoint in the browser.

| tool name | endpoint | what it does |
|---|---|---|
| `search_evidence` | `POST /tools/search_evidence` | wraps `data.search.search_evidence`, returns `{"results": [PASSAGE + score]}` |
| `get_claims` | `POST /tools/claims` | verified claims from `claims/verified/claims.jsonl`, filtered by site and system |
| `estimate` | `POST /tools/estimate` | years, people, person-days from quantity, crews and rates |
| `haul_force` | `POST /tools/haul_force` | sledge pulling force and people needed |
| `carbon` | `POST /tools/carbon` | embodied carbon for a volume of material |

Extras for the web app: `GET /tools/presets` (the estimator presets) and `GET /health`.

## Rules the endpoints follow

* All tools are POST, JSON in and out. Errors are 4xx with `{"detail": "..."}` as a string (validation errors are 422, unknown site or system 400, no passages built yet 503).
* `get_claims` only returns claims with `status: verified`. Until `claims/verified/claims.jsonl` has any, it returns the contract example and sets the header `X-Stratum-Fallback`.
* `estimate`: `years = quantity / (crews x rate_per_crew_day x days_per_year)`, `people = crews x crew_size`, `person_days = people x days_per_year x years`. All inputs must be > 0.
* `haul_force`: `F = m x g x (sin(theta) + mu x cos(theta))`, g = 9.81, `people_needed = ceil(F / pull_per_person_n)`. Friction and pull per person are always listed as assumptions.
* `carbon`: unknown materials get a 404 with `known_materials`. Friendly names work (`fired brick`, `hangtu`).

## Files

| file | what |
|---|---|
| `app.py` | the FastAPI app, request models, and the maths as plain functions (`run_estimate`, `run_haul_force`, `run_carbon`) |
| `openapi_tools.json` | tool definitions in Anthropic tool-use format, generated from the models in `app.py` |
| `presets.json` | one estimator preset per site |
| `data/carbon_factors.csv` | material, kgco2e_per_kg, density_kg_per_m3, kgco2e_per_m3, source |
| `tests/test_app.py` | endpoint tests, including the Giza 20.2 vs 4.8 years check |

## Presets

Giza reproduces the CLAUDE.md reference: 2,300,000 blocks (attested), 190 crews of 20 at 2 blocks per crew-day for about 20.2 years, against 20 crane crews of 6 at 80 blocks per crane-day for about 4.8 years.

Uruk (city wall, about 9 km), Mohenjo-daro (fired bricks) and Qin (Straight Road, about 700 km) are marked `draft: true`. Their quantities and rates are round-number assumptions, all tagged `assumed`, so the estimator card works for every site. Swap in sourced numbers once a verified claim backs one up, and change the tag to `attested` only then.

## Carbon factors

| material | kgCO2e/kg | density kg/m3 | kgCO2e/m3 | source |
|---|---|---|---|---|
| limestone | 0.09 | 2180 | 196.2 | ICE v3 |
| granite | 0.70 | 2650 (typical, assumed) | 1855 | ICE v3 |
| marble | 0.13 | 2500 | 325 | ICE v3 |
| clay_brick | 0.213 | 1700 | 362.1 | ICE v3, clay bricks general |
| rammed_earth | 0.017 | 2000 (assumed) | 34 | Arenas and Shafique (not ICE), per m3 |

All are cradle to gate (A1 to A3). To add a material, add a row with both numbers and the source, then run `python -m tools.app --export` so the agents see it in the `carbon` tool description.
