# Stratum dev commands. Run from the repo root.
PY ?= python

.PHONY: data tools agents web all

# build passages.jsonl and the search index (Dev 1)
data:
	$(PY) -m data.build

# tool API on :8001 (Dev 3)
tools:
	$(PY) -m uvicorn tools.app:app --port 8001 --reload

# chat API on :8000 (Dev 4)
agents:
	$(PY) -m uvicorn agents.server:app --port 8000 --reload

# static web app on :5173 (Dev 5)
web:
	$(PY) -m http.server 5173 --directory web

# build data first, then run the three servers side by side
all: data
	$(MAKE) -j3 tools agents web
