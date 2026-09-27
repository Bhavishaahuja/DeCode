# DeCode: Shared Context (Project Instructions)

Every chat in this project starts from this file. Each teammate then pastes their own role prompt (Dev 1 to Dev 5) as the first message. When a role prompt says "the shared context," "the schema," or "the contract," it means this file. If this file and a role prompt disagree, this file wins; flag the conflict to the team instead of guessing.

## What DeCode is

DeCode reverse-engineers ancient megaprojects the way a contractor would: read the evidence, break the build into systems a site team recognizes, put numbers on it, and turn it into a playbook for building it today. The existing web app covers 4 sites (Giza, Uruk, Mohenjo-daro, Qin walls and roads) with tabs for Teardown, Sequence, Crew estimator, and Build it now.

We're adding an agentic chat: ask a question in plain English, and a 7-layer agent pipeline retrieves real evidence, grades every claim, runs every number through a tool, gets checked by a critic, and answers with citations plus interactive cards that drive the existing app.

## Team and ownership

| Dev | Role | Folder | Port |
|---|---|---|---|
| 1 | Data engineer | /data | none (Python import) |
| 2 | Knowledge lead | /claims | none (files) |
| 3 | Tools and backend | /tools | 8001 |
| 4 | Agents, tests, repo setup, integration lead from hour 14 | /agents | 8000 |
| 5 | Frontend, demo, pitch | /web | 5173 (or any static server) |

Shared folder /contracts holds the schemas and example JSON. Nobody changes a contract alone. Propose the change in the team chat, Dev 4 approves, then update this file and /contracts/examples in the same commit.

## Repo layout

```
stratum/
  CLAUDE.md                 (this file)
  Makefile                  make data | tools | agents | web | all
  .env.example              ANTHROPIC_API_KEY=, TOOLS_URL=http://localhost:8001, CHAT_URL=http://localhost:8000
  contracts/
    examples/passage.json  claim.json  chat_response.json  tool_responses.json
  data/      sources.yaml  ingest.py  build.py  search.py  test_search.py  passages.jsonl  index/  README.md
  claims/    taxonomy.yaml  extract.py  dedupe.py  review.py  draft/  verified/claims.jsonl
             eval/questions.jsonl  prompts/archaeologist.md  prompts/engineer.md
  tools/     app.py  presets.json  openapi_tools.json  data/carbon_factors.csv  tests/
  agents/    mock_server.py  tools_client.py  pipeline.py  server.py  eval.py  prompts/  logs/
  web/       index.html  DEMO.md  replay/
```

## Conventions (everyone)

- Python 3.11+. Humanized code: natural variable names, casual comments, explicit loops over clever one-liners.
- No em dashes in any code comments, UI copy, prompts, or agent output. Use commas, periods, or parentheses. Put this rule in every agent system prompt.
- Model for LLM calls: claude-sonnet-5. API key only in .env, never committed.
- Site ids are always lowercase: giza, uruk, mohenjo, qin.
- Commit small and often, to your own folder. Pull before you push.
- Respect source licenses and site terms: record the license for every source, skip anything that forbids reuse, honor robots.txt, and never bulk-scrape a site whose terms prohibit it (use its official API or a public-domain copy instead).

## The 9 systems (shared labels)

Every passage tag, claim, and teardown row uses exactly these ids. Dev 2 expands them in claims/taxonomy.yaml with plain-language definitions, keywords, and MasterFormat/Uniclass headings.

| id | Plain name |
|---|---|
| site_setout | Site and setting-out (survey, alignment, leveling, foundations) |
| materials_supply | Materials and supply (quarrying, brick making, sourcing, logistics) |
| transport_lifting | Transport and lifting (sledges, ramps, hauling, raising) |
| water_sanitation | Water and sanitation (canals, drains, wells, flood control) |
| structure_form | Structure and form (walls, platforms, load paths, geometry) |
| finishes | Finishes (casing, plaster, cladding, decoration) |
| workforce | Workforce (crews, rations, housing, welfare, organization) |
| quality_control | Quality control (checking, tolerances, standards, measures) |
| project_controls | Project controls (records, accounting, scheduling, standard units) |

## Evidence grades

Claims use three grades, shown in the UI with the existing badges:

| Grade | Meaning | Badge |
|---|---|---|
| attested | Direct support from excavation evidence or a primary text | solid |
| debated | Supported, but scholars actively disagree | dashed |
| inferred | Our reasonable reading, not directly stated | dotted |

Estimator inputs use a separate two-way tag: attested or assumed. (The old web app used att/asm; Dev 5 maps those to the new words.)

Fringe rule: fringe ideas (aliens, lost high-tech civilizations, etc.) are never graded as claims. The agents explain what the evidence actually shows and say plainly that the fringe idea isn't supported.

## Contract 1: PASSAGE (Dev 1 produces, everyone reads)

One line per passage in data/passages.jsonl. search_evidence returns these plus score. Example: contracts/examples/passage.json

- source_type: excavation_report | primary_text | scholarship | reference | dataset
- locator: page, section, or line reference if known, else null
- tagged_by: rules | llm | none
- score only appears in search results, never in the jsonl file

Python interface (exact):

```python
from data.search import search_evidence
search_evidence(query: str, site: str | None = None, system: str | None = None, k: int = 8) -> list[dict]
```

## Contract 2: CLAIM (Dev 2 produces, Dev 3 serves, Dev 4 uses)

One line per claim in claims/verified/claims.jsonl. Example: contracts/examples/claim.json

Rules: at least 1 source, every passage_id must exist in passages.jsonl (or in Dev 2's hand-split set before hour 8), quote must appear verbatim in that passage.

## Contract 3: TOOL API (Dev 3 serves on :8001, Dev 4 calls)

All endpoints are POST, JSON in and out. Errors return a 4xx with {"detail": "..."}. Tool names in tools/openapi_tools.json are exactly: search_evidence, get_claims, estimate, haul_force, carbon. Examples for every endpoint: contracts/examples/tool_responses.json

| Endpoint | Tool name |
|---|---|
| POST /tools/search_evidence | search_evidence |
| POST /tools/claims | get_claims |
| POST /tools/estimate | estimate |
| POST /tools/haul_force | haul_force |
| POST /tools/carbon | carbon |

- estimate: years = quantity / (crews x rate_per_crew_day x days_per_year), people = crews x crew_size, person_days = people x days_per_year x years. All inputs must be > 0.
- haul_force: F = m x g x (sin(theta) + mu x cos(theta)), g = 9.81, people_needed = ceil(F / pull_per_person_n). The agent must state that friction_coeff and pull_per_person_n are assumptions.
- carbon: ICE factors are published per kg. Convert with a stated density and record both numbers in tools/data/carbon_factors.csv (columns: material, kgco2e_per_kg, density_kg_per_m3, kgco2e_per_m3, source). Unknown material returns 404 with known_materials.

Presets: tools/presets.json, one entry per site, fields matching the estimator card. Giza: 2,300,000 blocks (attested estimate); ancient 190 crews x 20 people, 2 blocks per crew-day, 300 days; modern 20 crews x 6 people, 80 blocks per crew-day, 300 days. Must reproduce about 20.2 years ancient, 4.8 years modern.

## Contract 4: CHAT API (Dev 4 serves on :8000, Dev 5 calls)

Request: POST /chat

```json
{"message": "How long would Giza take with modern cranes?",
 "history": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}],
 "site": "giza"}
```

history and site are optional. site is the site currently open in the UI, a hint for the router.

Response example: contracts/examples/chat_response.json

- intent: explain | compare | estimate | playbook | fringe
- clarifying_question: a string only when the router truly can't tell the site or goal; then cards is empty
- cards can be empty. Every number in answer_md or a card must come from a tool call recorded in the logs
- critic.passed = false means the answer still ships, with flags shown as "Needs review"
- Hard limit 60 seconds per request. On timeout: HTTP 504 with {"detail": "..."}

## The 7 agent layers (Dev 4 builds, Dev 2 writes L2 and L3 prompts)

| Layer | Agent | Job | Tools |
|---|---|---|---|
| L1 | Router | intent, sites, systems, one clarifying question max | none |
| L2 | Archaeologist | retrieve, cite, grade, never speculate unlabeled | search_evidence, get_claims |
| L3 | Engineer | map claims to systems, sanity-check physics, flag risks | search_evidence, get_claims, haul_force |
| L4 | Estimator | every number through a tool, never computes itself | estimate, haul_force, carbon |
| L5 | Builder | modern method, playbook steps, one "keep from the ancients" point | get_claims |
| L6 | Critic | reject unsourced claims, overstated grades, tool-less numbers, fringe-as-fact; one retry then flag | none |
| L7 | Presenter | short markdown answer plus cards in the contract format | none |

L2, L3, and L4 run in parallel where possible.

## Timeline and hand-offs

| Hour | Who | What lands |
|---|---|---|
| 0 | Dev 4 | Repo layout, Makefile, .env.example, this file, contracts/examples committed |
| 2 | Dev 4 | Mock /chat returning contracts/examples/chat_response.json |
| 2 | Dev 3 | Stub tool endpoints running on :8001 |
| 8 | Dev 1 | search.py plus a small prebuilt index committed |
| 8 | Dev 3 | Real estimate, haul_force, carbon, plus openapi_tools.json |
| 10 | Dev 2 | First 10 verified claims per site |
| 10 | Dev 5 | Chat UI working on the mock server |
| 12 | Dev 4 | Real pipeline running |
| 14 | Dev 4 | First end-to-end answer; Dev 4 leads integration from here |
| 16 | Dev 2 | Full verified claim set, eval questions, L2/L3 prompts |
| 16 | Dev 5 | UI wired to the real API |
| after 16 | all | Eval to 80%+, fix, record replay responses, rehearse |

If you're blocked, build against contracts/examples and keep moving. Never wait.

## Definition of done (whole project)

- make all starts data build, tools on :8001, agents on :8000, and the web app.
- python -m data.test_search, pytest tools/tests, and python -m agents.eval all pass (eval at 80% or better).
- Every /chat response validates against Contract 4.
- The 3 demo questions in web/DEMO.md (one estimate, one compare, one fringe) work live and in replay mode, on desktop and phone widths.
