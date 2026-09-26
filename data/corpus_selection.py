from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from data.corpus_models import (
    CorpusLoadStatus,
    SiteCorpusLink,
    SourceRecord,
)


@dataclass
class CorpusSelection:
    site_id: str
    source: SourceRecord
    existing_link: Optional[SiteCorpusLink] = None

    @property
    def send_to_intake(self) -> bool:
        return self.existing_link is None

    def __post_init__(self) -> None:
        self.site_id = (
            self.site_id.strip()
            .lower()
            .replace(" ", "_")
        )

        if not self.site_id:
            raise ValueError(
                "site_id must not be empty"
            )


def select_corpus(
    site_id: str,
    source: SourceRecord,
    selectable_sources: Iterable[SourceRecord],
    existing_links: Iterable[SiteCorpusLink],
) -> CorpusSelection:
    selectable = list(selectable_sources)

    if not any(
        candidate.source_id == source.source_id
        for candidate in selectable
    ):
        raise ValueError(
            "selected source is not in selectable sources"
        )

    normalized_site_id = (
        site_id.strip()
        .lower()
        .replace(" ", "_")
    )

    existing_link = next(
        (
            link
            for link in existing_links
            if (
                link.site_id == normalized_site_id
                and link.source_id == source.source_id
                and link.load_status
                is CorpusLoadStatus.LOADED
            )
        ),
        None,
    )

    return CorpusSelection(
        site_id=normalized_site_id,
        source=source,
        existing_link=existing_link,
    )
