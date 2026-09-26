# Stratum `/data`: sources, registry, passages, search

Dev 1 (data engineer) with Chad (source registry and corpus models). This folder covers stages 1 to 3 of the Decode flow: find legally usable sources, import them as passages, and make them searchable. The full flow is in [`DECODE.md`](DECODE.md).

```python
from data.search import search_evidence

hits = search_evidence("Giza ramp sledge wet sand", site=None, system=None, k=8)
for h in hits:
    print(h["score"], h["passage_id"], h["system_tags"], h["title"], h["locator"], h["license"])
```

## Build

```bash
pip install -r data/requirements.txt
python -m data.build --small     # curated sources only, no OpenAlex. Fast, good for a hand-off
python -m data.build             # full build (same as `make data`)
```

The build checks every source against the registry, downloads (cached in `data/raw/`), cleans, chunks, tags, embeds into `data/index/`, then runs `python -m data.test_search`. The first full run takes roughly 20 to 40 minutes, mostly downloads and PDF parsing. Reruns use the cache.

| command | what it does |
|---|---|
| `python -m data.build` | full rebuild plus tests |
| `python -m data.build --small` | curated sources only (no OpenAlex discovery) |
| `python -m data.build --llm` | also runs the claude-sonnet-5 tag pass on untagged passages (needs `ANTHROPIC_API_KEY`, capped at 400, cached in `data/llm_tags.json`) |
| `python -m data.build --offline` | rebuild only from `data/raw/` |
| `python -m data.build --sites qin` | rebuild one site, keep the others |
| `python -m data.source_check` | run the stage 1 gate on every source and print the ones that won't be used, and why |
| `python -m data.test_search` | the acceptance checks |
| `pytest data` | registry, source gate and corpus model tests (plus the acceptance checks) |
| `python -m data.search "Mohenjo-daro drains" --site mohenjo -k 5` | quick manual query |

Optional: `export STRATUM_CONTACT_EMAIL=you@team.org` puts a contact address in the User-Agent (polite pools for OpenAlex and Wikipedia).
**Size guard:** any single download over 500 MB stops with `[ASK FIRST]`. Rerun with `--allow-large` only after the team agrees.

## The contract (Contract 1 in CLAUDE.md)

`search_evidence(query: str, site: str | None = None, system: str | None = None, k: int = 8) -> list[dict]`

Each result is a PASSAGE plus `"score"` (0 to 1, higher is better), best first:

```json
{
  "passage_id": "giza-petrie1883-0042",
  "source_id": "petrie1883",
  "site": "giza",
  "title": "The Pyramids and Temples of Gizeh (Petrie, 1883)",
  "author": "W. M. Flinders Petrie",
  "year": 1883,
  "url": "https://archive.org/details/...",
  "license": "Public domain (published 1883; author died 1942)",
  "source_type": "excavation_report",
  "period": "Old Kingdom, Dynasty 4 (c. 2600-2500 BCE)",
  "locator": "p. 42",
  "text": "...300 to 500 tokens...",
  "system_tags": ["transport_lifting"],
  "tagged_by": "rules",
  "page": 42,
  "char_start": 81234,
  "char_end": 83410,
  "score": 0.8123
}
```

* `site`: `giza`, `uruk`, `mohenjo`, `qin`. Aliases work as input only: `"Warka"`, `"Mohenjo-daro"`, `"Great Wall"`, `"Great Pyramid"`, and so on. Stored data always uses the four ids.
* `system`: one of the 9 shared ids, same as `claims/taxonomy.yaml`: `site_setout`, `materials_supply`, `transport_lifting`, `water_sanitation`, `structure_form`, `finishes`, `workforce`, `quality_control`, `project_controls`. Aliases work as input: `"water"`, `"QA"`, `"labor"`, `"materials"`, `"records"`, and so on.
* `source_type`: `excavation_report | primary_text | scholarship | reference | dataset`. Wikipedia and Wikidata/Pleiades are `reference`, books and papers are `scholarship`.
* `author`: `"Wikipedia contributors"` for Wikipedia, `null` if unknown.
* `year`: publication year. For living web pages (Wikipedia, Wikidata) it's the retrieval year, since the pinned `oldid` in the url is what fixes the text.
* `locator`: `"p. 42"` for paged sources, `"section: Construction"` for Wikipedia sections, else `null`.
* `tagged_by`: `rules` (keyword rules), `llm` (the optional tag pass), `none` (no tags).
* Extras on top of the contract: `page`, `char_start`, `char_end` (offsets into `data/text/<source_id>.txt`).
* `score` only ever appears in search results, never in `passages.jsonl`.
* Unknown site or system raises `ValueError`. Empty query or `k <= 0` returns `[]`.
* Helpers: `data.search.get_passage(passage_id)`, `list_sites()`, `list_systems()`, `reload()`.

**Dev 2:** when you copy a passage into a CLAIM, copy `source_id`, `passage_id`, `title`, `url` and `locator` from the passage, never from memory.

## How it works

```
sources.yaml ──► registry ──► fetch.py ──► textproc.py ──► tagging.py ──► passages.jsonl ──► index.py ──► index/ (Chroma)
 (curated +      valid only    download,    clean, site     keyword rules          │                         │
  OpenAlex                     extract      filter, chunk   (+ optional LLM)       └───── search.py ◄────────┘
  discovery)                   PDF/HTML/OCR 300-500 tok                                   BM25 + vector, fused
```

1. **Sources** (`sources.yaml`): about 130 curated entries, each with `id, site, type, title, url, license, author` (plus `year` where there is one) and a `fetch` recipe.
   * Wikipedia articles (CC BY-SA 4.0), with the pinned revision url (`oldid`) recorded so citations don't drift.
   * Public-domain books and reports on the Internet Archive, resolved by search at ingest time: Petrie 1883, Vyse 1840, Clarke and Engelbach 1930, Lucas 1926, the ASI Annual Reports 1922 to 27, Loftus 1857 (Warka), Hilprecht 1903, Geil 1909 (Great Wall).
   * Project Gutenberg: Herodotus Book II (Macaulay tr.), the Old Babylonian Gilgamesh (Jastrow and Clay 1920).
   * ETCSL translations for Uruk (Enmerkar and the Lord of Aratta, Gilgamesh and Aga; non-commercial licence).
   * Wikidata (CC0) plus Pleiades (CC BY) place records.
   * `discovery.openalex`: open-access papers per site, only with a CC or PD license on the best OA location. Full text comes from Europe PMC when available, else the OA PDF, else the landing page (robots.txt checked first).
2. **Gate and registry**: `source_check.py` decides use or skip for each source (switched off, known valid, known invalid, or a fresh license, access and robots.txt check). Chad's `SourceRegistry` answers "known valid / invalid / unknown" from the files below. See `DECODE.md` stage 1.
3. **Resolved sources** (`sources.resolved.yaml`, generated and committed): every source actually ingested with the concrete url, license, author, year, retrieval date and passage count, plus every skipped source with its `reason`. This is where registry decisions are saved.
4. **Cleaning**: de-hyphenation, line re-wrapping, citation marks and reference lists removed. OCR chunks with fewer than 60% real words are dropped. General works are cut down to paragraphs about the site (`keep_regex`).
5. **Chunking**: whole sentences packed to about 400 tokens (bge tokenizer), capped at 500, with about 60 tokens of overlap.
6. **Tagging**: `site` comes from the source. `period` comes from regex rules per site (`config.PERIOD_RULES`), falling back to the source period, then the site default. `system_tags` need 1 strong or 2 weak keyword hits (`systems.yaml`). `--llm` sends only untagged passages to `claude-sonnet-5`, 20 per call, truncated to 1,200 characters, cached.
7. **Index**: `BAAI/bge-small-en-v1.5`, normalised, in the Chroma collection `stratum_passages` (cosine) at `data/index/`. Metadata includes a `sys_<id>` boolean per system for filtering.
8. **Search**: filter by site and system, then take the top 50 vector hits and the top 50 BM25 hits. Score is `0.65 x cosine + 0.35 x BM25/max` over the union. Without chromadb, sentence-transformers or the index, search falls back to BM25 only and warns, so a fresh clone with just `passages.jsonl` still works.

## Sites

| id | what we cover | main sources |
|---|---|---|
| `giza` | Giza pyramid complex | Wikipedia, Petrie, Vyse, Clarke and Engelbach, Lucas, Herodotus, OpenAlex |
| `uruk` | Uruk (Warka): Eanna, Anu ziggurat and White Temple, Uruk period building and administration | Wikipedia, Loftus 1857, Hilprecht 1903, Gilgamesh (Jastrow and Clay), ETCSL, OpenAlex |
| `mohenjo` | Mohenjo-daro | Wikipedia, ASI Annual Reports 1922 to 27, OpenAlex |
| `qin` | Qin walls and roads: the Qin Great Wall, the Straight Road, Qin canals, standardization and labour statutes | Wikipedia, Geil 1909, OpenAlex |

## Licensing decisions

* **Skipped because reuse isn't allowed or isn't practical** (`enabled: false` with a note, and listed with a `reason` in `sources.resolved.yaml`):
  * Marshall 1931 *Mohenjo-daro and the Indus Civilization*: US public domain only from 2027-01-01.
  * Mackay 1938: US copyright until 2034.
  * Digital Giza: bulk reuse isn't licensed.
  * tDAR: needs a login and the user agreement.
  * OpenAlex works with no stated license (`other-oa`, `publisher-specific-oa`, `null`) are never fetched.
* **Included with conditions:**
  * CC BY-NC and CC BY-ND OpenAlex works and ETCSL are fine for this non-commercial project. Drop them from `discovery.openalex.licenses_allowed` before any commercial use.
* **Deferred:** the Chinese *Shiji* (ctext.org) and the French Chavannes translation are public domain, but the English embedder can't retrieve them well. Enable them with a multilingual model (`BAAI/bge-m3`). CDLI (CC0) and ORACC (CC BY-SA) are listed but disabled until specific translated texts are picked.

## Files

| path | committed? | what |
|---|---|---|
| `sources.yaml` | yes | curated sources plus discovery queries |
| `sources.resolved.yaml` | yes | generated: exactly what was ingested (with licenses) and what was skipped (with reasons) |
| `systems.yaml` | yes | the 9 system ids, aliases, keyword rules |
| `passages.jsonl` | yes | all passages (Contract 1, no score) |
| `index/` | yes | prebuilt Chroma index (vectors and metadata only, text stays in passages.jsonl) |
| `raw/`, `text/`, `llm_tags.json` | no | download cache, cleaned full texts, LLM tag cache |
| `config.py` | yes | sites, periods, source types, paths, the `Passage` TypedDict |
| `corpus_models.py`, `source_registry.py` | yes | Chad's corpus models and source registry |
| `source_check.py` | yes | the stage 1 gate ingest calls (license, access, robots.txt) |
| `fetch.py`, `textproc.py`, `tagging.py`, `ingest.py`, `index.py`, `search.py`, `build.py` | yes | the pipeline |
| `test_search.py`, `test_source_check.py`, `test_source_registry.py`, `test_corpus_models.py` | yes | tests |
| `DECODE.md` | yes | the Decode flow, end to end |

## Adding a source

Add an entry to `sources.yaml`, for example

```yaml
- id: my_paper
  site: qin
  type: scholarship
  title: Some open-access paper (2021)
  url: https://doi.org/10.xxxx/yyyy
  license: CC BY 4.0
  author: A. Author
  year: 2021
  fetch: {kind: url, url: https://example.org/paper.pdf, format: pdf}
```

Then run `python -m data.build --sites qin`. The gate checks the license and robots.txt the first time and the answer is saved in `sources.resolved.yaml`. Other sites' passages are kept.
