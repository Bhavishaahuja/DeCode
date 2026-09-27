# claims (Dev 2, knowledge lead)

Graded claims for all 4 sites. Contract 2 in CLAUDE.md.

Planned files: taxonomy.yaml, extract.py, dedupe.py, review.py, draft/, verified/claims.jsonl, eval/questions.jsonl, prompts/archaeologist.md, prompts/engineer.md

Lands by hour 10: first 10 verified claims per site. Hour 16: full set, eval questions, L2/L3 prompts.

## Decode map (pointing extraction at the right passages)

`--limit` takes passages in file order, so a long book can crowd out the passages that matter. The decode map fixes that. It runs Chad's decode code (`data/decode.py`, `tools/decode_ai.py`) to build a small tree of transforms for a site, where each node is tied to the passages that support it. Then extraction follows the tree.

```powershell
python -m claims.decode_map --site mohenjo --system finishes          # builds claims/decode/mohenjo-finishes.json and .md
python -m claims.decode_map --site mohenjo --system finishes --show   # print it again, no API calls
python -m claims.extract --from-map claims/decode/mohenjo-finishes.json --limit 10
python -m claims.extract --from-map claims/decode/mohenjo-finishes.json --node mohenjo-t02
```

Guard rails on top of Chad's code: passages are picked round-robin across sources, ids are assigned by us (`mohenjo-t01`, `mohenjo-t01-02`), depth and counts are capped (default depth 1, 5 roots, 3 children), children of one level run in parallel, bad passage ids are dropped instead of crashing the run, and it uses a plain Stratum decode prompt (Chad's "Resolve Through Monads" prompt is still there with `--chad-prompt`, but on real runs it returned one transform with no text).

Every node is an unreviewed reading, not a claim. Drafts from `--from-map` go through `review.py` like any other.
