"""Tiny review CLI: accept, edit, or reject each draft claim by hand.

Accepted claims get a final id (site-system-NNN) and are appended to
claims/verified/claims.jsonl. Every decision is logged in
claims/draft/decisions.jsonl, so you can quit any time and pick up later.

Usage:
    python -m claims.review                         # everything undecided
    python -m claims.review --site giza --system workforce
    python -m claims.review --coverage              # just show the scoreboard
    python -m claims.review --reviewer bhavisha     # stamp your own name into reviewed_by
"""

import argparse
import os
import textwrap

from claims.common import (
    DECISIONS_PATH, DEDUPED_PATH, DRAFT_PATH, GRADES, REQUIRED_SYSTEMS, SITES,
    VERIFIED_ID_PATTERN, VERIFIED_PATH,
    append_jsonl, load_passages, read_jsonl, squash_spaces, system_ids, validate_claim,
)

REVIEWER = "dev2"
TARGET_MIN = 30
TARGET_MAX = 50

os.system("")  # turns on ANSI colors in Windows terminals
BOLD = "\033[1m"
DIM = "\033[2m"
YELLOW = "\033[33m"
GREEN = "\033[32m"
RED = "\033[31m"
RESET = "\033[0m"


def wrap(text, indent="    "):
    return textwrap.fill(text or "", width=96, initial_indent=indent, subsequent_indent=indent)


def show_coverage(verified, systems):
    print(f"\n{BOLD}Coverage (verified claims){RESET}   target {TARGET_MIN}-{TARGET_MAX} per site, "
          f"5+ systems, must include {', '.join(REQUIRED_SYSTEMS)}")
    header = "system".ljust(20)
    for site in SITES:
        header += site.rjust(9)
    print(header)
    totals = {site: 0 for site in SITES}
    for system in systems:
        line = system.ljust(20)
        for site in SITES:
            n = 0
            for claim in verified:
                if claim["site"] == site and claim["system"] == system:
                    n += 1
            totals[site] += n
            cell = str(n).rjust(9)
            if system in REQUIRED_SYSTEMS and n == 0:
                cell = RED + cell + RESET
            line += cell
        print(line)
    total_line = "TOTAL".ljust(20)
    for site in SITES:
        color = GREEN if totals[site] >= TARGET_MIN else YELLOW
        total_line += color + str(totals[site]).rjust(9) + RESET
    print(total_line + "\n")


def passage_excerpt(passage, quote, width=700):
    """Show the passage around the quote with the quote highlighted."""
    text = squash_spaces(passage["text"])
    quote = squash_spaces(quote)
    at = text.find(quote)
    if at == -1:
        return text[:width] + ("..." if len(text) > width else "")
    start = max(0, at - 250)
    end = min(len(text), at + len(quote) + 250)
    before = ("..." if start > 0 else "") + text[start:at]
    after = text[at + len(quote):end] + ("..." if end < len(text) else "")
    return before + YELLOW + BOLD + quote + RESET + after


def show_claim(claim, passages, position, total):
    print("=" * 96)
    print(f"{BOLD}[{position}/{total}] {claim['claim_id']}{RESET}   site={claim['site']}   system={claim['system']}")
    grade_line = f"grade: {BOLD}{claim['grade']}{RESET}"
    if claim.get("grade_conflict"):
        grade_line += f"   {RED}grade conflict across duplicates: {', '.join(claim['grade_conflict'])}{RESET}"
    print(grade_line)
    print(f"{DIM}why: {claim.get('grade_reason') or 'n/a'}{RESET}")
    print(f"\n{BOLD}statement{RESET}\n{wrap(claim['statement'])}")
    print(f"{BOLD}quote{RESET}\n{wrap(claim['quote'])}")
    print(f"{BOLD}modern_equivalent{RESET}\n{wrap(claim['modern_equivalent'])}")
    print(f"{BOLD}lesson{RESET}\n{wrap(claim['lesson'])}")
    print(f"{BOLD}sources{RESET}")
    for source in claim["sources"]:
        passage = passages.get(source["passage_id"], {})
        print(f"    {source['passage_id']}  {source['title']}, {source.get('locator') or 'no locator'}  "
              f"[{passage.get('source_type', '?')}, {passage.get('year', '?')}]")
    first = passages.get(claim["sources"][0]["passage_id"])
    if first:
        print(f"\n{BOLD}passage context{RESET}")
        print(textwrap.fill(passage_excerpt(first, claim["quote"]), width=96,
                            initial_indent="    ", subsequent_indent="    "))
    print()


def ask(prompt, current):
    shown = current if len(str(current)) < 80 else str(current)[:77] + "..."
    answer = input(f"  {prompt} [{shown}]: ").strip()
    return answer if answer else current


def edit_claim(claim, systems):
    print(f"{DIM}  Enter keeps the current value.{RESET}")
    edited = dict(claim)
    edited["statement"] = ask("statement", claim["statement"])
    edited["quote"] = ask("quote (must be verbatim from the passage)", claim["quote"])
    while True:
        grade = ask(f"grade {GRADES}", claim["grade"])
        if grade in GRADES:
            edited["grade"] = grade
            break
        print("  pick one of", GRADES)
    while True:
        system = ask("system", claim["system"])
        if system in systems:
            edited["system"] = system
            break
        print("  pick one of", systems)
    edited["modern_equivalent"] = ask("modern_equivalent", claim["modern_equivalent"])
    edited["lesson"] = ask("lesson", claim["lesson"])
    return edited


def next_claim_id(site, system, verified):
    highest = 0
    for claim in verified:
        match = VERIFIED_ID_PATTERN.match(claim["claim_id"])
        if match and match.group(1) == site and match.group(2) == system:
            highest = max(highest, int(match.group(3)))
    return f"{site}-{system}-{highest + 1:03d}"


def to_verified(claim, verified, reviewer=REVIEWER):
    final = {
        "claim_id": next_claim_id(claim["site"], claim["system"], verified),
        "site": claim["site"],
        "system": claim["system"],
        "statement": claim["statement"].strip(),
        "quote": claim["quote"].strip(),
        "grade": claim["grade"],
        "sources": claim["sources"],
        "modern_equivalent": claim["modern_equivalent"].strip(),
        "lesson": claim["lesson"].strip(),
        "status": "verified",
        "reviewed_by": reviewer,
    }
    return final


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", choices=SITES)
    parser.add_argument("--system")
    parser.add_argument("--grade", choices=GRADES)
    parser.add_argument("--coverage", action="store_true", help="show coverage and exit")
    parser.add_argument("--reviewer", default=REVIEWER, help="name stamped into reviewed_by (default dev2)")
    args = parser.parse_args()
    reviewer = args.reviewer.strip() or REVIEWER

    systems = system_ids()
    passages = load_passages()
    verified = read_jsonl(VERIFIED_PATH)
    show_coverage(verified, systems)
    if args.coverage:
        return

    draft_path = DEDUPED_PATH if DEDUPED_PATH.exists() else DRAFT_PATH
    drafts = read_jsonl(draft_path)
    decided = set()
    for row in read_jsonl(DECISIONS_PATH):
        decided.add(row["draft_id"])

    queue = []
    for claim in drafts:
        if claim["claim_id"] in decided:
            continue
        if args.site and claim["site"] != args.site:
            continue
        if args.system and claim["system"] != args.system:
            continue
        if args.grade and claim["grade"] != args.grade:
            continue
        queue.append(claim)

    print(f"reviewing {len(queue)} undecided drafts from {draft_path.name}")
    if not queue:
        return

    for position, claim in enumerate(queue, start=1):
        current = claim
        while True:
            show_claim(current, passages, position, len(queue))
            choice = input("  [a]ccept  [e]dit  [r]eject  [s]kip  [q]uit > ").strip().lower()

            if choice == "q":
                show_coverage(verified, systems)
                return
            if choice == "s":
                break
            if choice == "r":
                reason = input("  reason (optional): ").strip()
                append_jsonl(DECISIONS_PATH, {"draft_id": claim["claim_id"], "decision": "rejected",
                                              "reason": reason, "reviewed_by": reviewer})
                print(f"  {RED}rejected{RESET}")
                break
            if choice == "e":
                current = edit_claim(current, systems)
                continue
            if choice == "a":
                final = to_verified(current, verified, reviewer)
                problems = validate_claim(final, passages, systems=systems, verified=True)
                if problems:
                    print(f"  {RED}can't accept yet:{RESET}")
                    for problem in problems:
                        print(f"    - {problem}")
                    print("  fix it with [e]dit, or [r]eject")
                    input("  (enter to continue)")
                    continue
                append_jsonl(VERIFIED_PATH, final)
                verified.append(final)
                append_jsonl(DECISIONS_PATH, {"draft_id": claim["claim_id"], "decision": "accepted",
                                              "claim_id": final["claim_id"], "edited": current != claim,
                                              "reviewed_by": reviewer})
                print(f"  {GREEN}accepted as {final['claim_id']}{RESET}")
                break
            print("  type a, e, r, s, or q")

    show_coverage(verified, systems)


if __name__ == "__main__":
    main()
