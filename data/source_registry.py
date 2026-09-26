from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from data.corpus_models import (
    AccessType,
    InvalidRelationshipError,
    SourceRecord,
    SourceStatus,
)


class SourceRegistry:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._records = self._load()

    def all(self) -> list[SourceRecord]:
        return list(self._records.values())

    def get_by_id(self, source_id: str) -> Optional[SourceRecord]:
        key = source_id.strip().lower().replace(" ", "_")
        return self._records.get(key)

    def get_by_url(self, base_url: str) -> Optional[SourceRecord]:
        normalized_url = base_url.strip()

        for record in self._records.values():
            if record.base_url == normalized_url:
                return record

        return None

    def upsert(self, record: SourceRecord) -> None:
        existing_by_url = self.get_by_url(record.base_url)

        if (
            existing_by_url is not None
            and existing_by_url.source_id != record.source_id
        ):
            raise InvalidRelationshipError(
                "SourceRegistry.base_url",
                (
                    f'URL "{record.base_url}" is already registered '
                    f'as source "{existing_by_url.source_id}"'
                ),
            )

        self._records[record.source_id] = record
        self._save()

    def _load(self) -> dict[str, SourceRecord]:
        if not self.path.exists():
            return {}

        raw = json.loads(self.path.read_text(encoding="utf-8"))

        records: dict[str, SourceRecord] = {}

        for item in raw.get("sources", []):
            last_validated = item.get("last_validated")

            record = SourceRecord(
                source_id=item["source_id"],
                name=item["name"],
                base_url=item["base_url"],
                status=SourceStatus(item["status"]),
                access_type=(
                    AccessType(item["access_type"])
                    if item.get("access_type") is not None
                    else None
                ),
                access_path=item.get("access_path"),
                last_validated=(
                    datetime.fromisoformat(last_validated)
                    if last_validated is not None
                    else None
                ),
                validation_reason=item.get("validation_reason"),
                metadata=item.get("metadata", {}),
            )

            existing_by_url = next(
                (
                    existing
                    for existing in records.values()
                    if existing.base_url == record.base_url
                ),
                None,
            )

            if (
                existing_by_url is not None
                and existing_by_url.source_id != record.source_id
            ):
                raise InvalidRelationshipError(
                    "SourceRegistry.base_url",
                    (
                        f'URL "{record.base_url}" is already registered '
                        f'as source "{existing_by_url.source_id}"'
                    ),
                )

            records[record.source_id] = record

        return records

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "sources": [
                {
                    "source_id": record.source_id,
                    "name": record.name,
                    "base_url": record.base_url,
                    "status": record.status.value,
                    "access_type": (
                        record.access_type.value
                        if record.access_type is not None
                        else None
                    ),
                    "access_path": record.access_path,
                    "last_validated": (
                        record.last_validated.isoformat()
                        if record.last_validated is not None
                        else None
                    ),
                    "validation_reason": record.validation_reason,
                    "metadata": record.metadata,
                }
                for record in self._records.values()
            ]
        }

        self.path.write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
