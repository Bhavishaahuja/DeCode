from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import yaml

from data import config
from data.corpus_models import (
    CorpusLoadStatus,
    SiteCorpusLink,
)
from data.corpus_selection import CorpusSelection


ConsumedCorpus = tuple[
    dict,
    list[dict],
]

CorpusConsumer = Callable[
    [str, object],
    ConsumedCorpus,
]


@dataclass
class CorpusImport:
    link: SiteCorpusLink
    resolved_source: dict | None = None
    passages: list[dict] | None = None
    imported: bool = False


def import_selected_corpus(
    selection: CorpusSelection,
    consume_source: CorpusConsumer,
    passages_path: Path = config.PASSAGES_JSONL,
    resolved_path: Path = config.RESOLVED_YAML,
) -> CorpusImport:
    if not selection.send_to_intake:
        return CorpusImport(
            link=selection.existing_link,
            imported=False,
        )

    resolved_source, passages = consume_source(
        selection.site_id,
        selection.source,
    )

    source_id = selection.source.source_id

    if resolved_source.get("id") != source_id:
        raise ValueError(
            "consumed source id does not match "
            "selected source"
        )

    if resolved_source.get("site") != selection.site_id:
        raise ValueError(
            "consumed source site does not match "
            "selected site"
        )

    for passage in passages:
        if passage.get("source_id") != source_id:
            raise ValueError(
                "passage source does not match "
                "selected source"
            )

        if passage.get("site") != selection.site_id:
            raise ValueError(
                "passage site does not match "
                "selected site"
            )

    _persist_passages(
        passages_path,
        source_id,
        passages,
    )

    _persist_resolved_source(
        resolved_path,
        resolved_source,
    )

    link = SiteCorpusLink(
        site_id=selection.site_id,
        corpus_id=source_id,
        source_id=source_id,
        load_status=CorpusLoadStatus.LOADED,
        loaded_at=datetime.now(timezone.utc),
    )

    return CorpusImport(
        link=link,
        resolved_source=resolved_source,
        passages=passages,
        imported=True,
    )


def _persist_passages(
    path: Path,
    source_id: str,
    imported: list[dict],
) -> None:
    existing = []

    if path.exists():
        existing = [
            json.loads(line)
            for line in path.read_text(
                encoding="utf-8"
            ).splitlines()
            if line.strip()
        ]

    combined = [
        passage
        for passage in existing
        if passage.get("source_id") != source_id
    ]

    combined.extend(imported)

    with path.open(
        "w",
        encoding="utf-8",
    ) as handle:
        for passage in combined:
            handle.write(
                json.dumps(
                    passage,
                    ensure_ascii=False,
                )
                + "\n"
            )


def _persist_resolved_source(
    path: Path,
    imported: dict,
) -> None:
    if path.exists():
        payload = yaml.safe_load(
            path.read_text(
                encoding="utf-8"
            )
        ) or {}
    else:
        payload = {}

    sources = list(
        payload.get("sources", [])
    )

    sources = [
        source
        for source in sources
        if source.get("id") != imported["id"]
    ]

    sources.append(imported)

    payload["generated"] = (
        datetime.now(timezone.utc)
        .isoformat(timespec="seconds")
    )
    payload["sources"] = sources
    payload.setdefault(
        "listed_but_not_ingested",
        [],
    )

    path.write_text(
        yaml.safe_dump(
            payload,
            sort_keys=False,
            allow_unicode=True,
            width=180,
        ),
        encoding="utf-8",
    )
