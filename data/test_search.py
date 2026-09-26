"""Acceptance checks for consumable Stratum corpus artifacts.

    python -m data.test_search
    pytest data/test_search.py
"""
from __future__ import annotations

import json
import sys

import yaml

from . import config


def _passages():
    assert config.PASSAGES_JSONL.exists(), (
        f"{config.PASSAGES_JSONL} does not exist"
    )

    passages = []

    for line_number, line in enumerate(
        config.PASSAGES_JSONL.read_text(
            encoding="utf-8"
        ).splitlines(),
        start=1,
    ):
        if not line.strip():
            continue

        try:
            passage = json.loads(line)
        except json.JSONDecodeError as exc:
            raise AssertionError(
                f"invalid JSONL at line "
                f"{line_number}: {exc}"
            ) from exc

        passages.append(passage)

    return passages


def _resolved_payload():
    assert config.RESOLVED_YAML.exists(), (
        f"{config.RESOLVED_YAML} does not exist"
    )

    payload = yaml.safe_load(
        config.RESOLVED_YAML.read_text(
            encoding="utf-8"
        )
    )

    if payload is None:
        payload = {}

    assert isinstance(payload, dict), (
        "sources.resolved.yaml must contain "
        "a mapping"
    )

    assert "sources" in payload, (
        "sources.resolved.yaml is missing "
        "'sources'"
    )
    assert isinstance(
        payload["sources"],
        list,
    ), "'sources' must be a list"

    assert "listed_but_not_ingested" in payload, (
        "sources.resolved.yaml is missing "
        "'listed_but_not_ingested'"
    )
    assert isinstance(
        payload["listed_but_not_ingested"],
        list,
    ), (
        "'listed_but_not_ingested' "
        "must be a list"
    )

    return payload


def test_resolved_sources_file_is_consumable():
    _resolved_payload()


def test_resolved_source_entries_are_valid():
    payload = _resolved_payload()

    for source in payload["sources"]:
        assert isinstance(
            source,
            dict,
        ), "resolved source entry must be a mapping"

        for field in (
            "id",
            "site",
            "type",
            "title",
            "url",
            "license",
        ):
            assert source.get(field), (
                f"resolved source missing "
                f"{field!r}: {source}"
            )

        assert source["site"] in config.SITES, (
            f"resolved source has unknown site "
            f"{source['site']!r}"
        )


def test_listed_not_ingested_entries_are_valid():
    payload = _resolved_payload()

    for source in payload[
        "listed_but_not_ingested"
    ]:
        assert isinstance(
            source,
            dict,
        ), (
            "listed-but-not-ingested entry "
            "must be a mapping"
        )

        assert source.get("id"), (
            "listed-but-not-ingested source "
            "is missing 'id'"
        )


def test_passages_file_is_consumable():
    _passages()


def test_passage_entries_are_valid():
    passages = _passages()

    for passage in passages:
        assert isinstance(
            passage,
            dict,
        ), "passage entry must be an object"

        missing = [
            field
            for field in config.PASSAGE_KEYS
            if field not in passage
        ]

        assert not missing, (
            f"{passage.get('id')} "
            f"missing fields {missing}"
        )

        assert passage["site"] in config.SITES, (
            f"{passage.get('id')} has "
            f"unknown site "
            f"{passage['site']!r}"
        )

        assert isinstance(
            passage["system_tags"],
            list,
        ), (
            f"{passage.get('id')} "
            f"system_tags must be a list"
        )

        unknown_systems = (
            set(passage["system_tags"])
            - set(config.system_ids())
        )

        assert not unknown_systems, (
            f"{passage.get('id')} has "
            f"unknown system tags "
            f"{sorted(unknown_systems)}"
        )

        assert passage.get("license"), (
            f"{passage.get('id')} "
            f"is missing a license"
        )


def test_passage_ids_are_unique():
    passages = _passages()

    ids = [
        passage["id"]
        for passage in passages
    ]

    assert len(ids) == len(set(ids)), (
        "duplicate passage ids"
    )


def test_passage_sources_exist():
    passages = _passages()
    payload = _resolved_payload()

    resolved_ids = {
        source["id"]
        for source in payload["sources"]
    }

    orphaned = {
        passage["source_id"]
        for passage in passages
        if passage["source_id"]
        not in resolved_ids
    }

    assert not orphaned, (
        "passages reference unresolved sources: "
        f"{sorted(orphaned)}"
    )


CHECKS = [
    value
    for name, value
    in list(globals().items())
    if (
        name.startswith("test_")
        and callable(value)
    )
]


def main() -> int:
    failed = 0

    for fn in CHECKS:
        try:
            fn()
            print(f"PASS  {fn.__name__}")
        except AssertionError as exc:
            failed += 1
            print(
                f"FAIL  {fn.__name__}: "
                f"{exc}"
            )
        except Exception as exc:
            failed += 1
            print(
                f"ERROR {fn.__name__}: "
                f"{type(exc).__name__}: "
                f"{exc}"
            )

    print(
        f"\n{len(CHECKS) - failed}/"
        f"{len(CHECKS)} checks passed"
    )

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
