from __future__ import annotations

from data.corpus_models import (
    CorpusLoadStatus,
    SourceStatus,
)


class StateStore:
    def update_source_status(
        self,
        source_id: str,
        status: SourceStatus,
        reason: str | None = None,
    ) -> None:
        # TODO:
        # Route this through the existing source
        # registry persistence layer.
        raise NotImplementedError

    def update_corpus_load_status(
        self,
        site_id: str,
        corpus_id: str,
        source_id: str,
        status: CorpusLoadStatus,
        reason: str | None = None,
    ) -> None:
        # TODO:
        # Persist SiteCorpusLink state through the
        # existing data layer when that writer exists.
        raise NotImplementedError
