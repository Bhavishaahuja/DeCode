import json
from datetime import datetime, timezone

import pytest

from data.corpus_models import (
    AccessType,
    InvalidRelationshipError,
    SourceRecord,
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


def record(**overrides):
    kwargs = {
        "source_id": "source",
        "name": "Source",
        "base_url": "https://example.org",
    }
    kwargs.update(overrides)
    return SourceRecord(**kwargs)


def test_empty_registry_and_all_and_missing_lookup(tmp_path):
    registry = SourceRegistry(
        tmp_path / "nested" / "registry.json",
    )

    assert registry.all() == []
    assert registry.get_by_id("missing") is None
    assert (
        registry.get_by_url(" https://none.example ")
        is None
    )


def test_upsert_save_lookup_replace_and_reload(tmp_path):
    path = tmp_path / "nested" / "registry.json"
    registry = SourceRegistry(path)

    first = record()
    registry.upsert(first)

    assert path.exists()
    assert registry.all() == [first]
    assert registry.get_by_id(" Source ") == first
    assert (
        registry.get_by_url(" https://example.org ")
        == first
    )

    valid = record(
        name="Updated",
        status=SourceStatus.VALID,
        access_type=AccessType.API,
        access_path="/api",
        last_validated=NOW,
        validation_reason="ok",
        metadata={"k": "v"},
    )

    registry.upsert(valid)

    assert registry.get_by_id("source").name == "Updated"

    loaded = SourceRegistry(path)
    got = loaded.get_by_id("source")

    assert got == valid
    assert got.last_validated == NOW
    assert got.access_type is AccessType.API

    data = json.loads(path.read_text())

    assert (
        data["sources"][0]["last_validated"]
        == NOW.isoformat()
    )
    assert data["sources"][0]["access_type"] == "api"


def test_unknown_roundtrip_none_fields(tmp_path):
    path = tmp_path / "registry.json"

    SourceRegistry(path).upsert(record())

    got = SourceRegistry(path).get_by_id("source")

    assert got.access_type is None
    assert got.last_validated is None
    assert got.validation_reason is None


def test_upsert_duplicate_url_rejected(tmp_path):
    registry = SourceRegistry(
        tmp_path / "registry.json",
    )

    registry.upsert(record())

    with pytest.raises(
        InvalidRelationshipError,
        match=(
            'SourceRegistry.base_url: URL '
            '"https://example.org" is already '
            'registered as source "source"'
        ),
    ):
        registry.upsert(
            record(source_id="other"),
        )


def test_load_duplicate_url_rejected(tmp_path):
    path = tmp_path / "registry.json"

    path.write_text(
        json.dumps(
            {
                "sources": [
                    {
                        "source_id": "one",
                        "name": "One",
                        "base_url": "https://same.example",
                        "status": "unknown",
                        "access_type": None,
                        "access_path": None,
                        "last_validated": None,
                        "validation_reason": None,
                        "metadata": {},
                    },
                    {
                        "source_id": "two",
                        "name": "Two",
                        "base_url": "https://same.example",
                        "status": "unknown",
                        "access_type": None,
                        "access_path": None,
                        "last_validated": None,
                        "validation_reason": None,
                        "metadata": {},
                    },
                ]
            }
        )
    )

    with pytest.raises(
        InvalidRelationshipError,
        match=(
            'SourceRegistry.base_url: URL '
            '"https://same.example" is already '
            'registered as source "one"'
        ),
    ):
        SourceRegistry(path)


def test_load_missing_sources_key(tmp_path):
    path = tmp_path / "registry.json"

    path.write_text("{}")

    assert SourceRegistry(path).all() == []


def test_get_by_url_nonmatch_with_existing_record(tmp_path):
    registry = SourceRegistry(
        tmp_path / "registry.json",
    )

    registry.upsert(record())

    assert (
        registry.get_by_url(
            "https://different.example",
        )
        is None
    )
