from datetime import datetime, timedelta, timezone

import pytest

import data.corpus_models as m


UTC = timezone.utc
NOW = datetime(2026, 9, 26, 20, 0, tzinfo=UTC)


def assert_error(exc, path, msg, fn):
    with pytest.raises(exc) as e:
        fn()

    assert e.value.field_path == path
    assert e.value.message == msg
    assert str(e.value) == f"{path}: {msg}"


def valid_source(**overrides):
    kwargs = {
        "source_id": "source",
        "name": "Source",
        "base_url": "https://example.org",
    }
    kwargs.update(overrides)
    return m.SourceRecord(**kwargs)


def valid_corpus(**overrides):
    kwargs = {
        "corpus_id": "corpus",
        "source_id": "source",
        "name": "Corpus",
        "corpus_type": m.CorpusType.TEXT,
        "access_path": "/api",
        "access_type": m.AccessType.API,
    }
    kwargs.update(overrides)
    return m.CorpusRecord(**kwargs)


def valid_option(**overrides):
    kwargs = {
        "site_id": "site",
        "corpus_id": "corpus",
        "source_id": "source",
        "corpus_name": "Corpus",
        "source_name": "Source",
        "corpus_type": m.CorpusType.TEXT,
        "access_type": m.AccessType.API,
        "access_path": "/api",
    }
    kwargs.update(overrides)
    return m.CorpusOption(**kwargs)


def test_enums_and_error_object():
    assert {item.value for item in m.SourceStatus} == {
        "valid",
        "invalid",
        "unknown",
    }
    assert {item.value for item in m.CorpusType} == {
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
    assert {item.value for item in m.AccessType} == {
        "api",
        "download",
        "web",
        "repository",
        "file",
        "other",
    }
    assert {item.value for item in m.CorpusLoadStatus} == {
        "loading",
        "loaded",
        "failed",
        "unloaded",
    }
    assert {item.value for item in m.CorpusLoadedState} == {
        "available",
        "already_loaded",
    }

    error = m.ModelValidationError("X.y", "bad")

    assert error.field_path == "X.y"
    assert error.message == "bad"
    assert str(error) == "X.y: bad"


def test_identifier_normalization_and_errors():
    assert m._normalize_identifier(" A B-c ", "x") == "a_b-c"

    assert_error(
        m.InvalidIdentifierError,
        "x",
        "must be a string",
        lambda: m._normalize_identifier(3, "x"),
    )
    assert_error(
        m.InvalidIdentifierError,
        "x",
        "must not be empty",
        lambda: m._normalize_identifier("   ", "x"),
    )
    assert_error(
        m.InvalidIdentifierError,
        "x",
        "must match ^[a-z0-9][a-z0-9_-]*$",
        lambda: m._normalize_identifier("/bad", "x"),
    )


def test_required_optional_string_normalization():
    assert m._normalize_required_string(" x ", "f") == "x"

    assert_error(
        m.ModelValidationError,
        "f",
        "must be a string",
        lambda: m._normalize_required_string(2, "f"),
    )
    assert_error(
        m.ModelValidationError,
        "f",
        "must not be empty",
        lambda: m._normalize_required_string(" ", "f"),
    )

    assert m._normalize_optional_string(None, "f") is None
    assert m._normalize_optional_string("   ", "f") is None
    assert m._normalize_optional_string(" x ", "f") == "x"

    assert_error(
        m.ModelValidationError,
        "f",
        "must be a string",
        lambda: m._normalize_optional_string(2, "f"),
    )


def test_url_normalization_errors():
    assert (
        m._normalize_base_url(
            " https://example.org/x ",
            "u",
        )
        == "https://example.org/x"
    )

    assert_error(
        m.InvalidURLValueError,
        "u",
        "must be an absolute http:// or https:// URL",
        lambda: m._normalize_base_url("example.org", "u"),
    )
    assert_error(
        m.InvalidURLValueError,
        "u",
        "must use http:// or https://",
        lambda: m._normalize_base_url("ftp://example.org", "u"),
    )
    assert_error(
        m.InvalidURLValueError,
        "u",
        "must include a hostname",
        lambda: m._normalize_base_url("https:///path", "u"),
    )


def test_access_path_rules():
    assert (
        m._normalize_access_path(
            "/api",
            m.AccessType.API,
            "a",
        )
        == "/api"
    )
    assert (
        m._normalize_access_path(
            "https://example.org/file",
            m.AccessType.DOWNLOAD,
            "a",
        )
        == "https://example.org/file"
    )

    assert_error(
        m.ModelValidationError,
        "a",
        (
            "must be an absolute http:// or https:// URL "
            "when access_type is DOWNLOAD"
        ),
        lambda: m._normalize_access_path(
            "/file",
            m.AccessType.DOWNLOAD,
            "a",
        ),
    )
    assert_error(
        m.ModelValidationError,
        "a",
        "must include a hostname when access_type is DOWNLOAD",
        lambda: m._normalize_access_path(
            "https:///file",
            m.AccessType.DOWNLOAD,
            "a",
        ),
    )


def test_timestamp_rules():
    assert m._normalize_timestamp(None, "t") is None

    chicago = timezone(timedelta(hours=-5))

    assert (
        m._normalize_timestamp(
            datetime(
                2026,
                9,
                26,
                15,
                tzinfo=chicago,
            ),
            "t",
        )
        == NOW
    )

    assert_error(
        m.InvalidTimestampError,
        "t",
        "must be a datetime",
        lambda: m._normalize_timestamp("x", "t"),
    )
    assert_error(
        m.InvalidTimestampError,
        "t",
        "must be timezone-aware",
        lambda: m._normalize_timestamp(
            datetime(2026, 9, 26, 20),
            "t",
        ),
    )


def test_metadata_rules():
    assert m._normalize_metadata(
        {" a ": " b "},
        "meta",
    ) == {"a": "b"}

    assert_error(
        m.ModelValidationError,
        "meta",
        "must be a dict[str, str]",
        lambda: m._normalize_metadata([], "meta"),
    )
    assert_error(
        m.ModelValidationError,
        "meta[2]",
        "must be a non-empty string",
        lambda: m._normalize_metadata({2: "x"}, "meta"),
    )
    assert_error(
        m.ModelValidationError,
        "meta['   ']",
        "must be a non-empty string",
        lambda: m._normalize_metadata({"   ": "x"}, "meta"),
    )
    assert_error(
        m.ModelValidationError,
        'meta[" a "]',
        'duplicates key "a" after normalization',
        lambda: m._normalize_metadata(
            {
                "a": "1",
                " a ": "2",
            },
            "meta",
        ),
    )
    assert_error(
        m.ModelValidationError,
        'meta["a"]',
        "must be a string",
        lambda: m._normalize_metadata({"a": 2}, "meta"),
    )


def test_candidate_source_full_and_revalidate():
    source = m.CandidateSource(
        " Candidate Source ",
        " Name ",
        " https://example.org ",
        " from ",
        " text ",
        {" k ": " v "},
    )

    assert (
        source.source_id,
        source.name,
        source.base_url,
        source.discovered_from,
        source.discovery_text,
        source.metadata,
    ) == (
        "candidate_source",
        "Name",
        "https://example.org",
        "from",
        "text",
        {"k": "v"},
    )

    source.validate()


def test_source_record_unknown_and_invalid_types():
    source = valid_source()
    source.validate()

    assert source.status is m.SourceStatus.UNKNOWN

    assert_error(
        m.InvalidStateError,
        "SourceRecord.status",
        "must be a valid SourceStatus",
        lambda: valid_source(status="unknown"),
    )
    assert_error(
        m.InvalidStateError,
        "SourceRecord.access_type",
        "must be a valid AccessType",
        lambda: valid_source(access_type="api"),
    )


@pytest.mark.parametrize(
    "field,kwargs,msg",
    [
        (
            "last_validated",
            {"last_validated": NOW},
            "must be None when status is UNKNOWN",
        ),
        (
            "access_type",
            {"access_type": m.AccessType.API},
            "must be None when status is UNKNOWN",
        ),
        (
            "access_path",
            {"access_path": "/api"},
            "must be None when status is UNKNOWN",
        ),
        (
            "validation_reason",
            {"validation_reason": "why"},
            "must be None when status is UNKNOWN",
        ),
    ],
)
def test_source_unknown_state_errors(field, kwargs, msg):
    assert_error(
        m.InvalidStateError,
        f"SourceRecord.{field}",
        msg,
        lambda: valid_source(**kwargs),
    )


@pytest.mark.parametrize(
    "field,kwargs",
    [
        (
            "access_type",
            {
                "access_path": "/api",
                "last_validated": NOW,
            },
        ),
        (
            "access_path",
            {
                "access_type": m.AccessType.API,
                "last_validated": NOW,
            },
        ),
        (
            "last_validated",
            {
                "access_type": m.AccessType.API,
                "access_path": "/api",
            },
        ),
    ],
)
def test_source_valid_required_fields(field, kwargs):
    kwargs["status"] = m.SourceStatus.VALID

    assert_error(
        m.InvalidStateError,
        f"SourceRecord.{field}",
        f"is required when status is VALID",
        lambda: valid_source(**kwargs),
    )


def test_source_valid_success_and_normalization():
    source = valid_source(
        status=m.SourceStatus.VALID,
        access_type=m.AccessType.API,
        access_path=" /api ",
        last_validated=NOW,
        validation_reason=" ok ",
        metadata={" a ": " b "},
    )

    assert source.access_path == "/api"
    assert source.validation_reason == "ok"
    assert source.metadata == {"a": "b"}


@pytest.mark.parametrize(
    "field,kwargs,msg",
    [
        (
            "last_validated",
            {},
            "is required when status is INVALID",
        ),
        (
            "validation_reason",
            {"last_validated": NOW},
            "is required when status is INVALID",
        ),
        (
            "access_type",
            {
                "last_validated": NOW,
                "validation_reason": "bad",
                "access_type": m.AccessType.API,
            },
            "must be None when status is INVALID",
        ),
        (
            "access_path",
            {
                "last_validated": NOW,
                "validation_reason": "bad",
                "access_path": "/x",
            },
            "must be None when status is INVALID",
        ),
    ],
)
def test_source_invalid_state_errors(field, kwargs, msg):
    kwargs["status"] = m.SourceStatus.INVALID

    assert_error(
        m.InvalidStateError,
        f"SourceRecord.{field}",
        msg,
        lambda: valid_source(**kwargs),
    )


def test_source_invalid_success():
    source = valid_source(
        status=m.SourceStatus.INVALID,
        last_validated=NOW,
        validation_reason=" bad ",
    )

    assert source.validation_reason == "bad"


def test_corpus_record_success_and_errors():
    corpus = valid_corpus(
        description=" d ",
        language=" en ",
        license=" cc0 ",
        metadata={" k ": " v "},
    )

    corpus.validate()

    assert (
        corpus.description,
        corpus.language,
        corpus.license,
        corpus.metadata,
    ) == (
        "d",
        "en",
        "cc0",
        {"k": "v"},
    )

    assert_error(
        m.InvalidStateError,
        "CorpusRecord.corpus_type",
        "must be a valid CorpusType",
        lambda: valid_corpus(corpus_type="text"),
    )
    assert_error(
        m.InvalidStateError,
        "CorpusRecord.access_type",
        "must be a valid AccessType",
        lambda: valid_corpus(access_type="api"),
    )


def test_site_record_success_alias_handling_and_errors():
    site = m.SiteRecord(
        " Mohenjo Daro ",
        " Site ",
        [
            "Mohenjo Daro",
            "Mohenjo-daro",
            "Alias",
            " alias ",
            "",
            "Second",
        ],
        country=" PK ",
        region=" Sindh ",
        metadata={" k ": " v "},
    )

    assert site.site_id == "mohenjo_daro"
    assert site.alternate_names == [
        "Alias",
        "Second",
    ]
    assert site.country == "PK"
    assert site.region == "Sindh"
    assert site.metadata == {"k": "v"}

    site.validate()

    assert_error(
        m.ModelValidationError,
        "SiteRecord.alternate_names",
        "must be a list[str]",
        lambda: m.SiteRecord(
            "site",
            "Site",
            alternate_names="x",
        ),
    )
    assert_error(
        m.ModelValidationError,
        "SiteRecord.alternate_names[1]",
        "must be a string",
        lambda: m.SiteRecord(
            "site",
            "Site",
            alternate_names=[
                "a",
                2,
            ],
        ),
    )


def test_site_link_loading_success_and_errors():
    link = m.SiteCorpusLink(
        " site ",
        " corpus ",
        source_id=" source ",
        metadata={" k ": " v "},
    )

    link.validate()

    assert link.site_id == "site"
    assert link.corpus_id == "corpus"
    assert link.source_id == "source"
    assert link.metadata == {"k": "v"}

    assert_error(
        m.InvalidStateError,
        "SiteCorpusLink.load_status",
        "must be a valid CorpusLoadStatus",
        lambda: m.SiteCorpusLink(
            "site",
            "corpus",
            load_status="loading",
        ),
    )
    assert_error(
        m.InvalidStateError,
        "SiteCorpusLink.loaded_at",
        "must be None when load_status is LOADING",
        lambda: m.SiteCorpusLink(
            "site",
            "corpus",
            loaded_at=NOW,
        ),
    )
    assert_error(
        m.InvalidStateError,
        "SiteCorpusLink.unloaded_at",
        "must be None when load_status is LOADING",
        lambda: m.SiteCorpusLink(
            "site",
            "corpus",
            unloaded_at=NOW,
        ),
    )
    assert_error(
        m.InvalidStateError,
        "SiteCorpusLink.failure_reason",
        "must be None when load_status is LOADING",
        lambda: m.SiteCorpusLink(
            "site",
            "corpus",
            failure_reason="bad",
        ),
    )


def test_site_link_loaded_success_and_errors():
    link = m.SiteCorpusLink(
        "site",
        "corpus",
        load_status=m.CorpusLoadStatus.LOADED,
        loaded_at=NOW,
    )

    assert link.loaded_at == NOW

    assert_error(
        m.InvalidStateError,
        "SiteCorpusLink.loaded_at",
        "is required when load_status is LOADED",
        lambda: m.SiteCorpusLink(
            "site",
            "corpus",
            load_status=m.CorpusLoadStatus.LOADED,
        ),
    )
    assert_error(
        m.InvalidStateError,
        "SiteCorpusLink.unloaded_at",
        "must be None when load_status is LOADED",
        lambda: m.SiteCorpusLink(
            "site",
            "corpus",
            load_status=m.CorpusLoadStatus.LOADED,
            loaded_at=NOW,
            unloaded_at=NOW,
        ),
    )
    assert_error(
        m.InvalidStateError,
        "SiteCorpusLink.failure_reason",
        "must be None when load_status is LOADED",
        lambda: m.SiteCorpusLink(
            "site",
            "corpus",
            load_status=m.CorpusLoadStatus.LOADED,
            loaded_at=NOW,
            failure_reason="bad",
        ),
    )


def test_site_link_failed_success_and_errors():
    link = m.SiteCorpusLink(
        "site",
        "corpus",
        load_status=m.CorpusLoadStatus.FAILED,
        failure_reason=" bad ",
    )

    assert link.failure_reason == "bad"

    assert_error(
        m.InvalidStateError,
        "SiteCorpusLink.loaded_at",
        "must be None when load_status is FAILED",
        lambda: m.SiteCorpusLink(
            "site",
            "corpus",
            load_status=m.CorpusLoadStatus.FAILED,
            loaded_at=NOW,
            failure_reason="bad",
        ),
    )
    assert_error(
        m.InvalidStateError,
        "SiteCorpusLink.unloaded_at",
        "must be None when load_status is FAILED",
        lambda: m.SiteCorpusLink(
            "site",
            "corpus",
            load_status=m.CorpusLoadStatus.FAILED,
            unloaded_at=NOW,
            failure_reason="bad",
        ),
    )
    assert_error(
        m.InvalidStateError,
        "SiteCorpusLink.failure_reason",
        "is required when load_status is FAILED",
        lambda: m.SiteCorpusLink(
            "site",
            "corpus",
            load_status=m.CorpusLoadStatus.FAILED,
        ),
    )


def test_site_link_unloaded_success_and_errors_and_ordering():
    later = NOW + timedelta(hours=1)

    link = m.SiteCorpusLink(
        "site",
        "corpus",
        load_status=m.CorpusLoadStatus.UNLOADED,
        loaded_at=NOW,
        unloaded_at=later,
    )

    assert link.unloaded_at == later

    assert_error(
        m.InvalidStateError,
        "SiteCorpusLink.loaded_at",
        "is required when load_status is UNLOADED",
        lambda: m.SiteCorpusLink(
            "site",
            "corpus",
            load_status=m.CorpusLoadStatus.UNLOADED,
            unloaded_at=later,
        ),
    )
    assert_error(
        m.InvalidStateError,
        "SiteCorpusLink.unloaded_at",
        "is required when load_status is UNLOADED",
        lambda: m.SiteCorpusLink(
            "site",
            "corpus",
            load_status=m.CorpusLoadStatus.UNLOADED,
            loaded_at=NOW,
        ),
    )
    assert_error(
        m.InvalidStateError,
        "SiteCorpusLink.failure_reason",
        "must be None when load_status is UNLOADED",
        lambda: m.SiteCorpusLink(
            "site",
            "corpus",
            load_status=m.CorpusLoadStatus.UNLOADED,
            loaded_at=NOW,
            unloaded_at=later,
            failure_reason="bad",
        ),
    )
    assert_error(
        m.InvalidTimestampError,
        "SiteCorpusLink.unloaded_at",
        "must be greater than or equal to loaded_at",
        lambda: m.SiteCorpusLink(
            "site",
            "corpus",
            load_status=m.CorpusLoadStatus.UNLOADED,
            loaded_at=later,
            unloaded_at=NOW,
        ),
    )


def test_corpus_option_success_and_errors():
    option = valid_option(
        description=" d ",
        differentiator_text=" Available ",
        metadata={" k ": " v "},
    )

    option.validate()

    assert option.description == "d"
    assert option.differentiator_text == "Available"
    assert option.metadata == {"k": "v"}

    loaded = valid_option(
        loaded_state=m.CorpusLoadedState.ALREADY_LOADED,
    )

    assert (
        loaded.loaded_state
        is m.CorpusLoadedState.ALREADY_LOADED
    )

    assert_error(
        m.InvalidStateError,
        "CorpusOption.corpus_type",
        "must be a valid CorpusType",
        lambda: valid_option(corpus_type="text"),
    )
    assert_error(
        m.InvalidStateError,
        "CorpusOption.access_type",
        "must be a valid AccessType",
        lambda: valid_option(access_type="api"),
    )
    assert_error(
        m.InvalidStateError,
        "CorpusOption.loaded_state",
        "must be a valid CorpusLoadedState",
        lambda: valid_option(loaded_state="available"),
    )


def test_internal_state_validators_allow_no_matching_branch_when_called_directly():
    source = valid_source()
    source.status = object()
    source._validate_state()

    link = m.SiteCorpusLink(
        "site",
        "corpus",
    )
    link.load_status = object()
    link._validate_state()
