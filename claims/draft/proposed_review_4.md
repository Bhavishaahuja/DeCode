# Proposed review, round 4 (Mohenjo-daro follow-up)

Targeted extraction for mohenjo workforce and finishes added 29 drafts (all 29 survived dedupe). 275 drafts are undecided in total. Verified before this round: 81. Reviewer: bhavisha.

Every accept and edit was dry-run through to_verified (continuing the current numbering) plus validate_claim(verified=True) with no problems. Nothing is written to claims/verified or decisions.jsonl yet.

## Coverage, before and after (before -> after)

| system | giza | uruk | mohenjo | qin |
|---|---|---|---|---|
| site_setout | 2 | 2 | 3 | 2 |
| materials_supply (required) | 2 | 2 | 2 | 2 |
| transport_lifting (required) | 2 | 2 | 2 | 2 |
| water_sanitation (required) | 2 | 2 | 4 | 3 |
| structure_form | 3 | 3 | 4 | 2 |
| finishes | 3 | 3 | 1 -> 2 | **0** |
| workforce (required) | 3 | 2 | 1 -> 2 | 3 |
| quality_control (required) | 2 | 2 | 3 | 2 |
| project_controls | 2 | 2 | 2 | 2 |
| **TOTAL** | 21 -> 21 | 20 -> 20 | 22 -> 24 | 18 -> 18 |

Bold cells are still under 2 after this round.

Verdicts: 0 accept, 2 edit then accept, 1 reject, 272 skip (left undecided).

## What the targeted extraction produced

| command | passages | drafts kept | usable for the gap |
|---|---|---|---|
| finishes, `--source asi_ar_1926_27 --limit 10` | 10 ASI excavation report passages | 10 | 1 (bare walls, few signs of mud plaster) |
| finishes, `--source asi_ar_1924_25 --limit 10` | 10 ASI excavation report passages | 10 | 0 (floors, foundations, wells, storage) |
| workforce, `--per-source 2 --limit 15` | 15 passages from 9 scholarly sources | 9 | 1 (infrastructure needed the labor of thousands) |

**No ASI report passage is tagged workforce**, so an ASI-only workforce run would find nothing, and the tags were not widened. The workforce command spread across the other sources instead, as written in proposed_review_3.md.

## Result for the two goals

- **mohenjo workforce: 1 -> 2.** The new claim is a scholar's reading (inferred) that Indus city infrastructure "required the labor of thousands". It sits alongside the verified drainage "feat of collective action" claim. Every other workforce draft describes craft producers (seal and bead makers), not builders, so they stay skipped like d18c9ed19.
- **mohenjo finishes: 1 -> 2.** The ASI 1926-27 excavator contrasts Ur's mud plastered, whitewashed walls with Mohenjo-daro, where there were "few indications of such mud plaster". That is a direct observation that the walls were left as bare burnt brick. The other finish drafts are about gold jewellery and seal glazes, not buildings.

## Judgment calls to check

- **Quote swap:** mohenjo-finishes-df849e81f's quote is widened to include the preceding sentence about Ur, an exact substring of the same passage (25 words), so the contrast in the statement is supported.
- **System move:** mohenjo-water_sanitation-d651896f3 goes to workforce. Its quote is about the labour behind the infrastructure. Its statement says "Indus cities" because the passage speaks of Indus communities in general, not Mohenjo-daro alone.
- **Worth keeping in mind:** mohenjo-quality_control-d22673ec9 (an ASI clay sealing "used to authenticate documents") is strong project_controls evidence, left as skip because project_controls is already at 2.


## mohenjo

### site_setout

- `mohenjo-site_setout-d13b98b44`: **skip**. Site preservation, not the build.
- `mohenjo-site_setout-d4977d84f`: **skip**. Site_setout already has 3.

### materials_supply

- `mohenjo-materials_supply-d580c4902`: **skip**. Weight standard; project_controls already has 2.
- `mohenjo-materials_supply-d6ff72556`: **skip**. Shell for ornaments, not building supply.
- `mohenjo-materials_supply-d72efed68`: **skip**. Glaze on seals, not on a building.
- `mohenjo-materials_supply-d54dac5f6`: **skip**. Burnt brick walls already covered by a verified claim.
- `mohenjo-materials_supply-df8c9ecbf`: **skip**. Seal making, not building supply.

### water_sanitation

- `mohenjo-water_sanitation-d3ce2b6f3`: **REJECT**. About soak pits at other Indus sites, not Mohenjo-daro.
- `mohenjo-water_sanitation-dfaa839dc`: **skip**. Water_sanitation already has 4.
- `mohenjo-water_sanitation-daafda49c`: **skip**. Duplicates verified drainage claims; its ornament line has OCR errors.
- `mohenjo-water_sanitation-dc005b9d9`: **skip**. Water_sanitation already has 4.
- `mohenjo-water_sanitation-d82626599`: **skip**. Overlaps verified drainage claims.

### structure_form

- `mohenjo-structure_form-da18f668f`: **skip**. Structure_form already has 4.
- `mohenjo-structure_form-d9e7e5223`: **skip**. Mortar choice is solid evidence but not a gap this round.
- `mohenjo-structure_form-d65889381`: **skip**. Structure_form already has 4.
- `mohenjo-structure_form-dc115b9a9`: **skip**. Structure_form already has 4.
- `mohenjo-structure_form-ded6828e0`: **skip**. Structure_form already has 4.
- `mohenjo-structure_form-d0120f694`: **skip**. Structure_form already has 4.
- `mohenjo-structure_form-d385a6c27`: **skip**. Brick bond pattern; structure_form already has 4.
- `mohenjo-structure_form-d976b8752`: **skip**. Storage use is the excavator's guess; not a gap.
- `mohenjo-structure_form-da8390b52`: **skip**. Same sentence as the accepted workforce claim; vaguer.

### finishes

- `mohenjo-finishes-df849e81f`: **EDIT then accept**. ASI excavator's direct observation of wall finish; widen quote so the Ur contrast is supported.
  - would become `mohenjo-finishes-002`, grade attested. Statement: "Unlike the walls at Ur, which were mud plastered and whitewashed, the excavators found few indications of mud plaster on the walls at Mohenjo-daro."
  - `quote` before: "There were few indications of such mud plaster  at Mohenjo-daro."
  - `quote` after: "At Ur, mud was also used for the plastering of walls which were also whitewashed. There were few indications of such mud plaster at Mohenjo-daro."
  - `statement` before: "Unlike houses at Ur which had mud plaster and whitewash on walls, Mohenjo-daro houses showed few signs of such plaster finishing."
  - `statement` after: "Unlike the walls at Ur, which were mud plastered and whitewashed, the excavators found few indications of mud plaster on the walls at Mohenjo-daro."
- `mohenjo-finishes-d928fe79f`: **skip**. Polish on gold jewellery, not on a building.

### workforce

- `mohenjo-water_sanitation-d651896f3` (moved from water_sanitation): **EDIT then accept**. About the labour force behind the infrastructure, so workforce; scholar's reading, inferred.
  - would become `mohenjo-workforce-002`, grade inferred. Statement: "Assembling and maintaining drainage systems and constructing massive city infrastructures in the Indus cities required the labor of thousands."
  - `system` before: "water_sanitation"
  - `system` after: "workforce"
  - `statement` before: "Indus urban centers built and maintained drainage systems as part of city infrastructure."
  - `statement` after: "Assembling and maintaining drainage systems and constructing massive city infrastructures in the Indus cities required the labor of thousands."
  - `modern_equivalent` before: "Installing and maintaining a municipal stormwater and sewage drainage network."
  - `modern_equivalent` after: "Planning the labour force for a large public works programme, including the crews that maintain it afterwards."
  - `lesson` before: "Ongoing maintenance of drainage systems must be planned for, not just initial construction."
  - `lesson` after: "City-scale infrastructure needs a labour plan for both construction and upkeep, not just a design."
- `mohenjo-workforce-d8cc9852e`: **skip**. Craft producers, not the builders (same as d18c9ed19).
- `mohenjo-workforce-d1088746d`: **skip**. Seal makers, not the builders (same as d18c9ed19).

### quality_control

- `mohenjo-quality_control-d22673ec9`: **skip**. Strong project_controls evidence (sealings authenticate documents); not a gap this round.
- `mohenjo-quality_control-db487b5a4`: **skip**. Quality_control already has 3.
- `mohenjo-quality_control-dafd9dd89`: **skip**. Quality_control already has 3.


## Older undecided drafts (246), still skipped

Not re-listed here; they are unchanged from earlier rounds and are in proposed_decisions_4.jsonl as skip.

