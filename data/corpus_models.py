from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from urllib.parse import urlparse


IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------

class ModelValidationError(ValueError):
    def __init__(self, field_path: str, message: str) -> None:
        self.field_path = field_path
        self.message = message
        super().__init__(f"{field_path}: {message}")


class InvalidIdentifierError(ModelValidationError):
    pass


class InvalidURLValueError(ModelValidationError):
    pass


class InvalidStateError(ModelValidationError):
    pass


class InvalidTimestampError(ModelValidationError):
    pass


class InvalidRelationshipError(ModelValidationError):
    pass


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class SourceStatus(str, Enum):
    VALID = "valid"
    INVALID = "invalid"
    UNKNOWN = "unknown"


class CorpusType(str, Enum):
    TEXT = "text"
    IMAGE = "image"
    PLAN = "plan"
    INSCRIPTION = "inscription"
    DATASET = "dataset"
    SCAN_3D = "scan_3d"
    POINT_CLOUD = "point_cloud"
    GIS = "gis"
    REPORT = "report"
    CATALOG = "catalog"
    MIXED = "mixed"
    OTHER = "other"


class AccessType(str, Enum):
    API = "api"
    DOWNLOAD = "download"
    WEB = "web"
    REPOSITORY = "repository"
    FILE = "file"
    OTHER = "other"


class CorpusLoadStatus(str, Enum):
    LOADING = "loading"
    LOADED = "loaded"
    FAILED = "failed"
    UNLOADED = "unloaded"


class CorpusLoadedState(str, Enum):
    AVAILABLE = "available"
    ALREADY_LOADED = "already_loaded"


# ---------------------------------------------------------------------------
# Shared normalization
# ---------------------------------------------------------------------------

def _normalize_identifier(
    value: str,
    field_path: str,
) -> str:
    if not isinstance(value, str):
        raise InvalidIdentifierError(
            field_path,
            "must be a string",
        )

    normalized = value.strip().lower().replace(" ", "_")

    if not normalized:
        raise InvalidIdentifierError(
            field_path,
            "must not be empty",
        )

    if not IDENTIFIER_PATTERN.fullmatch(normalized):
        raise InvalidIdentifierError(
            field_path,
            "must match ^[a-z0-9][a-z0-9_-]*$",
        )

    return normalized


def _normalize_required_string(
    value: str,
    field_path: str,
) -> str:
    if not isinstance(value, str):
        raise ModelValidationError(
            field_path,
            "must be a string",
        )

    normalized = value.strip()

    if not normalized:
        raise ModelValidationError(
            field_path,
            "must not be empty",
        )

    return normalized


def _normalize_optional_string(
    value: Optional[str],
    field_path: str,
) -> Optional[str]:
    if value is None:
        return None

    if not isinstance(value, str):
        raise ModelValidationError(
            field_path,
            "must be a string",
        )

    normalized = value.strip()

    if not normalized:
        return None

    return normalized


def _normalize_base_url(
    value: str,
    field_path: str,
) -> str:
    value = _normalize_required_string(
        value,
        field_path,
    )

    parsed = urlparse(value)

    if not parsed.scheme:
        raise InvalidURLValueError(
            field_path,
            "must be an absolute http:// or https:// URL",
        )

    if parsed.scheme not in {"http", "https"}:
        raise InvalidURLValueError(
            field_path,
            "must use http:// or https://",
        )

    if not parsed.hostname:
        raise InvalidURLValueError(
            field_path,
            "must include a hostname",
        )

    return value


def _normalize_access_path(
    value: str,
    access_type: AccessType,
    field_path: str,
) -> str:
    value = _normalize_required_string(
        value,
        field_path,
    )

    if access_type == AccessType.DOWNLOAD:
        parsed = urlparse(value)

        if parsed.scheme not in {"http", "https"}:
            raise ModelValidationError(
                field_path,
                "must be an absolute http:// or https:// URL when access_type is DOWNLOAD",
            )

        if not parsed.hostname:
            raise ModelValidationError(
                field_path,
                "must include a hostname when access_type is DOWNLOAD",
            )

    return value


def _normalize_timestamp(
    value: Optional[datetime],
    field_path: str,
) -> Optional[datetime]:
    if value is None:
        return None

    if not isinstance(value, datetime):
        raise InvalidTimestampError(
            field_path,
            "must be a datetime",
        )

    if value.tzinfo is None or value.utcoffset() is None:
        raise InvalidTimestampError(
            field_path,
            "must be timezone-aware",
        )

    return value.astimezone(timezone.utc)


def _normalize_metadata(
    value: dict[str, str],
    field_path: str,
) -> dict[str, str]:
    if not isinstance(value, dict):
        raise ModelValidationError(
            field_path,
            "must be a dict[str, str]",
        )

    normalized: dict[str, str] = {}

    for key, item in value.items():
        if not isinstance(key, str):
            raise ModelValidationError(
                f"{field_path}[{key!r}]",
                "must be a non-empty string",
            )

        normalized_key = key.strip()

        if not normalized_key:
            raise ModelValidationError(
                f"{field_path}[{key!r}]",
                "must be a non-empty string",
            )

        if normalized_key in normalized:
            raise ModelValidationError(
                f'{field_path}["{key}"]',
                f'duplicates key "{normalized_key}" after normalization',
            )

        if not isinstance(item, str):
            raise ModelValidationError(
                f'{field_path}["{normalized_key}"]',
                "must be a string",
            )

        normalized[normalized_key] = item.strip()

    return normalized


# ---------------------------------------------------------------------------
# Candidate source
#
# A source discovered during source discovery.
# Discovery does not imply that the source is valid or consumable.
# ---------------------------------------------------------------------------

@dataclass
class CandidateSource:
    source_id: str
    name: str
    base_url: str

    discovered_from: Optional[str] = None
    discovery_text: Optional[str] = None

    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        self.source_id = _normalize_identifier(
            self.source_id,
            "CandidateSource.source_id",
        )

        self.name = _normalize_required_string(
            self.name,
            "CandidateSource.name",
        )

        self.base_url = _normalize_base_url(
            self.base_url,
            "CandidateSource.base_url",
        )

        self.discovered_from = _normalize_optional_string(
            self.discovered_from,
            "CandidateSource.discovered_from",
        )

        self.discovery_text = _normalize_optional_string(
            self.discovery_text,
            "CandidateSource.discovery_text",
        )

        self.metadata = _normalize_metadata(
            self.metadata,
            "CandidateSource.metadata",
        )


# ---------------------------------------------------------------------------
# Source registry record
#
# Persistent knowledge about whether a source can be consumed and how.
# ---------------------------------------------------------------------------

@dataclass
class SourceRecord:
    source_id: str
    name: str
    base_url: str

    status: SourceStatus = SourceStatus.UNKNOWN

    access_type: Optional[AccessType] = None
    access_path: Optional[str] = None

    last_validated: Optional[datetime] = None
    validation_reason: Optional[str] = None

    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        self.source_id = _normalize_identifier(
            self.source_id,
            "SourceRecord.source_id",
        )

        self.name = _normalize_required_string(
            self.name,
            "SourceRecord.name",
        )

        self.base_url = _normalize_base_url(
            self.base_url,
            "SourceRecord.base_url",
        )

        if not isinstance(self.status, SourceStatus):
            raise InvalidStateError(
                "SourceRecord.status",
                "must be a valid SourceStatus",
            )

        if (
            self.access_type is not None
            and not isinstance(self.access_type, AccessType)
        ):
            raise InvalidStateError(
                "SourceRecord.access_type",
                "must be a valid AccessType",
            )

        self.access_path = _normalize_optional_string(
            self.access_path,
            "SourceRecord.access_path",
        )

        if (
            self.access_path is not None
            and self.access_type is not None
        ):
            self.access_path = _normalize_access_path(
                self.access_path,
                self.access_type,
                "SourceRecord.access_path",
            )

        self.last_validated = _normalize_timestamp(
            self.last_validated,
            "SourceRecord.last_validated",
        )

        self.validation_reason = _normalize_optional_string(
            self.validation_reason,
            "SourceRecord.validation_reason",
        )

        self.metadata = _normalize_metadata(
            self.metadata,
            "SourceRecord.metadata",
        )

        self._validate_state()

    def _validate_state(self) -> None:
        if self.status == SourceStatus.UNKNOWN:
            if self.last_validated is not None:
                raise InvalidStateError(
                    "SourceRecord.last_validated",
                    "must be None when status is UNKNOWN",
                )

            if self.access_type is not None:
                raise InvalidStateError(
                    "SourceRecord.access_type",
                    "must be None when status is UNKNOWN",
                )

            if self.access_path is not None:
                raise InvalidStateError(
                    "SourceRecord.access_path",
                    "must be None when status is UNKNOWN",
                )

            if self.validation_reason is not None:
                raise InvalidStateError(
                    "SourceRecord.validation_reason",
                    "must be None when status is UNKNOWN",
                )

        elif self.status == SourceStatus.VALID:
            if self.access_type is None:
                raise InvalidStateError(
                    "SourceRecord.access_type",
                    "is required when status is VALID",
                )

            if self.access_path is None:
                raise InvalidStateError(
                    "SourceRecord.access_path",
                    "is required when status is VALID",
                )

            if self.last_validated is None:
                raise InvalidStateError(
                    "SourceRecord.last_validated",
                    "is required when status is VALID",
                )

        elif self.status == SourceStatus.INVALID:
            if self.last_validated is None:
                raise InvalidStateError(
                    "SourceRecord.last_validated",
                    "is required when status is INVALID",
                )

            if self.validation_reason is None:
                raise InvalidStateError(
                    "SourceRecord.validation_reason",
                    "is required when status is INVALID",
                )

            if self.access_type is not None:
                raise InvalidStateError(
                    "SourceRecord.access_type",
                    "must be None when status is INVALID",
                )

            if self.access_path is not None:
                raise InvalidStateError(
                    "SourceRecord.access_path",
                    "must be None when status is INVALID",
                )


# ---------------------------------------------------------------------------
# Corpus record
#
# Persistent identity and access information for a corpus.
# source_id provides corpus provenance.
# ---------------------------------------------------------------------------

@dataclass
class CorpusRecord:
    corpus_id: str
    source_id: str

    name: str
    corpus_type: CorpusType

    access_path: str
    access_type: AccessType

    description: Optional[str] = None
    language: Optional[str] = None
    license: Optional[str] = None

    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        self.corpus_id = _normalize_identifier(
            self.corpus_id,
            "CorpusRecord.corpus_id",
        )

        self.source_id = _normalize_identifier(
            self.source_id,
            "CorpusRecord.source_id",
        )

        self.name = _normalize_required_string(
            self.name,
            "CorpusRecord.name",
        )

        if not isinstance(self.corpus_type, CorpusType):
            raise InvalidStateError(
                "CorpusRecord.corpus_type",
                "must be a valid CorpusType",
            )

        if not isinstance(self.access_type, AccessType):
            raise InvalidStateError(
                "CorpusRecord.access_type",
                "must be a valid AccessType",
            )

        self.access_path = _normalize_access_path(
            self.access_path,
            self.access_type,
            "CorpusRecord.access_path",
        )

        self.description = _normalize_optional_string(
            self.description,
            "CorpusRecord.description",
        )

        self.language = _normalize_optional_string(
            self.language,
            "CorpusRecord.language",
        )

        self.license = _normalize_optional_string(
            self.license,
            "CorpusRecord.license",
        )

        self.metadata = _normalize_metadata(
            self.metadata,
            "CorpusRecord.metadata",
        )


# ---------------------------------------------------------------------------
# Site record
#
# Optional structured representation of a site.
# The existing application may continue supplying sites from data.config.SITES.
# ---------------------------------------------------------------------------

@dataclass
class SiteRecord:
    site_id: str
    name: str

    alternate_names: list[str] = field(default_factory=list)

    country: Optional[str] = None
    region: Optional[str] = None

    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        self.site_id = _normalize_identifier(
            self.site_id,
            "SiteRecord.site_id",
        )

        self.name = _normalize_required_string(
            self.name,
            "SiteRecord.name",
        )

        if not isinstance(self.alternate_names, list):
            raise ModelValidationError(
                "SiteRecord.alternate_names",
                "must be a list[str]",
            )

        normalized_aliases: list[str] = []
        seen_aliases: set[str] = set()

        for index, alias in enumerate(self.alternate_names):
            if not isinstance(alias, str):
                raise ModelValidationError(
                    f"SiteRecord.alternate_names[{index}]",
                    "must be a string",
                )

            alias = alias.strip()

            if not alias:
                continue

            normalized_alias_key = (
                alias.lower()
                .replace(" ", "_")
                .replace("-", "_")
            )

            site_key = self.site_id.replace("-", "_")

            if normalized_alias_key == site_key:
                continue

            if normalized_alias_key in seen_aliases:
                continue

            seen_aliases.add(normalized_alias_key)
            normalized_aliases.append(alias)

        self.alternate_names = normalized_aliases

        self.country = _normalize_optional_string(
            self.country,
            "SiteRecord.country",
        )

        self.region = _normalize_optional_string(
            self.region,
            "SiteRecord.region",
        )

        self.metadata = _normalize_metadata(
            self.metadata,
            "SiteRecord.metadata",
        )


# ---------------------------------------------------------------------------
# Site/corpus relationship
#
# Unique persistence key:
#
#     (site_id, corpus_id)
#
# Persistence is responsible for enforcing uniqueness across records.
# ---------------------------------------------------------------------------

@dataclass
class SiteCorpusLink:
    site_id: str
    corpus_id: str

    load_status: CorpusLoadStatus = CorpusLoadStatus.LOADING

    loaded_at: Optional[datetime] = None
    unloaded_at: Optional[datetime] = None

    failure_reason: Optional[str] = None

    source_id: Optional[str] = None

    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        self.site_id = _normalize_identifier(
            self.site_id,
            "SiteCorpusLink.site_id",
        )

        self.corpus_id = _normalize_identifier(
            self.corpus_id,
            "SiteCorpusLink.corpus_id",
        )

        if self.source_id is not None:
            self.source_id = _normalize_identifier(
                self.source_id,
                "SiteCorpusLink.source_id",
            )

        if not isinstance(self.load_status, CorpusLoadStatus):
            raise InvalidStateError(
                "SiteCorpusLink.load_status",
                "must be a valid CorpusLoadStatus",
            )

        self.loaded_at = _normalize_timestamp(
            self.loaded_at,
            "SiteCorpusLink.loaded_at",
        )

        self.unloaded_at = _normalize_timestamp(
            self.unloaded_at,
            "SiteCorpusLink.unloaded_at",
        )

        self.failure_reason = _normalize_optional_string(
            self.failure_reason,
            "SiteCorpusLink.failure_reason",
        )

        self.metadata = _normalize_metadata(
            self.metadata,
            "SiteCorpusLink.metadata",
        )

        self._validate_state()
        self._validate_timestamps()

    def _validate_state(self) -> None:
        if self.load_status == CorpusLoadStatus.LOADING:
            if self.loaded_at is not None:
                raise InvalidStateError(
                    "SiteCorpusLink.loaded_at",
                    "must be None when load_status is LOADING",
                )

            if self.unloaded_at is not None:
                raise InvalidStateError(
                    "SiteCorpusLink.unloaded_at",
                    "must be None when load_status is LOADING",
                )

            if self.failure_reason is not None:
                raise InvalidStateError(
                    "SiteCorpusLink.failure_reason",
                    "must be None when load_status is LOADING",
                )

        elif self.load_status == CorpusLoadStatus.LOADED:
            if self.loaded_at is None:
                raise InvalidStateError(
                    "SiteCorpusLink.loaded_at",
                    "is required when load_status is LOADED",
                )

            if self.unloaded_at is not None:
                raise InvalidStateError(
                    "SiteCorpusLink.unloaded_at",
                    "must be None when load_status is LOADED",
                )

            if self.failure_reason is not None:
                raise InvalidStateError(
                    "SiteCorpusLink.failure_reason",
                    "must be None when load_status is LOADED",
                )

        elif self.load_status == CorpusLoadStatus.FAILED:
            if self.loaded_at is not None:
                raise InvalidStateError(
                    "SiteCorpusLink.loaded_at",
                    "must be None when load_status is FAILED",
                )

            if self.unloaded_at is not None:
                raise InvalidStateError(
                    "SiteCorpusLink.unloaded_at",
                    "must be None when load_status is FAILED",
                )

            if self.failure_reason is None:
                raise InvalidStateError(
                    "SiteCorpusLink.failure_reason",
                    "is required when load_status is FAILED",
                )

        elif self.load_status == CorpusLoadStatus.UNLOADED:
            if self.loaded_at is None:
                raise InvalidStateError(
                    "SiteCorpusLink.loaded_at",
                    "is required when load_status is UNLOADED",
                )

            if self.unloaded_at is None:
                raise InvalidStateError(
                    "SiteCorpusLink.unloaded_at",
                    "is required when load_status is UNLOADED",
                )

            if self.failure_reason is not None:
                raise InvalidStateError(
                    "SiteCorpusLink.failure_reason",
                    "must be None when load_status is UNLOADED",
                )

    def _validate_timestamps(self) -> None:
        if (
            self.loaded_at is not None
            and self.unloaded_at is not None
            and self.unloaded_at < self.loaded_at
        ):
            raise InvalidTimestampError(
                "SiteCorpusLink.unloaded_at",
                "must be greater than or equal to loaded_at",
            )


# ---------------------------------------------------------------------------
# Corpus search option
#
# This is the site-aware result returned by corpus discovery.
#
# loaded_state is resolved before constructing this object.
# differentiator_text is display information only and never determines state.
# ---------------------------------------------------------------------------

@dataclass
class CorpusOption:
    site_id: str

    corpus_id: str
    source_id: str

    corpus_name: str
    source_name: str

    corpus_type: CorpusType

    access_type: AccessType
    access_path: str

    description: Optional[str] = None

    loaded_state: CorpusLoadedState = CorpusLoadedState.AVAILABLE
    differentiator_text: Optional[str] = None

    metadata: dict[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        self.site_id = _normalize_identifier(
            self.site_id,
            "CorpusOption.site_id",
        )

        self.corpus_id = _normalize_identifier(
            self.corpus_id,
            "CorpusOption.corpus_id",
        )

        self.source_id = _normalize_identifier(
            self.source_id,
            "CorpusOption.source_id",
        )

        self.corpus_name = _normalize_required_string(
            self.corpus_name,
            "CorpusOption.corpus_name",
        )

        self.source_name = _normalize_required_string(
            self.source_name,
            "CorpusOption.source_name",
        )

        if not isinstance(self.corpus_type, CorpusType):
            raise InvalidStateError(
                "CorpusOption.corpus_type",
                "must be a valid CorpusType",
            )

        if not isinstance(self.access_type, AccessType):
            raise InvalidStateError(
                "CorpusOption.access_type",
                "must be a valid AccessType",
            )

        self.access_path = _normalize_access_path(
            self.access_path,
            self.access_type,
            "CorpusOption.access_path",
        )

        self.description = _normalize_optional_string(
            self.description,
            "CorpusOption.description",
        )

        if not isinstance(self.loaded_state, CorpusLoadedState):
            raise InvalidStateError(
                "CorpusOption.loaded_state",
                "must be a valid CorpusLoadedState",
            )

        self.differentiator_text = _normalize_optional_string(
            self.differentiator_text,
            "CorpusOption.differentiator_text",
        )

        self.metadata = _normalize_metadata(
            self.metadata,
            "CorpusOption.metadata",
        )
