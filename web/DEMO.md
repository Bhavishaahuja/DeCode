# DeCode demo script

Three questions, about 5 minutes total. Each one shows a different part of what makes DeCode different:

| # | Question | Intent | What it proves |
|---|---|---|---|
| 1 | How long would Giza take with modern cranes? | estimate | Every number comes from a tool, not the model |
| 2 | Which of the four sites used the most standardized building units? | compare | Range across all 4 sites, and graded evidence (attested vs debated) |
| 3 | Did aliens build the pyramids? | fringe | DeCode won't grade nonsense as fact, and a critic checks every answer |

## Before you go on

- [ ] Restart everything on default settings: `.\start-decode.cmd` (no `DECODE_BUDGET_S` or `DECODE_TIMEOUT_S` in `.env`)
- [ ] Send one warm-up question after startup (anything, then wait for the answer) so the search index is loaded before the first real question
- [ ] Open http://localhost:5173 and check the chat says the API is live
- [ ] Load each replay once so you know it renders: q1, q2, q3
- [ ] Browser zoom at 125% or more so the back row can read the citations
- [ ] Close every other tab and turn off notifications

**Live or replay?** A live answer takes 30 to 45 seconds. Use the replays for all three by default. If time allows, run one live (q1 is the fastest at about 30 seconds) and talk over the pipeline panel while it works. Always say out loud which one it is.

## Opening (20 seconds)

> "Megaprojects today run late and over budget, but some of the most ambitious builds in history were finished without cranes, computers, or steel. DeCode reads the actual evidence for four of them, Giza, Uruk, Mohenjo-daro, and the Qin walls and roads, and lets you question the build like a contractor would. Every answer is cited, every number comes from a tool, and a critic checks it before it ships."

## 1. Estimate: "How long would Giza take with modern cranes?"

Site: Giza. Replay: `web/replay/q1_estimate.json`

**Point at:**
- The estimator card: **20.2 years with 3,800 people** (ancient crews) vs **4.8 years with 120 people** (modern crane crews)
- Drag a crew-rate slider and let the number move
- The line "Keep from the ancients: long-lead heavy material logistics usually take longer than the actual placement work"

**Say:**
> "The language model never does the math. The estimate goes through a calculator tool with the formula and assumptions written down, and every rate is tagged as attested or assumed. And notice what it tells you to keep from the ancients: getting 25 to 80 tonne granite blocks 900 km from Aswan was the real problem, not stacking them. That's a lesson any project manager recognizes."

## 2. Compare: "Which of the four sites used the most standardized building units?"

No site selected. Replay: `web/replay/q2_compare.json`

**Point at:**
- 4 teardown cards, one per site
- Mohenjo-daro wins: bricks in a fixed **4:2:1 ratio**, and a ruler divided into **34 mm units accurate to 0.13 mm**
- The grade badges: most citations are solid (attested), but the Uruk "uniform bowls" claim is dashed (debated), right next to a source showing volumes from 385 to 2,580 ml

**Say:**
> "This one pulls from all four sites at once. Mohenjo-daro had a standard brick ratio and a calibrated ruler, which is basically a building code and a QA tool 4,500 years ago. Look at the badges. Solid means excavation evidence, dashed means scholars disagree. When sources conflict, DeCode shows you the disagreement instead of picking a side."

## 3. Fringe: "Did aliens build the pyramids?"

No site selected. Replay: `web/replay/q3_fringe.json`

**Point at:**
- The first line: the idea is not supported by the evidence
- What it points to instead (check these against the final q3 recording): the Diary of Merer, the workers' settlement, the gang marks
- The critic result at the bottom, and the pipeline panel showing the critic layer ran

**Say:**
> "Every hackathon demo gets this question, so we built for it. Fringe ideas are never graded as claims. DeCode says plainly it isn't supported, then shows what the evidence does say, like a papyrus logbook from a crew hauling limestone for Khufu. That's the critic's job: no unsourced claims, no overstated grades, no numbers without a tool."

## Closing (20 seconds)

> "Behind every answer is a knowledge base we built ourselves: over 3,500 passages from 120 sources we checked were legal to use, turned into 84 claims a human reviewed and graded. Seven agents, one critic, zero made-up numbers. That's DeCode."

## If a judge asks

- **"How do you know it isn't hallucinating?"** The chat can only cite claims a human verified. Every quote has to appear word for word in its source passage, and `claims.validate` checks that. Numbers only come from tools, and the critic rejects any number that didn't.
- **"Where does the data come from?"** A source registry records the license for every source and skips anything that forbids reuse. Show `data/sources.yaml` if they want proof.
- **"Why is it slow?"** Seven layers, three of them running in parallel, plus a critic pass. We chose checked over fast. The pipeline panel shows each layer as it runs.
- **"Could it do a fifth site?"** Yes. The same flow runs: find sources, check licenses, import passages, decode them into draft claims, human review. The 4 sites were just our hackathon scope.
- **"Who is this for?"** Contractors, project managers, and AEC students who want to learn from how the biggest projects in history were actually run.

## If something breaks

- **Chat API is down:** the page shows a labeled demo answer. Switch to the replays and keep going.
- **A live answer shows "Needs review":** that's the critic doing its job. Say so, then open the replay.
- **Live answer hits 60 seconds:** say "this is why we recorded it", then open the replay.
