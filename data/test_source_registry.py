from datetime import datetime, timezone

import pytest
import yaml

from data.corpus_models import (
    AccessType,
    SourceStatus,
)
from data.source_registry import SourceRegistry


NOW = datetime(
    2026,
    9,
    26,
    20,
    0,
    tzinfo=timezone.utc,
)


def write_yaml(path, payload):
    path.write_text(
        yaml.safe_dump(
            payload,
            sort_keys=False,
        ),
        encoding="utf-8",
    )


def catalog_source(**overrides):
    source = {
        "id": "source",
        "site": "giza",
        "type": "journal_article",
        "title": "Source",
        "url": "https://example.org/source",
        "license": "CC BY 4.0",
        "fetch": {
            "kind": "url",
            "url": "https://example.org/source",
        },
    }
    source.update(overrides)
    return source


def resolved_source(**overrides):
    source = {
        "id": "source",
        "site": "giza",
        "type": "journal_article",
        "title": "Resolved Source",
        "url": "https://example.org/resolved",
        "license": "CC BY 4.0",
        "retrieved": "2026-09-26",
        "n_passages": 12,
    }
    source.update(overrides)
    return source


def make_registry(
    tmp_path,
    catalog=None,
    resolved=None,
    listed=None,
    logs=(),
):
    sources_path = tmp_path / "sources.yaml"
    resolved_path = (
        tmp_path / "sources.resolved.yaml"
    )

    write_yaml(
        sources_path,
        {
            "sources": catalog or [],
        },
    )

    write_yaml(
        resolved_path,
        {
            "generated":
                "2026-09-26T20:00:00",
            "sources": resolved or [],
            "listed_but_not_ingested":
                listed or [],
        },
    )

    return SourceRegistry(
        sources_path=sources_path,
        resolved_path=resolved_path,
        ingest_log_lines=logs,
        ingest_log_time=NOW,
    )


def test_catalog_only_source_is_unknown(
    tmp_path,
):
    registry = make_registry(
        tmp_path,
        catalog=[catalog_source()],
    )

    record = registry.get_by_id(
        " Source "
    )

    assert record is not None
    assert record.source_id == "source"
    assert record.name == "Source"
    assert record.status is SourceStatus.UNKNOWN
    assert record.access_type is None
    assert record.access_path is None
    assert record.last_validated is None
    assert record.validation_reason is None
    assert record.metadata["site"] == "giza"
    assert (
        record.metadata["source_type"]
        == "journal_article"
    )


def test_resolved_source_is_valid(
    tmp_path,
):
    registry = make_registry(
        tmp_path,
        catalog=[catalog_source()],
        resolved=[resolved_source()],
    )

    record = registry.get_by_id(
        "source"
    )

    assert record is not None
    assert record.status is SourceStatus.VALID
    assert record.name == "Resolved Source"
    assert record.base_url == (
        "https://example.org/source"
    )
    assert (
        record.access_type
        is AccessType.WEB
    )
    assert record.access_path == (
        "https://example.org/resolved"
    )
    assert record.last_validated == datetime(
        2026,
        9,
        26,
        tzinfo=timezone.utc,
    )
    assert (
        record.validation_reason
        == "successfully ingested"
    )
    assert (
        record.metadata["n_passages"]
        == "12"
    )


def test_success_log_marks_source_valid(
    tmp_path,
):
    registry = make_registry(
        tmp_path,
        catalog=[catalog_source()],
        logs=[
            "  [ok] source: 7 passages",
        ],
    )

    record = registry.get_by_id(
        "source"
    )

    assert record is not None
    assert record.status is SourceStatus.VALID
    assert record.last_validated == NOW
    assert (
        record.validation_reason
        == "7 passages"
    )


def test_failed_log_marks_source_invalid(
    tmp_path,
):
    registry = make_registry(
        tmp_path,
        catalog=[catalog_source()],
        logs=[
            (
                "  [skip] source: "
                "HTTP 404 for "
                "https://example.org/source"
            ),
        ],
    )

    record = registry.get_by_id(
        "source"
    )

    assert record is not None
    assert (
        record.status
        is SourceStatus.INVALID
    )
    assert record.access_type is None
    assert record.access_path is None
    assert record.last_validated == NOW
    assert record.validation_reason == (
        "HTTP 404 for "
        "https://example.org/source"
    )


def test_deferred_source_remains_unknown(
    tmp_path,
):
    registry = make_registry(
        tmp_path,
        catalog=[catalog_source()],
        logs=[
            (
                "  [ASK FIRST] source: "
                "download exceeds limit"
            ),
        ],
    )

    assert (
        registry.status("source")
        is SourceStatus.UNKNOWN
    )


def test_deferred_does_not_override_resolved(
    tmp_path,
):
    registry = make_registry(
        tmp_path,
        catalog=[catalog_source()],
        resolved=[resolved_source()],
        logs=[
            (
                "  [ASK FIRST] source: "
                "download exceeds limit"
            ),
        ],
    )

    assert (
        registry.status("source")
        is SourceStatus.VALID
    )


def test_failed_log_overrides_old_resolved_state(
    tmp_path,
):
    registry = make_registry(
        tmp_path,
        catalog=[catalog_source()],
        resolved=[resolved_source()],
        logs=[
            (
                "  [skip] source: "
                "source no longer reachable"
            ),
        ],
    )

    assert (
        registry.status("source")
        is SourceStatus.INVALID
    )


def test_latest_log_outcome_wins(
    tmp_path,
):
    registry = make_registry(
        tmp_path,
        catalog=[catalog_source()],
        logs=[
            (
                "  [skip] source: "
                "temporary failure"
            ),
            "  [ok] source: 3 passages",
        ],
    )

    assert (
        registry.status("source")
        is SourceStatus.VALID
    )


def test_disabled_source_is_not_invalid(
    tmp_path,
):
    registry = make_registry(
        tmp_path,
        catalog=[
            catalog_source(
                enabled=False,
                note="login required",
            )
        ],
        listed=[
            {
                "id": "source",
                "site": "giza",
                "title": "Source",
                "url":
                    "https://example.org/source",
                "license": "CC BY 4.0",
                "note": "login required",
            }
        ],
    )

    record = registry.get_by_id(
        "source"
    )

    assert record is not None
    assert (
        record.status
        is SourceStatus.UNKNOWN
    )
    assert (
        record.metadata["enabled"]
        == "False"
    )
    assert (
        record.metadata["note"]
        == "login required"
    )


def test_resolved_only_openalex_source(
    tmp_path,
):
    registry = make_registry(
        tmp_path,
        resolved=[
            resolved_source(
                id="oa_w123",
                title="OpenAlex Paper",
                url="https://doi.org/10.1/test",
                doi="https://doi.org/10.1/test",
            )
        ],
    )

    record = registry.get_by_id(
        "oa_w123"
    )

    assert record is not None
    assert record.status is SourceStatus.VALID
    assert (
        record.access_type
        is AccessType.API
    )
    assert record.base_url == (
        "https://doi.org/10.1/test"
    )


def test_get_by_url_prefers_resolved_url(
    tmp_path,
):
    registry = make_registry(
        tmp_path,
        catalog=[
            catalog_source(
                id="one",
                url="https://example.org/search",
            ),
            catalog_source(
                id="two",
                url="https://example.org/search",
            ),
        ],
        resolved=[
            resolved_source(
                id="two",
                url="https://example.org/concrete",
            )
        ],
    )

    assert (
        registry.get_by_url(
            " https://example.org/concrete "
        ).source_id
        == "two"
    )

    assert (
        registry.get_by_url(
            "https://example.org/search"
        ).source_id
        == "one"
    )


def test_all_includes_catalog_resolved_and_listed(
    tmp_path,
):
    registry = make_registry(
        tmp_path,
        catalog=[
            catalog_source(
                id="catalog",
                url="https://example.org/catalog",
            )
        ],
        resolved=[
            resolved_source(
                id="resolved",
                url="https://example.org/resolved",
            )
        ],
        listed=[
            {
                "id": "listed",
                "title": "Listed",
                "url": "https://example.org/listed",
            }
        ],
    )

    assert [
        record.source_id
        for record in registry.all()
    ] == [
        "catalog",
        "listed",
        "resolved",
    ]


def test_missing_files_produce_empty_registry(
    tmp_path,
):
    registry = SourceRegistry(
        sources_path=tmp_path / "missing.yaml",
        resolved_path=(
            tmp_path / "missing-resolved.yaml"
        ),
        ingest_log_time=NOW,
    )

    assert registry.all() == []
    assert registry.get_by_id("missing") is None
    assert registry.status("missing") is None
    assert (
        registry.get_by_url(
            "https://example.org/missing"
        )
        is None
    )


def test_unrelated_log_lines_are_ignored(
    tmp_path,
):
    registry = make_registry(
        tmp_path,
        catalog=[catalog_source()],
        logs=[
            "[giza] source (url)",
            "random output",
        ],
    )

    assert (
        registry.status("source")
        is SourceStatus.UNKNOWN
    )


def test_naive_log_time_is_rejected(
    tmp_path,
):
    sources_path = tmp_path / "sources.yaml"
    resolved_path = (
        tmp_path / "sources.resolved.yaml"
    )

    write_yaml(
        sources_path,
        {"sources": []},
    )
    write_yaml(
        resolved_path,
        {"sources": []},
    )

    with pytest.raises(
        ValueError,
        match=(
            "ingest_log_time must be "
            "timezone-aware"
        ),
    ):
        SourceRegistry(
            sources_path=sources_path,
            resolved_path=resolved_path,
            ingest_log_time=datetime(
                2026,
                9,
                26,
                20,
                0,
            ),
        )


def test_default_registry_reads_existing_catalog(
    tmp_path,
):
    sources_path = tmp_path / "sources.yaml"

    write_yaml(
        sources_path,
        {
            "sources": [
                catalog_source(
                    id="wp_great_pyramid_of_giza",
                    site="giza",
                    title=(
                        "Great Pyramid of Giza "
                        "(Wikipedia)"
                    ),
                    url=(
                        "https://en.wikipedia.org/"
                        "wiki/Great_Pyramid_of_Giza"
                    ),
                    type="encyclopedia",
                    fetch={
                        "kind": "wikipedia",
                        "page":
                            "Great Pyramid of Giza",
                    },
                )
            ]
        },
    )

    registry = SourceRegistry(
        sources_path=sources_path,
        resolved_path=(
            tmp_path / "missing-resolved.yaml"
        ),
        ingest_log_time=NOW,
    )

    record = registry.get_by_id(
        "wp_great_pyramid_of_giza"
    )

    assert record is not None
    assert (
        record.status
        is SourceStatus.UNKNOWN
    )
    assert record.metadata["site"] == "giza"
    assert (
        record.metadata["source_type"]
        == "encyclopedia"
    )


def test_search_valid_sources_accepts_injected_iterable(
    tmp_path,
):
    registry = make_registry(
        tmp_path,
        catalog=[catalog_source()],
    )

    source_iter = (
        source
        for source in registry.all()
    )

    result = registry.search_valid_sources(
        source_iter
    )

    assert [
        source.source_id
        for source in result
    ] == ["source"]


def test_selectable_sources_returns_injected_sources_unchanged(
    tmp_path,
):
    registry = make_registry(
        tmp_path,
        catalog=[catalog_source()],
    )

    sources = registry.all()

    result = registry.selectable_sources(
        source
        for source in sources
    )

    assert result == sources
