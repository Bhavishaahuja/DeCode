from datetime import datetime

from data.corpus_models import (
    AccessType,
    CorpusRecord,
    CorpusSearchOption,
    CorpusType,
    SiteCorpusLink,
    SiteRecord,
    SourceRecord,
    SourceStatus,
)


def test_source_status_values():
    assert SourceStatus.VALID.value == "valid"
    assert SourceStatus.INVALID.value == "invalid"
    assert SourceStatus.UNKNOWN.value == "unknown"


def test_corpus_type_values():
    assert {item.value for item in CorpusType} == {
        "text",
        "image",
        "plan",
        "inscription",
        "dataset",
        "scan_3d",
        "point_cloud",
        "gis",
        "report",
        "catalog",
        "mixed",
        "other",
    }


def test_access_type_values():
    assert {item.value for item in AccessType} == {
        "api",
        "download",
        "web",
        "repository",
        "file",
        "other",
    }


def test_source_record_defaults():
    source = SourceRecord(
        source_id="ignca",
        name="IGNCA",
        base_url="https://ignca.gov.in",
    )

    assert source.source_id == "ignca"
    assert source.name == "IGNCA"
    assert source.base_url == "https://ignca.gov.in"
    assert source.status == SourceStatus.UNKNOWN
    assert source.access_type is None
    assert source.access_path is None
    assert source.last_validated is None
    assert source.validation_reason is None
    assert source.metadata == {}


def test_source_record_all_fields():
    validated_at = datetime(2026, 9, 26, 15, 0, 0)

    source = SourceRecord(
        source_id="commons",
        name="Wikimedia Commons",
        base_url="https://commons.wikimedia.org",
        status=SourceStatus.VALID,
        access_type=AccessType.API,
        access_path="/w/api.php",
        last_validated=validated_at,
        validation_reason="API reachable",
        metadata={"license": "varies"},
    )

    assert source.status == SourceStatus.VALID
    assert source.access_type == AccessType.API
    assert source.access_path == "/w/api.php"
    assert source.last_validated == validated_at
    assert source.validation_reason == "API reachable"
    assert source.metadata == {"license": "varies"}


def test_source_record_metadata_is_not_shared():
    first = SourceRecord("one", "One", "https://one.example")
    second = SourceRecord("two", "Two", "https://two.example")

    first.metadata["key"] = "value"

    assert second.metadata == {}


def test_corpus_record_required_and_optional_fields():
    corpus = CorpusRecord(
        corpus_id="ajanta-9-images",
        source_id="commons",
        name="Ajanta Cave 9 Images",
        corpus_type=CorpusType.IMAGE,
        access_path="/wiki/Category:Cave_9,_Ajanta",
        access_type=AccessType.WEB,
        description="Photographic corpus",
        language="en",
        license="varies",
        metadata={"site": "ajanta"},
    )

    assert corpus.corpus_id == "ajanta-9-images"
    assert corpus.source_id == "commons"
    assert corpus.name == "Ajanta Cave 9 Images"
    assert corpus.corpus_type == CorpusType.IMAGE
    assert corpus.access_path == "/wiki/Category:Cave_9,_Ajanta"
    assert corpus.access_type == AccessType.WEB
    assert corpus.description == "Photographic corpus"
    assert corpus.language == "en"
    assert corpus.license == "varies"
    assert corpus.metadata == {"site": "ajanta"}


def test_corpus_record_optional_defaults():
    corpus = CorpusRecord(
        corpus_id="corpus",
        source_id="source",
        name="Corpus",
        corpus_type=CorpusType.DATASET,
        access_path="/data",
        access_type=AccessType.DOWNLOAD,
    )

    assert corpus.description is None
    assert corpus.language is None
    assert corpus.license is None
    assert corpus.metadata == {}


def test_site_record_defaults():
    site = SiteRecord(
        site_id="ajanta",
        name="Ajanta Caves",
    )

    assert site.site_id == "ajanta"
    assert site.name == "Ajanta Caves"
    assert site.alternate_names == []
    assert site.country is None
    assert site.region is None
    assert site.metadata == {}


def test_site_record_all_fields():
    site = SiteRecord(
        site_id="ajanta",
        name="Ajanta Caves",
        alternate_names=["Ajanta"],
        country="India",
        region="Maharashtra",
        metadata={"unesco": "242"},
    )

    assert site.alternate_names == ["Ajanta"]
    assert site.country == "India"
    assert site.region == "Maharashtra"
    assert site.metadata == {"unesco": "242"}


def test_site_record_mutable_defaults_are_not_shared():
    first = SiteRecord("one", "One")
    second = SiteRecord("two", "Two")

    first.alternate_names.append("First")
    first.metadata["key"] = "value"

    assert second.alternate_names == []
    assert second.metadata == {}


def test_site_corpus_link_defaults():
    before = datetime.utcnow()

    link = SiteCorpusLink(
        site_id="ajanta",
        corpus_id="ajanta-9-images",
    )

    after = datetime.utcnow()

    assert link.site_id == "ajanta"
    assert link.corpus_id == "ajanta-9-images"
    assert before <= link.linked_at <= after
    assert link.metadata == {}


def test_site_corpus_link_all_fields():
    linked_at = datetime(2026, 9, 26, 15, 30, 0)

    link = SiteCorpusLink(
        site_id="ajanta",
        corpus_id="ajanta-9-images",
        linked_at=linked_at,
        metadata={"selected_by": "user"},
    )

    assert link.linked_at == linked_at
    assert link.metadata == {"selected_by": "user"}


def test_corpus_search_option():
    option = CorpusSearchOption(
        corpus_id="ajanta-9-images",
        source_id="commons",
        corpus_name="Ajanta Cave 9 Images",
        source_name="Wikimedia Commons",
        corpus_type=CorpusType.IMAGE,
        access_type=AccessType.WEB,
        access_path="/wiki/Category:Cave_9,_Ajanta",
        description="Photographic corpus",
    )

    assert option.corpus_id == "ajanta-9-images"
    assert option.source_id == "commons"
    assert option.corpus_name == "Ajanta Cave 9 Images"
    assert option.source_name == "Wikimedia Commons"
    assert option.corpus_type == CorpusType.IMAGE
    assert option.access_type == AccessType.WEB
    assert option.access_path == "/wiki/Category:Cave_9,_Ajanta"
    assert option.description == "Photographic corpus"


def test_corpus_search_option_description_defaults_to_none():
    option = CorpusSearchOption(
        corpus_id="corpus",
        source_id="source",
        corpus_name="Corpus",
        source_name="Source",
        corpus_type=CorpusType.TEXT,
        access_type=AccessType.API,
        access_path="/api",
    )

    assert option.description is None
