from datetime import datetime, timezone

import yaml

from data.corpus_import import (
    import_selected_corpus,
)
from data.corpus_models import (
    AccessType,
    CorpusLoadStatus,
    SiteCorpusLink,
    SourceRecord,
    SourceStatus,
)
from data.corpus_selection import CorpusSelection


NOW = datetime(
    2026,
    9,
    26,
    20,
    0,
    tzinfo=timezone.utc,
)


def selected_source():
    return SourceRecord(
        source_id="oracc_ur",
        name="ORACC royal inscriptions",
        base_url="https://oracc.museum.upenn.edu/",
        status=SourceStatus.VALID,
        access_type=AccessType.WEB,
        access_path="https://oracc.museum.upenn.edu/",
        last_validated=NOW,
        validation_reason="source reachable",
        metadata={
            "site": "ur",
            "source_type": "primary_text",
        },
    )


def consumed():
    return (
        {
            "id": "oracc_ur",
            "site": "ur",
            "type": "primary_text",
            "title": "ORACC royal inscriptions",
            "url": "https://oracc.museum.upenn.edu/",
            "license": "CC BY-SA 3.0",
            "retrieved": "2026-09-26",
            "n_passages": 1,
        },
        [
            {
                "passage_id": "ur-oracc_ur-0000",
                "source_id": "oracc_ur",
                "site": "ur",
                "title": "ORACC royal inscriptions",
                "author": None,
                "year": None,
                "url": "https://oracc.museum.upenn.edu/",
                "license": "CC BY-SA 3.0",
                "source_type": "primary_text",
                "period": "Ur III",
                "locator": None,
                "text": "example inscription",
                "system_tags": [],
                "tagged_by": "none",
                "page": None,
                "char_start": 0,
                "char_end": 19,
            }
        ],
    )


def test_import_selected_corpus_consumes_selected_source(
    tmp_path,
):
    source = selected_source()
    selection = CorpusSelection(
        site_id="ur",
        source=source,
    )

    received = []

    def consume(site_id, selected):
        received.append(
            (site_id, selected)
        )
        return consumed()

    result = import_selected_corpus(
        selection,
        consume,
        passages_path=tmp_path / "passages.jsonl",
        resolved_path=tmp_path / "sources.resolved.yaml",
    )

    assert received == [
        ("ur", source)
    ]
    assert result.imported is True


def test_import_selected_corpus_creates_loaded_link(
    tmp_path,
):
    selection = CorpusSelection(
        site_id="ur",
        source=selected_source(),
    )

    result = import_selected_corpus(
        selection,
        lambda site_id, source: consumed(),
        passages_path=tmp_path / "passages.jsonl",
        resolved_path=tmp_path / "sources.resolved.yaml",
    )

    assert result.link.site_id == "ur"
    assert result.link.corpus_id == "oracc_ur"
    assert result.link.source_id == "oracc_ur"
    assert (
        result.link.load_status
        is CorpusLoadStatus.LOADED
    )


def test_import_selected_corpus_persists_passages(
    tmp_path,
):
    selection = CorpusSelection(
        site_id="ur",
        source=selected_source(),
    )
    passages_path = (
        tmp_path / "passages.jsonl"
    )

    import_selected_corpus(
        selection,
        lambda site_id, source: consumed(),
        passages_path=passages_path,
        resolved_path=tmp_path / "sources.resolved.yaml",
    )

    assert (
        "ur-oracc_ur-0000"
        in passages_path.read_text(
            encoding="utf-8"
        )
    )


def test_import_selected_corpus_persists_resolved_source(
    tmp_path,
):
    selection = CorpusSelection(
        site_id="ur",
        source=selected_source(),
    )
    resolved_path = (
        tmp_path / "sources.resolved.yaml"
    )

    import_selected_corpus(
        selection,
        lambda site_id, source: consumed(),
        passages_path=tmp_path / "passages.jsonl",
        resolved_path=resolved_path,
    )

    payload = yaml.safe_load(
        resolved_path.read_text(
            encoding="utf-8"
        )
    )

    assert [
        source["id"]
        for source in payload["sources"]
    ] == ["oracc_ur"]


def test_import_replaces_existing_source_material(
    tmp_path,
):
    selection = CorpusSelection(
        site_id="ur",
        source=selected_source(),
    )
    passages_path = (
        tmp_path / "passages.jsonl"
    )
    resolved_path = (
        tmp_path / "sources.resolved.yaml"
    )

    import_selected_corpus(
        selection,
        lambda site_id, source: consumed(),
        passages_path=passages_path,
        resolved_path=resolved_path,
    )

    import_selected_corpus(
        selection,
        lambda site_id, source: consumed(),
        passages_path=passages_path,
        resolved_path=resolved_path,
    )

    assert (
        passages_path.read_text(
            encoding="utf-8"
        ).count(
            "ur-oracc_ur-0000"
        )
        == 1
    )

    payload = yaml.safe_load(
        resolved_path.read_text(
            encoding="utf-8"
        )
    )

    assert [
        source["id"]
        for source in payload["sources"]
    ] == ["oracc_ur"]


def test_existing_loaded_selection_bypasses_consumer(
    tmp_path,
):
    source = selected_source()

    existing = SiteCorpusLink(
        site_id="ur",
        corpus_id="oracc_ur",
        source_id="oracc_ur",
        load_status=CorpusLoadStatus.LOADED,
        loaded_at=NOW,
    )

    selection = CorpusSelection(
        site_id="ur",
        source=source,
        existing_link=existing,
    )

    called = False

    def consume(site_id, selected):
        nonlocal called
        called = True
        return consumed()

    result = import_selected_corpus(
        selection,
        consume,
        passages_path=tmp_path / "passages.jsonl",
        resolved_path=tmp_path / "sources.resolved.yaml",
    )

    assert called is False
    assert result.imported is False
    assert result.link is existing


def test_import_rejects_wrong_source(
    tmp_path,
):
    selection = CorpusSelection(
        site_id="ur",
        source=selected_source(),
    )

    resolved, passages = consumed()
    resolved["id"] = "other"

    try:
        import_selected_corpus(
            selection,
            lambda site_id, source: (
                resolved,
                passages,
            ),
            passages_path=tmp_path / "passages.jsonl",
            resolved_path=tmp_path / "sources.resolved.yaml",
        )
    except ValueError as exc:
        assert str(exc) == (
            "consumed source id does not match "
            "selected source"
        )
    else:
        raise AssertionError(
            "expected source mismatch failure"
        )


def test_import_rejects_wrong_site(
    tmp_path,
):
    selection = CorpusSelection(
        site_id="ur",
        source=selected_source(),
    )

    resolved, passages = consumed()
    resolved["site"] = "giza"

    try:
        import_selected_corpus(
            selection,
            lambda site_id, source: (
                resolved,
                passages,
            ),
            passages_path=tmp_path / "passages.jsonl",
            resolved_path=tmp_path / "sources.resolved.yaml",
        )
    except ValueError as exc:
        assert str(exc) == (
            "consumed source site does not match "
            "selected site"
        )
    else:
        raise AssertionError(
            "expected site mismatch failure"
        )


def test_import_returns_consumed_source_and_passages(
    tmp_path,
):
    selection = CorpusSelection(
        site_id="ur",
        source=selected_source(),
    )

    resolved, passages = consumed()

    result = import_selected_corpus(
        selection,
        lambda site_id, source: (
            resolved,
            passages,
        ),
        passages_path=tmp_path / "passages.jsonl",
        resolved_path=tmp_path / "sources.resolved.yaml",
    )

    assert result.resolved_source is resolved
    assert result.passages is passages


def test_import_rejects_passage_from_wrong_source(
    tmp_path,
):
    selection = CorpusSelection(
        site_id="ur",
        source=selected_source(),
    )

    resolved, passages = consumed()
    passages[0]["source_id"] = "other"

    try:
        import_selected_corpus(
            selection,
            lambda site_id, source: (
                resolved,
                passages,
            ),
            passages_path=tmp_path / "passages.jsonl",
            resolved_path=tmp_path / "sources.resolved.yaml",
        )
    except ValueError as exc:
        assert str(exc) == (
            "passage source does not match "
            "selected source"
        )
    else:
        raise AssertionError(
            "expected passage source mismatch failure"
        )


def test_import_rejects_passage_from_wrong_site(
    tmp_path,
):
    selection = CorpusSelection(
        site_id="ur",
        source=selected_source(),
    )

    resolved, passages = consumed()
    passages[0]["site"] = "giza"

    try:
        import_selected_corpus(
            selection,
            lambda site_id, source: (
                resolved,
                passages,
            ),
            passages_path=tmp_path / "passages.jsonl",
            resolved_path=tmp_path / "sources.resolved.yaml",
        )
    except ValueError as exc:
        assert str(exc) == (
            "passage site does not match "
            "selected site"
        )
    else:
        raise AssertionError(
            "expected passage site mismatch failure"
        )


def test_import_preserves_other_source_passages(
    tmp_path,
):
    selection = CorpusSelection(
        site_id="ur",
        source=selected_source(),
    )

    passages_path = (
        tmp_path / "passages.jsonl"
    )

    passages_path.write_text(
        '{"passage_id":"giza-other-0000",'
        '"source_id":"other",'
        '"site":"giza"}\n',
        encoding="utf-8",
    )

    import_selected_corpus(
        selection,
        lambda site_id, source: consumed(),
        passages_path=passages_path,
        resolved_path=tmp_path / "sources.resolved.yaml",
    )

    text = passages_path.read_text(
        encoding="utf-8"
    )

    assert "giza-other-0000" in text
    assert "ur-oracc_ur-0000" in text


def test_import_preserves_other_resolved_sources(
    tmp_path,
):
    selection = CorpusSelection(
        site_id="ur",
        source=selected_source(),
    )

    resolved_path = (
        tmp_path / "sources.resolved.yaml"
    )

    resolved_path.write_text(
        yaml.safe_dump(
            {
                "generated": None,
                "sources": [
                    {
                        "id": "other",
                        "site": "giza",
                    }
                ],
                "listed_but_not_ingested": [],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    import_selected_corpus(
        selection,
        lambda site_id, source: consumed(),
        passages_path=tmp_path / "passages.jsonl",
        resolved_path=resolved_path,
    )

    payload = yaml.safe_load(
        resolved_path.read_text(
            encoding="utf-8"
        )
    )

    assert [
        source["id"]
        for source in payload["sources"]
    ] == [
        "other",
        "oracc_ur",
    ]


def test_import_preserves_listed_not_ingested(
    tmp_path,
):
    selection = CorpusSelection(
        site_id="ur",
        source=selected_source(),
    )

    resolved_path = (
        tmp_path / "sources.resolved.yaml"
    )

    skipped = {
        "id": "blocked",
        "site": "ur",
        "reason": "not consumable",
    }

    resolved_path.write_text(
        yaml.safe_dump(
            {
                "generated": None,
                "sources": [],
                "listed_but_not_ingested": [
                    skipped
                ],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    import_selected_corpus(
        selection,
        lambda site_id, source: consumed(),
        passages_path=tmp_path / "passages.jsonl",
        resolved_path=resolved_path,
    )

    payload = yaml.safe_load(
        resolved_path.read_text(
            encoding="utf-8"
        )
    )

    assert (
        payload["listed_but_not_ingested"]
        == [skipped]
    )
