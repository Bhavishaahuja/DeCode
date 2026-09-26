import pytest

from data.decode import (
    TransformExtract,
    TransformGraph,
    TransformLink,
    extract_child_transforms,
    extract_core_transforms,
    recursively_extract_children,
)


CORPUS = [
    {
        "passage_id": "p1",
        "source_id": "source_a",
        "site": "giza",
        "text": "move stone",
    },
    {
        "passage_id": "p2",
        "source_id": "source_b",
        "site": "uruk",
        "text": "move by water",
    },
    {
        "passage_id": "p3",
        "source_id": "source_c",
        "site": "qin",
        "text": "unrelated",
    },
]


def test_core_pass_receives_full_corpus():
    received = []

    def evaluator(passages):
        received.extend(passages)
        return []

    extract_core_transforms(
        CORPUS,
        evaluator,
    )

    assert received == CORPUS


def test_core_pass_builds_root_transforms_and_links():
    def evaluator(passages):
        return [
            TransformExtract(
                transform_id="t1",
                text="move material",
                evidence=(
                    TransformLink(
                        transform_id="ignored",
                        source_id="source_a",
                        site_id="giza",
                        passage_id="p1",
                    ),
                ),
            )
        ]

    graph = extract_core_transforms(
        CORPUS,
        evaluator,
    )

    transform = graph.transforms["t1"]

    assert transform.parent_transform_id is None
    assert transform.root_transform_id == "t1"
    assert transform.depth == 0

    assert graph.links_for("t1") == [
        TransformLink(
            transform_id="t1",
            source_id="source_a",
            site_id="giza",
            passage_id="p1",
        )
    ]


def test_child_pass_receives_only_parent_linked_evidence():
    graph = TransformGraph()

    graph.add_core_transform(
        "t1",
        "move material",
    )

    graph.add_link(
        TransformLink(
            transform_id="t1",
            source_id="source_a",
            site_id="giza",
            passage_id="p1",
        )
    )

    received = []

    def evaluator(parent, passages):
        received.extend(passages)
        return []

    extract_child_transforms(
        "t1",
        CORPUS,
        evaluator,
        graph,
    )

    assert received == [CORPUS[0]]


def test_child_pass_creates_child_with_ancestry():
    graph = TransformGraph()

    graph.add_core_transform(
        "t1",
        "move material",
    )

    graph.add_link(
        TransformLink(
            transform_id="t1",
            source_id="source_a",
            site_id="giza",
            passage_id="p1",
        )
    )

    def evaluator(parent, passages):
        return [
            TransformExtract(
                transform_id="t1_1",
                text="move stone",
            )
        ]

    children = extract_child_transforms(
        "t1",
        CORPUS,
        evaluator,
        graph,
    )

    child = children[0]

    assert child.parent_transform_id == "t1"
    assert child.root_transform_id == "t1"
    assert child.depth == 1


def test_child_evidence_is_attached_to_child():
    graph = TransformGraph()

    graph.add_core_transform(
        "t1",
        "move material",
    )

    graph.add_link(
        TransformLink(
            transform_id="t1",
            source_id="source_a",
            site_id="giza",
            passage_id="p1",
        )
    )

    def evaluator(parent, passages):
        return [
            TransformExtract(
                transform_id="t1_1",
                text="move stone",
                evidence=(
                    TransformLink(
                        transform_id="ignored",
                        source_id="source_b",
                        site_id="uruk",
                        passage_id="p2",
                    ),
                ),
            )
        ]

    extract_child_transforms(
        "t1",
        CORPUS,
        evaluator,
        graph,
    )

    assert graph.links_for("t1_1") == [
        TransformLink(
            transform_id="t1_1",
            source_id="source_b",
            site_id="uruk",
            passage_id="p2",
        )
    ]


def test_recursive_pass_only_builds_children():
    graph = TransformGraph()

    graph.add_core_transform(
        "t1",
        "move material",
    )

    graph.add_link(
        TransformLink(
            transform_id="t1",
            source_id="source_a",
            site_id="giza",
            passage_id="p1",
        )
    )

    def evaluator(parent, passages):
        if parent.transform_id == "t1":
            return [
                TransformExtract(
                    transform_id="t1_1",
                    text="move stone",
                    evidence=(
                        TransformLink(
                            transform_id="ignored",
                            source_id="source_b",
                            site_id="uruk",
                            passage_id="p2",
                        ),
                    ),
                )
            ]

        if parent.transform_id == "t1_1":
            return [
                TransformExtract(
                    transform_id="t1_1_1",
                    text="move stone by water",
                )
            ]

        return []

    descendants = recursively_extract_children(
        "t1",
        CORPUS,
        evaluator,
        graph,
    )

    assert [
        transform.transform_id
        for transform in descendants
    ] == [
        "t1_1",
        "t1_1_1",
    ]

    grandchild = graph.transforms[
        "t1_1_1"
    ]

    assert (
        grandchild.parent_transform_id
        == "t1_1"
    )
    assert (
        grandchild.root_transform_id
        == "t1"
    )
    assert grandchild.depth == 2


def test_child_pass_requires_existing_parent():
    graph = TransformGraph()

    with pytest.raises(
        ValueError,
        match="parent transform does not exist",
    ):
        extract_child_transforms(
            "missing",
            CORPUS,
            lambda parent, passages: [],
            graph,
        )


def test_transform_ids_are_unique():
    graph = TransformGraph()

    graph.add_core_transform(
        "t1",
        "move material",
    )

    with pytest.raises(
        ValueError,
        match="transform already exists",
    ):
        graph.add_core_transform(
            "t1",
            "another transform",
        )


def test_duplicate_evidence_link_is_not_added_twice():
    graph = TransformGraph()

    graph.add_core_transform(
        "t1",
        "move material",
    )

    link = TransformLink(
        transform_id="t1",
        source_id="source_a",
        site_id="giza",
        passage_id="p1",
    )

    graph.add_link(link)
    graph.add_link(link)

    assert graph.links_for("t1") == [link]
