"""DeCode's Claude-powered 7-layer chat pipeline (Contract 4 in CLAUDE.md).

    from agents.llm_pipeline import LLMPipeline, ToolBridge
    response, record = LLMPipeline(tools=ToolBridge(tools_client)).run("How long would Giza take?", site="giza")

agents/chat.py decides whether a request runs here or in the rule-based pipeline (agents/pipeline.py),
and falls back to the rules if this one fails, so the chat always answers.

Layers:
    L1 Router         intent, sites, systems, at most one clarifying question     (no tools)
    L2 Archaeologist  retrieve, cite, grade                                      (search_evidence, get_claims)
    L3 Engineer       map to systems, physics checks, risks                      (search_evidence, get_claims, haul_force)
    L4 Estimator      every number through a tool                                (estimate, haul_force, carbon)
    L5 Builder        modern method, playbook, one keep-from-the-ancients point  (get_claims)
    L6 Critic         unsourced claims, overstated grades, tool-less numbers, fringe-as-fact; one retry then flag
    L7 Presenter      short markdown answer; cards are built in code from tool results

L2 to L5 run in parallel, and only the ones the intent needs. The presenter drafts, the critic checks the
draft, and if it fails the presenter gets one rewrite. Cards (teardown, estimator) are built here from
verified claims and tool results, never written by a model, so every number in them has a logged tool call.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from agents.contract import GRADES, INTENTS, SITES, SYSTEMS
from agents.tools_client import ToolAPIError

AGENTS_DIR = Path(__file__).resolve().parent
REPO_ROOT = AGENTS_DIR.parent
PROMPTS_DIR = AGENTS_DIR / "prompts"
CLAIMS_PROMPTS_DIR = REPO_ROOT / "claims" / "prompts"   # L2 and L3 prompts live with the claims work
LOG_DIR = AGENTS_DIR / "logs"
TOOL_DEFS_PATH = REPO_ROOT / "tools" / "openapi_tools.json"

MODEL = os.getenv("DECODE_MODEL", "claude-sonnet-5")
TOTAL_BUDGET_S = 46          # the server cuts off at 60; this leaves room for the rules fallback
AGENT_PHASE_S = 22           # L2 to L5 get this long, counted from when they start (not from the request)
PRESENT_RESERVE_S = 16       # always leave the presenter and critic at least this much
PREFETCH_PASSAGES_PER_SITE = 4

# sonnet 5 thinks before it answers, and thinking counts against max_tokens, so these need headroom.
# A reply cut off at max_tokens has no text left (the router once spent 299 of 300 tokens thinking).
MAX_TOKENS = {"router": 2000, "agent": 6000, "presenter": 4000, "critic": 3000}
# effort per layer: less thinking where the job is simple. The critic keeps the default (high),
# it's the last check before an answer ships. None means don't send output_config at all.
EFFORT = {"router": "low", "estimator": "low", "archaeologist": "medium", "engineer": "medium",
          "builder": "medium", "presenter": "medium", "critic": None}
PREFETCH_CLAIMS_MAX = 24

MAX_SOURCES = 12

# which of L2 to L5 each intent needs
LAYER_PLAN = {
    "explain": ["archaeologist", "engineer"],
    "compare": ["archaeologist", "engineer"],
    "estimate": ["archaeologist", "estimator"],
    "playbook": ["archaeologist", "engineer", "builder"],
    "fringe": ["archaeologist", "engineer"],
}

# (tools, max tool calls). Kept low on purpose: the evidence is prefetched, so most agents answer in one turn.
AGENT_TOOLS = {
    "archaeologist": (["search_evidence", "get_claims"], 3),
    "engineer": (["search_evidence", "get_claims", "haul_force"], 3),
    "estimator": (["estimate", "haul_force", "carbon"], 4),
    "builder": (["get_claims"], 2),
}
# agents that get the prefetched claims and passages in their input
EVIDENCE_AGENTS = {"archaeologist", "engineer", "builder"}

GRADE_RANK = {"attested": 0, "debated": 1, "inferred": 2}


# ---------------------------------------------------------------------------------------------
# Bridge between the agents and agents/tools_client.py
#
# The agents speak in tool names and argument dicts (that's how Claude tool use works). ToolBridge
# turns those into ToolsClient calls, keeps a per-request log (the critic checks numbers against it),
# and hands errors back as {"error": ...} so the agent can fix its input instead of crashing.

MAX_SEARCH_K = 6


def load_tool_definitions() -> list[dict]:
    return json.loads(TOOL_DEFS_PATH.read_text(encoding="utf-8"))


class ToolBridge:
    def __init__(self, client):
        self.client = client
        self.log: list[dict] = []
        self._lock = threading.Lock()
        self._allowed_args = {}
        for tool in load_tool_definitions():
            self._allowed_args[tool["name"]] = set(tool["input_schema"].get("properties", {}))

    def call(self, name: str, args: dict, caller: str = "") -> dict:
        started = time.time()
        # models sometimes add extra keys, keep only what the tool takes
        args = {k: v for k, v in dict(args or {}).items() if k in self._allowed_args.get(name, set())}
        try:
            if name == "search_evidence":
                args["k"] = min(int(args.get("k") or 8), MAX_SEARCH_K)
                result = self.client.search_evidence(**args)
            elif name == "get_claims":
                raw = self.client.get_claims(**args)
                if raw.get("_fallback"):
                    # the tools server is serving the contract example, never cite that
                    result = {"claims": [], "note": "no verified claims yet"}
                else:
                    claims = [c for c in raw.get("claims", []) if c.get("status") == "verified"]
                    result = {"claims": claims}
            elif name in ("estimate", "haul_force", "carbon"):
                result = getattr(self.client, name)(**args)
            else:
                result = {"error": f"unknown tool {name!r}"}
        except ToolAPIError as err:
            result = {"error": str(err)}
        except TypeError as err:  # missing required arguments
            result = {"error": f"bad arguments for {name}: {err}"}
        self._record(name, args, result, caller, started)
        return result

    def presets(self, caller: str = "pipeline") -> dict:
        started = time.time()
        try:
            result = self.client.get_presets()
        except ToolAPIError as err:
            result = {}
            self._record("presets", {}, {"error": str(err)}, caller, started)
            return result
        self._record("presets", {}, result, caller, started)
        return result

    def calls(self, name: str | None = None) -> list[dict]:
        with self._lock:
            return [entry for entry in self.log if name is None or entry["tool"] == name]

    def _record(self, name, args, result, caller, started):
        with self._lock:
            self.log.append({"tool": name, "caller": caller, "input": args, "output": result,
                             "ok": "error" not in result, "ms": int((time.time() - started) * 1000)})



# ---------------------------------------------------------------------------------------------
# Small helpers

def load_prompt(name: str) -> str:
    """L2 and L3 prompts live in claims/prompts (written alongside the claims work), the rest in agents/prompts."""
    if name in ("archaeologist", "engineer"):
        return (CLAIMS_PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8")


def parse_json(text: str) -> dict:
    """Pull the JSON object out of a model reply, even with fences or chatter around it."""
    if not text:
        return {}
    cleaned = re.sub(r"```(?:json)?", "", text).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start < 0 or end <= start:
        return {}
    try:
        parsed = json.loads(cleaned[start:end + 1])
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def strip_dashes(text: str) -> str:
    """No em or en dashes anywhere in DeCode output (CLAUDE.md). Ranges become 'to', the rest become commas."""
    if not text:
        return text
    text = re.sub(r"(\d)\s*[\u2013\u2014]\s*(\d)", r"\1 to \2", text)
    text = re.sub(r"\s*[\u2013\u2014]\s*", ", ", text)
    text = re.sub(r",\s*,", ",", text)
    return text


_MARKER = re.compile(r"\[\^(\d+)\]")
_NUMBER = re.compile(r"(?<![\w.])(\d{1,3}(?:,\d{3})+|\d+)(?:\.(\d+))?(?![\d])")


def numbers_in(text: str) -> list[tuple[float, int, str]]:
    """(value, decimals, as written) for every number in text, skipping footnote markers."""
    text = _MARKER.sub(" ", text or "")
    found = []
    for match in _NUMBER.finditer(text):
        whole = match.group(1).replace(",", "")
        decimals = match.group(2) or ""
        value = float(f"{whole}.{decimals}" if decimals else whole)
        found.append((value, len(decimals), match.group(0)))
    return found


def allowed_numbers(tool_log: list[dict], extra_texts: list[str]) -> set[float]:
    allowed = set()
    for entry in tool_log:
        blob = json.dumps(entry.get("input"), ensure_ascii=False) + " " + json.dumps(entry.get("output"), ensure_ascii=False)
        for value, _, _ in numbers_in(blob):
            allowed.add(value)
    for text in extra_texts:
        for value, _, _ in numbers_in(text):
            allowed.add(value)
    return allowed


def unsourced_numbers(answer: str, allowed: set[float]) -> list[str]:
    """Numbers in the answer that no tool call (or the user) produced. Small counts like 'three' or '2 sites' are fine."""
    missing = []
    for value, decimals, written in numbers_in(answer):
        if decimals == 0 and value <= 12:
            continue
        if value in allowed:
            continue
        # allow a tool number that was only shortened, like 20.18 written as 20.2 or 20
        if any(abs(round(a, decimals) - value) < 1e-9 for a in allowed):
            continue
        missing.append(written)
    return missing


class Deadline:
    def __init__(self, seconds: float):
        self.start = time.time()
        self.end = self.start + seconds

    def left(self) -> float:
        return self.end - time.time()

    def at(self, seconds_from_start: float) -> float:
        return min(self.end, self.start + seconds_from_start)


# ---------------------------------------------------------------------------------------------

_shared_client = None


def default_llm():
    """One Anthropic client for the whole process (it's thread safe)."""
    global _shared_client
    if _shared_client is None:
        import anthropic
        _shared_client = anthropic.Anthropic(max_retries=1, timeout=35)
    return _shared_client


class LLMPipeline:
    def __init__(self, tools: ToolBridge, llm=None, model: str = MODEL, write_logs: bool = True):
        self.llm = llm or default_llm()
        self.tools = tools
        self.model = model
        self.write_logs = write_logs
        self.tool_defs = load_tool_definitions()

    # ------------------------------------------------------------------------------------------
    def run(self, message: str, history: list[dict] | None = None, site: str | None = None) -> tuple[dict, dict]:
        """Returns (contract response, internal record with the tool log and raw layer outputs)."""
        deadline = Deadline(TOTAL_BUDGET_S)
        history = history or []
        site_hint = site if site in SITES else None
        trace: list[dict] = []
        layers: dict = {}

        # L1 router ------------------------------------------------------------------------------
        t0 = time.time()
        route = self._route(message, history, site_hint)
        layers["router"] = route
        trace.append(self._step("router", t0, f"intent={route['intent']}, sites={','.join(route['sites']) or 'none'}"
                                + (", asking a clarifying question" if route["clarifying_question"] else "")))

        if route["clarifying_question"]:
            response = self._response(strip_dashes(route["clarifying_question"]), route, [], [], [],
                                      {"passed": True, "flags": [], "retries": 0}, trace)
            response["clarifying_question"] = response["answer_md"]
            return self._finish(message, history, site, response, layers)

        # prefetch the evidence once, so the agents can usually answer in a single turn ----------
        t0 = time.time()
        site_claims, passages = self._prefetch(message, route)
        trace.append(self._step("prefetch", t0, f"{len(site_claims)} verified claims, {len(passages)} passages"))

        # L2 to L5 in parallel -------------------------------------------------------------------
        plain_block = self._agent_input(message, history, route)
        evidence_block = plain_block + self._evidence_input(route, site_claims, passages)
        plan = LAYER_PLAN[route["intent"]]
        # the agents' window starts now, so a slow prefetch doesn't leave them with no time at all,
        # but it never eats into what the presenter and critic need
        stop_at = min(time.time() + AGENT_PHASE_S, deadline.end - PRESENT_RESERVE_S)
        with ThreadPoolExecutor(max_workers=len(plan)) as pool:
            futures = {}
            for name in plan:
                block = evidence_block if name in EVIDENCE_AGENTS else plain_block
                futures[name] = pool.submit(self._run_agent, name, block, stop_at)
            for name, future in futures.items():
                output, step = future.result()
                layers[name] = output
                trace.append(step)

        # sources the presenter may cite ---------------------------------------------------------
        sources = self._collect_sources(layers, route, site_claims, message)

        # estimator card, built from the preset through the estimate tool -----------------------
        cards = []
        estimator_card = self._estimator_card(layers.get("estimator", {}), route)
        teardown_cards = self._teardown_cards(route, site_claims, sources)
        cards.extend(teardown_cards)
        if estimator_card:
            cards.append(estimator_card)

        # an estimate answer with no calculation behind it would tempt the presenter to do the maths
        # itself. Every number has to come from a tool, so hand the question to the rules pipeline,
        # which always runs the tools.
        if route["intent"] == "estimate" and not self._calculation_ran():
            raise RuntimeError("estimate question but no calculation tool ran")

        # L7 presenter draft, L6 critic, one retry ----------------------------------------------
        extra_number_texts = [message] + [turn.get("content", "") for turn in history if turn.get("role") == "user"]
        t0 = time.time()
        answer = self._present(message, history, route, layers, sources, deadline)
        trace.append(self._step("presenter", t0, f"{len(answer.split())} words"))

        t0 = time.time()
        flags = self._critique(message, answer, sources, extra_number_texts, deadline)
        trace.append(self._step("critic", t0, "passed" if not flags else f"{len(flags)} flags"))
        retries = 0
        fixable = [f for f in flags if not f.startswith("The critic could not")]
        if fixable and deadline.left() > 14:
            retries = 1
            t0 = time.time()
            answer = self._present(message, history, route, layers, sources, deadline, previous=answer, fix=fixable)
            trace.append(self._step("presenter", t0, "rewrite after critic"))
            t0 = time.time()
            flags = self._critique(message, answer, sources, extra_number_texts, deadline)
            trace.append(self._step("critic", t0, "passed on retry" if not flags else f"{len(flags)} flags remain"))

        if route["intent"] == "fringe":
            answer = self._fringe_opening(answer)
        answer, citations = self._renumber(answer, sources)
        systems = self._response_systems(route, citations, sources)
        critic = {"passed": not flags, "flags": flags, "retries": retries}
        response = self._response(answer, route, systems, citations, cards, critic, trace)
        layers["sources"] = sources
        return self._finish(message, history, site, response, layers)

    # ------------------------------------------------------------------------------------------
    # L1

    def _route(self, message, history, site_hint) -> dict:
        lines = []
        for turn in history[-6:]:
            lines.append(f"{turn.get('role', 'user')}: {str(turn.get('content', ''))[:400]}")
        user = (f"Conversation so far:\n{chr(10).join(lines) or '(none)'}\n\n"
                f"Site open in the UI (hint): {site_hint or 'none'}\n\nUser message: {message}")
        # no try here: if Claude can't even route, agents/chat.py falls back to the rules pipeline
        text, stop = self._ask("router", load_prompt("router"), user, max_tokens=MAX_TOKENS["router"])
        raw = parse_json(text)
        if not raw:
            # one retry, with a plain reminder of the format
            text, stop = self._ask("router", load_prompt("router"),
                                   user + "\n\nReply with only the JSON object.", max_tokens=MAX_TOKENS["router"])
            raw = parse_json(text)
        if not raw:
            raise RuntimeError(f"router reply wasn't JSON (stop_reason={stop})")

        intent = raw.get("intent") if raw.get("intent") in INTENTS else "explain"
        sites = [s for s in (raw.get("sites") or []) if s in SITES]
        systems = [s for s in (raw.get("systems") or []) if s in SYSTEMS]
        question = raw.get("clarifying_question")
        question = question.strip() if isinstance(question, str) and question.strip() else None
        if not sites and site_hint:
            sites = [site_hint]
        if sites and question and site_hint:
            question = None  # the UI already told us the site, so just answer
        return {"intent": intent, "sites": sites, "systems": systems[:4], "clarifying_question": question}

    # ------------------------------------------------------------------------------------------
    # L2 to L5

    def _agent_input(self, message, history, route) -> str:
        recent = [f"{t.get('role')}: {str(t.get('content', ''))[:300]}" for t in history[-4:]]
        return (f"Question: {message}\n\n"
                f"Router: intent={route['intent']}, sites={route['sites']}, systems={route['systems']}\n"
                + (f"\nRecent conversation:\n" + "\n".join(recent) if recent else ""))

    def _prefetch(self, message: str, route: dict) -> tuple[list[dict], list[dict]]:
        """Verified claims for the sites in play, plus a quick passage search per site, all in parallel."""
        sites = route["sites"]
        if not sites:
            return [], []
        system = route["systems"][0] if len(route["systems"]) == 1 else None
        with ThreadPoolExecutor(max_workers=len(sites) * 2) as pool:
            claim_jobs = [pool.submit(self.tools.call, "get_claims", {"site": site}, "prefetch") for site in sites]
            search_jobs = [pool.submit(self.tools.call, "search_evidence",
                                       {"query": message, "site": site, "system": system,
                                        "k": PREFETCH_PASSAGES_PER_SITE}, "prefetch") for site in sites]
            claims, passages = [], []
            for job in claim_jobs:
                claims.extend(job.result().get("claims") or [])
            for job in search_jobs:
                passages.extend(job.result().get("results") or [])
        return claims, passages

    @staticmethod
    def _evidence_input(route: dict, site_claims: list[dict], passages: list[dict]) -> str:
        """The prefetched evidence, compact, so the agent doesn't need to call tools for it."""
        wanted = set(route["systems"])
        relevant = [c for c in site_claims if not wanted or c.get("system") in wanted]
        others = [c for c in site_claims if c not in relevant]
        chosen = (relevant + others)[:PREFETCH_CLAIMS_MAX]
        lines = ["", "Evidence already fetched for you (these came from get_claims and search_evidence, cite them by id):", "",
                 "VERIFIED CLAIMS:"]
        for c in chosen:
            lines.append(f"- {c['claim_id']} | {c.get('system')} | {c.get('grade')} | {c.get('statement')} "
                         f"| quote: \"{c.get('quote')}\"")
        if not chosen:
            lines.append("- (none for these sites yet)")
        lines += ["", "PASSAGES:"]
        for p in passages:
            where = f", {p['locator']}" if p.get("locator") else ""
            lines.append(f"- {p['passage_id']} | {p.get('site')} | {p.get('title')}{where} | "
                         f"{(p.get('text') or '')[:700]}")
        if not passages:
            lines.append("- (none)")
        lines += ["", "Use this evidence first and answer in one turn if it covers the question. Only call a tool "
                      "for something it doesn't cover, and if you do, make all your tool calls in the same turn."]
        return "\n".join(lines)

    def _run_agent(self, name: str, user_block: str, stop_at: float) -> tuple[dict, dict]:
        t0 = time.time()
        tool_names, budget = AGENT_TOOLS[name]
        system = load_prompt(name)
        if name == "estimator":
            presets = self.tools.presets(caller="estimator")
            system = system.replace("{presets}", json.dumps(presets, separators=(",", ":")))
        try:
            text, note = self._agent_loop(name, system, user_block, tool_names, budget, stop_at)
            output = parse_json(text)
            summary = self._agent_summary(name, output)
            if not output:
                summary = f"no usable output ({note or 'reply was not JSON'})"
        except Exception as err:
            output = {}
            summary = f"error: {type(err).__name__}: {str(err)[:120]}"
        return output, self._step(name, t0, summary)

    def _agent_loop(self, layer, system, user, tool_names, max_tool_calls, stop_at) -> tuple[str, str | None]:
        """(final text, why it ended early if it did)."""
        tools = [t for t in self.tool_defs if t["name"] in tool_names]
        messages = [{"role": "user", "content": user}]
        calls = 0
        for _ in range(8):
            left = stop_at - time.time()
            if left < 3:
                break
            last_turn = left < 10 or calls >= max_tool_calls
            kwargs = {"max_tokens": MAX_TOKENS["agent"], "system": system, "tools": tools, "messages": messages}
            if last_turn:
                kwargs["tool_choice"] = {"type": "none"}
            reply = self._create(layer, **kwargs)
            tool_uses = [b for b in reply.content if getattr(b, "type", None) == "tool_use"]
            if reply.stop_reason != "tool_use" or not tool_uses:
                note = "cut off at max_tokens" if reply.stop_reason == "max_tokens" else None
                return self._text(reply), note
            messages.append({"role": "assistant", "content": reply.content})
            results = []
            for block in tool_uses:
                calls += 1
                if calls > max_tool_calls:
                    output = {"error": "tool budget used up, reply with your JSON now"}
                else:
                    output = self.tools.call(block.name, dict(block.input), caller=layer)
                results.append({"type": "tool_result", "tool_use_id": block.id,
                                "content": self._compact(block.name, output), "is_error": "error" in output})
            messages.append({"role": "user", "content": results})
        # out of turns or time: one last push for the JSON with no tools
        if stop_at - time.time() > 2:
            messages.append({"role": "user", "content": "Time is up. Reply with your JSON now using what you have."})
            if messages[-2]["role"] == "user":
                # two user turns in a row aren't allowed, fold the nudge into the last one
                nudge = messages.pop()
                last = messages[-1]
                if isinstance(last["content"], list):
                    last["content"] = last["content"] + [{"type": "text", "text": nudge["content"]}]
            reply = self._create(layer, max_tokens=MAX_TOKENS["agent"], system=system, tools=tools,
                                 tool_choice={"type": "none"}, messages=messages)
            note = "cut off at max_tokens" if reply.stop_reason == "max_tokens" else None
            return self._text(reply), note
        return "", "ran out of time"

    @staticmethod
    def _compact(tool_name: str, output: dict) -> str:
        """What the model sees. The full output stays in the tool log."""
        if tool_name == "search_evidence" and "results" in output:
            slim = []
            for p in output["results"]:
                slim.append({k: p.get(k) for k in ("passage_id", "source_id", "site", "title", "author", "year",
                                                   "source_type", "period", "locator", "system_tags", "score")}
                            | {"text": (p.get("text") or "")[:1500]})
            return json.dumps({"results": slim}, ensure_ascii=False)
        if tool_name == "get_claims" and "claims" in output:
            return json.dumps({"claims": output["claims"][:15], **({"note": output["note"]} if "note" in output else {})},
                              ensure_ascii=False)
        return json.dumps(output, ensure_ascii=False)

    @staticmethod
    def _agent_summary(name, output) -> str:
        if not output:
            return "no usable output"
        if name == "archaeologist":
            return f"{len(output.get('findings') or [])} findings, {len(output.get('gaps') or [])} gaps" + (
                ", fringe check" if output.get("fringe_check") else "")
        if name == "engineer":
            return f"{len(output.get('system_map') or [])} systems mapped, {len(output.get('physics_checks') or [])} physics checks"
        if name == "estimator":
            return f"card site={output.get('estimator_card_site')}"
        if name == "builder":
            return f"{len(output.get('playbook_steps') or [])} playbook steps"
        return "done"

    # ------------------------------------------------------------------------------------------
    # Sources and cards

    _STOPWORDS = {"what", "which", "when", "where", "with", "from", "that", "this", "they", "them", "their", "there",
                  "were", "have", "would", "could", "should", "about", "does", "into", "made", "make", "your", "used",
                  "using", "today", "between", "compare", "versus"}

    @classmethod
    def _fallback_claim_ids(cls, message: str, route: dict, site_claims: list[dict]) -> list[str]:
        """When no agent cited anything: the site's claims that share words with the question first,
        then the rest of the router's systems. A bitumen question should find the bitumen claim even
        if the router filed it under water_sanitation."""
        words = {w for w in re.findall(r"[a-z]+", (message or "").lower()) if len(w) > 3} - cls._STOPWORDS
        scored = []
        for c in site_claims:
            text = f"{c.get('statement', '')} {c.get('quote', '')}".lower()
            overlap = sum(1 for w in words if w in text)
            in_system = not route["systems"] or c.get("system") in route["systems"]
            if overlap or in_system:
                scored.append((-overlap, not in_system, c["claim_id"]))
        return [cid for _, _, cid in sorted(scored)]

    def _collect_sources(self, layers: dict, route: dict, site_claims: list[dict], message: str = "") -> list[dict]:
        claims_by_id = {c["claim_id"]: c for c in site_claims}
        passages_by_id = {}
        for entry in self.tools.calls():
            output = entry.get("output") or {}
            for c in output.get("claims") or []:
                claims_by_id.setdefault(c["claim_id"], c)
            for p in output.get("results") or []:
                passages_by_id.setdefault(p["passage_id"], p)

        wanted_claims: list[str] = []
        passage_findings: list[tuple[str, str, dict]] = []   # (passage_id, grade, finding)

        for f in (layers.get("archaeologist") or {}).get("findings") or []:
            if f.get("claim_id") in claims_by_id:
                wanted_claims.append(f["claim_id"])
            elif f.get("passage_id") in passages_by_id and f.get("grade") in GRADES:
                passage_findings.append((f["passage_id"], f["grade"], f))
        for row in (layers.get("engineer") or {}).get("system_map") or []:
            for cid in row.get("claim_ids") or []:
                if cid in claims_by_id:
                    wanted_claims.append(cid)
            for pid in row.get("passage_ids") or []:
                if pid in passages_by_id and row.get("grade") in GRADES:
                    passage_findings.append((pid, row["grade"], {"statement": row.get("ancient_method"), "quote": ""}))
        builder = layers.get("builder") or {}
        for step in builder.get("playbook_steps") or []:
            for cid in step.get("claim_ids") or []:
                if cid in claims_by_id:
                    wanted_claims.append(cid)
        keep = builder.get("keep_from_the_ancients") or {}
        if keep.get("claim_id") in claims_by_id:
            wanted_claims.append(keep["claim_id"])

        # if the agents cited nothing, fall back to the verified claims that best match the question
        if not wanted_claims and not passage_findings:
            wanted_claims = self._fallback_claim_ids(message, route, site_claims)

        sources, seen = [], set()
        for cid in wanted_claims:
            if cid in seen:
                continue
            seen.add(cid)
            claim = claims_by_id[cid]
            src = (claim.get("sources") or [{}])[0]
            sources.append({"kind": "claim", "claim_id": cid, "site": claim.get("site"), "system": claim.get("system"),
                            "source_id": src.get("source_id"), "title": src.get("title"), "url": src.get("url"),
                            "locator": src.get("locator"), "grade": claim.get("grade"),
                            "statement": claim.get("statement"), "quote": claim.get("quote"),
                            "modern": claim.get("modern_equivalent"), "lesson": claim.get("lesson")})
        for pid, grade, finding in passage_findings:
            if pid in seen:
                continue
            seen.add(pid)
            p = passages_by_id[pid]
            sources.append({"kind": "passage", "claim_id": None, "passage_id": pid, "site": p.get("site"),
                            "system": finding.get("system"), "source_id": p.get("source_id"), "title": p.get("title"),
                            "url": p.get("url"), "locator": p.get("locator"), "grade": grade,
                            "statement": finding.get("statement"), "quote": finding.get("quote")})
        return sources[:MAX_SOURCES]

    def _teardown_cards(self, route: dict, site_claims: list[dict], sources: list[dict]) -> list[dict]:
        cited = {s["claim_id"] for s in sources if s["kind"] == "claim"}
        cited_systems = {s["system"] for s in sources if s["kind"] == "claim"}
        cards = []
        for site in route["sites"]:
            by_system: dict[str, list[dict]] = {}
            for c in site_claims:
                if c.get("site") == site:
                    by_system.setdefault(c["system"], []).append(c)
            wanted = [s for s in SYSTEMS if s in set(route["systems"]) | cited_systems and s in by_system]
            if not wanted:
                wanted = [s for s in SYSTEMS if s in by_system]
            rows = []
            for system in wanted[:5]:
                claims = sorted(by_system[system], key=lambda c: (c["claim_id"] not in cited, GRADE_RANK.get(c.get("grade"), 3)))
                best = claims[0]
                src = (best.get("sources") or [{}])[0]
                where = src.get("title") or ""
                if src.get("locator"):
                    where += f", {src['locator']}"
                rows.append({"system": system, "grade": best.get("grade"), "ancient": best.get("statement"),
                             "evidence": f"\"{best.get('quote')}\" ({where})", "modern": best.get("modern_equivalent"),
                             "lesson": best.get("lesson"), "claim_ids": [c["claim_id"] for c in claims[:3]]})
            if rows:
                cards.append({"type": "teardown", "site": site, "rows": rows})
        return cards

    def _estimator_card(self, estimator_output: dict, route: dict) -> dict | None:
        site = estimator_output.get("estimator_card_site") if estimator_output else None
        if site not in SITES:
            return None
        presets = self.tools.presets(caller="pipeline")
        preset = presets.get(site)
        if not preset:
            return None
        result = {}
        for era in ("ancient", "modern"):
            p = preset[era]
            out = self.tools.call("estimate", {"quantity": preset["quantity"], "unit": preset["unit"], "crews": p["crews"],
                                               "crew_size": p["crew_size"], "rate_per_crew_day": p["rate_per_crew_day"],
                                               "days_per_year": p["days_per_year"]}, caller="pipeline")
            if "error" in out:
                return None
            result[era] = {"years": out["years"], "people": out["people"], "person_days": out["person_days"]}
        card_preset = {"unit": preset["unit"], "quantity": preset["quantity"], "quantity_tag": preset["quantity_tag"]}
        for era in ("ancient", "modern"):
            card_preset[era] = {k: preset[era][k] for k in ("crews", "crew_size", "rate_per_crew_day", "days_per_year",
                                                          "crew_label", "rate_label", "tag")}
        return {"type": "estimator", "site": site, "preset": card_preset, "result": result}

    # ------------------------------------------------------------------------------------------
    # L7 and L6

    # how a sentence citing each grade has to read (the critic flags anything stated more strongly)
    HEDGE = {"attested": "can be stated as fact",
             "debated": "must be hedged, e.g. 'scholars disagree' or 'one view is'",
             "inferred": "must be hedged, e.g. 'likely' or 'our reading is'"}

    def _sources_block(self, sources: list[dict]) -> str:
        lines = []
        for i, s in enumerate(sources, start=1):
            label = f"claim {s['claim_id']}" if s["kind"] == "claim" else f"passage {s.get('passage_id')} (not yet human-reviewed)"
            hedge = self.HEDGE.get(s.get("grade"), "must be hedged")
            line = f"[{i}] {label} | site {s.get('site')} | grade {s.get('grade')} ({hedge}) | {s.get('title')}"
            line += f"\n    statement: {s.get('statement')}"
            if s.get("quote"):
                line += f"\n    quote: \"{s['quote']}\""
            if s.get("modern"):
                line += f"\n    modern equivalent: {s['modern']} | lesson: {s.get('lesson')}"
            lines.append(line)
        return "\n".join(lines) or "(no sources found)"

    def _calculation_ran(self) -> bool:
        return any(entry["ok"] for entry in self.tools.calls() if entry["tool"] in ("estimate", "haul_force", "carbon"))

    def _number_tools_block(self) -> str:
        lines = []
        for entry in self.tools.calls():
            if entry["tool"] in ("estimate", "haul_force", "carbon") and entry["ok"]:
                lines.append(f"- {entry['tool']} input {json.dumps(entry['input'])} -> {json.dumps(entry['output'])}")
        return "\n".join(lines) or "(no calculations)"

    def _present(self, message, history, route, layers, sources, deadline, previous=None, fix=None) -> str:
        if deadline.left() < 4:
            if previous:
                return previous
            raise TimeoutError("no time left for the presenter")
        archaeologist = layers.get("archaeologist") or {}
        parts = [
            f"Question: {message}",
            f"Router: intent={route['intent']}, sites={route['sites']}, systems={route['systems']}",
            f"SOURCES (cite as [^n]):\n{self._sources_block(sources)}",
            f"Fringe check: {archaeologist.get('fringe_check')}" if archaeologist.get("fringe_check") else "",
            f"Evidence gaps: {archaeologist.get('gaps')}" if archaeologist.get("gaps") else "",
            f"Engineer: {json.dumps(layers['engineer'], ensure_ascii=False)}" if layers.get("engineer") else "",
            f"Calculations (tool results):\n{self._number_tools_block()}",
            f"Estimator: {json.dumps(layers['estimator'], ensure_ascii=False)}" if layers.get("estimator") else "",
            f"Builder: {json.dumps(layers['builder'], ensure_ascii=False)}" if layers.get("builder") else "",
        ]
        if history:
            parts.insert(1, "Earlier in the conversation:\n" + "\n".join(
                f"{t.get('role')}: {str(t.get('content', ''))[:300]}" for t in history[-4:]))
        if previous and fix:
            parts.append(f"Your previous draft:\n{previous}\n\nA reviewer found these problems. Rewrite the answer "
                         f"to fix every one:\n- " + "\n- ".join(fix))
        try:
            text, _ = self._ask("presenter", load_prompt("presenter"), "\n\n".join(p for p in parts if p),
                                max_tokens=MAX_TOKENS["presenter"])
        except Exception:
            if previous:
                return previous
            raise  # no draft at all, let agents/chat.py fall back to the rules pipeline
        text = strip_dashes(text.strip())
        # the UI shows sources itself, so drop any footnote definitions the model added anyway
        text = "\n".join(line for line in text.splitlines() if not re.match(r"^\s*\[\^\d+\]:", line)).strip()
        if not text:
            if previous:
                return previous
            raise RuntimeError("presenter returned an empty answer")
        return text

    def _critique(self, message, answer, sources, extra_number_texts, deadline) -> list[str]:
        auto = []
        missing = unsourced_numbers(answer, allowed_numbers(self.tools.calls(), extra_number_texts))
        if missing:
            auto.append(f"numbers with no tool or source behind them: {', '.join(dict.fromkeys(missing))}")
        bad_markers = sorted({int(n) for n in _MARKER.findall(answer) if not 1 <= int(n) <= len(sources)})
        if bad_markers:
            auto.append(f"citation markers that match no source: {bad_markers}")
        # if the critic can't finish its review, the answer ships flagged, never silently passed
        not_reviewed = "The critic could not complete its review ({}), so this answer needs a human check."
        if deadline.left() < 5:
            return auto + [not_reviewed.format("out of time")]
        user = (f"Question: {message}\n\nDraft answer:\n{answer}\n\nSOURCES:\n{self._sources_block(sources)}\n\n"
                f"Automatic problems already found: {auto or 'none'}")
        try:
            text, stop = self._ask("critic", load_prompt("critic"), user, max_tokens=MAX_TOKENS["critic"])
        except Exception as err:
            return auto + [not_reviewed.format(type(err).__name__)]
        verdict = parse_json(text)
        if not verdict or "passed" not in verdict:
            why = "reply cut off at max_tokens" if stop == "max_tokens" else "reply was not JSON"
            return auto + [not_reviewed.format(why)]
        flags = [strip_dashes(str(f)) for f in (verdict.get("flags") or []) if str(f).strip()]
        if verdict.get("passed") is True and not flags:
            return auto
        return auto + flags

    # ------------------------------------------------------------------------------------------
    # Assembly

    FRINGE_PHRASES = ("not supported", "no evidence", "isn't supported", "is not supported", "not visible",
                      "cannot", "can't", "myth")

    @classmethod
    def _fringe_opening(cls, answer: str) -> str:
        """Fringe answers have to say plainly that the idea isn't supported. If the model got creative, say it for it."""
        if any(phrase in answer.lower() for phrase in cls.FRINGE_PHRASES):
            return answer
        return "That idea is not supported by the evidence. " + answer

    @staticmethod
    def _renumber(answer: str, sources: list[dict]) -> tuple[str, list[dict]]:
        """Number citations in order of first use, drop unused ones, remove markers that point nowhere."""
        order: list[int] = []
        for n in _MARKER.findall(answer):
            n = int(n)
            if 1 <= n <= len(sources) and n not in order:
                order.append(n)
        mapping = {old: new for new, old in enumerate(order, start=1)}

        def swap(match):
            old = int(match.group(1))
            return f"[^{mapping[old]}]" if old in mapping else ""

        answer = _MARKER.sub(swap, answer)
        citations = []
        for old in order:
            s = sources[old - 1]
            citations.append({"n": mapping[old], "claim_id": s.get("claim_id"), "source_id": s.get("source_id"),
                              "title": s.get("title"), "url": s.get("url"), "locator": s.get("locator"),
                              "grade": s.get("grade")})
        return answer, citations

    @staticmethod
    def _response_systems(route, citations, sources) -> list[str]:
        systems = set(route["systems"])
        by_claim = {s.get("claim_id"): s for s in sources if s.get("claim_id")}
        for c in citations:
            src = by_claim.get(c.get("claim_id"))
            if src and src.get("system") in SYSTEMS:
                systems.add(src["system"])
        return [s for s in SYSTEMS if s in systems]

    @staticmethod
    def _response(answer, route, systems, citations, cards, critic, trace) -> dict:
        return {"answer_md": answer, "intent": route["intent"], "sites": route["sites"], "systems": systems or route["systems"],
                "clarifying_question": None, "citations": citations, "cards": cards, "critic": critic, "trace": trace}

    @staticmethod
    def _step(layer, started, summary) -> dict:
        return {"layer": layer, "ms": int((time.time() - started) * 1000), "summary": strip_dashes(summary)}

    def _create(self, layer: str, **kwargs):
        """One model call with the layer's effort setting."""
        effort = EFFORT.get(layer)
        if effort:
            kwargs["output_config"] = {"effort": effort}
        return self.llm.messages.create(model=self.model, **kwargs)

    @staticmethod
    def _text(reply) -> str:
        return "".join(getattr(b, "text", "") for b in reply.content if getattr(b, "type", None) == "text")

    def _ask(self, layer: str, system: str, user: str, max_tokens: int) -> tuple[str, str | None]:
        """(text, stop_reason) for a single-turn call with no tools."""
        reply = self._create(layer, max_tokens=max_tokens, system=system,
                             messages=[{"role": "user", "content": user}])
        return self._text(reply), getattr(reply, "stop_reason", None)

    def _finish(self, message, history, site, response, layers) -> tuple[dict, dict]:
        record = {"time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                  "request": {"message": message, "history": history, "site": site},
                  "response": response, "layers": layers, "tool_log": self.tools.calls()}
        if self.write_logs:
            try:
                LOG_DIR.mkdir(parents=True, exist_ok=True)
                day = datetime.now(timezone.utc).strftime("%Y%m%d")
                with open(LOG_DIR / f"chat-{day}.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
            except (OSError, TypeError, ValueError):
                pass  # logging should never break an answer
        return response, record
