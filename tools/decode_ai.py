from __future__ import annotations

import json
from pathlib import Path

from data import config
from data.decode import (
    TransformExtract,
    TransformGraph,
    TransformLink,
    TransformRecord,
    extract_core_transforms,
    recursively_extract_children,
)


PROMPT_PATH = (
    Path(__file__).resolve().parent.parent
    / "agents"
    / "prompts"
    / "V8_Resolve_Through_Monads.txt"
)

MODEL = config.LLM_TAG_MODEL


class AnthropicDecodeEvaluator:
    def __init__(
        self,
        client,
        model: str = MODEL,
        prompt_path: Path = PROMPT_PATH,
    ) -> None:
        self.client = client
        self.model = model
        self.system_prompt = prompt_path.read_text(
            encoding="utf-8"
        )

    def core(
        self,
        passages: list[dict],
    ) -> list[TransformExtract]:
        return self._evaluate(
            mode="core",
            passages=passages,
            parent=None,
        )

    def child(
        self,
        parent: TransformRecord,
        passages: list[dict],
    ) -> list[TransformExtract]:
        return self._evaluate(
            mode="child",
            passages=passages,
            parent=parent,
        )

    def _evaluate(
        self,
        mode: str,
        passages: list[dict],
        parent: TransformRecord | None,
    ) -> list[TransformExtract]:
        passage_map = {
            passage["passage_id"]: passage
            for passage in passages
        }

        response = self.client.messages.create(
            model=self.model,
            max_tokens=4000,
            system=self.system_prompt,
            tools=[_transform_tool()],
            tool_choice={
                "type": "tool",
                "name": "record_transforms",
            },
            messages=[
                {
                    "role": "user",
                    "content": _build_user_message(
                        mode=mode,
                        passages=passages,
                        parent=parent,
                    ),
                }
            ],
        )

        raw_transforms = _tool_output(response)

        return [
            _to_transform_extract(
                raw,
                passage_map,
            )
            for raw in raw_transforms
            if isinstance(raw, dict)
        ]


def create_anthropic_decode_evaluator(
    model: str = MODEL,
    prompt_path: Path = PROMPT_PATH,
) -> AnthropicDecodeEvaluator:
    from dotenv import load_dotenv

    load_dotenv()

    import anthropic

    client = anthropic.Anthropic(
        max_retries=4
    )

    return AnthropicDecodeEvaluator(
        client=client,
        model=model,
        prompt_path=prompt_path,
    )


def _transform_tool() -> dict:
    return {
        "name": "record_transforms",
        "description": (
            "Record transforms resolved from the supplied "
            "corpus evidence."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "transforms": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "transform_id": {
                                "type": "string",
                            },
                            "text": {
                                "type": "string",
                            },
                            "evidence_passage_ids": {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                },
                            },
                        },
                        "required": [
                            "transform_id",
                            "text",
                            "evidence_passage_ids",
                        ],
                    },
                }
            },
            "required": [
                "transforms",
            ],
        },
    }


def _build_user_message(
    mode: str,
    passages: list[dict],
    parent: TransformRecord | None,
) -> str:
    if mode == "core":
        instruction = (
            "Resolve the supplied corpus as one corpus. "
            "Extract the root/core transform set. "
            "Each transform must cite the passage IDs "
            "that support it."
        )
    else:
        instruction = (
            "Re-resolve only the supplied evidence for "
            "the parent transform. Extract only child "
            "transforms that deepen that parent. Do not "
            "create new root transforms."
        )

    parts = [
        f"Mode: {mode}",
        instruction,
    ]

    if parent is not None:
        parts.extend(
            [
                "",
                "Parent transform:",
                f"ID: {parent.transform_id}",
                f"Root ID: {parent.root_transform_id}",
                f"Depth: {parent.depth}",
                f"Text: {parent.text}",
            ]
        )

    parts.extend(
        [
            "",
            "Corpus evidence:",
        ]
    )

    for passage in passages:
        parts.extend(
            [
                "",
                f"Passage ID: {passage['passage_id']}",
                f"Source ID: {passage['source_id']}",
                f"Site: {passage['site']}",
                (
                    "Locator: "
                    f"{passage.get('locator') or 'none'}"
                ),
                "<passage>",
                passage["text"],
                "</passage>",
            ]
        )

    return "\n".join(parts)


def _tool_output(
    response,
) -> list[dict]:
    for block in response.content:
        if (
            block.type == "tool_use"
            and block.name == "record_transforms"
        ):
            transforms = (
                block.input.get("transforms")
                or []
            )

            if isinstance(transforms, str):
                try:
                    transforms = json.loads(
                        transforms
                    )
                except json.JSONDecodeError:
                    return []

            if isinstance(transforms, dict):
                transforms = [transforms]

            if not isinstance(transforms, list):
                return []

            return transforms

    return []


def _to_transform_extract(
    raw: dict,
    passage_map: dict[str, dict],
) -> TransformExtract:
    transform_id = (
        raw.get("transform_id")
        or ""
    ).strip()

    text = (
        raw.get("text")
        or ""
    ).strip()

    evidence_ids = (
        raw.get("evidence_passage_ids")
        or []
    )

    if not transform_id:
        raise ValueError(
            "AI transform_id must not be empty"
        )

    if not text:
        raise ValueError(
            "AI transform text must not be empty"
        )

    links = []

    for passage_id in evidence_ids:
        passage = passage_map.get(
            passage_id
        )

        if passage is None:
            raise ValueError(
                "AI referenced evidence outside "
                f"the supplied corpus: {passage_id}"
            )

        links.append(
            TransformLink(
                transform_id=transform_id,
                source_id=passage["source_id"],
                site_id=passage["site"],
                passage_id=passage["passage_id"],
                locator=passage.get("locator"),
            )
        )

    return TransformExtract(
        transform_id=transform_id,
        text=text,
        evidence=tuple(links),
    )


def run_decode(
    passages: list[dict],
    evaluator: AnthropicDecodeEvaluator,
) -> str:
    try:
        graph = extract_core_transforms(
            passages,
            evaluator.core,
        )

        root_transform_ids = [
            transform.transform_id
            for transform in graph.transforms.values()
            if transform.parent_transform_id is None
        ]

        for root_transform_id in root_transform_ids:
            recursively_extract_children(
                root_transform_id,
                passages,
                evaluator.child,
                graph,
            )

    except Exception as err:
        return f"Decode failed: {err}"

    message = "Decode completed successfully"

    _notify_app(
        message=message,
        graph=graph,
    )

    return message


def _notify_app(
    message: str,
    graph: TransformGraph,
) -> None:
    # TODO: send decode completion notification to the app.
    pass
