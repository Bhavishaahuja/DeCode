from __future__ import annotations

from collections.abc import Iterable

from data.decode_models import (
    DecodeRunRecord,
    PersistedTransform,
    PersistedTransformLink,
)


class DecodeStore:
    def save_transforms(
        self,
        transforms: Iterable[PersistedTransform],
    ) -> None:
        # TODO:
        # Persist transforms through the existing
        # data layer once a transform store exists.
        raise NotImplementedError

    def save_links(
        self,
        links: Iterable[PersistedTransformLink],
    ) -> None:
        # TODO:
        # Persist evidence links through the existing
        # data layer once a transform-link store exists.
        raise NotImplementedError

    def save_run(
        self,
        run: DecodeRunRecord,
    ) -> None:
        # TODO:
        # Persist decode run state through the existing
        # data layer once a decode-run store exists.
        raise NotImplementedError
