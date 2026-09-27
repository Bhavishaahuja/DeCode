# Proposed review, round 1

Input: claims/draft/claims_deduped.jsonl (360 drafts, none decided yet). Reviewer: bhavisha.

Every accept and edit below was dry-run through to_verified plus validate_claim(verified=True) with no problems. Nothing has been written to claims/verified or decisions.jsonl yet.

## Coverage if approved

| system | giza | uruk | mohenjo | qin |
|---|---|---|---|---|
| site_setout | 1 | 0 | 1 | 0 |
| materials_supply (required) | 2 | 2 | 2 | 2 |
| transport_lifting (required) | 2 | 2 | 2 | 2 |
| water_sanitation (required) | 2 | 2 | 4 | 3 |
| structure_form | 0 | 1 | 0 | 0 |
| finishes | 0 | 0 | 0 | 0 |
| workforce (required) | 3 | 2 | **0** (short) | 3 |
| quality_control (required) | 2 | 2 | 3 | 2 |
| project_controls | 0 | 1 | 0 | 1 |
| **TOTAL** | 12 | 12 | 12 | 13 |

Verdicts: 28 accept, 21 edit then accept, 46 reject, 265 skip (left undecided).

### Gaps and judgment calls to check

- **Mohenjo workforce is 0.** The only two drafts describe the 1920s ASI excavation crew and wages, not the ancient builders, so I propose rejecting both. Fixing this needs new drafts (extract from the ASI reports or scholarship on Harappan labour).
- **Mohenjo and Uruk transport_lifting are thin.** Mohenjo: a ship amulet (attested object) and a hedged bullock cart line (inferred). Uruk: hedged ziggurat ramps (inferred) and solid wheels (debated). They meet the count, but none is strong builder evidence.
- **System moves:** Giza Khufu harbor to water_sanitation (the taxonomy lists harbours there); Uruk Riemchen/Patzen bricks and Mohenjo fired brick buildings to materials_supply (brick making); Qin earth volume matching to quality_control (it is a quantity check).
- **Quote swaps** (each is an exact substring of the same passage, 40 words max): giza-transport_lifting-d671b5142, uruk-quality_control-db9b6a2aa, mohenjo-quality_control-draft0001, qin-project_controls-de782d5e4.
- **Diodorus exception:** giza-workforce-dd39e0e29 is kept, debated, under workforce. All other Diodorus, Herodotus, Pliny and Sima Qian drafts are rejected.
- Most Qin and Uruk evidence comes from Wikipedia summaries. Accepted ones either describe physical remains, excavated texts (Shuihudi, Kushim tablet), or are graded debated or inferred.


## giza

### site_setout

- `giza-site_setout-defd146cb`: **ACCEPT**. Measured flatness of the leveled perimeter strip.
  - final grade: attested. Statement: "The strip leveled around the pyramid base perimeter was measured to be horizontal and flat to within 21 millimetres."
- `giza-site_setout-dbff0eb97`: **REJECT**. Duplicate of accepted leveling claim, vaguer wording.

### materials_supply

- `giza-materials_supply-d70e5fd29`: **ACCEPT**. Diary of Merer, primary text from the build.
  - final grade: attested. Statement: "The Diary of Merer, a papyrus discovered in 2013, records deliveries of limestone from Tura to Giza in year 27 of Khufu's reign."
- `giza-materials_supply-d1f85031d`: **ACCEPT**. Granite blocks physically in place, quarry origin known.
  - final grade: attested. Statement: "Granite blocks weighing 25 to 80 tonnes were transported over 900 km from Aswan to form the King's Chamber ceiling and relieving chambers above it."
- `giza-materials_supply-draft0001`: **REJECT**. Duplicate of accepted Merer diary claim.
- `giza-materials_supply-dffcf3d73`: **REJECT**. Duplicate of accepted Aswan granite claim.
- `giza-materials_supply-dc35f5620`: **REJECT**. Duplicate of accepted Merer diary claim.
- `giza-materials_supply-d154179f4`: **REJECT**. Relies on ancient writers' account of quarry sourcing.
- `giza-materials_supply-dd5231663`: **REJECT**. Duplicate of accepted Khufu harbor claim.
- `giza-materials_supply-d46228073`: **REJECT**. Duplicate of accepted Merer diary claim.
- `giza-materials_supply-d2baafc33`: **REJECT**. Duplicate of accepted Merer diary claim.

### transport_lifting

- `giza-transport_lifting-d800b9398`: **ACCEPT**. Petrie's own measured description of the excavated causeway.
  - final grade: attested. Statement: "The causeway linking the Granite Temple to the Second Pyramid temple was about 15 feet wide and over a quarter mile long, cut into sloping bedrock and paved with two layers of fine white limestone."
- `giza-transport_lifting-d671b5142`: **EDIT then accept**. Physical ramp evidence; swap quote so it supports the small-ramps point.
  - final grade: attested. Statement: "The archaeological record shows only small ramps and inclined causeways, not ramps that could have built even most of the monument."
  - `quote` before: "Archaeological evidence for the use of ramps has been found at the Great Pyramid of Giza and other pyramids."
  - `quote` after: "The archaeological record gives evidence of only small ramps and inclined causeways, not something that could have been used to construct even a majority of the monument."
  - `statement` before: "Archaeological evidence for ramps used to raise blocks has been found at the Great Pyramid of Giza and other pyramids, but only small ramps and inclined causeways are documented."
  - `statement` after: "The archaeological record shows only small ramps and inclined causeways, not ramps that could have built even most of the monument."
- `giza-transport_lifting-d102d2f9b`: **REJECT**. Diodorus account of ramps, a later writer.
- `giza-transport_lifting-ddb066a21`: **REJECT**. Diodorus account of ramps, a later writer.
- `giza-transport_lifting-d117d7cfb`: **REJECT**. Pliny account of lifting methods, a later writer.
- `giza-transport_lifting-d7bfe730b`: **REJECT**. Diodorus account of ramps, a later writer.
- `giza-transport_lifting-d8c00bee1`: **REJECT**. Herodotus account of levers, a later writer.
- `giza-transport_lifting-d4eb908c4`: **REJECT**. Herodotus account of the causeway, a later writer.

### water_sanitation

- `giza-water_sanitation-d24d0f80e`: **ACCEPT**. Petrie directly observed drains cut into surviving paving.
  - final grade: attested. Statement: "Surviving paving blocks from the causeway have a shallow drain cut into them on the upper side of the lower paving layer."
- `giza-materials_supply-d5a39abe4` (moved from materials_supply): **EDIT then accept**. Sediment core evidence; taxonomy puts harbours in water_sanitation; trim overreach.
  - final grade: debated. Statement: "Sediment cores from the Giza floodplain show deposits consistent with an Old Kingdom port, known as Khufu's harbor."
  - `system` before: "materials_supply"
  - `system` after: "water_sanitation"
  - `statement` before: "Sediment cores from the Giza floodplain show deposits consistent with an Old Kingdom Nile-connected harbor that likely allowed stones and supplies to be transported to the pyramid complex."
  - `statement` after: "Sediment cores from the Giza floodplain show deposits consistent with an Old Kingdom port, known as Khufu's harbor."
- `giza-water_sanitation-df5813909`: **REJECT**. Pliny hearsay, quote says it is thought.
- `giza-water_sanitation-dd71b8adf`: **REJECT**. Herodotus account of a Nile channel, a later writer.
- `giza-water_sanitation-d6f629179`: **REJECT**. Sphinx water erosion dating idea is fringe.
- `giza-water_sanitation-dc3b6b8c7`: **REJECT**. Ventilation channels, not water; quote does not support statement.

### structure_form

- `giza-structure_form-d9d0289c1`: **REJECT**. Quote does not mention two construction phases.

### finishes

- `giza-finishes-df8761cd3`: **REJECT**. Diodorus account, a later writer.

### workforce

- `giza-workforce-d0e0d9a01`: **ACCEPT**. Gang graffiti observed in the relieving chambers.
  - final grade: attested. Statement: "Construction gangs building the Great Pyramid marked stone blocks with painted graffiti naming their gang and incorporating the pharaoh's name."
- `giza-workforce-dca87603d`: **ACCEPT**. Excavated workers' settlement at Heit el-Ghurab.
  - final grade: attested. Statement: "The Heit el-Ghurab settlement south of the Sphinx included bakeries, working-class and elite housing, and administrative buildings supporting the Giza workforce."
- `giza-workforce-dd39e0e29`: **EDIT then accept**. The one allowed Diodorus claim; name him explicitly.
  - final grade: debated. Statement: "Diodorus Siculus, a Greek historian writing long after the build, estimated that 360,000 workers built the Great Pyramid over 20 years."
  - `statement` before: "A later Greek historian estimated that 360,000 workers built the Great Pyramid over a period of 20 years."
  - `statement` after: "Diodorus Siculus, a Greek historian writing long after the build, estimated that 360,000 workers built the Great Pyramid over 20 years."
- `giza-workforce-d3373fff5`: **REJECT**. Duplicate of accepted gang graffiti claim.
- `giza-workforce-d805710bb`: **REJECT**. Duplicate of accepted gang graffiti claim.
- `giza-workforce-d00a2d31f`: **REJECT**. Herodotus workforce figure, a later writer.

### quality_control

- `giza-quality_control-d36930c10`: **ACCEPT**. Survey measurement of the built base.
  - final grade: attested. Statement: "The pyramid's base sides had an average error of only 58 millimetres in length and the base was squared to a mean corner error of only 12 seconds of arc."
- `giza-quality_control-d89d4fde9`: **EDIT then accept**. Measured joints; core block remark is not in the quote.
  - final grade: attested. Statement: "Many casing stones and inner chamber blocks of the Great Pyramid fit together with joints averaging only 0.5 millimetres wide."
  - `statement` before: "The casing stones and inner chamber blocks fit together with joints averaging only 0.5 millimetres wide, while core blocks were only roughly shaped."
  - `statement` after: "Many casing stones and inner chamber blocks of the Great Pyramid fit together with joints averaging only 0.5 millimetres wide."
  - `lesson` before: "Reserve tight tolerances for visible finish surfaces and allow looser fits in hidden structural fill to save time and cost."
  - `lesson` after: "Put the tightest tolerances on the faces and joints that matter most, like casing and chamber linings."

### project_controls

- `giza-project_controls-d7cc3c59a`: **REJECT**. Duplicate of accepted Merer diary claim.

### giza skipped (83, left undecided)

- site_setout: `giza-site_setout-d35660a6c`, `giza-site_setout-d70a415aa`, `giza-site_setout-d15eada33`, `giza-site_setout-df226f3d4`, `giza-site_setout-df77258d0`, `giza-site_setout-db85401ff`, `giza-site_setout-da644435b`, `giza-site_setout-d09b22141`, `giza-site_setout-dac3b1b6a`, `giza-site_setout-dc1b0b7ca`, `giza-site_setout-dce876b30`, `giza-site_setout-d73b707fa`
- materials_supply: `giza-materials_supply-d5aa3a575`, `giza-materials_supply-d205333d9`, `giza-materials_supply-d3f7cf07f`, `giza-materials_supply-d84795dd9`, `giza-materials_supply-d5063dd0c`, `giza-materials_supply-d75a149d9`, `giza-materials_supply-d28dbb70b`, `giza-materials_supply-d0faa61bc`, `giza-materials_supply-d27877284`, `giza-materials_supply-d4b0250d0`, `giza-materials_supply-dac5ff8e9`, `giza-materials_supply-db7cd4de9`, `giza-materials_supply-dac9c30bf`, `giza-materials_supply-dd28b376e`, `giza-materials_supply-d00076592`, `giza-materials_supply-d7f26f2bb`, `giza-materials_supply-d2fa5571b`, `giza-materials_supply-d3d7f0156`, `giza-materials_supply-db1e65d5e`, `giza-materials_supply-d20ed2d8d`, `giza-materials_supply-d041d47eb`
- transport_lifting: `giza-transport_lifting-draft0001`, `giza-transport_lifting-db01f60e1`, `giza-transport_lifting-d4688582b`, `giza-transport_lifting-d42e4e5be`, `giza-transport_lifting-dee1c083b`, `giza-transport_lifting-d5a9df9a3`, `giza-transport_lifting-d4d23cbfe`, `giza-transport_lifting-d764661da`, `giza-transport_lifting-d95a703a4`, `giza-transport_lifting-dd1a8cd7c`, `giza-transport_lifting-d0d50827c`, `giza-transport_lifting-d5dfa2114`
- water_sanitation: `giza-water_sanitation-d2b12a14f`
- structure_form: `giza-structure_form-d5dd1a665`, `giza-structure_form-d136c28c3`, `giza-structure_form-dc2029bb1`, `giza-structure_form-d5bb8ce22`, `giza-structure_form-d19920ab9`, `giza-structure_form-d0f7f5ce3`, `giza-structure_form-d497e21fd`, `giza-structure_form-de25ddd23`, `giza-structure_form-dd9b21106`, `giza-structure_form-d7d5466e6`, `giza-structure_form-dcad83b49`, `giza-structure_form-de45959ae`, `giza-structure_form-d15e8065d`, `giza-structure_form-d8b67333c`, `giza-structure_form-d3d050744`
- finishes: `giza-finishes-df1554eb1`, `giza-finishes-dc08b0321`, `giza-finishes-d76b70563`, `giza-finishes-d2238283d`, `giza-finishes-d7969bad0`, `giza-finishes-deeb32019`, `giza-finishes-d2a21e500`, `giza-finishes-d7e8fd986`, `giza-finishes-d2f35c18a`
- workforce: `giza-workforce-draft0001`, `giza-workforce-d094d99ac`, `giza-workforce-d89a46e72`
- quality_control: `giza-quality_control-dcb4ef27e`, `giza-quality_control-d2471ea15`, `giza-quality_control-debb72c82`, `giza-quality_control-dc3b6a322`, `giza-quality_control-d19461710`
- project_controls: `giza-project_controls-dd90bfe2a`, `giza-project_controls-d91187cc5`, `giza-project_controls-da485f148`, `giza-project_controls-d285f7a91`, `giza-project_controls-dba263856`


## uruk

### materials_supply

- `uruk-structure_form-dde8d5f27` (moved from structure_form): **EDIT then accept**. Brick making is materials_supply; niches detail is not in the quote.
  - final grade: attested. Statement: "Two standardized forms of molded mud-brick appear in Uruk buildings: small square Riemchen bricks that were easy to handle, and large Patzen bricks used for terraces."
  - `system` before: "structure_form"
  - `system` after: "materials_supply"
  - `statement` before: "Two standardized molded mud-brick forms were used at Uruk: small square Riemchen bricks for handling and decorative niches, and large Patzen bricks for building terraces."
  - `statement` after: "Two standardized forms of molded mud-brick appear in Uruk buildings: small square Riemchen bricks that were easy to handle, and large Patzen bricks used for terraces."
- `uruk-materials_supply-d8f916fb7`: **EDIT then accept**. Bitumen and gypsum use; quarry distance is not in the quote.
  - final grade: inferred. Statement: "Uruk period builders began to waterproof bricks with bitumen and to use gypsum as mortar."
  - `statement` before: "Builders at Uruk waterproofed bricks with bitumen and used gypsum as mortar, while limestone, gypsum and sandstone were quarried about 50 km west of Uruk."
  - `statement` after: "Uruk period builders began to waterproof bricks with bitumen and to use gypsum as mortar."
- `uruk-materials_supply-d49ec7a34`: **REJECT**. Duplicate of accepted standardized brick claim.
- `uruk-materials_supply-df51761a1`: **REJECT**. Duplicate of accepted Riemchen and Patzen brick claim.
- `uruk-materials_supply-dcc84cf89`: **REJECT**. Quote does not say sun-dried or less durable.
- `uruk-materials_supply-db1669886`: **REJECT**. Loftus describes a nineteenth century bridge, not the ancient build.

### transport_lifting

- `uruk-transport_lifting-d2d201e9f`: **EDIT then accept**. Only ramp evidence for Uruk; statement must keep the hedge.
  - final grade: inferred. Statement: "Access to the shrine on top of a ziggurat would have been by ramps on one side or by a spiral ramp from base to summit."
  - `statement` before: "Access to the shrine atop a ziggurat was provided by ramps on one side or by a spiral ramp from base to summit."
  - `statement` after: "Access to the shrine on top of a ziggurat would have been by ramps on one side or by a spiral ramp from base to summit."
- `uruk-transport_lifting-d81d2d8ba`: **EDIT then accept**. Wheel evidence for Uruk period vehicles; tighten wording to the quote.
  - final grade: debated. Statement: "Uruk period vehicle wheels were solid blocks, and spokes were not invented until about 2000 BC."
  - `statement` before: "Early Mesopotamian vehicle wheels of the Uruk period and following were solid blocks, with spoked wheels not invented until about 2000 BCE."
  - `statement` after: "Uruk period vehicle wheels were solid blocks, and spokes were not invented until about 2000 BC."

### water_sanitation

- `uruk-water_sanitation-draft0001`: **ACCEPT**. Canal network through the city, debated is fair.
  - final grade: debated. Statement: "A canal system connected Uruk with the Euphrates and the surrounding agricultural belt."
- `uruk-water_sanitation-d3a36cff9`: **ACCEPT**. Physical drainage trough on the Anu ziggurat.
  - final grade: attested. Statement: "A trough running parallel to the limestone staircase of the Anu ziggurat was used to drain water off the structure."

### structure_form

- `uruk-structure_form-da2b3a167`: **ACCEPT**. Measured excavated White Temple and its base terrace.
  - final grade: attested. Statement: "The White Temple was a 24 by 19 meter buttressed and niched tripartite structure built on a four course bitumen and mudbrick base terrace."

### workforce

- `uruk-workforce-d40d67457`: **ACCEPT**. Ration evidence from institutional records, graded inferred.
  - final grade: inferred. Statement: "Wool became an essential part of the maintenance rations given to workers alongside barley in the Jemdet Nasr period."
- `uruk-workforce-d0d062305`: **EDIT then accept**. Mainstream but contested ration theory, debated is right; trim.
  - final grade: debated. Statement: "Beveled rim bowls are widely thought to have measured grain rations paid to laborers under a corvee labor system."
  - `statement` before: "Beveled rim bowls found at Uruk are widely thought to have measured grain rations paid to laborers under a corvee labor system."
  - `statement` after: "Beveled rim bowls are widely thought to have measured grain rations paid to laborers under a corvee labor system."
- `uruk-workforce-draft0001`: **REJECT**. Duplicate of accepted ration bowl claim.
- `uruk-workforce-d51426d6d`: **REJECT**. Duplicate of accepted ration bowl claim.

### quality_control

- `uruk-quality_control-d42791cc4`: **ACCEPT**. Standard size claim for ration bowls, correctly debated.
  - final grade: debated. Statement: "Beveled rim bowls are generally considered uniform in size, standing about 10 cm tall with a mouth diameter of about 18 cm."
- `uruk-quality_control-db9b6a2aa`: **EDIT then accept**. Measured size variation; swap quote so the statement matches it.
  - final grade: attested. Statement: "Beveled rim bowls do vary in size; at Chogha Mish they were found with volumes from 385 to 2,580 milliliters."
  - `quote` before: "At Tepe Farukhabad BRB diameters ranged from 15 to 31 centimeters."
  - `quote` after: "There is in fact some variation in size. For example at the site of Chogha Mish beveled rim bowls were found with volumes from 385 to 2,580 milliliters"
  - `statement` before: "Beveled rim bowl sizes varied across sites, with diameters at Tepe Farukhabad ranging from 15 to 31 centimeters and volumes at Chogha Mish ranging from 385 to 2580 milliliters."
  - `statement` after: "Beveled rim bowls do vary in size; at Chogha Mish they were found with volumes from 385 to 2,580 milliliters."

### project_controls

- `uruk-project_controls-d8e75f29a`: **EDIT then accept**. Kushim tablet is a primary text; drop details not in quote.
  - final grade: attested. Statement: "A cuneiform tablet from Uruk records 29,086 measures of barley over 37 months, with the name Kushim."
  - `statement` before: "A cuneiform tablet from Uruk recorded an accountant named Kushim tracking a barley trade transaction of 29,086 measures over 37 months."
  - `statement` after: "A cuneiform tablet from Uruk records 29,086 measures of barley over 37 months, with the name Kushim."

### uruk skipped (70, left undecided)

- site_setout: `uruk-site_setout-df9e4e166`, `uruk-site_setout-d49d8ba9a`, `uruk-site_setout-daab282f4`, `uruk-site_setout-d90172a87`, `uruk-site_setout-db056c3a8`, `uruk-site_setout-d5b7f6b1f`, `uruk-site_setout-d48c4f729`, `uruk-site_setout-d8c09a7a0`, `uruk-site_setout-dfd6a79df`
- materials_supply: `uruk-materials_supply-d2ed256d8`, `uruk-materials_supply-d21e386e9`, `uruk-materials_supply-df560c09a`, `uruk-materials_supply-dca4de51f`, `uruk-materials_supply-db4bd8eba`, `uruk-materials_supply-d5926d7b0`, `uruk-materials_supply-de128536b`, `uruk-materials_supply-d3ff33c2c`, `uruk-materials_supply-d073049e0`, `uruk-materials_supply-d88638f2a`, `uruk-materials_supply-deb457855`, `uruk-materials_supply-dff393bbb`, `uruk-materials_supply-dc698171f`, `uruk-materials_supply-d39850178`
- transport_lifting: `uruk-transport_lifting-d679e95e7`, `uruk-transport_lifting-d8496c227`
- water_sanitation: `uruk-water_sanitation-d59c399c7`, `uruk-water_sanitation-dc3b4b5ca`, `uruk-water_sanitation-d5344df51`, `uruk-water_sanitation-dcc831f9e`, `uruk-water_sanitation-da476f25e`, `uruk-water_sanitation-d42fbacb0`
- structure_form: `uruk-structure_form-draft0001`, `uruk-structure_form-de9a907cc`, `uruk-structure_form-d521305b0`, `uruk-structure_form-d9c6692dc`, `uruk-structure_form-d886e29a6`, `uruk-structure_form-db8fe1765`, `uruk-structure_form-d80911e06`, `uruk-structure_form-d097cf945`, `uruk-structure_form-d55efcc94`, `uruk-structure_form-ddc2518c6`, `uruk-structure_form-d07665951`, `uruk-structure_form-d0f6925ca`, `uruk-structure_form-d7173130f`, `uruk-structure_form-ded5c6521`, `uruk-structure_form-df0d6a566`, `uruk-structure_form-d463fa9d2`, `uruk-structure_form-dac631e67`, `uruk-structure_form-d706f3eb0`, `uruk-structure_form-d9ac7f30d`, `uruk-structure_form-dacafb06a`, `uruk-structure_form-dbae312bb`, `uruk-structure_form-d0ef9fdef`
- finishes: `uruk-finishes-deb0f7c85`, `uruk-finishes-d398db25b`, `uruk-finishes-d9a4c09ba`, `uruk-finishes-da9985d18`
- workforce: `uruk-workforce-d2060648f`, `uruk-workforce-d51ee1a03`
- quality_control: `uruk-quality_control-d7cdc222f`, `uruk-quality_control-d3ddd5c2b`, `uruk-quality_control-d45ac4bbf`
- project_controls: `uruk-project_controls-draft0001`, `uruk-project_controls-db29b80d2`, `uruk-project_controls-d8d7d2e64`, `uruk-project_controls-dcaaeb7f2`, `uruk-project_controls-dc11680d2`, `uruk-project_controls-d492e4e60`, `uruk-project_controls-d686e629f`, `uruk-project_controls-d9cb71cb9`


## mohenjo

### site_setout

- `mohenjo-site_setout-dd29cfeda`: **ACCEPT**. Observed orthogonal street layout of the lower city.
  - final grade: attested. Statement: "The lower city streets ran north-south or east-west, laid out parallel or at right angles to each other, with rounded building corners."

### materials_supply

- `mohenjo-structure_form-dc955520d` (moved from structure_form): **EDIT then accept**. Building materials observed; this is materials_supply.
  - final grade: attested. Statement: "Most buildings at Mohenjo-daro were constructed of fired and mortared brick, with some sun-dried mud-brick and wooden superstructures."
  - `system` before: "structure_form"
  - `system` after: "materials_supply"
- `mohenjo-materials_supply-d6b301967`: **EDIT then accept**. Observed bitumen lining; say Great Bath, keep the presumably.
  - final grade: attested. Statement: "A thick layer of bitumen was laid along the sides of the Great Bath pool, and presumably also on the floor."
  - `statement` before: "A thick layer of bitumen was applied along the sides of the pool, and presumably also on the floor, to further waterproof the tank."
  - `statement` after: "A thick layer of bitumen was laid along the sides of the Great Bath pool, and presumably also on the floor."
- `mohenjo-materials_supply-d17c9fa20`: **REJECT**. Duplicate of accepted ship depiction claim.
- `mohenjo-materials_supply-d1dbe9ccc`: **REJECT**. Duplicate of accepted brick ratio claim; rural detail unsupported.

### transport_lifting

- `mohenjo-transport_lifting-d6c963071`: **ACCEPT**. Excavated amulet showing a ship, direct object evidence.
  - final grade: attested. Statement: "A terracotta amulet from Mohenjo-daro depicts a ship, measuring 4.5 cm in length."
- `mohenjo-transport_lifting-d83317c95`: **EDIT then accept**. Only cart evidence; sailboat detail not in the quote.
  - final grade: inferred. Statement: "The Indus Valley Civilisation may have had bullock carts like those seen throughout South Asia today, as well as boats."
  - `statement` before: "The Indus Valley Civilisation likely used bullock carts and small flat-bottomed sailboats for transportation, similar to those seen in the region today."
  - `statement` after: "The Indus Valley Civilisation may have had bullock carts like those seen throughout South Asia today, as well as boats."

### water_sanitation

- `mohenjo-water_sanitation-draft0001`: **ACCEPT**. ASI excavation report, covered vaulted drain.
  - final grade: attested. Statement: "Excavators recorded a large covered drain associated with the Great Bath, with a corbelled vaulted roof."
- `mohenjo-water_sanitation-d45532506`: **ACCEPT**. Observed watertight brick-on-edge construction of the Great Bath.
  - final grade: attested. Statement: "The Great Bath floor was made watertight using finely fitted bricks laid on edge with gypsum plaster, with side walls built the same way."
- `mohenjo-water_sanitation-da155b203`: **ACCEPT**. ASI report, well with connected masonry drains.
  - final grade: attested. Statement: "A second trench dug at right angles to the first, running north-south, uncovered a well connected to a system of masonry drains and water channels."
- `mohenjo-water_sanitation-dbfe49327`: **ACCEPT**. ASI report, rope wear grooves in well linings.
  - final grade: attested. Statement: "Water was drawn from the wells without windlasses or pulleys, as shown by deep grooves worn into the well linings by rope friction."
- `mohenjo-finishes-draft0001`: **REJECT**. Duplicate of accepted Great Bath bitumen claim.
- `mohenjo-water_sanitation-d3d97468b`: **REJECT**. Duplicate of accepted Great Bath bitumen claim.

### structure_form

- `mohenjo-structure_form-dad8e5ec0`: **REJECT**. Quote does not mention corbelling or stone arches.

### workforce

- `mohenjo-workforce-d171a24db`: **REJECT**. About the 1920s excavation crew, not the ancient builders.
- `mohenjo-workforce-d614b6b93`: **REJECT**. About 1920s excavation wages, not the ancient builders.

### quality_control

- `mohenjo-quality_control-draft0001`: **EDIT then accept**. ASI brick ratio; swap to the clean part of the OCR quote.
  - final grade: attested. Statement: "The excavators recorded that common bricks had a length, breadth and thickness ratio of 4 : 2 : 1, well suited to bonding."
  - `quote` before: "The walls are generally built of solid brick masonry in mud mortar, the size, of bricks' in common use being Il''x5|''x2|" the ratio of the length, breadth and thickness thus being 4 : 2 : 1"
  - `quote` after: "the ratio of the length, breadth and thickness thus being 4 : 2 : 1, which is admirably suited for the purpose of bonding"
  - `statement` before: "The excavators recorded common bricks with a 4:2:1 length-to-breadth-to-thickness ratio."
  - `statement` after: "The excavators recorded that common bricks had a length, breadth and thickness ratio of 4 : 2 : 1, well suited to bonding."
- `mohenjo-quality_control-d0a328096`: **EDIT then accept**. Measured artifact; the quote does not say ivory.
  - final grade: attested. Statement: "The Mohenjo-daro ruler is divided into units of 34 millimetres, with decimal subdivisions accurate to within 0.13 millimetres."
  - `statement` before: "An ivory ruler from Mohenjo-daro was divided into units of 34 millimetres with decimal subdivisions accurate to within 0.13 millimetres."
  - `statement` after: "The Mohenjo-daro ruler is divided into units of 34 millimetres, with decimal subdivisions accurate to within 0.13 millimetres."
- `mohenjo-quality_control-df33d7fdc`: **EDIT then accept**. Excavated weights; shared standards conclusion is not in the quote.
  - final grade: attested. Statement: "Twenty-four stone haematite weights of the Mesopotamian barrel-shaped type were found at Mohenjo-daro and Harappa."
  - `statement` before: "Twenty four stone haematite weights of the Mesopotamian barrel-shaped type were found at Mohenjo-daro and Harappa, indicating shared weight standards."
  - `statement` after: "Twenty-four stone haematite weights of the Mesopotamian barrel-shaped type were found at Mohenjo-daro and Harappa."

### mohenjo skipped (69, left undecided)

- site_setout: `mohenjo-site_setout-db8c4fc65`, `mohenjo-site_setout-da8ebd03d`, `mohenjo-site_setout-d16113538`, `mohenjo-site_setout-d4e14340d`, `mohenjo-site_setout-da60c2228`, `mohenjo-site_setout-dd6d64153`, `mohenjo-site_setout-da27243d9`, `mohenjo-site_setout-db9ed47a4`, `mohenjo-site_setout-d84762daa`
- materials_supply: `mohenjo-materials_supply-d4047bd2d`, `mohenjo-materials_supply-d551e6094`, `mohenjo-materials_supply-d9c79767d`, `mohenjo-materials_supply-db68da426`, `mohenjo-materials_supply-d90eda020`, `mohenjo-materials_supply-dbac06b61`
- transport_lifting: `mohenjo-transport_lifting-d597cdc0a`, `mohenjo-transport_lifting-d0b9c81ac`
- water_sanitation: `mohenjo-water_sanitation-d4ae4c970`, `mohenjo-water_sanitation-da72053d7`, `mohenjo-water_sanitation-d45626d0f`, `mohenjo-water_sanitation-d6d5aba76`, `mohenjo-water_sanitation-daab8f4f6`, `mohenjo-water_sanitation-d8d7467d6`, `mohenjo-water_sanitation-deb6aaed0`, `mohenjo-water_sanitation-dc8b6c213`, `mohenjo-water_sanitation-d816cf132`, `mohenjo-water_sanitation-d193c62a6`, `mohenjo-water_sanitation-d019b8c03`, `mohenjo-water_sanitation-d6e201074`, `mohenjo-water_sanitation-dd500073d`, `mohenjo-water_sanitation-d63156ec8`, `mohenjo-water_sanitation-d4f8b14a7`, `mohenjo-water_sanitation-d727bef46`, `mohenjo-water_sanitation-de8e62bb3`, `mohenjo-water_sanitation-d5ea0fb7e`, `mohenjo-water_sanitation-d2f804059`, `mohenjo-water_sanitation-d694d06fd`, `mohenjo-water_sanitation-d12004757`, `mohenjo-water_sanitation-d41e848e7`, `mohenjo-water_sanitation-d477921f7`, `mohenjo-water_sanitation-d52765d49`, `mohenjo-water_sanitation-d03837327`, `mohenjo-water_sanitation-d4172f0fc`, `mohenjo-water_sanitation-dbffd02a9`, `mohenjo-water_sanitation-d99b0fa19`, `mohenjo-water_sanitation-d1b0ff1dc`, `mohenjo-water_sanitation-d5963bb2d`, `mohenjo-water_sanitation-de4987cd3`, `mohenjo-water_sanitation-d0c7ee246`
- structure_form: `mohenjo-structure_form-d5552a39d`, `mohenjo-structure_form-d144f3d8b`, `mohenjo-structure_form-d672d9819`, `mohenjo-structure_form-dde9aac8a`, `mohenjo-structure_form-da6865ad8`, `mohenjo-structure_form-daf6a531c`, `mohenjo-structure_form-d8e6d7af7`, `mohenjo-structure_form-d67fa939b`, `mohenjo-structure_form-dc32b8bb3`, `mohenjo-structure_form-d4a0e976c`, `mohenjo-structure_form-d8984282b`, `mohenjo-structure_form-dab5f730f`
- quality_control: `mohenjo-quality_control-d02f9f849`, `mohenjo-quality_control-dae0f28f4`, `mohenjo-quality_control-d556c21d7`, `mohenjo-quality_control-d3c7e1e32`, `mohenjo-quality_control-db40a9eee`, `mohenjo-quality_control-d7ba66974`, `mohenjo-quality_control-d6f11c773`, `mohenjo-quality_control-df8e1ad70`


## qin

### materials_supply

- `qin-materials_supply-d760c94f5`: **ACCEPT**. Local materials principle, correctly inferred.
  - final grade: inferred. Statement: "Qin wall builders used local materials, quarried rock in mountain areas and rammed earth on plains, to avoid difficult long-distance transport."
- `qin-materials_supply-d64cba24b`: **ACCEPT**. Zhulong stone baskets for the levee, debated is fair.
  - final grade: debated. Statement: "The levee was built from long sausage-shaped woven bamboo baskets filled with stones, called Zhulong, held in place by wooden tripods called Macha."

### transport_lifting

- `qin-transport_lifting-dbcd22ba8`: **ACCEPT**. Road network under Meng Tian, correctly debated.
  - final grade: debated. Statement: "Meng Tian supervised construction of a road network connecting the former Yan, Qi, Wu, and Chu regions, including roads reserved for imperial use."
- `qin-transport_lifting-d9e410904`: **EDIT then accept**. Direct Road is a known Qin build; purpose clause not in quote.
  - final grade: attested. Statement: "The Direct Road (Zhidao) was built connecting the capital Xianyang with the Ordos."
  - `statement` before: "A dedicated road, the Direct Road (Zhidao), was built connecting the capital Xianyang with the Ordos to support the frontier construction and administration."
  - `statement` after: "The Direct Road (Zhidao) was built connecting the capital Xianyang with the Ordos."
- `qin-transport_lifting-dc254e2fb`: **REJECT**. Duplicate of accepted standard axle claim.
- `qin-transport_lifting-dce061660`: **REJECT**. Legend, quote says supposedly.

### water_sanitation

- `qin-water_sanitation-d2b672662`: **ACCEPT**. Physical form of the extant Fish Mouth Levee.
  - final grade: attested. Statement: "The Fish Mouth Levee divides the river into a deep narrow inner stream and a shallow wide outer stream to control water distribution."
- `qin-water_sanitation-d308a736a`: **EDIT then accept**. Extant canal route and length; military purpose not in quote.
  - final grade: debated. Statement: "The Lingqu Canal, 34 kilometres long, links the Xiang River, which flows into the Yangtze, with the Lijiang River, which flows into the Pearl River."
  - `statement` before: "The Lingqu Canal, 34 kilometres long, was built to link the Xiang River and Lijiang River, connecting the Yangtze and Pearl River drainage systems for military water transport."
  - `statement` after: "The Lingqu Canal, 34 kilometres long, links the Xiang River, which flows into the Yangtze, with the Lijiang River, which flows into the Pearl River."
- `qin-water_sanitation-dc5c2d67f`: **EDIT then accept**. Measured weir opening; purpose clause not in the quote.
  - final grade: attested. Statement: "The Flying Sand Weir has a 200-meter-wide opening that connects the inner and outer streams."
  - `statement` before: "The Flying Sand Weir has a 200-meter-wide opening connecting the inner and outer streams to drain excess water and prevent flooding."
  - `statement` after: "The Flying Sand Weir has a 200-meter-wide opening that connects the inner and outer streams."

### workforce

- `qin-workforce-draft0001`: **ACCEPT**. Excavated Shuihudi statutes on labor norms and rations.
  - final grade: inferred. Statement: "Qin administrative texts set labor productivity measures by age, sex, and physical capacity, and regulated food rations by status."
- `qin-workforce-d18905fe9`: **ACCEPT**. Allocation of convict labor, correctly debated.
  - final grade: debated. Statement: "Convicted criminals sentenced to hard labor mainly built roads and canals, with only a minority sent to build the great wall."
- `qin-workforce-d819081b6`: **ACCEPT**. Bodde's support-labor estimate, correctly inferred.
  - final grade: inferred. Statement: "A scholar estimated that for every worker building the wall at the site, dozens more were needed to build approach roads and transport supplies."
- `qin-workforce-d6d053fc2`: **REJECT**. Later sources' workforce figures, not contemporary evidence.
- `qin-workforce-d4b670e1c`: **REJECT**. Hearsay about killing the workmen.
- `qin-workforce-d8870f6d6`: **REJECT**. Sima Qian workforce figure, a later writer.
- `qin-workforce-d92cec9bd`: **REJECT**. Duplicate of accepted Bodde support labor claim.

### quality_control

- `qin-quality_control-d5fcf33b6`: **ACCEPT**. Standard measures and axle lengths, debated is fair.
  - final grade: debated. Statement: "The Qin state standardized measurements and practical details such as chariot axle length across its territories."
- `qin-project_controls-de782d5e4` (moved from project_controls): **EDIT then accept**. Earth volume reconciliation is a check; widen quote to civil engineering.
  - final grade: inferred. Statement: "In civil engineering projects, Qin officials had to match the volume of earth moved, transported, and tamped."
  - `system` before: "project_controls"
  - `system` after: "quality_control"
  - `quote` before: "officials had to match the volume of earth moved, transported, and tamped, requiring volume calculations and logistical planning reminiscent of mathematical modeling"
  - `quote` after: "In contexts such as civil engineering projects, officials had to match the volume of earth moved, transported, and tamped"
  - `statement` before: "Qin officials used volume calculations to match the amount of earth moved, transported, and tamped on civil engineering projects."
  - `statement` after: "In civil engineering projects, Qin officials had to match the volume of earth moved, transported, and tamped."
- `qin-quality_control-d45b513a8`: **REJECT**. Duplicate of accepted standard measures claim.
- `qin-quality_control-dfc6545b4`: **REJECT**. Duplicate of accepted standard measures claim.

### project_controls

- `qin-project_controls-da2c5340b`: **ACCEPT**. Excavated statutes on food provisioning calculations.
  - final grade: attested. Statement: "Qin legal statutes calculated food requirements for populations of varying sizes and dynamically adjusted provisions according to shortfalls, time, and distance."
- `qin-project_controls-draft0001`: **REJECT**. Duplicate of accepted standard measures and axle claim.

### qin skipped (43, left undecided)

- site_setout: `qin-site_setout-d7ad4ce16`, `qin-site_setout-dd292c08b`, `qin-site_setout-d5cfdee21`, `qin-site_setout-d5afe3381`
- materials_supply: `qin-materials_supply-d487f94fd`, `qin-materials_supply-dda232b6d`, `qin-materials_supply-d0be85d63`, `qin-materials_supply-d9613d11f`, `qin-materials_supply-d6dfd15dc`
- water_sanitation: `qin-water_sanitation-d62f163a1`, `qin-water_sanitation-d443ce3a6`, `qin-water_sanitation-de770c87c`, `qin-water_sanitation-d6c85e72c`, `qin-water_sanitation-dc8fa4306`, `qin-water_sanitation-d551738f9`, `qin-water_sanitation-dd91e3514`, `qin-water_sanitation-d23d6774b`, `qin-water_sanitation-d2e48be11`, `qin-water_sanitation-da7f4514f`, `qin-water_sanitation-d10d19d28`, `qin-water_sanitation-d0961c3e0`, `qin-water_sanitation-d58f018c8`
- structure_form: `qin-structure_form-de64d79b8`, `qin-structure_form-d360c5e70`, `qin-structure_form-d6377c34f`, `qin-structure_form-dfad8c8fa`, `qin-structure_form-d9108c87d`
- workforce: `qin-workforce-d4f794397`, `qin-workforce-df13ab7d7`, `qin-workforce-d3f699daa`, `qin-workforce-d495146e2`, `qin-workforce-d940ac14b`, `qin-workforce-d28bd1c2f`, `qin-workforce-d2eec398c`, `qin-workforce-d0d4c0c26`, `qin-workforce-d7f030229`, `qin-workforce-da0a9a3b2`
- quality_control: `qin-quality_control-d53f54c59`
- project_controls: `qin-project_controls-dd7f97a6a`, `qin-project_controls-d1883a4b0`, `qin-project_controls-dfdddc982`, `qin-project_controls-d49ea2f5f`, `qin-project_controls-d6bbbb0f2`

