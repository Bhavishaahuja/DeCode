from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable


@dataclass(frozen=True)
class TransformLink:
    transform_id: str
    source_id: str
    site_id: str
    passage_id: str | None = None
    locator: str | None = None


@dataclass(frozen=True)
class TransformExtract:
    transform_id: str
    text: str
    evidence: tuple[
        TransformLink,
        ...,
    ] = ()


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


CoreEvaluator = Callable[
    [list[dict]],
    Iterable[TransformExtract],
]

ChildEvaluator = Callable[
    [
        TransformRecord,
        list[dict],
    ],
    Iterable[TransformExtract],
]


def extract_core_transforms(
    passages: Iterable[dict],
    evaluator: CoreEvaluator,
    graph: TransformGraph | None = None,
) -> TransformGraph:
    graph = graph or TransformGraph()
    corpus = list(passages)

    for extracted in evaluator(corpus):
        transform = graph.add_core_transform(
            extracted.transform_id,
            extracted.text,
        )

        for link in extracted.evidence:
            graph.add_link(
                TransformLink(
                    transform_id=(
                        transform.transform_id
                    ),
                    source_id=link.source_id,
                    site_id=link.site_id,
                    passage_id=link.passage_id,
                    locator=link.locator,
                )
            )

    return graph


def extract_child_transforms(
    parent_transform_id: str,
    passages: Iterable[dict],
    evaluator: ChildEvaluator,
    graph: TransformGraph,
) -> list[TransformRecord]:
    parent = graph.transforms.get(
        parent_transform_id
    )

    if parent is None:
        raise ValueError(
            "parent transform does not exist"
        )

    linked_passages = _linked_evidence(
        parent,
        passages,
        graph,
    )

    children = []

    for extracted in evaluator(
        parent,
        linked_passages,
    ):
        child = graph.add_derived_transform(
            extracted.transform_id,
            extracted.text,
            parent_transform_id=(
                parent.transform_id
            ),
        )

        for link in extracted.evidence:
            graph.add_link(
                TransformLink(
                    transform_id=(
                        child.transform_id
                    ),
                    source_id=link.source_id,
                    site_id=link.site_id,
                    passage_id=link.passage_id,
                    locator=link.locator,
                )
            )

        children.append(child)

    return children


def recursively_extract_children(
    parent_transform_id: str,
    passages: Iterable[dict],
    evaluator: ChildEvaluator,
    graph: TransformGraph,
) -> list[TransformRecord]:
    corpus = list(passages)
    descendants = []

    children = extract_child_transforms(
        parent_transform_id,
        corpus,
        evaluator,
        graph,
    )

    descendants.extend(children)

    for child in children:
        descendants.extend(
            recursively_extract_children(
                child.transform_id,
                corpus,
                evaluator,
                graph,
            )
        )

    return descendants


def _linked_evidence(
    parent: TransformRecord,
    passages: Iterable[dict],
    graph: TransformGraph,
) -> list[dict]:
    links = graph.links_for(
        parent.transform_id
    )

    passage_ids = {
        link.passage_id
        for link in links
        if link.passage_id is not None
    }

    source_ids = {
        link.source_id
        for link in links
    }

    site_ids = {
        link.site_id
        for link in links
    }

    return [
        passage
        for passage in passages
        if (
            passage.get("passage_id")
            in passage_ids
            or passage.get("source_id")
            in source_ids
            or passage.get("site")
            in site_ids
        )
    ]
