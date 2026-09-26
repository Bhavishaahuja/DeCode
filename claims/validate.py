"""Check claims/verified/claims.jsonl against Contract 2 and our coverage goals.

Exits 1 if any claim is broken, so it works in a Makefile or CI.
Coverage gaps are printed as warnings unless you pass --strict.

Usage:
    python -m claims.validate
    python -m claims.validate --strict     # coverage gaps fail too (use at hour 16)
"""

import argparse
import sys

from claims.common import (
    REQUIRED_SYSTEMS, SITES, VERIFIED_PATH,
    load_passages, read_jsonl, system_ids, validate_claim,
)

TARGET_MIN = 30
MIN_SYSTEMS = 5


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true", help="treat coverage gaps as failures")
    parser.add_argument("--path", default=str(VERIFIED_PATH))
    args = parser.parse_args()

    claims = read_jsonl(args.path)
    passages = load_passages()
    systems = system_ids()

    broken = 0
    seen_ids = set()
    for claim in claims:
        problems = validate_claim(claim, passages, systems=systems, verified=True)
        if claim.get("claim_id") in seen_ids:
            problems.append("duplicate claim_id")
        seen_ids.add(claim.get("claim_id"))
        if problems:
            broken += 1
            print(f"FAIL {claim.get('claim_id')}")
            for problem in problems:
                print(f"     - {problem}")

    gaps = []
    for site in SITES:
        site_claims = []
        for claim in claims:
            if claim.get("site") == site:
                site_claims.append(claim)
        covered = set()
        for claim in site_claims:
            covered.add(claim.get("system"))
        missing = []
        for system in REQUIRED_SYSTEMS:
            if system not in covered:
                missing.append(system)
        print(f"{site}: {len(site_claims)} claims, {len(covered)} systems"
              + (f", missing {', '.join(missing)}" if missing else ""))
        if len(site_claims) < TARGET_MIN:
            gaps.append(f"{site} has {len(site_claims)} claims (target {TARGET_MIN})")
        if len(covered) < MIN_SYSTEMS:
            gaps.append(f"{site} covers {len(covered)} systems (target {MIN_SYSTEMS})")
        if missing:
            gaps.append(f"{site} missing required systems: {', '.join(missing)}")

    print(f"\n{len(claims)} claims, {broken} broken")
    for gap in gaps:
        print(f"{'FAIL' if args.strict else 'WARN'} coverage: {gap}")

    if broken or (args.strict and gaps):
        sys.exit(1)


if __name__ == "__main__":
    main()
