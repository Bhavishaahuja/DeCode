"""Tests for claims/decode_map.py with a fake model, so no API calls."""
import re
from types import SimpleNamespace

from claims import decode_map
from claims.decode_map import SafeEvaluator, build_map, graph_to_json, mapped_passage_ids, pick_passages


def passage(pid, source, site="mohenjo", tags=("finishes",)):
    return {"passage_id": pid, "source_id": source, "site": site, "title": source.upper(), "locator": "p. 1",
            "text": f"text of {pid}", "system_tags": list(tags)}


CORPUS = [passage("m-a-1", "a"), passage("m-a-2", "a"), passage("m-a-3", "a"), passage("m-b-1", "b"),
          passage("m-b-2", "b"), passage("g-x-1", "x", site="giza"), passage("m-c-1", "c", tags=())]


class FakeClient:
    """Core returns two roots (one citing a bogus id), child returns three children per node."""

    def __init__(self):
        self.messages = self
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        text = kwargs["messages"][0]["content"]
        if "Mode: core" in text:
            rows = [{"transform_id": "same", "text": "Bare burnt brick walls", "evidence_passage_ids": ["m-a-1", "m-b-1", "nope"]},
                    {"transform_id": "same", "text": "Fitted brick floors", "evidence_passage_ids": ["m-a-2"]},
                    {"transform_id": "z", "text": "Made up", "evidence_passage_ids": ["nope"]}]
        else:
            # children cite the first passage they were given (the parent's own evidence)
            first_id = re.search(r"Passage ID: (\S+)", text).group(1)
            rows = [{"transform_id": "c", "text": f"child {i}", "evidence_passage_ids": [first_id]} for i in range(3)]
        block = SimpleNamespace(type="tool_use", name="record_transforms", input={"transforms": rows})
        return SimpleNamespace(content=[block], stop_reason="tool_use")


def fake_evaluator():
    return SimpleNamespace(client=FakeClient(), model="fake", system_prompt="rules")


def test_pick_passages_round_robins_sources_and_stays_on_site():
    picked = pick_passages({p["passage_id"]: p for p in CORPUS}, "mohenjo", None, 4)
    assert [p["passage_id"] for p in picked] == ["m-a-1", "m-b-1", "m-a-2", "m-b-2"]
    assert all(p["site"] == "mohenjo" and p["system_tags"] for p in picked)


def test_build_map_assigns_stable_ids_drops_bad_evidence_and_caps():
    corpus = [p for p in CORPUS if p["site"] == "mohenjo"]
    graph = build_map(SafeEvaluator(fake_evaluator()), "mohenjo", corpus, depth=1, max_roots=5, max_children=2,
                      log=lambda *_: None)
    ids = sorted(graph.transforms)
    # duplicate model ids didn't crash, the bogus-only transform was dropped, children capped at 2
    assert ids == ["mohenjo-t01", "mohenjo-t01-01", "mohenjo-t01-02", "mohenjo-t02", "mohenjo-t02-01", "mohenjo-t02-02"]
    root_links = {link.passage_id for link in graph.links_for("mohenjo-t01")}
    assert root_links == {"m-a-1", "m-b-1"}


def test_depth_zero_is_one_call():
    evaluator = fake_evaluator()
    graph = build_map(SafeEvaluator(evaluator), "mohenjo", CORPUS[:5], depth=0, max_roots=5, max_children=3,
                      log=lambda *_: None)
    assert evaluator.client.calls == 1
    assert all(t.depth == 0 for t in graph.transforms.values())


def test_saved_map_feeds_extract_in_tree_order():
    corpus = [p for p in CORPUS if p["site"] == "mohenjo"]
    graph = build_map(SafeEvaluator(fake_evaluator()), "mohenjo", corpus, depth=1, max_roots=5, max_children=2,
                      log=lambda *_: None)
    doc = graph_to_json(graph, "mohenjo", "finishes", corpus, {}, "fake")
    assert all(node["status"] == "unreviewed" for node in doc["transforms"])
    assert mapped_passage_ids(doc) == ["m-a-1", "m-b-1", "m-a-2"]
    assert mapped_passage_ids(doc, node_id="mohenjo-t02") == ["m-a-2"]
    assert "Decode map: Mohenjo-daro, finishes" in decode_map.map_to_markdown(doc)


def test_children_cannot_cite_outside_their_parent():
    class OutsideClient(FakeClient):
        def create(self, **kwargs):
            if "Mode: core" in kwargs["messages"][0]["content"]:
                return super().create(**kwargs)
            self.calls += 1
            rows = [{"transform_id": "c", "text": "sneaky", "evidence_passage_ids": ["m-b-2"]}]
            block = SimpleNamespace(type="tool_use", name="record_transforms", input={"transforms": rows})
            return SimpleNamespace(content=[block], stop_reason="tool_use")

    evaluator = SimpleNamespace(client=OutsideClient(), model="fake", system_prompt="rules")
    corpus = [p for p in CORPUS if p["site"] == "mohenjo"]
    graph = build_map(SafeEvaluator(evaluator), "mohenjo", corpus, depth=1, max_roots=5, max_children=3,
                      log=lambda *_: None)
    assert all(t.depth == 0 for t in graph.transforms.values())


def test_forgives_id_slips_and_source_ids():
    from claims.decode_map import resolve_passage_id
    passages = {"m-a-1": {}, "m-a-2": {}}
    by_source = {"a": ["m-a-1", "m-a-2"]}
    assert resolve_passage_id(" [M-A-1] ", passages, by_source) == ["m-a-1"]
    assert resolve_passage_id("Passage ID: m-a-2", passages, by_source) == ["m-a-2"]
    assert resolve_passage_id("a", passages, by_source) == ["m-a-1", "m-a-2"]
    assert resolve_passage_id({"passage_id": "m-a-1"}, passages, by_source) == ["m-a-1"]
    assert resolve_passage_id("nope", passages, by_source) == []
