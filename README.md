# DeCode

DeCode reverse-engineers ancient megaprojects the way a contractor would.

It combines source-backed archaeological evidence, verified claims, deterministic engineering tools, and an agent pipeline to answer questions such as:

- How was this structure built?
- What evidence supports that conclusion?
- How much labor or time would it require?
- How would we approach the same project today?
- Which ancient construction practices are worth carrying forward?

The current project covers:

- Giza
- Uruk
- Mohenjo-daro
- Qin walls and roads

## Requirements

DeCode requires:

- Python 3.11 or newer
- `pip`
- Git

An Anthropic API key is optional.

Without an API key, DeCode can run using its rule-based pipeline.

## Clone the repository

```cmd
git clone https://github.com/Bhavishaahuja/Stratum.git
cd Stratum
```

## Create a virtual environment

```cmd
python -m venv .venv
.venv\Scripts\activate
```

## Install dependencies

```cmd
pip install -r requirements.txt
```

## Configure the environment

Copy `.env.example` to `.env`:

```cmd
copy .env.example .env
```

The default configuration is:

```text
ANTHROPIC_API_KEY=
TOOLS_URL=http://localhost:8001
CHAT_URL=http://localhost:8000
```

To use the Claude-powered agent pipeline, add an Anthropic API key:

```text
ANTHROPIC_API_KEY=your_key_here
```

If no API key is supplied, DeCode uses the deterministic rule-based pipeline.

## Build the evidence data

Run from the repository root:

```cmd
python -m data.build
```

This builds the evidence passages and search index used by DeCode.

The resulting evidence layer is consumed by both the tools API and the agent pipeline.

## Start DeCode

DeCode currently consists of three running services.

### 1. Tools API

Open a Command Prompt in the repository root:

```cmd
python -m uvicorn tools.app:app --port 8001
```

The tools service provides:

- evidence search
- verified claims
- construction estimates
- haul-force calculations
- carbon calculations
- site presets

Health check:

```text
http://localhost:8001/health
```

### 2. Agent API

Open a second Command Prompt:

```cmd
python -m uvicorn agents.server:app --port 8000
```

The agent API exposes the DeCode chat pipeline.

Health check:

```text
http://localhost:8000/health
```

The chat endpoint is:

```text
POST http://localhost:8000/chat
```

### 3. Web application

Open a third Command Prompt:

```cmd
python -m http.server 5173 --directory web
```

Then open:

```text
http://localhost:5173
```

No frontend build step is currently required. The web application is served directly from `web/index.html`.

### One-command startup

After setup is complete, the same startup script can be launched from either shell.

Command Prompt:

```cmd
start-decode.cmd
```

PowerShell:

```powershell
.\start-decode.cmd
```

The script detects whether it was launched from Command Prompt or PowerShell, verifies `.venv` and `.env`, rebuilds the data/index, starts all three DeCode services, and opens the web app.

## Pipeline modes

DeCode supports three agent modes.

### Automatic

```cmd
set DECODE_MODE=auto
```

This is the default.

If `ANTHROPIC_API_KEY` is available, DeCode uses the LLM pipeline. Otherwise it uses the rule-based pipeline.

### Rule-based

```cmd
set DECODE_MODE=rules
```

This runs without an LLM API.

### LLM

```cmd
set DECODE_MODE=llm
```

This explicitly enables the Claude-powered pipeline.

## Run the tests

### Evidence search

```cmd
python -m data.test_search
```

### Data tests

```cmd
python -m pytest data
```

### Tool tests

```cmd
python -m pytest tools/tests
```

### Agent tests

```cmd
python -m pytest agents/tests
```

### Agent evaluation

```cmd
python -m agents.eval
```

## How the pieces connect

```text
Source material
      |
      v
 data/
 ingestion + passages + search index
      |
      +----------------------+
      |                      |
      v                      v
 claims/                  tools/
 verified claims          deterministic calculations
      |                      |
      +----------+-----------+
                 |
                 v
              agents/
        seven-layer pipeline
                 |
                 v
               web/
             DeCode UI
```

The agent pipeline is organized as:

```text
Router
  |
  +--> Archaeologist
  +--> Engineer
  +--> Estimator
          |
          v
       Builder
          |
          v
        Critic
          |
          v
      Presenter
```

Evidence retrieval, verified claims, and calculations come from tools rather than being invented by the language model.

## Decode pipeline

DeCode also contains a recursive evidence-decoding system used to map source passages into increasingly specific construction practices.

The core transform graph lives in:

```text
data/decode.py
```

Site-specific decode maps are built through:

```text
claims/decode_map.py
```

A decode map starts with broad construction transforms and recursively resolves them into more specific child transforms.

Each transform remains linked to the evidence passages that produced it.

Those passage links can then guide claim extraction instead of simply processing the corpus in file order.

Example:

```cmd
python -m claims.decode_map --site mohenjo --system finishes
```

View an existing decode map:

```cmd
python -m claims.decode_map --site mohenjo --show
```

Use a decode map for claim extraction:

```cmd
python -m claims.extract --from-map claims/decode/mohenjo.json --limit 10
```

## Repository structure

```text
Stratum/
|
+-- data/        source ingestion, evidence passages, indexing, search, decode graph
+-- claims/      claim extraction, review, verification, decode maps
+-- tools/       deterministic engineering and evidence API
+-- agents/      chat pipeline and evaluation
+-- contracts/   shared JSON contracts and examples
+-- web/         DeCode browser interface
|
+-- CLAUDE.md
+-- Makefile
+-- requirements.txt
+-- .env.example
+-- README.md
```
