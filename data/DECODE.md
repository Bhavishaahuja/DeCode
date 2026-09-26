# How Stratum builds its knowledge (the Decode flow)

Stratum answers questions from two things: **passages** (cleaned chunks of legally usable sources) and **claims** (graded transforms decoded from those passages). This file walks through how a site goes from "we know its name" to "the chat can cite it."

Two words to keep straight:

* A **transform is a claim.** An ancient practice (`statement`) decoded into a modern equivalent (`modern_equivalent`), with a `lesson` and an evidence `grade`. There is no separate transform dataset. `claims/verified/claims.jsonl` is the transform dataset.
* The **Decode Agent is the claims pipeline** in `/claims` (`extract.py`, `dedupe.py`, `review.py`, `validate.py`). It only ever writes drafts. A human review turns a draft into a verified claim.

Site ids are always `giza`, `uruk`, `mohenjo`, `qin`. System ids are the 9 in `data/systems.yaml` (same as `claims/taxonomy.yaml`).

## The flow

```text
SITE (giza | uruk | mohenjo | qin)
  ↓
1. FIND SOURCES          sources.yaml + source registry               Dev 1 + Chad
  ↓
2. SELECT                data/sources.yaml (enabled, per site)        Dev 1
  ↓
3. IMPORT                python -m data.build -> passages.jsonl       Dev 1
  ↓
4. DECODE                claims pipeline -> claims/verified/          Dev 2
  ↓
5. DISPLAY               tool API (:8001) -> chat cards and web app   Dev 3 serves, Dev 5 shows
```

The chat pipeline (`/agents`) only reads the end of this: verified claims and passages from valid sources. It never runs the Decode flow itself.

---

## Stage 1: Find sources (the source registry)

Every candidate source is checked before anything is downloaded.

```text
candidate source (sources.yaml entry, or an OpenAlex hit)
  ↓
switched off in sources.yaml? ──→ skip, with its note as the reason
  ↓
ask the source registry
  ↓
KNOWN VALID ─────→ use it
KNOWN INVALID ───→ skip it (and say why)
UNKNOWN ─────────→ check it now
                     license: does it allow reuse?
                     access:  official API, or a direct download?
                     robots:  for direct downloads, does robots.txt allow us?
                     ↓
                   save the answer (sources.resolved.yaml)
```

* The registry is Chad's `SourceRegistry` in `data/source_registry.py`, built on his models in `data/corpus_models.py` (`SourceRecord`, `SourceStatus`, `AccessType`). It reads what we already know from `sources.yaml`, `sources.resolved.yaml` and ingest logs, so it isn't a second data layer.
* The gate is `data/source_check.py` (`decide()`), which ingest calls for every source.
* Answers are saved by ingest in `sources.resolved.yaml`: sources it used go under `sources` (the registry reads those as valid), sources it skipped go under `listed_but_not_ingested` with a `reason`.
* `enabled: false` in `sources.yaml` is where the "can't legally use this" decisions live, each with a note (for example Marshall 1931, still in copyright; Digital Giza, bulk reuse not licensed).
* Wikipedia, Internet Archive, Gutenberg, Wikidata and OpenAlex go through their official APIs, so the site terms are respected by design. Direct downloads (ETCSL pages, open-access PDFs) get a robots.txt check first.

Check the whole list without building anything:

```bash
python -m data.source_check            # prints every source that won't be used, and why
python -m data.source_check --offline  # same, but leaves robots.txt checks for later
```

**Demo moment:** run that command and point at a skipped line, for example `invalid giza digital_giza: switched off in sources.yaml: Per-item rights vary and bulk download isn't licensed.`

## Stage 2: Select

Which valid sources go in for each site is decided in `data/sources.yaml`: the curated list, plus the `discovery.openalex` block that tops each site up with open-access papers whose license is on the allow list. Nothing is decoded here.

## Stage 3: Import

`python -m data.build` (or `make data`) fetches each valid source, cleans it, keeps only the paragraphs about the site for general works (`keep_regex`), chunks it into 300 to 500 token passages, tags each passage with a period and system tags, and embeds everything into `data/index/`.

Output is `data/passages.jsonl`, one Contract 1 PASSAGE per line:

```json
{"passage_id": "giza-petrie1883-0042", "source_id": "petrie1883", "site": "giza",
 "title": "The Pyramids and Temples of Gizeh (Petrie, 1883)", "author": "W. M. Flinders Petrie", "year": 1883,
 "url": "https://archive.org/details/...", "license": "Public domain (published 1883; author died 1942)",
 "source_type": "excavation_report", "period": "Old Kingdom, Dynasty 4 (c. 2600-2500 BCE)", "locator": "p. 42",
 "text": "...", "system_tags": ["transport_lifting"], "tagged_by": "rules",
 "page": 42, "char_start": 81234, "char_end": 83410}
```

Rules that hold at this stage:

* Only sources that pass the gate produce passages. `python -m data.test_search` fails if any passage's source isn't valid in the registry.
* Dev 2's hand-split passages (`claims/handsplit/passages.jsonl`) are merged in unchanged, so their `passage_id`s keep working. Their sources are only used when `reuse_allowed: true` and the license allows reuse, and they land in `sources.resolved.yaml` like everything else.

## Stage 4: Decode (passages to graded claims)

This is the Decode Agent, and it lives in `/claims`:

```text
passages (search_evidence or claims/handsplit)
  ↓
extract.py    passages -> draft claims (statement, quote, modern_equivalent, lesson, suggested grade)
  ↓
dedupe.py     merge claims that say the same thing
  ↓
review.py     a human accepts, edits, re-grades or rejects; reviewed_by gets filled in
  ↓
validate.py   every quote must appear verbatim in its passage, every passage_id must exist
  ↓
claims/verified/claims.jsonl   (status: verified)
```

* Grades: `attested` (direct excavation or primary-text support), `debated` (supported but scholars disagree), `inferred` (our reasonable reading).
* Fringe ideas are never graded as claims.
* The pipeline only writes drafts. Nothing reaches `verified` without a human.

## Stage 5: Display

Dev 3's tool API serves the verified claims (`/tools/claims`) and passages (`/tools/search_evidence`). The chat turns them into citations, teardown rows (`ancient = statement`, `modern = modern_equivalent`, `lesson = lesson`) and cards, and the web app shows them with the grade badges.

---

## End to end, for the demo

1. `python -m data.source_check` shows a source being skipped for its license.
2. `python -m data.search "Qin Straight Road built for troops" --site qin -k 3` shows the passage a claim came from.
3. The same passage appears as a draft in `claims/draft/claims.jsonl`, then reviewed and graded in `claims/verified/claims.jsonl`.
4. Ask the chat about it, and the claim shows up as a cited, graded row.
