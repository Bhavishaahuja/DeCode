"""Grounded seven-stage chat pipeline for Contract 4."""
from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from agents.tools_client import ToolAPIError

SITES = ("giza", "uruk", "mohenjo", "qin")
SYSTEMS = (
    "site_setout", "materials_supply", "transport_lifting", "water_sanitation",
    "structure_form", "finishes", "workforce", "quality_control", "project_controls",
)
_SYSTEM_TERMS = {
    "site_setout": ("survey", "alignment", "aligned", "level", "leveled", "levelled", "foundation", "setting out"),
    "materials_supply": ("material", "quarry", "stone", "brick", "supply", "timber", "earth", "block"),
    "transport_lifting": ("transport", "haul", "sledge", "ramp", "crane", "lift", "road", "move", "drag", "wheel"),
    "water_sanitation": ("water", "watertight", "canal", "drain", "sewage", "sewer", "well", "flood"),
    "structure_form": ("structure", "wall", "platform", "geometry", "load path", "rammed", "held up"),
    "finishes": ("finish", "casing", "plaster", "cladding", "decoration", "bitumen"),
    "workforce": ("workforce", "worker", "crew", "labour", "labor", "ration", "people", "fed", "housed"),
    "quality_control": ("quality", "tolerance", "precision", "measurement", "inspection", "consistent", "standard", "accurately"),
    "project_controls": ("schedule", "accounting", "record", "tablet", "project control", "management", "organized", "organised"),
}
_SITE_TERMS = {
    "giza": ("giza", "great pyramid", "pyramid of khufu", "khufu"),
    "uruk": ("uruk", "ziggurat of anu"),
    "mohenjo": ("mohenjo", "mohenjo-daro", "mohenjo daro"),
    "qin": ("qin", "qin wall", "straight road", "great wall"),
}
_FRINGE_TERMS = ("alien", "aliens", "extraterrestrial", "lost advanced civilization", "ancient high-tech",
                 "nuclear blast", "ancient nuclear", "anunnaki", "nibiru", "power plant", "from the moon",
                 "see the moon", "visible from the moon")
_ESTIMATE_TERMS = ("how long", "how many", "estimate", "duration", "take to build", "years", "calculate")
_PLAYBOOK_TERMS = ("how would we build", "build it today", "modern method", "playbook", "build today")
_COMPARE_TERMS = ("compare", "versus", " vs ", "difference between", "ancient and modern", " differ")
_EVIDENCE_CUES = {
    "site_setout": ("aligned", "levelled", "survey", "foundation", "orientation"),
    "materials_supply": ("quarry", "brick", "stone", "timber", "earth", "supply"),
    "transport_lifting": ("sledge", "sledges", "sled", "ramp", "haul", "drag", "pulley"),
    "water_sanitation": ("bitumen", "watertight", "water-proof", "drain", "sewage", "canal"),
    "structure_form": ("rammed", "wall", "earth", "load-bearing", "structure"),
    "finishes": ("bitumen", "plaster", "casing", "cladding"),
    "workforce": ("village", "bread", "ration", "workers", "crew", "labour"),
    "quality_control": ("standard", "tolerance", "precision", "measured", "consistent"),
    "project_controls": ("tablet", "accounting", "record", "schedule", "quota"),
}


def route(message: str, history: list[dict[str, str]] | None = None,
          site_hint: str | None = None) -> dict[str, Any]:
    text = message.casefold()
    context = " ".join(item["content"] for item in (history or []) if item.get("role") == "user")
    routing_text = f"{context} {text}".casefold()
    sites = [site for site, aliases in _SITE_TERMS.items()
             if any(alias in routing_text for alias in aliases)]
    if not sites and any(term in text for term in ("four sites", "all four sites", "each site")):
        sites = list(SITES)
    if not sites and site_hint and site_hint.casefold() in SITES:
        sites = [site_hint.casefold()]
    calculation = None
    if any(term in text for term in ("carbon", "co2", "embodied")):
        calculation = "carbon"
    elif any(term in routing_text for term in ("friction", "per person", "drag a", "haul force")):
        calculation = "haul_force"
    intent = "explain"
    if any(term in text for term in _FRINGE_TERMS):
        intent = "fringe"
    elif (any(term in text for term in _PLAYBOOK_TERMS)
          or ("today" in text and any(term in text for term in ("build", "learn", "contractor", "teach")))
          or ("today" in text and any(term in text for term in ("run", "project controls")))
          or "what can" in text and "learn" in text or "what does" in text and "teach" in text):
        intent = "playbook"
    elif calculation or any(term in text for term in _ESTIMATE_TERMS):
        intent = "estimate"
    elif any(term in text for term in _COMPARE_TERMS) or (len(sites) > 1 and text.startswith("which ")):
        intent = "compare"
    systems = [system for system, terms in _SYSTEM_TERMS.items()
               if any(term in text for term in terms)]
    if intent == "playbook" and not systems and "giza" in sites:
        systems.extend(("materials_supply", "transport_lifting", "workforce"))
    if intent == "fringe" and not systems:
        if "power plant" in text:
            systems.append("structure_form")
        elif "uruk" in sites:
            systems.append("workforce")
        elif "giza" in sites:
            systems.extend(("workforce", "transport_lifting"))
    if intent == "estimate" and calculation is None:
        if "crane" in text or "block" in text or "road" in text:
            systems.append("transport_lifting")
        systems.append("workforce")
    systems = list(dict.fromkeys(systems))
    needs_site = not sites and calculation != "carbon"
    return {
        "intent": intent,
        "sites": sites,
        "systems": systems,
        "calculation": calculation,
        "query": message,
        "clarifying_question": "Which site are you asking about: Giza, Uruk, Mohenjo-daro, or Qin?" if needs_site else None,
    }


def run_pipeline(message: str, history: list[dict[str, str]] | None, site_hint: str | None,
                 tools: Any) -> dict[str, Any]:
    trace: list[dict[str, Any]] = []

    def record(layer: str, started: float, summary: str) -> None:
        trace.append({"layer": layer, "ms": round((time.perf_counter() - started) * 1000), "summary": summary})

    started = time.perf_counter()
    routed = route(message, history, site_hint)
    record("router", started, f"intent={routed['intent']}, sites={','.join(routed['sites']) or 'unknown'}")
    if routed["clarifying_question"]:
        return _empty_response(routed, routed["clarifying_question"], trace)

    sites = routed["sites"]
    systems = routed["systems"]
    selected_systems = systems or list(SYSTEMS)
    started = time.perf_counter()
    claims_by_site: dict[str, dict[str, Any]] = {}
    evidence_by_site: dict[str, dict[str, Any]] = {}
    if sites:
        with ThreadPoolExecutor(max_workers=max(2, len(sites) * 2)) as executor:
            claim_futures = {site: executor.submit(tools.get_claims, site=site) for site in sites}
            evidence_futures = {
                site: executor.submit(tools.search_evidence, query=message, site=site,
                                      system=systems[0] if len(systems) == 1 else None, k=6)
                for site in sites
            }
            claims_by_site = {site: _read_tool_result(future, "claims") for site, future in claim_futures.items()}
            evidence_by_site = {site: _read_tool_result(future, "results") for site, future in evidence_futures.items()}
    verified_claims: list[dict[str, Any]] = []
    flags: list[str] = []
    for site, result in claims_by_site.items():
        if result.get("_fallback"):
            flags.append(f"{site}: verified claims are not available yet; contract placeholder was excluded.")
            continue
        if result.get("_error"):
            flags.append(f"{site}: claim lookup failed: {result['_error']}")
        for claim in result.get("claims", []):
            if claim.get("status") != "verified" or (systems and claim.get("system") not in systems):
                continue
            if claim.get("grade") not in ("attested", "debated", "inferred") or not claim.get("sources"):
                flags.append(f"{site}: a claim was omitted because its grade or source was incomplete.")
                continue
            verified_claims.append(claim)
    evidence = [passage for result in evidence_by_site.values()
                for passage in result.get("results", [])]
    for site, result in evidence_by_site.items():
        if result.get("_error"):
            flags.append(f"{site}: evidence search failed: {result['_error']}")
    record("archaeologist", started, f"retrieved {len(verified_claims)} verified claims and {len(evidence)} passages")
    started = time.perf_counter()
    engineer_notes = _engineering_notes(verified_claims, evidence)
    record("engineer", started, f"checked {len(engineer_notes)} system findings")

    estimate_card = None
    calculation_result = None
    if routed.get("calculation"):
        started = time.perf_counter()
        calculation_result, calculation_flag = _run_calculation(routed["calculation"], message, history, tools)
        if calculation_flag:
            flags.append(calculation_flag)
        record("estimator", started, f"ran {routed['calculation']} tool" if calculation_result else "calculation unavailable")
    elif routed["intent"] == "estimate" and sites:
        started = time.perf_counter()
        estimate_card, estimate_flag = _build_estimator_card(sites[0], tools)
        if estimate_flag:
            flags.append(estimate_flag)
        record("estimator", started, "ran estimate tool for requested site" if estimate_card else "no preset estimate available")
    else:
        started = time.perf_counter()
        record("estimator", started, "no calculation requested")

    started = time.perf_counter()
    teardown_cards = [card for site in sites
                      if (card := _build_teardown_card(site, verified_claims, selected_systems))]
    record("builder", started, f"prepared {sum(len(card['rows']) for card in teardown_cards)} teardown rows")

    started = time.perf_counter()
    citations = _citations(verified_claims, evidence)
    critic_flags = list(flags)
    if not verified_claims and not evidence and not calculation_result and not estimate_card:
        critic_flags.append("No evidence was returned by the tools; answer is limited to that limitation.")
    if evidence and not verified_claims:
        critic_flags.append("Search passages are cited as unreviewed evidence because no verified claim was available.")
    if routed["intent"] == "fringe":
        critic_flags.append("Fringe premise is not supported as fact by the evidence returned.")
    record("critic", started, f"passed={not critic_flags}, flags={len(critic_flags)}")

    started = time.perf_counter()
    answer = _present(routed, verified_claims, evidence, estimate_card, calculation_result, citations, engineer_notes)
    cards = list(teardown_cards)
    if estimate_card:
        cards.append(estimate_card)
    record("presenter", started, f"answer length={len(answer)} characters, cards={len(cards)}")
    return {
        "answer_md": answer,
        "intent": routed["intent"],
        "sites": sites,
        "systems": systems,
        "clarifying_question": None,
        "citations": citations,
        "cards": cards,
        "critic": {"passed": not critic_flags, "flags": critic_flags, "retries": 0},
        "trace": trace,
    }


def _read_tool_result(future: Any, key: str) -> dict[str, Any]:
    try:
        result = future.result()
        if not isinstance(result, dict):
            return {key: result if isinstance(result, list) else []}
        return result
    except ToolAPIError as error:
        return {key: [], "_error": str(error)}


def _run_calculation(kind: str, message: str, history: list[dict[str, str]] | None,
                     tools: Any) -> tuple[dict[str, Any] | None, str | None]:
    context = " ".join(item["content"] for item in (history or []) if item.get("role") == "user")
    text = f"{context} {message}".casefold()
    if kind == "haul_force":
        mass = re.search(r"([\d,]+(?:\.\d+)?)\s*(tonnes?|tons?|kilograms?|kgs?|kg)\b", text)
        friction = re.search(r"friction(?:\s+coefficient)?(?:\s+of)?\s*([\d.]+)", text)
        pull = re.search(r"([\d.]+)\s*(?:n|newtons?)\s*(?:of\s+pull\s*)?(?:per\s+person|/\s*person)", text)
        slope = re.search(r"([\d.]+)\s*(?:degrees?|°)\b", text)
        if not mass or not friction or not pull:
            return None, "Haul-force estimate needs a load mass, friction coefficient, and pull per person."
        mass_value = float(mass.group(1).replace(",", ""))
        mass_kg = mass_value * 1000 if mass.group(2).startswith(("tonne", "ton")) else mass_value
        slope_value = float(slope.group(1)) if slope else (0 if "flat" in text else None)
        if slope_value is None:
            return None, "Haul-force estimate needs a slope angle, or a statement that the ground is flat."
        inputs = {"mass_kg": mass_kg, "slope_deg": slope_value,
                  "friction_coeff": float(friction.group(1)), "pull_per_person_n": float(pull.group(1))}
        try:
            return {"kind": kind, "input": inputs, "result": tools.haul_force(**inputs)}, None
        except ToolAPIError as error:
            return None, str(error)

    volume = re.search(r"([\d,]+(?:\.\d+)?)\s*(?:cubic\s+meters?|cubic\s+metres?|m3|m³)", text)
    if not volume:
        return None, "Carbon estimate needs a volume in cubic metres."
    material_aliases = ("rammed earth", "fired brick", "clay brick", "limestone", "granite", "brick")
    materials = [material for material in material_aliases
                 if re.search(rf"\b{re.escape(material)}\b", text)]
    if any(material in materials for material in ("fired brick", "clay brick")):
        materials = [material for material in materials if material != "brick"]
    if not materials:
        return None, "Carbon estimate needs a known material, such as limestone or fired brick."
    volume_m3 = float(volume.group(1).replace(",", ""))
    results = []
    for material in materials:
        try:
            results.append({"material": material,
                            "result": tools.carbon(material=material, volume_m3=volume_m3)})
        except ToolAPIError as error:
            return None, str(error)
    return {"kind": kind, "volume_m3": volume_m3, "results": results}, None


def _build_estimator_card(site: str, tools: Any) -> tuple[dict[str, Any] | None, str | None]:
    try:
        presets = tools.get_presets()
        preset = presets.get(site)
        if not preset:
            return None, f"No estimator preset exists for {site}."
        result: dict[str, Any] = {}
        for era in ("ancient", "modern"):
            inputs = preset[era]
            result[era] = tools.estimate(
                quantity=preset["quantity"], unit=preset["unit"],
                crews=inputs["crews"], crew_size=inputs["crew_size"],
                rate_per_crew_day=inputs["rate_per_crew_day"],
                days_per_year=inputs["days_per_year"],
            )
        card_preset = {key: value for key, value in preset.items() if key not in ("draft", "quantity_note")}
        return {"type": "estimator", "site": site, "preset": card_preset, "result": result}, None
    except (ToolAPIError, KeyError, TypeError) as error:
        return None, f"Estimator tools could not complete the calculation: {error}"


def _build_teardown_card(site: str, claims: list[dict[str, Any]], systems: list[str]) -> dict[str, Any] | None:
    rows = []
    seen = set()
    for claim in claims:
        system = claim.get("system")
        if system not in systems or system in seen:
            continue
        seen.add(system)
        rows.append({
            "system": system,
            "grade": claim.get("grade", "inferred"),
            "ancient": claim.get("statement", ""),
            "evidence": claim.get("quote", ""),
            "modern": claim.get("modern_equivalent", ""),
            "lesson": claim.get("lesson", ""),
            "claim_ids": [claim["claim_id"]] if claim.get("claim_id") else [],
        })
        if len(rows) == 4:
            break
    return {"type": "teardown", "site": site, "rows": rows} if rows else None


def _citations(claims: list[dict[str, Any]], evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    citations = []
    seen = set()
    for claim in claims:
        source = next((item for item in claim.get("sources", []) if item.get("source_id")), None)
        if source is None:
            continue
        source_id = source["source_id"]
        seen.add(source_id)
        citations.append({
            "n": len(citations) + 1,
            "claim_id": claim.get("claim_id"),
            "source_id": source_id,
            "title": source.get("title", ""),
            "url": source.get("url", ""),
            "locator": source.get("locator"),
            "grade": claim.get("grade", "inferred"),
        })
    for passage in evidence:
        source_id = passage.get("source_id")
        if not source_id or source_id in seen:
            continue
        seen.add(source_id)
        citations.append({
            "n": len(citations) + 1,
            "claim_id": None,
            "source_id": source_id,
            "title": passage.get("title", ""),
            "url": passage.get("url", ""),
            "locator": passage.get("locator"),
            "grade": "inferred",
        })
    return citations


def _engineering_notes(claims: list[dict[str, Any]], evidence: list[dict[str, Any]]) -> list[str]:
    notes = []
    if not claims and evidence:
        notes.append("Search passages are available, but no verified claims were returned.")
    return notes


def _present(routed: dict[str, Any], claims: list[dict[str, Any]], evidence: list[dict[str, Any]],
             estimate_card: dict[str, Any] | None, calculation_result: dict[str, Any] | None,
             citations: list[dict[str, Any]], engineer_notes: list[str]) -> str:
    intent = routed["intent"]
    site_names = {"giza": "Giza", "uruk": "Uruk", "mohenjo": "Mohenjo-daro", "qin": "Qin"}
    citation_by_claim = {citation["claim_id"]: citation["n"] for citation in citations if citation.get("claim_id")}
    citation_by_source = {citation["source_id"]: citation["n"] for citation in citations if not citation.get("claim_id")}
    if calculation_result and calculation_result["kind"] == "haul_force":
        result = calculation_result["result"]
        assumptions = "; ".join(result.get("assumptions", []))
        return (f"The tool estimates {result['people_needed']} people are needed, with a required pull of "
                f"{result['force_kn']:g} kN. Assumptions: {assumptions}.")
    if calculation_result and calculation_result["kind"] == "carbon":
        statements = []
        for item in calculation_result["results"]:
            result = item["result"]
            assumptions = "; ".join(result.get("assumptions", []))
            statements.append(f"{result['material']}: {result['kgco2e']:g} kgCO2e. Source: {result['source']}. {assumptions}.")
        return f"For {calculation_result['volume_m3']:g} m3, " + " ".join(statements)
    site_name = site_names.get(routed["sites"][0], "the requested site") if routed["sites"] else "the requested site"
    if intent == "fringe":
        if claims:
            claim = claims[0]
            cite = citation_by_claim.get(claim.get("claim_id"))
            footnote = f"[^{cite}]" if cite else ""
            return (f"The fringe explanation is not supported as fact. For {site_name}, the verified material instead describes "
                    f"{claim.get('statement', 'documented construction evidence')}{footnote}.")
        passage = _first_passage(routed["sites"], evidence, routed["query"], routed["systems"])
        if passage:
            number = citation_by_source.get(passage.get("source_id"))
            footnote = f"[^{number}]" if number else ""
            excerpt = _evidence_excerpt(passage, routed["query"], routed["systems"])
            return (f"This fringe explanation is not supported as fact in the evidence retrieved for {site_name}. "
                    f"An indexed source states: \"{excerpt}\"{footnote}")
        return f"This fringe explanation is not supported by verified evidence for {site_name}."
    if estimate_card:
        old = estimate_card["result"]["ancient"]
        modern = estimate_card["result"]["modern"]
        unit = estimate_card["preset"]["unit"]
        answer = (f"Using the site's current estimator assumptions for {estimate_card['preset']['quantity']:,} {unit}, "
                  f"the ancient-rate scenario is about {old['years']:g} years ({old['people']:,} people), "
                  f"while the modern-rate scenario is about {modern['years']:g} years "
                  f"({modern['people']:,} people). These are straight-line scenarios, not a construction schedule.")
        answer += " Crew sizes, production rates, and working calendars are assumptions."
        if estimate_card["preset"].get("quantity_tag") == "assumed":
            answer += " The quantity is also an assumption."
        return answer
    if claims:
        statements = []
        for claim in claims[:6]:
            citation_number = citation_by_claim.get(claim.get("claim_id"))
            footnote = f"[^{citation_number}]" if citation_number else ""
            claim_site = site_names.get(claim.get("site"), site_name)
            statements.append(f"{claim_site}: {claim.get('statement', '').strip()}{footnote}")
        answer = " ".join(statements)
        if intent == "playbook":
            selected = claims[:1]
            modern = selected[0].get("modern_equivalent")
            lesson = selected[0].get("lesson")
            if modern:
                answer += f" A modern equivalent is {modern}."
            if lesson:
                answer += f" The practical lesson is {lesson}"
        return answer
    if evidence:
        statements = []
        for site in routed["sites"]:
            passage = _first_passage([site], evidence, routed["query"], routed["systems"])
            if not passage:
                continue
            number = citation_by_source.get(passage.get("source_id"))
            footnote = f"[^{number}]" if number else ""
            excerpt = _evidence_excerpt(passage, routed["query"], routed["systems"])
            statements.append(f"{site_names.get(site, site)}: \"{excerpt}\"{footnote}")
        if statements:
            return ("The indexed sources contain the following relevant passages, but they have not yet been converted "
                    "into reviewed claims: " + " ".join(statements))
    detail = f" {engineer_notes[0]}" if engineer_notes else ""
    return f"I could not retrieve supporting evidence for {site_name}.{detail}"


def _first_passage(sites: list[str], evidence: list[dict[str, Any]], query: str,
                   systems: list[str]) -> dict[str, Any] | None:
    candidates = [passage for passage in evidence if passage.get("site") in sites]
    if not candidates:
        return None
    cues = {cue for system in systems for cue in _EVIDENCE_CUES.get(system, ())}
    query_terms = set(re.findall(r"[a-z]{4,}", query.casefold()))
    priority_cues = set()
    query_lower = query.casefold()
    if "wheel" in query_lower and any(term in query_lower for term in ("move", "drag", "transport")):
        priority_cues.update(("sledge", "sledges", "sled"))
    if "moon" in query_lower and any(term in query_lower for term in ("see", "visible")):
        priority_cues.update(("visible", "myth", "false belief"))
    cues.update(priority_cues)

    def relevance(passage: dict[str, Any]) -> float:
        text = passage.get("text", "").casefold()
        cue_matches = sum((50 if cue in priority_cues else 10) for cue in cues if cue in text)
        query_matches = sum(term in text for term in query_terms)
        return cue_matches * 10 + query_matches + float(passage.get("score", 0))

    return max(candidates, key=relevance)


def _evidence_excerpt(passage: dict[str, Any], query: str, systems: list[str]) -> str:
    text = passage.get("text", "").strip()
    sentences = [sentence.strip() for sentence in re.split(r"(?<=[.!?])\s+", text) if sentence.strip()]
    if not sentences:
        return text[:400]
    terms = set(re.findall(r"[a-z]{4,}", query.casefold()))
    cues = {cue for system in systems for cue in _EVIDENCE_CUES.get(system, ())}
    query_lower = query.casefold()
    if "wheel" in query_lower and any(term in query_lower for term in ("move", "drag", "transport")):
        cues.update(("sledge", "sledges", "sled"))
    if "moon" in query_lower and any(term in query_lower for term in ("see", "visible")):
        cues.update(("visible", "myth", "false belief"))
    sentence = max(sentences, key=lambda candidate: (
        sum(cue in candidate.casefold() for cue in cues) * 10
        + sum(term in candidate.casefold() for term in terms)
    ))
    return sentence[:500]


def _empty_response(routed: dict[str, Any], question: str, trace: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "answer_md": question,
        "intent": routed["intent"],
        "sites": routed["sites"],
        "systems": routed["systems"],
        "clarifying_question": question,
        "citations": [],
        "cards": [],
        "critic": {"passed": True, "flags": [], "retries": 0},
        "trace": trace,
    }