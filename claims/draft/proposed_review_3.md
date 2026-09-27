# Proposed review, round 3 (gap fill)

Fresh extraction for the four gaps added 27 drafts (26 after dedupe). 258 drafts are undecided in total. Verified before this round: 76. Reviewer: bhavisha.

Every accept and edit was dry-run through to_verified (continuing the current numbering) plus validate_claim(verified=True) with no problems. Nothing is written to claims/verified or decisions.jsonl yet.

## Coverage, before and after (before -> after)

| system | giza | uruk | mohenjo | qin |
|---|---|---|---|---|
| site_setout | 2 | 2 | 3 | 2 |
| materials_supply (required) | 2 | 2 | 2 | 2 |
| transport_lifting (required) | 2 | 2 | 2 | 2 |
| water_sanitation (required) | 2 | 2 | 4 | 3 |
| structure_form | 3 | 3 | 4 | 2 |
| finishes | 3 | 3 | **0 -> 1** | **0** |
| workforce (required) | 3 | 2 | **0 -> 1** | 3 |
| quality_control (required) | 2 | 2 | 3 | 2 |
| project_controls | 1 -> 2 | 2 | 0 -> 2 | 2 |
| **TOTAL** | 20 -> 21 | 20 -> 20 | 18 -> 22 | 18 -> 18 |

Bold cells are still under 2 after this round.

Verdicts: 1 accept, 4 edit then accept, 7 reject, 246 skip (left undecided).

## What the extraction produced

| gap | tagged passages | extracted now | drafts kept | usable |
|---|---|---|---|---|
| mohenjo workforce | 113 | 15 (11 from one 2020 paper, 4 from another) | 12 | 1 |
| mohenjo finishes | 95 | 15 (Wikipedia: pottery, Priest-King sculpture, seals) | 7 | 1 (moved from structure_form) |
| qin finishes | **25, all from one source (Geil 1909)** | 15 | 2 | 0 |
| mohenjo project_controls | 382 | 15 (Wikipedia Indus Valley page) | 6 | 2 (moved from quality_control) |

## Gaps the drafts can't honestly fill

- **qin finishes (0 after):** all 25 tagged passages come from Geil's 1909 travel book. His own footnote says "The walls built by the First Emperor and in the time of the Sungs have disappeared", so what he describes is later wall. There is no Qin finish evidence in the sources. Filling this needs a new source (for example excavation reports on Qin rammed earth or the Qin roads), not more extraction.
- **mohenjo workforce (1 after):** the 2020 paper is about craft workshops and social organisation. Only the drainage "feat of collective action" line is about building. `mohenjo-workforce-d18c9ed19` (craft production inside houses) is left as skip because craft workers are not the builders. Say "approved except add d18c9ed19" if you want it.
- **mohenjo finishes (1 after):** most finishes-tagged passages in the first 15 were about the Priest-King sculpture. The 36 finishes-tagged ASI excavation report passages were never reached, because `--limit 15` takes passages in file order. A targeted run should do better:

```powershell
python -m claims.extract --site mohenjo --system finishes --only-tagged --source asi_ar_1926_27 --limit 10
python -m claims.extract --site mohenjo --system finishes --only-tagged --source asi_ar_1924_25 --limit 10
python -m claims.extract --site mohenjo --system workforce --only-tagged --per-source 2 --limit 15
python -m claims.dedupe
```

## Judgment calls to check

- **System moves:** the ornamental brickwork building goes to finishes (the taxonomy lists facing bricks, carving and decoration). The standardised weights and seals and the chert weight series go from quality_control to project_controls, which the taxonomy defines to include standard units and administration. Mohenjo quality_control stays at 3.
- **Other-site rejects:** five passages filed under mohenjo are really about Harappa or Lothal, so they are rejected rather than left to resurface.
- **Giza project_controls** reaches 2 with the Wadi al-Jarf papyri (a primary text from Khufu's reign).


## giza

### project_controls

- `giza-project_controls-d91187cc5`: **ACCEPT**. Wadi al-Jarf papyri are primary records of supplying the workforce.
  - would become `giza-project_controls-002`, grade attested. Statement: "Papyrus records from Wadi al-Jarf dating to Khufu's 27th regnal year document the central administration sending food and supplies to sailors and wharf workers."


## mohenjo

### site_setout

- `mohenjo-site_setout-db475ab5d`: **skip**. Site setout already has 3.

### materials_supply

- `mohenjo-materials_supply-d52a038a4`: **REJECT**. About Harappa's bead stones, not Mohenjo-daro.
- `mohenjo-materials_supply-dc1390d08`: **skip**. Craft raw material, not building supply.
- `mohenjo-materials_supply-dac1c498f`: **skip**. Craft raw material, not building supply.
- `mohenjo-materials_supply-d23019033`: **skip**. Metal casting for a statuette, not building supply.
- `mohenjo-materials_supply-d838b15c7`: **skip**. Metal access in general, not building supply.

### water_sanitation

- `mohenjo-water_sanitation-d1167bdad`: **skip**. Drainage already has 4 verified claims; this one overlaps them.
- `mohenjo-water_sanitation-d2ba27a7e`: **skip**. Late decline, not the build; not a gap.
- `mohenjo-water_sanitation-ddcf51f6e`: **skip**. Ritual use of the Great Bath, not how it was built.

### structure_form

- `mohenjo-structure_form-d5ea36d96`: **REJECT**. About Harappa, not Mohenjo-daro.
- `mohenjo-structure_form-d53dfc699`: **skip**. Structure already has 4; house size trend is not a gap.
- `mohenjo-structure_form-d474b3ee0`: **skip**. Late decline, not the build; not a gap.
- `mohenjo-structure_form-dd4bc25ec`: **skip**. Structure already has 4; generic Indus ring stones.

### finishes

- `mohenjo-structure_form-dfe118301` (moved from structure_form): **EDIT then accept**. Ornamental brickwork and a wall niche are surface work, so finishes.
  - would become `mohenjo-finishes-001`, grade attested. Statement: "The seated soapstone Priest-King figure was found in a building distinguished by unusually ornamental brickwork and a wall niche."
  - `system` before: "structure_form"
  - `system` after: "finishes"
- `mohenjo-finishes-dd822bb1d`: **skip**. Finish on the Priest-King sculpture, not on a building.
- `mohenjo-finishes-d30a90e47`: **skip**. Finish on the Priest-King sculpture, not on a building.
- `mohenjo-finishes-d7d6f859c`: **skip**. Finish on the Priest-King sculpture, not on a building.

### workforce

- `mohenjo-workforce-db856d7d9`: **EDIT then accept**. Drainage built by many groups; trim to what the quote says.
  - would become `mohenjo-workforce-001`, grade inferred. Statement: "Mohenjo-daro's drainage system, serving most of its residences, was a considerable feat of collective action that reveals cooperation among many different urban groups."
  - `statement` before: "Operating and building Mohenjo-daro's drainage system required substantial labor and cooperation among many different urban groups."
  - `statement` after: "Mohenjo-daro's drainage system, serving most of its residences, was a considerable feat of collective action that reveals cooperation among many different urban groups."
- `mohenjo-workforce-d2a99a084`: **REJECT**. About Harappa, not Mohenjo-daro.
- `mohenjo-workforce-d18c9ed19`: **skip**. Craft workshops in houses, not the builders; add it if you want craft labour.

### quality_control

- `mohenjo-quality_control-dd99b28da`: **REJECT**. About a Lothal scale, not Mohenjo-daro.
- `mohenjo-quality_control-d982314e8`: **skip**. Quality control already has 3; seal sizes are not a gap.

### project_controls

- `mohenjo-quality_control-df8e1ad70` (moved from quality_control): **EDIT then accept**. Seals and standard units are administration; trim the city-wide claim.
  - would become `mohenjo-project_controls-001`, grade attested. Statement: "Mohenjo-daro had standardised weights and measures, and standardised seals and sealings."
  - `system` before: "quality_control"
  - `system` after: "project_controls"
  - `statement` before: "Mohenjo-daro had standardised weights and measures and standardised seals and sealings used across the city."
  - `statement` after: "Mohenjo-daro had standardised weights and measures, and standardised seals and sealings."
  - `modern_equivalent` before: "Standardized measurement units and certification stamps for quality assurance."
  - `modern_equivalent` after: "Standard units and stamped verification marks used to control and track goods on a project."
- `mohenjo-quality_control-d216dfe48` (moved from quality_control): **EDIT then accept**. Measured weight series is a standard unit; hexahedron detail not in quote.
  - would become `mohenjo-project_controls-002`, grade attested. Statement: "Indus chert weights followed a 5:2:1 ratio series from 0.05 to 500 units, each unit weighing approximately 28 grams."
  - `system` before: "quality_control"
  - `system` after: "project_controls"
  - `statement` before: "Indus artisans used hexahedron chert weights in a 5:2:1 ratio series from 0.05 to 500 units, with each unit weighing about 28 grams."
  - `statement` after: "Indus chert weights followed a 5:2:1 ratio series from 0.05 to 500 units, each unit weighing approximately 28 grams."
- `mohenjo-project_controls-dc23906a8`: **REJECT**. About Harappa, not Mohenjo-daro.


## qin

### materials_supply

- `qin-materials_supply-d373cf810`: **REJECT**. Vague later travel writing; says nothing specific about how Qin built.

### structure_form

- `qin-structure_form-df17706e5`: **REJECT**. Geil's own footnote says the Qin walls disappeared; these ramparts are later.


## Older undecided drafts (230), still skipped

Not re-listed here; they are unchanged from rounds 1 and 2 and are in proposed_decisions_3.jsonl as skip.

