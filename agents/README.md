# agents (Dev 4, agents, tests, integration, port 8000)

7-layer pipeline behind POST /chat. Contract 4 in CLAUDE.md.

Planned files: mock_server.py, tools_client.py, pipeline.py, server.py, eval.py, prompts/, logs/

Run: `make agents`

Lands by hour 2: mock /chat. Hour 12: real pipeline. Hour 14: first end-to-end answer.
