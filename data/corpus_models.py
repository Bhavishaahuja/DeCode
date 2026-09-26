from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


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


@dataclass
class SiteRecord:
    site_id: str
    name: str
    alternate_names: list[str] = field(default_factory=list)
    country: Optional[str] = None
    region: Optional[str] = None
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class SiteCorpusLink:
    site_id: str
    corpus_id: str
    linked_at: datetime = field(default_factory=datetime.utcnow)
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass
class CorpusSearchOption:
    corpus_id: str
    source_id: str
    corpus_name: str
    source_name: str
    corpus_type: CorpusType
    access_type: AccessType
    access_path: str
    description: Optional[str] = None
