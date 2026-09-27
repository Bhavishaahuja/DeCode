from __future__ import annotations

from types import SimpleNamespace

import pytest

from data.decode import TransformRecord
from tools.decode_ai import (
    AnthropicDecodeEvaluator,
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

    client = FakeClient(
        [
            {
                "transform_id": "t1",
                "text": "Root transform",
                "evidence_passage_ids": [
                    "giza-source-a-0001",
                ],
            }
        ]
    )

    evaluator = AnthropicDecodeEvaluator(
        client=client,
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
