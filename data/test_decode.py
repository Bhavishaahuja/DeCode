import pytest

from data.decode import (
    TransformGraph,
    TransformLink,
    decode_core,
    decode_deeper,
)


def test_core_transform_is_its_own_root():
    graph = TransformGraph()

    transform = graph.add_core_transform(
        "t1",
        "move material",
    )

    assert transform.parent_transform_id is None
    assert transform.root_transform_id == "t1"
    assert transform.depth == 0


def test_derived_transform_links_to_parent():
    graph = TransformGraph()

    graph.add_core_transform(
        "t1",
        "move material",
    )

    child = graph.add_derived_transform(
        "t1_1",
        "move material by water",
        parent_transform_id="t1",
    )

    assert child.parent_transform_id == "t1"
    assert child.root_transform_id == "t1"
    assert child.depth == 1


def test_recursive_transform_keeps_original_root():
    graph = TransformGraph()

    graph.add_core_transform(
        "t1",
        "move material",
    )

    graph.add_derived_transform(
        "t1_1",
        "move material by water",
        parent_transform_id="t1",
    )

    grandchild = graph.add_derived_transform(
        "t1_1_1",
        "move stone by barge",
        parent_transform_id="t1_1",
    )

    assert (
        grandchild.parent_transform_id
        == "t1_1"
    )
    assert (
        grandchild.root_transform_id
        == "t1"
    )
    assert grandchild.depth == 2


def test_transform_can_have_many_evidence_links():
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

    graph.add_link(
        TransformLink(
            transform_id="t1",
            source_id="source_b",
            site_id="uruk",
            passage_id="p2",
        )
    )

    links = graph.links_for("t1")

    assert len(links) == 2
    assert {
        link.source_id
        for link in links
    } == {
        "source_a",
        "source_b",
    }


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


def test_derived_transform_requires_parent():
    graph = TransformGraph()

    with pytest.raises(
        ValueError,
        match="parent transform does not exist",
    ):
        graph.add_derived_transform(
            "t1_1",
            "move material by water",
            parent_transform_id="t1",
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


def test_link_requires_existing_transform():
    graph = TransformGraph()

    with pytest.raises(
        ValueError,
        match="linked transform does not exist",
    ):
        graph.add_link(
            TransformLink(
                transform_id="missing",
                source_id="source_a",
                site_id="giza",
            )
        )


def test_core_decode_is_stubbed():
    assert decode_core([]) == []


def test_deeper_decode_is_stubbed():
    graph = TransformGraph()

    parent = graph.add_core_transform(
        "t1",
        "move material",
    )

    assert (
        decode_deeper(
            parent,
            [],
        )
        == []
    )
