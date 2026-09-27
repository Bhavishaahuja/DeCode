# Proposed review, round 2

Input: claims/draft/claims_deduped.jsonl, 265 undecided drafts (95 already decided in round 1). Verified before this round: 49. Reviewer: bhavisha.

Every accept and edit was dry-run through to_verified (continuing the current verified numbering) plus validate_claim(verified=True) with no problems. Nothing is written to claims/verified or decisions.jsonl yet.

## Coverage, before and after (before -> after)

| system | giza | uruk | mohenjo | qin |
|---|---|---|---|---|
| site_setout | 1 -> 2 | 0 -> 2 | 1 -> 3 | 0 -> 2 |
| materials_supply (required) | 2 | 2 | 2 | 2 |
| transport_lifting (required) | 2 | 2 | 2 | 2 |
| water_sanitation (required) | 2 | 2 | 4 | 3 |
| structure_form | 0 -> 3 | 1 -> 3 | 0 -> 4 | 0 -> 2 |
| finishes | 0 -> 3 | 0 -> 3 | **0** | **0** |
| workforce (required) | 3 | 2 | **0** | 3 |
| quality_control (required) | 2 | 2 | 3 | 2 |
| project_controls | **0 -> 1** | 1 -> 2 | **0** | 1 -> 2 |
| **TOTAL** | 12 -> 20 | 12 -> 20 | 12 -> 18 | 13 -> 18 |

Bold cells are still under 2 after this round.

Verdicts: 20 accept, 7 edit then accept, 5 reject, 233 skip (left undecided).

## Gaps the current drafts can't fill

No undecided drafts exist for these. Each has rule-tagged passages in data/passages.jsonl, so extraction should produce candidates:

| gap | after this round | tagged passages |
|---|---|---|
| mohenjo workforce (required) | 0 | 113 |
| mohenjo finishes | 0 | 95 |
| qin finishes | 0 | 25 |
| mohenjo project_controls | 0 | 382 |

Also still under 2: giza project_controls (1). One usable undecided draft exists (giza-project_controls-d91187cc5, Wadi al-Jarf supply papyri), but I left it as skip to keep Giza at 8. Say "approved except add d91187cc5" if you want it.

Suggested commands (PowerShell, from the repo root). extract appends to claims/draft/claims.jsonl, and dedupe keeps existing draft ids, so decisions already logged stay valid:

```powershell
python -m claims.extract --site mohenjo --system workforce --only-tagged --per-source 3 --limit 15
python -m claims.extract --site mohenjo --system finishes --only-tagged --per-source 3 --limit 15
python -m claims.extract --site qin --system finishes --only-tagged --per-source 3 --limit 15
python -m claims.extract --site mohenjo --system project_controls --only-tagged --per-source 3 --limit 15
python -m claims.extract --site giza --system project_controls --only-tagged --per-source 2 --limit 10
python -m claims.dedupe
```

Watch for this: in round 1 the only Mohenjo workforce drafts described the 1920s excavation crew. Workforce-tagged ASI passages may often be about excavation labour, so new drafts need the same check.

## Judgment calls to check

- **Duplicate of a verified claim:** qin-structure_form-de64d79b8 repeats the verified Qin local materials (rammed earth) claim, so it is rejected.
- **Grades left as drafted:** uruk-finishes-d398db25b and mohenjo-structure_form-dc32b8bb3 stay inferred. The rules only ask me to downgrade, so I did not upgrade either.
- **uruk-finishes-deb0f7c85** comes from a general Mesopotamian architecture passage, so "at Uruk" is removed from the statement.
- **giza-project_controls-dba263856** is rejected because the passage places the papyrus find at Wadi al-Jarf, while the statement says Giza.
- No system moves and no quote swaps this round.


## giza

### site_setout

- `giza-site_setout-d15eada33`: **ACCEPT**. Observed cut and fill of Khafre's base on the slope.
  - would become `giza-site_setout-002`, grade attested. Statement: "Builders cut the northwest corner of Khafre's pyramid 10 m into the rock subsoil while building up the southeast corner, to compensate for the plateau's slope."

### structure_form

- `giza-structure_form-d19920ab9`: **ACCEPT**. Observed stepped core courses with casing set against them.
  - would become `giza-structure_form-001`, grade attested. Statement: "The pyramid's body was built of large local limestone blocks laid in regular courses forming steps against which the casing blocks were set."
- `giza-structure_form-d497e21fd`: **ACCEPT**. Observed rock outcrop built into Khafre's core.
  - would become `giza-structure_form-002`, grade attested. Statement: "Khafre's pyramid incorporates a natural rock outcropping within its core, similar to the Great Pyramid."
- `giza-structure_form-d7d5466e6`: **EDIT then accept**. Petrie measurement; progressive decrease is context, not quote.
  - would become `giza-structure_form-003`, grade attested. Statement: "Petrie measured the lowest course of the Great Pyramid at 148 centimetres high, while courses near the summit barely exceed 50 centimetres."
  - `statement` before: "Block height and weight decreased progressively toward the top, with the lowest course measured at 148 centimetres high and upper courses barely exceeding 50 centimetres."
  - `statement` after: "Petrie measured the lowest course of the Great Pyramid at 148 centimetres high, while courses near the summit barely exceed 50 centimetres."

### finishes

- `giza-finishes-dc08b0321`: **ACCEPT**. Menkaure casing materials by course, physically observed.
  - would become `giza-finishes-001`, grade attested. Statement: "The lowest sixteen courses of casing, over 20 meters high, were red granite from Aswan, while the casing above this level up to the pyramidion was fine limestone."
- `giza-finishes-d7969bad0`: **ACCEPT**. Khafre casing materials, observed on the monument.
  - would become `giza-finishes-002`, grade attested. Statement: "The bottom course of casing stones on Khafre's pyramid was pink granite while the rest of the pyramid was cased in Tura limestone."
- `giza-finishes-d2a21e500`: **EDIT then accept**. Observed undressed casing where hidden; drop the G3-a label (number not in quote).
  - would become `giza-finishes-003`, grade attested. Statement: "The first casing course of Menkaure's largest queen's pyramid was red granite from Aswan, never dressed smooth on the east face where the temple's back wall covered it."
  - `statement` before: "The lowest casing course of the largest queen's pyramid (G3-a) at Giza was red granite from Aswan, left undressed on the east face where the temple wall covered it."
  - `statement` after: "The first casing course of Menkaure's largest queen's pyramid was red granite from Aswan, never dressed smooth on the east face where the temple's back wall covered it."

### project_controls

- `giza-project_controls-dd90bfe2a`: **ACCEPT**. Merer diary names the receiving points and their supervisor.
  - would become `giza-project_controls-001`, grade attested. Statement: "Stones at the pyramid were accepted at designated receiving points called She Akhet-Khufu and Ro-She Khufu, under the supervision of the vizier Ankhhaf."
- `giza-project_controls-dba263856`: **REJECT**. Papyrus was found at Wadi al-Jarf, not Giza; statement overreaches.

### giza skipped (74, left undecided)

- site_setout: `giza-site_setout-d35660a6c`, `giza-site_setout-d70a415aa`, `giza-site_setout-df226f3d4`, `giza-site_setout-df77258d0`, `giza-site_setout-db85401ff`, `giza-site_setout-da644435b`, `giza-site_setout-d09b22141`, `giza-site_setout-dac3b1b6a`, `giza-site_setout-dc1b0b7ca`, `giza-site_setout-dce876b30`, `giza-site_setout-d73b707fa`
- materials_supply: `giza-materials_supply-d5aa3a575`, `giza-materials_supply-d205333d9`, `giza-materials_supply-d3f7cf07f`, `giza-materials_supply-d84795dd9`, `giza-materials_supply-d5063dd0c`, `giza-materials_supply-d75a149d9`, `giza-materials_supply-d28dbb70b`, `giza-materials_supply-d0faa61bc`, `giza-materials_supply-d27877284`, `giza-materials_supply-d4b0250d0`, `giza-materials_supply-dac5ff8e9`, `giza-materials_supply-db7cd4de9`, `giza-materials_supply-dac9c30bf`, `giza-materials_supply-dd28b376e`, `giza-materials_supply-d00076592`, `giza-materials_supply-d7f26f2bb`, `giza-materials_supply-d2fa5571b`, `giza-materials_supply-d3d7f0156`, `giza-materials_supply-db1e65d5e`, `giza-materials_supply-d20ed2d8d`, `giza-materials_supply-d041d47eb`
- transport_lifting: `giza-transport_lifting-draft0001`, `giza-transport_lifting-db01f60e1`, `giza-transport_lifting-d4688582b`, `giza-transport_lifting-d42e4e5be`, `giza-transport_lifting-dee1c083b`, `giza-transport_lifting-d5a9df9a3`, `giza-transport_lifting-d4d23cbfe`, `giza-transport_lifting-d764661da`, `giza-transport_lifting-d95a703a4`, `giza-transport_lifting-dd1a8cd7c`, `giza-transport_lifting-d0d50827c`, `giza-transport_lifting-d5dfa2114`
- water_sanitation: `giza-water_sanitation-d2b12a14f`
- structure_form: `giza-structure_form-d5dd1a665`, `giza-structure_form-d136c28c3`, `giza-structure_form-dc2029bb1`, `giza-structure_form-d5bb8ce22`, `giza-structure_form-d0f7f5ce3`, `giza-structure_form-de25ddd23`, `giza-structure_form-dd9b21106`, `giza-structure_form-dcad83b49`, `giza-structure_form-de45959ae`, `giza-structure_form-d15e8065d`, `giza-structure_form-d8b67333c`, `giza-structure_form-d3d050744`
- finishes: `giza-finishes-df1554eb1`, `giza-finishes-d76b70563`, `giza-finishes-d2238283d`, `giza-finishes-deeb32019`, `giza-finishes-d7e8fd986`, `giza-finishes-d2f35c18a`
- workforce: `giza-workforce-draft0001`, `giza-workforce-d094d99ac`, `giza-workforce-d89a46e72`
- quality_control: `giza-quality_control-dcb4ef27e`, `giza-quality_control-d2471ea15`, `giza-quality_control-debb72c82`, `giza-quality_control-dc3b6a322`, `giza-quality_control-d19461710`
- project_controls: `giza-project_controls-d91187cc5`, `giza-project_controls-da485f148`, `giza-project_controls-d285f7a91`


## uruk

### site_setout

- `uruk-site_setout-d48c4f729`: **ACCEPT**. Surveying with ropes, attested in administrative texts.
  - would become `uruk-site_setout-001`, grade attested. Statement: "Surveying of fields in Mesopotamia was done using ropes, known as EŠ.GID in Sumerian, eblu(m) in Babylonian Akkadian, and ašalu in Assyrian Akkadian."
- `uruk-site_setout-d8c09a7a0`: **ACCEPT**. Field layout along canals, correctly inferred.
  - would become `uruk-site_setout-002`, grade inferred. Statement: "In irrigated southern Mesopotamia, field widths were reduced and lengths extended so more fields could access canal water, producing long narrow rectangular plots."

### structure_form

- `uruk-structure_form-dbae312bb`: **ACCEPT**. Excavated Limestone Temple on a rammed-earth podium.
  - would become `uruk-structure_form-003`, grade attested. Statement: "The Limestone Temple at Uruk was built on a rammed-earth podium about 2 meters high."
- `uruk-structure_form-d463fa9d2`: **EDIT then accept**. Excavated build phases; Uruk period timing is not in the quote.
  - would become `uruk-structure_form-002`, grade attested. Statement: "The Anu ziggurat was expanded through 14 phases of construction, labeled L to A₃."
  - `statement` before: "The Anu ziggurat was built up through 14 distinct construction phases labeled L to A3 over the Uruk period."
  - `statement` after: "The Anu ziggurat was expanded through 14 phases of construction, labeled L to A₃."

### finishes

- `uruk-finishes-d398db25b`: **ACCEPT**. White Temple gypsum plaster; inferred is a safe grade.
  - would become `uruk-finishes-002`, grade inferred. Statement: "The White Temple atop the Anu ziggurat was covered in gypsum plaster that reflected sunlight."
- `uruk-finishes-da9985d18`: **ACCEPT**. Excavated cone mosaic benches of the Great Court.
  - would become `uruk-finishes-003`, grade attested. Statement: "The Great Court was a sunken courtyard surrounded by two tiers of benches covered in cone mosaic decoration."
- `uruk-finishes-deb0f7c85`: **EDIT then accept**. General Mesopotamian practice; quote does not say Uruk.
  - would become `uruk-finishes-001`, grade inferred. Statement: "Civic buildings slowed decay with cones of coloured stone, terracotta panels and clay nails driven into the mudbrick, forming a protective sheath that decorated the facade."
  - `statement` before: "Civic buildings at Uruk used cones of colored stone, terracotta panels, and clay nails driven into adobe brick to create a protective decorative facade sheath."
  - `statement` after: "Civic buildings slowed decay with cones of coloured stone, terracotta panels and clay nails driven into the mudbrick, forming a protective sheath that decorated the facade."

### quality_control

- `uruk-quality_control-d7cdc222f`: **REJECT**. Duplicate of accepted rope surveying claim.

### project_controls

- `uruk-project_controls-d492e4e60`: **EDIT then accept**. Attested counting systems; goods categories are not in the quote.
  - would become `uruk-project_controls-002`, grade attested. Statement: "Studies of protocuneiform indicate that twelve separate counting systems were used in Uruk IV-III."
  - `statement` before: "Protocuneiform records from Uruk IV-III show twelve separate counting systems used to track different categories of goods such as slaves, animals, fish, cereal, and rations."
  - `statement` after: "Studies of protocuneiform indicate that twelve separate counting systems were used in Uruk IV-III."

### uruk skipped (61, left undecided)

- site_setout: `uruk-site_setout-df9e4e166`, `uruk-site_setout-d49d8ba9a`, `uruk-site_setout-daab282f4`, `uruk-site_setout-d90172a87`, `uruk-site_setout-db056c3a8`, `uruk-site_setout-d5b7f6b1f`, `uruk-site_setout-dfd6a79df`
- materials_supply: `uruk-materials_supply-d2ed256d8`, `uruk-materials_supply-d21e386e9`, `uruk-materials_supply-df560c09a`, `uruk-materials_supply-dca4de51f`, `uruk-materials_supply-db4bd8eba`, `uruk-materials_supply-d5926d7b0`, `uruk-materials_supply-de128536b`, `uruk-materials_supply-d3ff33c2c`, `uruk-materials_supply-d073049e0`, `uruk-materials_supply-d88638f2a`, `uruk-materials_supply-deb457855`, `uruk-materials_supply-dff393bbb`, `uruk-materials_supply-dc698171f`, `uruk-materials_supply-d39850178`
- transport_lifting: `uruk-transport_lifting-d679e95e7`, `uruk-transport_lifting-d8496c227`
- water_sanitation: `uruk-water_sanitation-d59c399c7`, `uruk-water_sanitation-dc3b4b5ca`, `uruk-water_sanitation-d5344df51`, `uruk-water_sanitation-dcc831f9e`, `uruk-water_sanitation-da476f25e`, `uruk-water_sanitation-d42fbacb0`
- structure_form: `uruk-structure_form-draft0001`, `uruk-structure_form-de9a907cc`, `uruk-structure_form-d521305b0`, `uruk-structure_form-d9c6692dc`, `uruk-structure_form-d886e29a6`, `uruk-structure_form-db8fe1765`, `uruk-structure_form-d80911e06`, `uruk-structure_form-d097cf945`, `uruk-structure_form-d55efcc94`, `uruk-structure_form-ddc2518c6`, `uruk-structure_form-d07665951`, `uruk-structure_form-d0f6925ca`, `uruk-structure_form-d7173130f`, `uruk-structure_form-ded5c6521`, `uruk-structure_form-df0d6a566`, `uruk-structure_form-dac631e67`, `uruk-structure_form-d706f3eb0`, `uruk-structure_form-d9ac7f30d`, `uruk-structure_form-dacafb06a`, `uruk-structure_form-d0ef9fdef`
- finishes: `uruk-finishes-d9a4c09ba`
- workforce: `uruk-workforce-d2060648f`, `uruk-workforce-d51ee1a03`
- quality_control: `uruk-quality_control-d3ddd5c2b`, `uruk-quality_control-d45ac4bbf`
- project_controls: `uruk-project_controls-draft0001`, `uruk-project_controls-db29b80d2`, `uruk-project_controls-d8d7d2e64`, `uruk-project_controls-dcaaeb7f2`, `uruk-project_controls-dc11680d2`, `uruk-project_controls-d686e629f`, `uruk-project_controls-d9cb71cb9`


## mohenjo

### site_setout

- `mohenjo-site_setout-db8c4fc65`: **ACCEPT**. Flood platforms and Wheeler's rebuild theory, correctly debated.
  - would become `mohenjo-site_setout-002`, grade debated. Statement: "The city built large platforms, possibly intended as flood defense, and may have been flooded and rebuilt on the same location as many as six times."
- `mohenjo-site_setout-d84762daa`: **ACCEPT**. Datum-recorded phases show houses aligning to streets over time.
  - would become `mohenjo-site_setout-003`, grade attested. Statement: "Excavators used datums to record the depth of building periods across part of Mohenjo-daro, and residences became more uniform and more closely aligned with the city's streets over time."

### structure_form

- `mohenjo-structure_form-d672d9819`: **ACCEPT**. Identified wall foundations and fortifications.
  - would become `mohenjo-structure_form-001`, grade attested. Statement: "Mohenjo-daro was surrounded by mud-brick walls whose foundations have been identified by archaeologists, along with guard towers to the west and defensive fortifications to the south."
- `mohenjo-structure_form-d8e6d7af7`: **ACCEPT**. ASI test cuts proved a solid brick wall.
  - would become `mohenjo-structure_form-002`, grade attested. Statement: "A massive wall at the western end of the structure was found to be up to 28 feet thick and consisted of solid brickwork throughout, with no chambers or filling."
- `mohenjo-structure_form-dc32b8bb3`: **ACCEPT**. Excavator's load reasoning from piers, correctly inferred.
  - would become `mohenjo-structure_form-003`, grade inferred. Statement: "The heavy brick piers in the pillared hall implied that the roof they supported was very heavy, requiring beams over 14 feet long."
- `mohenjo-structure_form-dab5f730f`: **ACCEPT**. Excavated houses found on massive foundation platforms.
  - would become `mohenjo-structure_form-004`, grade attested. Statement: "Excavated rectilinear houses at Mohenjo-daro were found to rest upon massive foundation platforms."

### mohenjo skipped (63, left undecided)

- site_setout: `mohenjo-site_setout-da8ebd03d`, `mohenjo-site_setout-d16113538`, `mohenjo-site_setout-d4e14340d`, `mohenjo-site_setout-da60c2228`, `mohenjo-site_setout-dd6d64153`, `mohenjo-site_setout-da27243d9`, `mohenjo-site_setout-db9ed47a4`
- materials_supply: `mohenjo-materials_supply-d4047bd2d`, `mohenjo-materials_supply-d551e6094`, `mohenjo-materials_supply-d9c79767d`, `mohenjo-materials_supply-db68da426`, `mohenjo-materials_supply-d90eda020`, `mohenjo-materials_supply-dbac06b61`
- transport_lifting: `mohenjo-transport_lifting-d597cdc0a`, `mohenjo-transport_lifting-d0b9c81ac`
- water_sanitation: `mohenjo-water_sanitation-d4ae4c970`, `mohenjo-water_sanitation-da72053d7`, `mohenjo-water_sanitation-d45626d0f`, `mohenjo-water_sanitation-d6d5aba76`, `mohenjo-water_sanitation-daab8f4f6`, `mohenjo-water_sanitation-d8d7467d6`, `mohenjo-water_sanitation-deb6aaed0`, `mohenjo-water_sanitation-dc8b6c213`, `mohenjo-water_sanitation-d816cf132`, `mohenjo-water_sanitation-d193c62a6`, `mohenjo-water_sanitation-d019b8c03`, `mohenjo-water_sanitation-d6e201074`, `mohenjo-water_sanitation-dd500073d`, `mohenjo-water_sanitation-d63156ec8`, `mohenjo-water_sanitation-d4f8b14a7`, `mohenjo-water_sanitation-d727bef46`, `mohenjo-water_sanitation-de8e62bb3`, `mohenjo-water_sanitation-d5ea0fb7e`, `mohenjo-water_sanitation-d2f804059`, `mohenjo-water_sanitation-d694d06fd`, `mohenjo-water_sanitation-d12004757`, `mohenjo-water_sanitation-d41e848e7`, `mohenjo-water_sanitation-d477921f7`, `mohenjo-water_sanitation-d52765d49`, `mohenjo-water_sanitation-d03837327`, `mohenjo-water_sanitation-d4172f0fc`, `mohenjo-water_sanitation-dbffd02a9`, `mohenjo-water_sanitation-d99b0fa19`, `mohenjo-water_sanitation-d1b0ff1dc`, `mohenjo-water_sanitation-d5963bb2d`, `mohenjo-water_sanitation-de4987cd3`, `mohenjo-water_sanitation-d0c7ee246`
- structure_form: `mohenjo-structure_form-d5552a39d`, `mohenjo-structure_form-d144f3d8b`, `mohenjo-structure_form-dde9aac8a`, `mohenjo-structure_form-da6865ad8`, `mohenjo-structure_form-daf6a531c`, `mohenjo-structure_form-d67fa939b`, `mohenjo-structure_form-d4a0e976c`, `mohenjo-structure_form-d8984282b`
- quality_control: `mohenjo-quality_control-d02f9f849`, `mohenjo-quality_control-dae0f28f4`, `mohenjo-quality_control-d556c21d7`, `mohenjo-quality_control-d3c7e1e32`, `mohenjo-quality_control-db40a9eee`, `mohenjo-quality_control-d7ba66974`, `mohenjo-quality_control-d6f11c773`, `mohenjo-quality_control-df8e1ad70`


## qin

### site_setout

- `qin-site_setout-d5afe3381`: **ACCEPT**. Li Bing's site investigation before building Dujiangyan.
  - would become `qin-site_setout-002`, grade debated. Statement: "Qin hydrologist Li Bing investigated the Min River flooding problem and identified that fast spring meltwater from mountains overwhelmed a slow, silted stretch downstream."
- `qin-site_setout-d5cfdee21`: **EDIT then accept**. Contour canal; the routing explanation is not in the quote.
  - would become `qin-site_setout-001`, grade debated. Statement: "The Lingqu is the oldest contour canal in the world, and it receives its water from the Xiang."
  - `statement` before: "The Lingqu was built as a contour canal, following the natural land contours to route water between the two rivers."
  - `statement` after: "The Lingqu is the oldest contour canal in the world, and it receives its water from the Xiang."
- `qin-site_setout-dd292c08b`: **REJECT**. Quote does not mention the Yellow River or Ordos route.

### structure_form

- `qin-structure_form-d360c5e70`: **ACCEPT**. Qin joined and strengthened earlier walls, debated is fair.
  - would become `qin-structure_form-001`, grade debated. Statement: "The Qin northern border fortification project joined and strengthened existing walls built by feudal lords to form the base of the later Great Wall."
- `qin-structure_form-d6377c34f`: **ACCEPT**. Stone or rammed earth in board frames, debated is fair.
  - would become `qin-structure_form-002`, grade debated. Statement: "Warring States period border walls, including those built by Qin, were made mostly of stone or of stamped earth and gravel rammed between board frames."
- `qin-structure_form-de64d79b8`: **REJECT**. Duplicate of verified Qin local materials claim.
- `qin-structure_form-dfad8c8fa`: **REJECT**. Duplicate of accepted claim on joining existing walls.

### project_controls

- `qin-project_controls-dfdddc982`: **EDIT then accept**. Population registration; century is not in the quote.
  - would become `qin-project_controls-002`, grade debated. Statement: "The Qin state introduced a registration system for its population, first listing individuals and later tracking entire households."
  - `statement` before: "The Qin state introduced a population registration system in the 4th century BC that tracked individuals and later entire households."
  - `statement` after: "The Qin state introduced a registration system for its population, first listing individuals and later tracking entire households."

### qin skipped (35, left undecided)

- site_setout: `qin-site_setout-d7ad4ce16`
- materials_supply: `qin-materials_supply-d487f94fd`, `qin-materials_supply-dda232b6d`, `qin-materials_supply-d0be85d63`, `qin-materials_supply-d9613d11f`, `qin-materials_supply-d6dfd15dc`
- water_sanitation: `qin-water_sanitation-d62f163a1`, `qin-water_sanitation-d443ce3a6`, `qin-water_sanitation-de770c87c`, `qin-water_sanitation-d6c85e72c`, `qin-water_sanitation-dc8fa4306`, `qin-water_sanitation-d551738f9`, `qin-water_sanitation-dd91e3514`, `qin-water_sanitation-d23d6774b`, `qin-water_sanitation-d2e48be11`, `qin-water_sanitation-da7f4514f`, `qin-water_sanitation-d10d19d28`, `qin-water_sanitation-d0961c3e0`, `qin-water_sanitation-d58f018c8`
- structure_form: `qin-structure_form-d9108c87d`
- workforce: `qin-workforce-d4f794397`, `qin-workforce-df13ab7d7`, `qin-workforce-d3f699daa`, `qin-workforce-d495146e2`, `qin-workforce-d940ac14b`, `qin-workforce-d28bd1c2f`, `qin-workforce-d2eec398c`, `qin-workforce-d0d4c0c26`, `qin-workforce-d7f030229`, `qin-workforce-da0a9a3b2`
- quality_control: `qin-quality_control-d53f54c59`
- project_controls: `qin-project_controls-dd7f97a6a`, `qin-project_controls-d1883a4b0`, `qin-project_controls-d49ea2f5f`, `qin-project_controls-d6bbbb0f2`

