# Stratum `/data`: evidence index

A curated, tagged, searchable set of evidence passages for the four Stratum sites, exposed through one function:

```python
from data.search import search_evidence

hits = search_evidence("Giza ramp sledge wet sand", site=None, system=None, k=8)
for h in hits:
    print(h["score"], h["site"], h["system_tags"], h["title"], h["url"], h["license"])
    print(h["text"])
```

## Rebuild with one command

```bash
pip install -r data/requirements.txt
make data                 # same as: python -m data.build
```

`make data` downloads (cached in `data/raw/`), extracts, cleans, chunks, tags, embeds into `data/index/`, then runs `python -m data.test_search`.
The first run takes roughly 20–40 minutes, mostly downloads and PDF parsing. Reruns use the cache.

| command | what it does |
|---|---|
| `make data` / `python -m data.build` | full rebuild + tests |
| `make data-small` / `python -m data.build --small` | curated sources only (no OpenAlex discovery). Fast, used for the early hand-off |
| `make data-llm` / `python -m data.build --llm` | also runs the claude-sonnet-5 tag pass on untagged passages (needs `ANTHROPIC_API_KEY`; capped at 400 passages, cached in `data/llm_tags.json`) |
| `make data-offline` | rebuild only from `data/raw/` (no network) |
| `make data-test` / `python -m data.test_search` | the 10 acceptance checks |
| `python -m data.search "Mohenjo-daro drains" --site mohenjo_daro -k 5` | quick manual query |

Optional: `export STRATUM_CONTACT_EMAIL=you@team.org` puts a contact address in the User-Agent (polite pools for OpenAlex and Wikipedia).
**Size guard:** any single download over 500 MB stops with `[ASK FIRST]`. Rerun with `--allow-large` only after the team agrees.

## The contract

`search_evidence(query: str, site: str | None = None, system: str | None = None, k: int = 8) -> list[dict]`

Each result is a **PASSAGE** plus `"score"` (0–1, higher is better), best first:

```json
{
  "id": "giza-petrie1883-0042",
  "text": "...300-500 tokens...",
  "site": "giza",
  "period": "Old Kingdom, Dynasty 4 (c. 2600-2500 BCE)",
  "system_tags": ["transport_lifting"],
  "source_id": "petrie1883",
  "title": "The Pyramids and Temples of Gizeh (Petrie, 1883)",
  "url": "https://archive.org/details/...",
  "license": "Public domain (published 1883; author died 1942)",
  "source_type": "excavation_report",
  "page": 42,
  "char_start": 81234,
  "char_end": 83410,
  "score": 0.8123
}
```

* `site`: `giza`, `mohenjo_daro`, `ur`, `qin_mausoleum`. Aliases work: `"Mohenjo-daro"`, `"Terracotta Army"`, `"Great Pyramid"`, …
* `system`: one of the 9 ids in `data/systems.yaml`. Aliases work: `"water"`, `"QA"`, `"labor"`, `"transport"`, …

  `transport_lifting`, `materials`, `workforce`, `water_sanitation`, `quality_control`, `structural_design`, `surveying_layout`, `logistics_supply`, `administration_records`
* `source_type`: `excavation_report | journal_article | encyclopedia | primary_text | book | dataset | place_record`
* `page` is set for paged sources (PDF, paged OCR), otherwise `null`. `char_start`/`char_end` index into `data/text/<source_id>.txt`.
* Unknown site/system raises `ValueError`. Empty query or `k<=0` returns `[]`.
* Helpers: `data.search.get_passage(id)`, `list_sites()`, `list_systems()`, `reload()`.

**Dev 2:** reuse the system ids from `data/systems.yaml` in `claims/taxonomy.yaml`. When you copy a passage into a CLAIM, copy `title`, `url`, `license` and `id` from the passage, never from memory.

## How it works

```
sources.yaml ──► fetch.py ──► textproc.py ──► tagging.py ──► passages.jsonl ──► index.py ──► index/ (Chroma)
 (curated +       download,     clean, site      keyword rules            │                    │
  OpenAlex         extract       filter, chunk    (+ optional LLM)         └──── search.py ◄────┘
  discovery)       PDF/HTML/OCR  300-500 tok,                                   BM25 + vector, fused
                                 60 overlap
```

1. **Sources** (`sources.yaml`): about 120 curated entries. Each has `title, url, license, site, type`, and a `fetch` recipe:
   * Wikipedia articles (CC BY-SA 4.0). The pinned revision URL (`oldid`) is recorded so citations don't drift.
   * Public-domain reports and books on the Internet Archive, resolved by search at ingest time. Examples: Petrie 1883, Vyse 1840, Clarke & Engelbach 1930, Lucas 1926, the ASI Annual Reports 1922–27, Woolley 1928/1929/1930, Hall & Woolley 1927, Taylor 1855.
   * Herodotus Book II (Macaulay tr., Project Gutenberg). ETCSL translations for Ur (non-commercial licence).
   * Wikidata (CC0) + Pleiades (CC BY) place records.
   * `discovery.openalex`: open-access articles per site, **only** with a CC/PD license on the best OA location. Full text comes from Europe PMC when available, else the OA PDF, else the landing page.

   Each work's license is recorded, and fetched text must actually mention the site (a guard against paywall and cookie pages).
2. **Resolved sources** (`sources.resolved.yaml`, generated): every source actually ingested, with the concrete URL, license, retrieval date and passage count. It also lists the sources that were deliberately *not* ingested, and why.
3. **Cleaning**: de-hyphenation, line re-wrapping, citation marks and reference lists removed. OCR chunks with fewer than 60% real words are dropped. General works are cut down to paragraphs that mention the site (`keep_regex`).
4. **Chunking**: whole sentences packed to about 400 tokens (bge tokenizer), capped at 500, with about 60 tokens of overlap.
5. **Tagging**: `site` comes from the source. `period` comes from regex rules per site (`config.PERIOD_RULES`), falling back to the source period, then the site default. `system_tags` need ≥1 strong or ≥2 weak keyword hits (`systems.yaml`). `--llm` sends only untagged passages to `claude-sonnet-5`: 20 per call, truncated to 1,200 characters, cached.
6. **Index**: `BAAI/bge-small-en-v1.5`, normalised, in the Chroma collection `stratum_passages` (cosine) at `data/index/`. Metadata: `site`, `period`, `source_id`, `source_type`, `license`, `system_tags`, plus a `sys_<id>` boolean per system for filtering.
7. **Search**: filter by site/system, then take the top 50 vector hits (queries use the bge instruction prefix) and the top 50 BM25 hits. The score is `0.65·cosine + 0.35·BM25/max` over the union. Without chromadb, sentence-transformers or the index, search falls back to BM25-only and warns.

## Licensing decisions

* **Skipped because the license forbids reuse, or reuse isn't granted.** Each is listed in `sources.yaml` with `enabled: false` and a note:
  * Marshall 1931 *Mohenjo-daro and the Indus Civilization*: US public domain only from 2027-01-01, and in copyright in the UK until 2029.
  * Mackay 1938: US copyright until 2034.
  * Digital Giza: bulk reuse isn't licensed.
  * tDAR: requires login and the user agreement.
  * Open Access works with no stated license (`other-oa`, `publisher-specific-oa`, `null`).
* **Included with conditions:**
  * CC BY-NC / CC BY-ND OpenAlex works and ETCSL are fine for this non-commercial project. Drop them from `discovery.openalex.licenses_allowed` or disable them before any commercial use.
  * Woolley's 1920s books are public domain in the US only (UK copyright until 2030).
* **Deferred:** the Chinese *Shiji* (ctext.org) and the French Chavannes translation are public domain, but the English embedder can't retrieve them well. Enable them together with a multilingual model (`BAAI/bge-m3`). CDLI (CC0) and ORACC (CC BY-SA) are listed but disabled until specific translated texts are picked.

## Files

| path | committed? | what |
|---|---|---|
| `sources.yaml` | yes | curated sources + discovery queries |
| `sources.resolved.yaml` | yes | generated: exactly what was ingested, with licenses |
| `systems.yaml` | yes | the 9 system ids, aliases, keyword rules |
| `passages.jsonl` | yes | all passages (PASSAGE schema, no score) |
| `index/` | yes | prebuilt Chroma index (vectors + metadata only; text stays in passages.jsonl) |
| `raw/`, `text/`, `llm_tags.json` | no | download cache, cleaned full texts, LLM tag cache |
| `config.py` | yes | sites, periods, paths, `Passage` TypedDict |
| `fetch.py`, `textproc.py`, `tagging.py`, `ingest.py`, `index.py`, `search.py`, `build.py`, `test_search.py` | yes | the pipeline |

## Adding a source

Add an entry to `sources.yaml`, e.g.

```yaml
- id: my_paper
  site: ur
  type: journal_article
  title: "Some open-access paper (2021)"
  url: https://doi.org/10.xxxx/yyyy
  license: CC BY 4.0
  fetch: {kind: url, url: https://example.org/paper.pdf, format: pdf}
```

Then run `python -m data.build --sites ur`. Other sites' passages are kept, and every source must carry a license.
