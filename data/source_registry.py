from __future__ import annotations

import re
from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Iterable, Optional

import yaml

from data import config
from data.corpus_models import (
    AccessType,
    SourceRecord,
    SourceStatus,
)


FETCH_ACCESS_TYPES = {
    "wikipedia": AccessType.API,
    "archive_search": AccessType.API,
    "gutenberg_search": AccessType.API,
    "wikidata_place": AccessType.API,
    "url": AccessType.WEB,
}

_LOG_RESULT = re.compile(
    r"\[(?P<kind>ok|skip|ASK FIRST)\]\s+"
    r"(?P<source_id>[^:]+):\s*(?P<reason>.*)$"
)


class SourceRegistry:
    def __init__(
        self,
        sources_path: Path = config.SOURCES_YAML,
        resolved_path: Path = config.RESOLVED_YAML,
        ingest_log_lines: Iterable[str] = (),
        ingest_log_time: Optional[datetime] = None,
    ) -> None:
        self.sources_path = sources_path
        self.resolved_path = resolved_path

        self._catalog = self._load_catalog()
        self._resolved, self._listed_not_ingested = (
            self._load_resolved()
        )
        self._log_time = self._normalize_log_time(
            ingest_log_time
        )
        self._outcomes = self._load_outcomes(
            ingest_log_lines
        )

    def all(self) -> list[SourceRecord]:
        source_ids = (
            set(self._catalog)
            | set(self._resolved)
            | set(self._listed_not_ingested)
            | set(self._outcomes)
        )

        return [
            self._build_record(source_id)
            for source_id in sorted(source_ids)
        ]

    def search_valid_sources(
        self,
        sources: Iterable[SourceRecord],
    ) -> list[SourceRecord]:
        # TODO: validate sources and return only consumable sources.
        return list(sources)

    def selectable_sources(
        self,
        sources: Iterable[SourceRecord],
    ) -> list[SourceRecord]:
        return list(sources)

    def get_by_id(
        self,
        source_id: str,
    ) -> Optional[SourceRecord]:
        key = self._normalize_source_id(source_id)

        if key not in self._source_ids():
            return None

        return self._build_record(key)

    def get_by_url(
        self,
        base_url: str,
    ) -> Optional[SourceRecord]:
        normalized_url = base_url.strip()

        resolved_matches = sorted(
            source_id
            for source_id, source in self._resolved.items()
            if source.get("url") == normalized_url
        )

        if resolved_matches:
            return self._build_record(
                resolved_matches[0]
            )

        catalog_matches = sorted(
            source_id
            for source_id, source in self._catalog.items()
            if source.get("url") == normalized_url
        )

        if catalog_matches:
            return self._build_record(
                catalog_matches[0]
            )

        return None

    def status(
        self,
        source_id: str,
    ) -> Optional[SourceStatus]:
        record = self.get_by_id(source_id)
        return record.status if record is not None else None

    def _source_ids(self) -> set[str]:
        return (
            set(self._catalog)
            | set(self._resolved)
            | set(self._listed_not_ingested)
            | set(self._outcomes)
        )

    def _load_catalog(self) -> dict[str, dict]:
        if not self.sources_path.exists():
            return {}

        raw = yaml.safe_load(
            self.sources_path.read_text(
                encoding="utf-8"
            )
        ) or {}

        return {
            self._normalize_source_id(source["id"]):
                source
            for source in raw.get("sources", [])
        }

    def _load_resolved(
        self,
    ) -> tuple[dict[str, dict], dict[str, dict]]:
        if not self.resolved_path.exists():
            return {}, {}

        raw = yaml.safe_load(
            self.resolved_path.read_text(
                encoding="utf-8"
            )
        ) or {}

        resolved = {
            self._normalize_source_id(source["id"]):
                source
            for source in raw.get("sources", [])
        }

        listed_not_ingested = {
            self._normalize_source_id(source["id"]):
                source
            for source in raw.get(
                "listed_but_not_ingested",
                [],
            )
        }

        return resolved, listed_not_ingested

    def _load_outcomes(
        self,
        ingest_log_lines: Iterable[str],
    ) -> dict[str, tuple[str, str]]:
        outcomes: dict[str, tuple[str, str]] = {}

        for line in ingest_log_lines:
            match = _LOG_RESULT.search(line)

            if match is None:
                continue

            kind = match.group("kind")
            source_id = self._normalize_source_id(
                match.group("source_id")
            )
            reason = match.group("reason").strip()

            if kind == "ok":
                state = "success"
            elif kind == "skip":
                state = "failed"
            else:
                state = "deferred"

            outcomes[source_id] = (
                state,
                reason,
            )

        return outcomes

    def _build_record(
        self,
        source_id: str,
    ) -> SourceRecord:
        catalog = self._catalog.get(
            source_id,
            {},
        )
        resolved = self._resolved.get(
            source_id,
            {},
        )
        listed = self._listed_not_ingested.get(
            source_id,
            {},
        )
        outcome = self._outcomes.get(
            source_id
        )

        status = self._derive_status(
            source_id
        )

        name = (
            resolved.get("title")
            or catalog.get("title")
            or listed.get("title")
            or source_id
        )

        base_url = (
            catalog.get("url")
            or resolved.get("url")
            or listed.get("url")
        )

        if base_url is None:
            raise ValueError(
                f"SourceRegistry source "
                f"{source_id!r} has no URL"
            )

        metadata = self._metadata(
            catalog,
            resolved,
            listed,
        )

        if status == SourceStatus.VALID:
            access_type = self._access_type(
                source_id,
                catalog,
                resolved,
            )
            access_path = (
                resolved.get("url")
                or catalog.get("url")
            )
            last_validated = (
                self._resolved_timestamp(
                    resolved
                )
                or self._log_time
            )
            validation_reason = (
                outcome[1]
                if outcome
                and outcome[0] == "success"
                else "successfully ingested"
            )

        elif status == SourceStatus.INVALID:
            access_type = None
            access_path = None
            last_validated = self._log_time
            validation_reason = (
                outcome[1]
                if outcome is not None
                else "ingest failed"
            )

        else:
            access_type = None
            access_path = None
            last_validated = None
            validation_reason = None

        return SourceRecord(
            source_id=source_id,
            name=name,
            base_url=base_url,
            status=status,
            access_type=access_type,
            access_path=access_path,
            last_validated=last_validated,
            validation_reason=validation_reason,
            metadata=metadata,
        )

    def _derive_status(
        self,
        source_id: str,
    ) -> SourceStatus:
        outcome = self._outcomes.get(
            source_id
        )

        if outcome is not None:
            state, _ = outcome

            if state == "failed":
                return SourceStatus.INVALID

            if state == "success":
                return SourceStatus.VALID

            if state == "deferred":
                if source_id in self._resolved:
                    return SourceStatus.VALID

                return SourceStatus.UNKNOWN

        if source_id in self._resolved:
            return SourceStatus.VALID

        return SourceStatus.UNKNOWN

    def _access_type(
        self,
        source_id: str,
        catalog: dict,
        resolved: dict,
    ) -> AccessType:
        fetch_kind = (
            catalog.get("fetch", {})
            .get("kind")
        )

        if fetch_kind in FETCH_ACCESS_TYPES:
            return FETCH_ACCESS_TYPES[
                fetch_kind
            ]

        if (
            source_id.startswith("oa_")
            or resolved.get("doi")
        ):
            return AccessType.API

        return AccessType.WEB

    def _resolved_timestamp(
        self,
        resolved: dict,
    ) -> Optional[datetime]:
        retrieved = resolved.get("retrieved")

        if not retrieved:
            return None

        parsed = date.fromisoformat(
            str(retrieved)
        )

        return datetime.combine(
            parsed,
            time.min,
            tzinfo=timezone.utc,
        )

    def _metadata(
        self,
        catalog: dict,
        resolved: dict,
        listed: dict,
    ) -> dict[str, str]:
        metadata: dict[str, str] = {}

        for source in (
            catalog,
            listed,
            resolved,
        ):
            self._copy_metadata(
                metadata,
                source,
            )

        return metadata

    def _copy_metadata(
        self,
        metadata: dict[str, str],
        source: dict,
    ) -> None:
        fields = (
            "site",
            "type",
            "license",
            "period",
            "year",
            "note",
            "enabled",
            "keep_regex",
            "doi",
            "n_passages",
            "archive_id",
            "archive_rights",
            "archive_year",
            "fulltext_url",
            "upstream_title",
        )

        for field_name in fields:
            value = source.get(field_name)

            if value is None:
                continue

            key = (
                "source_type"
                if field_name == "type"
                else field_name
            )

            metadata[key] = str(value)

    def _normalize_source_id(
        self,
        source_id: str,
    ) -> str:
        return (
            source_id.strip()
            .lower()
            .replace(" ", "_")
        )

    def _normalize_log_time(
        self,
        value: Optional[datetime],
    ) -> datetime:
        if value is None:
            return datetime.now(
                timezone.utc
            )

        if (
            value.tzinfo is None
            or value.utcoffset() is None
        ):
            raise ValueError(
                "ingest_log_time must be "
                "timezone-aware"
            )

        return value.astimezone(
            timezone.utc
        )
