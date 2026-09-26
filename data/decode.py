from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable


@dataclass(frozen=True)
class TransformLink:
    transform_id: str
    source_id: str
    site_id: str
    passage_id: str | None = None
    locator: str | None = None


@dataclass
class TransformRecord:
    transform_id: str
    text: str

    parent_transform_id: str | None = None
    root_transform_id: str | None = None
    depth: int = 0

    def __post_init__(self) -> None:
        self.transform_id = self.transform_id.strip()
        self.text = self.text.strip()

        if not self.transform_id:
            raise ValueError(
                "transform_id must not be empty"
            )

        if not self.text:
            raise ValueError(
                "transform text must not be empty"
            )

        if self.parent_transform_id is None:
            self.root_transform_id = (
                self.transform_id
            )
            self.depth = 0


@dataclass
class TransformGraph:
    transforms: dict[
        str,
        TransformRecord,
    ] = field(default_factory=dict)

    links: list[
        TransformLink
    ] = field(default_factory=list)

    def add_core_transform(
        self,
        transform_id: str,
        text: str,
    ) -> TransformRecord:
        if transform_id in self.transforms:
            raise ValueError(
                "transform already exists"
            )

        transform = TransformRecord(
            transform_id=transform_id,
            text=text,
        )

        self.transforms[
            transform.transform_id
        ] = transform

        return transform

    def add_derived_transform(
        self,
        transform_id: str,
        text: str,
        parent_transform_id: str,
    ) -> TransformRecord:
        if transform_id in self.transforms:
            raise ValueError(
                "transform already exists"
            )

        parent = self.transforms.get(
            parent_transform_id
        )

        if parent is None:
            raise ValueError(
                "parent transform does not exist"
            )

        transform = TransformRecord(
            transform_id=transform_id,
            text=text,
            parent_transform_id=(
                parent.transform_id
            ),
            root_transform_id=(
                parent.root_transform_id
            ),
            depth=parent.depth + 1,
        )

        self.transforms[
            transform.transform_id
        ] = transform

        return transform

    def add_link(
        self,
        link: TransformLink,
    ) -> None:
        if (
            link.transform_id
            not in self.transforms
        ):
            raise ValueError(
                "linked transform does not exist"
            )

        if link not in self.links:
            self.links.append(link)

    def links_for(
        self,
        transform_id: str,
    ) -> list[TransformLink]:
        return [
            link
            for link in self.links
            if (
                link.transform_id
                == transform_id
            )
        ]


def decode_core(
    passages: Iterable[dict],
) -> list[TransformRecord]:
    # TODO:
    # Extract the initial core transform set
    # from the root corpus.
    list(passages)
    return []


def decode_deeper(
    parent: TransformRecord,
    passages: Iterable[dict],
) -> list[TransformRecord]:
    # TODO:
    # Re-resolve the parent transform against
    # newly loaded material and return any
    # deeper transforms derived from it.
    list(passages)
    return []
