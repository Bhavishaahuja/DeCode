# data (Dev 1, data engineer)

Builds `passages.jsonl` and the search index. Contract 1 in CLAUDE.md.

Planned files: sources.yaml, ingest.py, build.py, search.py, test_search.py

Interface: `from data.search import search_evidence`

Lands by hour 8: search.py plus a small prebuilt index.
