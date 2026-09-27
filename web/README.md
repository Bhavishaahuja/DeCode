# web: the DeCode app

One static page, `index.html`, no build step. It talks to the chat API on :8000 and the tools API on :8001.

## Run it

Three PowerShell windows, from the repo root:

```powershell
python -m uvicorn tools.app:app --port 8001        # tools: presets, verified claims, calculators
python -m uvicorn agents.server:app --port 8000    # chat: the 7-layer pipeline
python -m http.server 5173 --directory web         # this page
```

Then open http://localhost:5173.

## What comes from where

| part of the page | source |
|---|---|
| Ask (chat) | `POST :8000/chat` with `{message, site, history}`. Shows the markdown answer with footnotes, citations with grade badges (passages that aren't reviewed claims yet are labeled), the critic result and any flags, estimator numbers, and teardown rows |
| Pipeline panel | lights up the layers that actually ran, from the response `trace` |
| Build: teardown | verified claims from `POST :8001/tools/claims`, the best-graded claim per system |
| Build: crew estimator and Build it now | presets from `GET :8001/tools/presets`, the same numbers the chat uses |
| Site intro, fact, timeline, Decode walkthrough | written into the page |

If the tools API is offline, the Build tabs fall back to the demo data written into the page. If the chat API is offline, or a live answer fails, the chat shows a clearly labeled demo answer (and says why the live one failed).

A live answer takes about 30 seconds with the Claude pipeline. The page waits up to 65 seconds.
