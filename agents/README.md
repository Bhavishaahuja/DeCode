# agents: the chat API (port 8000)

POST /chat, Contract 4 in CLAUDE.md. Two pipelines behind one endpoint:

| file | what |
|---|---|
| `llm_pipeline.py` | the Claude pipeline: 7 layers (router, archaeologist, engineer, estimator, builder, critic, presenter) using `claude-sonnet-5` and the tool API |
| `pipeline.py` | the rule-based pipeline: keyword routing and templated answers, no API calls. Used as the fallback |
| `chat.py` | picks the pipeline and falls back to the rules if the Claude one fails or breaks the contract |
| `server.py` | FastAPI app with the 60 second limit (504 on timeout) |
| `contract.py` | `validate_chat_response()`, the Contract 4 checker used by chat, eval and tests |
| `eval.py` | runs `claims/eval/questions.jsonl` and scores it |
| `tools_client.py` | HTTP client for the tool API on :8001 |
| `prompts/` | router, estimator, builder, critic, presenter prompts. The archaeologist and engineer prompts live in `claims/prompts/` |

## Run it

```powershell
python -m uvicorn tools.app:app --port 8001          # window 1: tools
python -m uvicorn agents.server:app --port 8000      # window 2: chat
```

Then open http://localhost:8000/docs, try `POST /chat` with `{"message": "How long would Giza take with modern cranes?", "site": "giza"}`.

## Which pipeline answers

`DECODE_MODE` (env or `.env`):

* `auto` (default): Claude pipeline when `ANTHROPIC_API_KEY` is set, otherwise rules
* `llm`: always try Claude first
* `rules`: rules only (free, instant, good for UI work)

If the Claude pipeline errors, runs out of time, or returns something that fails the contract check, the rules pipeline answers instead. That answer has a `fallback` step at the top of `trace`, and the critic flags it.

## How the Claude pipeline works

1. **Router** reads the question (plus the UI's site hint and history) and picks intent, sites, systems, or asks one clarifying question.
2. Only the layers the intent needs run, in parallel: explain and compare use archaeologist and engineer, estimate uses archaeologist and estimator, playbook adds the builder, fringe uses archaeologist and engineer.
3. Each agent calls tools through `ToolBridge`, which keeps a per-request log of every call.
4. Cards are built in code, not by the model: teardown rows from verified claims, the estimator card from the site preset run through the `estimate` tool.
5. **Presenter** writes the answer with `[^n]` footnotes pointing at a numbered list of sources (verified claims first, then passages the archaeologist graded).
6. **Critic** checks the draft two ways: automatically (every number must appear in a logged tool call or the user's question, every footnote must exist) and with Claude (unsourced claims, overstated grades, fringe as fact). One rewrite, then any remaining flags ship as "Needs review".

Every request is logged with its full tool log to `agents/logs/chat-YYYYMMDD.jsonl`.

## Eval

```powershell
python -m agents.eval --mode rules     # free, about 10 seconds
python -m agents.eval --mode llm       # real Claude calls, a few minutes
python -m agents.eval --ids q15,q26    # just these
```

Uses the tools server if it's running, otherwise runs the tools in-process. Target is 80%. A full report lands in `agents/logs/eval-<time>.json`.

## Tests

```powershell
python -m pytest agents/tests
```

The Claude pipeline tests use a scripted fake model, so they never call the API.
