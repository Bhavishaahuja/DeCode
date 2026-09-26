from datetime import datetime, timezone

import pytest

from data.corpus_models import (
    AccessType,
    CorpusLoadStatus,
    SiteCorpusLink,
    SourceRecord,
    SourceStatus,
)
from data.corpus_selection import (
    CorpusSelection,
    select_corpus,
)


NOW = datetime(
    2026,
    9,
    26,
    20,
    0,
    tzinfo=timezone.utc,
)


def valid_source(
    source_id="oracc_ur",
) -> SourceRecord:
    return SourceRecord(
        source_id=source_id,
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


def test_select_corpus_links_source_to_site():
    source = valid_source()

    selection = select_corpus(
        site_id="ur",
        source=source,
        selectable_sources=[source],
        existing_links=[],
    )

    assert selection.site_id == "ur"
    assert selection.source is source


def test_select_corpus_preserves_source_record():
    source = valid_source()

    selection = select_corpus(
        site_id="ur",
        source=source,
        selectable_sources=[source],
        existing_links=[],
    )

    assert (
        selection.source.source_id
        == "oracc_ur"
    )
    assert (
        selection.source.access_type
        is AccessType.WEB
    )
    assert (
        selection.source.access_path
        == "https://oracc.museum.upenn.edu/"
    )
    assert (
        selection.source.metadata["site"]
        == "ur"
    )


def test_select_corpus_accepts_injected_selectable_iterable():
    source = valid_source()

    selectable_sources = (
        candidate
        for candidate in [source]
    )

    selection = select_corpus(
        site_id="ur",
        source=source,
        selectable_sources=selectable_sources,
        existing_links=[],
    )

    assert selection.source is source


def test_select_corpus_rejects_source_not_in_selectable_sources():
    selected = valid_source(
        source_id="oracc_ur",
    )
    other = valid_source(
        source_id="cdli_ur",
    )

    with pytest.raises(
        ValueError,
        match=(
            "selected source is not in "
            "selectable sources"
        ),
    ):
        select_corpus(
            site_id="ur",
            source=selected,
            selectable_sources=[other],
            existing_links=[],
        )


def test_select_corpus_normalizes_site_id():
    source = valid_source()

    selection = select_corpus(
        site_id=" Ur ",
        source=source,
        selectable_sources=[source],
        existing_links=[],
    )

    assert selection.site_id == "ur"


def test_select_corpus_rejects_empty_site_id():
    source = valid_source()

    with pytest.raises(
        ValueError,
        match="site_id must not be empty",
    ):
        select_corpus(
            site_id="   ",
            source=source,
            selectable_sources=[source],
            existing_links=[],
        )


def test_selection_can_be_handed_forward_unchanged():
    source = valid_source()

    selection = select_corpus(
        site_id="ur",
        source=source,
        selectable_sources=[source],
        existing_links=[],
    )

    intake_source = selection.source

    assert intake_source is source
    assert (
        intake_source.access_path
        == source.access_path
    )


def test_existing_loaded_corpus_returns_existing_link():
    source = valid_source()

    existing_link = SiteCorpusLink(
        site_id="ur",
        corpus_id="oracc_ur",
        source_id="oracc_ur",
        load_status=CorpusLoadStatus.LOADED,
        loaded_at=NOW,
    )

    selection = select_corpus(
        site_id="ur",
        source=source,
        selectable_sources=[source],
        existing_links=[existing_link],
    )

    assert selection.existing_link is existing_link


def test_existing_loaded_corpus_skips_intake():
    source = valid_source()

    existing_link = SiteCorpusLink(
        site_id="ur",
        corpus_id="oracc_ur",
        source_id="oracc_ur",
        load_status=CorpusLoadStatus.LOADED,
        loaded_at=NOW,
    )

    selection = select_corpus(
        site_id="ur",
        source=source,
        selectable_sources=[source],
        existing_links=[existing_link],
    )

    assert selection.send_to_intake is False


def test_new_source_is_sent_to_intake():
    source = valid_source()

    selection = select_corpus(
        site_id="ur",
        source=source,
        selectable_sources=[source],
        existing_links=[],
    )

    assert selection.existing_link is None
    assert selection.send_to_intake is True


def test_non_loaded_link_does_not_bypass_intake():
    source = valid_source()

    existing_link = SiteCorpusLink(
        site_id="ur",
        corpus_id="oracc_ur",
        source_id="oracc_ur",
        load_status=CorpusLoadStatus.FAILED,
        failure_reason="import failed",
    )

    selection = select_corpus(
        site_id="ur",
        source=source,
        selectable_sources=[source],
        existing_links=[existing_link],
    )

    assert selection.existing_link is None
    assert selection.send_to_intake is True
