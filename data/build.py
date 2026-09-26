"""One-command rebuild:  python -m data.build   (or `make data`)

    python -m data.build                  registry check -> ingest -> keyword tags -> embed -> tests
    python -m data.build --llm            + claude-sonnet-5 tags for untagged passages (needs ANTHROPIC_API_KEY)
    python -m data.build --offline        rebuild from the data/raw cache only
    python -m data.build --small          curated sources only (no OpenAlex discovery): fast, for an early hand-off
    python -m data.build --skip-ingest    re-tag + re-embed the existing passages.jsonl
    python -m data.build --sites qin      rebuild one site (contract ids: giza, uruk, mohenjo, qin)
"""
from __future__ import annotations

import argparse
import sys

from . import ingest, tagging, test_search


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--sites")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--small", action="store_true", help="skip OpenAlex discovery")
    ap.add_argument("--allow-large", action="store_true")
    ap.add_argument("--llm", action="store_true")
    ap.add_argument("--llm-max", type=int, default=400)
    ap.add_argument("--skip-ingest", action="store_true")
    ap.add_argument("--skip-index", action="store_true")
    ap.add_argument("--no-test", action="store_true")
    a = ap.parse_args(argv)

    if not a.skip_ingest:
        args = []
        if a.sites:
            args += ["--sites", a.sites]
        if a.offline:
            args.append("--offline")
        if a.small:
            args.append("--no-discovery")
        if a.allow_large:
            args.append("--allow-large")
        ingest.main(args)
    tagging.main(["--llm", "--max", str(a.llm_max)] if a.llm else [])
    if not a.skip_index:
        from . import index
        index.build()
    if a.no_test:
        return 0
    from . import search
    search.reload()
    return test_search.main()


if __name__ == "__main__":
    sys.exit(main())
