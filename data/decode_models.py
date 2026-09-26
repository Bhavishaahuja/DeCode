from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum

from data.corpus_models import (
    CorpusLoadStatus,
    SourceStatus,
)


class DecodeStatus(str, Enum):
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


SOURCE_STATUS_TRANSITIONS = {
    SourceStatus.UNKNOWN: {
        SourceStatus.VALID,
        SourceStatus.INVALID,
    },
    SourceStatus.VALID: {
        SourceStatus.VALID,
        SourceStatus.INVALID,
    },
    SourceStatus.INVALID: {
        SourceStatus.INVALID,
        SourceStatus.VALID,
    },
}


CORPUS_LOAD_STATUS_TRANSITIONS = {
    CorpusLoadStatus.LOADING: {
        CorpusLoadStatus.LOADED,
        CorpusLoadStatus.FAILED,
    },
    CorpusLoadStatus.FAILED: {
        CorpusLoadStatus.LOADING,
    },
    CorpusLoadStatus.LOADED: {
        CorpusLoadStatus.UNLOADED,
    },
    CorpusLoadStatus.UNLOADED: {
        CorpusLoadStatus.LOADING,
    },
}


DECODE_STATUS_TRANSITIONS = {
    DecodeStatus.RUNNING: {
        DecodeStatus.COMPLETE,
        DecodeStatus.FAILED,
    },
    DecodeStatus.COMPLETE: set(),
    DecodeStatus.FAILED: {
        DecodeStatus.RUNNING,
    },
}


@dataclass(frozen=True)
class PersistedTransform:
    transform_id: str
    text: str
    parent_transform_id: str | None
    root_transform_id: str
    depth: int


@dataclass(frozen=True)
class PersistedTransformLink:
    transform_id: str
    source_id: str
    site_id: str
    passage_id: str | None = None
    locator: str | None = None


@dataclass(frozen=True)
class DecodeRunRecord:
    source_id: str
    site_id: str
    root_transform_count: int
    derived_transform_count: int
    decode_status: DecodeStatus
    started_at: datetime
    completed_at: datetime | None = None
    failure_reason: str | None = None
