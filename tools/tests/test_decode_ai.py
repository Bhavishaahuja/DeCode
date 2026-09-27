from __future__ import annotations

from types import SimpleNamespace

import pytest

from data.decode import TransformRecord
from tools.decode_ai import (
    AnthropicDecodeEvaluator,
    run_decode,
)


PASSAGES = [
    {
        "passage_id": "giza-source-a-0001",
        "source_id": "source-a",
        "site": "giza",
        "locator": "p. 10",
        "text": "First passage.",
    },
    {
        "passage_id": "giza-source-b-0002",
        "source_id": "source-b",
        "site": "giza",
        "locator": "p. 20",
        "text": "Second passage.",
    },
]


class FakeMessages:
    def __init__(self, transforms):
        self.transforms = transforms
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)

        block = SimpleNamespace(
            type="tool_use",
            name="record_transforms",
            input={
                "transforms": self.transforms,
            },
        )

        return SimpleNamespace(
            content=[block]
        )


class FakeClient:
    def __init__(self, transforms):
        self.messages = FakeMessages(
            transforms
        )


def test_core_evaluator_returns_transform_extracts(
    tmp_path,
):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text(
        "Resolve through Monads.",
        encoding="utf-8",
    )

    class SequencedMessages:
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)

            transforms = (
                [
                    {
                        "transform_id": "t1",
                        "text": "Root transform",
                        "evidence_passage_ids": [
                            "giza-source-a-0001",
                        ],
                    }
                ]
                if len(self.calls) == 1
                else []
            )

            return SimpleNamespace(
                content=[
                    SimpleNamespace(
                        type="tool_use",
                        name="record_transforms",
                        input={
                            "transforms": transforms,
                        },
                    )
                ]
            )

    evaluator = AnthropicDecodeEvaluator(
        client=SimpleNamespace(
            messages=SequencedMessages()
        ),
        prompt_path=prompt,
    )

    result = evaluator.core(
        PASSAGES
    )

    assert len(result) == 1
    assert result[0].transform_id == "t1"
    assert result[0].text == "Root transform"

    assert result[0].evidence[0].source_id == (
        "source-a"
    )
    assert result[0].evidence[0].site_id == (
        "giza"
    )
    assert result[0].evidence[0].passage_id == (
        "giza-source-a-0001"
    )
    assert result[0].evidence[0].locator == (
        "p. 10"
    )


def test_core_evaluator_receives_full_corpus(
    tmp_path,
):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text(
        "Resolve through Monads.",
        encoding="utf-8",
    )

    client = FakeClient([])

    evaluator = AnthropicDecodeEvaluator(
        client=client,
        prompt_path=prompt,
    )

    evaluator.core(
        PASSAGES
    )

    message = (
        client.messages.calls[0]
        ["messages"][0]
        ["content"]
    )

    assert "First passage." in message
    assert "Second passage." in message


def test_child_evaluator_receives_parent(
    tmp_path,
):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text(
        "Resolve through Monads.",
        encoding="utf-8",
    )

    client = FakeClient([])

    evaluator = AnthropicDecodeEvaluator(
        client=client,
        prompt_path=prompt,
    )

    parent = TransformRecord(
        transform_id="t1",
        text="Root transform",
    )

    evaluator.child(
        parent,
        [PASSAGES[0]],
    )

    message = (
        client.messages.calls[0]
        ["messages"][0]
        ["content"]
    )

    assert "Mode: child" in message
    assert "ID: t1" in message
    assert "Root transform" in message
    assert "First passage." in message
    assert "Second passage." not in message


def test_ai_cannot_invent_evidence(
    tmp_path,
):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text(
        "Resolve through Monads.",
        encoding="utf-8",
    )

    client = FakeClient(
        [
            {
                "transform_id": "t1",
                "text": "Root transform",
                "evidence_passage_ids": [
                    "invented-passage",
                ],
            }
        ]
    )

    evaluator = AnthropicDecodeEvaluator(
        client=client,
        prompt_path=prompt,
    )

    with pytest.raises(
        ValueError,
        match="outside the supplied corpus",
    ):
        evaluator.core(
            PASSAGES
        )


def test_string_tool_output_is_accepted(
    tmp_path,
):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text(
        "Resolve through Monads.",
        encoding="utf-8",
    )

    client = FakeClient(
        """[
            {
                "transform_id": "t1",
                "text": "Root transform",
                "evidence_passage_ids": [
                    "giza-source-a-0001"
                ]
            }
        ]"""
    )

    evaluator = AnthropicDecodeEvaluator(
        client=client,
        prompt_path=prompt,
    )

    result = evaluator.core(
        PASSAGES
    )

    assert result[0].transform_id == "t1"


def test_ai_call_uses_prompt_tool_and_forced_tool_choice(
    tmp_path,
):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text(
        "Resolve through Monads.",
        encoding="utf-8",
    )

    client = FakeClient([])

    evaluator = AnthropicDecodeEvaluator(
        client=client,
        prompt_path=prompt,
    )

    evaluator.core(PASSAGES)

    call = client.messages.calls[0]

    assert call["system"] == "Resolve through Monads."
    assert call["model"] == evaluator.model

    assert call["tools"][0]["name"] == (
        "record_transforms"
    )

    assert call["tool_choice"] == {
        "type": "tool",
        "name": "record_transforms",
    }


def test_multiple_transforms_and_evidence_are_returned(
    tmp_path,
):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text(
        "Resolve through Monads.",
        encoding="utf-8",
    )

    client = FakeClient(
        [
            {
                "transform_id": "t1",
                "text": "First transform",
                "evidence_passage_ids": [
                    "giza-source-a-0001",
                    "giza-source-b-0002",
                ],
            },
            {
                "transform_id": "t2",
                "text": "Second transform",
                "evidence_passage_ids": [
                    "giza-source-b-0002",
                ],
            },
        ]
    )

    evaluator = AnthropicDecodeEvaluator(
        client=client,
        prompt_path=prompt,
    )

    result = evaluator.core(PASSAGES)

    assert [
        item.transform_id
        for item in result
    ] == [
        "t1",
        "t2",
    ]

    assert [
        link.passage_id
        for link in result[0].evidence
    ] == [
        "giza-source-a-0001",
        "giza-source-b-0002",
    ]

    assert [
        link.passage_id
        for link in result[1].evidence
    ] == [
        "giza-source-b-0002",
    ]


def test_missing_tool_use_returns_no_transforms(
    tmp_path,
):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text(
        "Resolve through Monads.",
        encoding="utf-8",
    )

    class NoToolMessages:
        def create(self, **kwargs):
            return SimpleNamespace(
                content=[
                    SimpleNamespace(
                        type="text",
                        name=None,
                    )
                ]
            )

    client = SimpleNamespace(
        messages=NoToolMessages()
    )

    evaluator = AnthropicDecodeEvaluator(
        client=client,
        prompt_path=prompt,
    )

    assert evaluator.core(PASSAGES) == []


def test_invalid_json_tool_output_returns_no_transforms(
    tmp_path,
):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text(
        "Resolve through Monads.",
        encoding="utf-8",
    )

    client = FakeClient(
        "{invalid json"
    )

    evaluator = AnthropicDecodeEvaluator(
        client=client,
        prompt_path=prompt,
    )

    assert evaluator.core(PASSAGES) == []


def test_wrong_tool_output_type_returns_no_transforms(
    tmp_path,
):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text(
        "Resolve through Monads.",
        encoding="utf-8",
    )

    client = FakeClient(42)

    evaluator = AnthropicDecodeEvaluator(
        client=client,
        prompt_path=prompt,
    )

    assert evaluator.core(PASSAGES) == []


def test_blank_transform_id_is_rejected(
    tmp_path,
):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text(
        "Resolve through Monads.",
        encoding="utf-8",
    )

    client = FakeClient(
        [
            {
                "transform_id": " ",
                "text": "Transform",
                "evidence_passage_ids": [],
            }
        ]
    )

    evaluator = AnthropicDecodeEvaluator(
        client=client,
        prompt_path=prompt,
    )

    with pytest.raises(
        ValueError,
        match="transform_id must not be empty",
    ):
        evaluator.core(PASSAGES)


def test_blank_transform_text_is_rejected(
    tmp_path,
):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text(
        "Resolve through Monads.",
        encoding="utf-8",
    )

    client = FakeClient(
        [
            {
                "transform_id": "t1",
                "text": " ",
                "evidence_passage_ids": [],
            }
        ]
    )

    evaluator = AnthropicDecodeEvaluator(
        client=client,
        prompt_path=prompt,
    )

    with pytest.raises(
        ValueError,
        match="transform text must not be empty",
    ):
        evaluator.core(PASSAGES)


def test_ai_adapter_runs_through_decode_graph(
    tmp_path,
):
    from data.decode import (
        extract_core_transforms,
        recursively_extract_children,
    )

    prompt = tmp_path / "prompt.txt"
    prompt.write_text(
        "Resolve through Monads.",
        encoding="utf-8",
    )

    class SequencedMessages:
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)

            if len(self.calls) == 1:
                transforms = [
                    {
                        "transform_id": "t1",
                        "text": "Root transform",
                        "evidence_passage_ids": [
                            "giza-source-a-0001",
                        ],
                    }
                ]
            elif len(self.calls) == 2:
                transforms = [
                    {
                        "transform_id": "t1_1",
                        "text": "Child transform",
                        "evidence_passage_ids": [
                            "giza-source-a-0001",
                        ],
                    }
                ]
            else:
                transforms = []

            return SimpleNamespace(
                content=[
                    SimpleNamespace(
                        type="tool_use",
                        name="record_transforms",
                        input={
                            "transforms": transforms,
                        },
                    )
                ]
            )

    client = SimpleNamespace(
        messages=SequencedMessages()
    )

    evaluator = AnthropicDecodeEvaluator(
        client=client,
        prompt_path=prompt,
    )

    graph = extract_core_transforms(
        PASSAGES,
        evaluator.core,
    )

    recursively_extract_children(
        "t1",
        PASSAGES,
        evaluator.child,
        graph,
    )

    assert graph.transforms[
        "t1"
    ].root_transform_id == "t1"

    assert graph.transforms[
        "t1_1"
    ].parent_transform_id == "t1"

    assert graph.transforms[
        "t1_1"
    ].root_transform_id == "t1"

    assert graph.transforms[
        "t1_1"
    ].depth == 1

    assert graph.links_for(
        "t1_1"
    )[0].passage_id == (
        "giza-source-a-0001"
    )


# def test_run_decode_returns_success_and_notifies_app(
#     tmp_path,
#     monkeypatch,
# ):
#     prompt = tmp_path / "prompt.txt"
#     prompt.write_text(
#         "Resolve through Monads.",
#         encoding="utf-8",
#     )
#
#     client = FakeClient(
#         [
#             {
#                 "transform_id": "t1",
#                 "text": "Root transform",
#                 "evidence_passage_ids": [
#                     "giza-source-a-0001",
#                 ],
#             }
#         ]
#     )
#
#     evaluator = AnthropicDecodeEvaluator(
#         client=client,
#         prompt_path=prompt,
#     )
#
#     notifications = []
#
#     monkeypatch.setattr(
#         "tools.decode_ai._notify_app",
#         lambda message, graph: notifications.append(
#             (message, graph)
#         ),
#     )
#
#     result = run_decode(
#         PASSAGES,
#         evaluator,
#     )
#
#     assert result == "Decode completed successfully"
#     assert notifications[0][0] == (
#         "Decode completed successfully"
#     )
#
#
#
def test_run_decode_returns_failure_message(
    tmp_path,
):
    prompt = tmp_path / "prompt.txt"
    prompt.write_text(
        "Resolve through Monads.",
        encoding="utf-8",
    )

    class FailingMessages:
        def create(self, **kwargs):
            raise RuntimeError("model unavailable")

    evaluator = AnthropicDecodeEvaluator(
        client=SimpleNamespace(
            messages=FailingMessages()
        ),
        prompt_path=prompt,
    )

    result = run_decode(
        PASSAGES,
        evaluator,
    )

    assert result == (
        "Decode failed: model unavailable"
    )
