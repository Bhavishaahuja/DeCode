"""Embed data/passages.jsonl with BAAI/bge-small-en-v1.5 into a persistent Chroma collection at data/index/.

    python -m data.index

Metadata per passage: site, period, source_id, source_type, license, system_tags (",a,b," string), and one boolean
per system ("sys_<id>") so Chroma `where` filters can select a system without list support.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import shutil
import sys

from . import config


def system_meta(tags: list[str]) -> dict:
    meta = {f"sys_{s}": (s in tags) for s in config.system_ids()}
    meta["system_tags"] = "," + ",".join(tags) + "," if tags else ","
    return meta


def load_passages() -> list[dict]:
    return [json.loads(l) for l in config.PASSAGES_JSONL.read_text(encoding="utf-8").splitlines() if l.strip()]


def passages_digest() -> str:
    return hashlib.sha1(config.PASSAGES_JSONL.read_bytes()).hexdigest()[:12]


def build(batch: int = 64) -> None:
    import chromadb
    from sentence_transformers import SentenceTransformer

    passages = load_passages()
    print(f"[index] embedding {len(passages)} passages with {config.EMBED_MODEL}", file=sys.stderr)
    model = SentenceTransformer(config.EMBED_MODEL)
    vecs = model.encode([p["text"] for p in passages], batch_size=batch, normalize_embeddings=True,
                        show_progress_bar=True, convert_to_numpy=True)

    if config.INDEX_DIR.exists():
        shutil.rmtree(config.INDEX_DIR)
    config.INDEX_DIR.mkdir(parents=True)
    client = chromadb.PersistentClient(path=str(config.INDEX_DIR))
    col = client.create_collection(config.COLLECTION, metadata={"hnsw:space": "cosine"})
    for i in range(0, len(passages), 1000):
        chunk = passages[i:i + 1000]
        col.add(
            ids=[p["passage_id"] for p in chunk],
            embeddings=vecs[i:i + 1000].tolist(),  # texts live in passages.jsonl; not duplicated here to keep the index small
            metadatas=[{"site": p["site"], "period": p["period"], "source_id": p["source_id"],
                        "source_type": p["source_type"], "license": p["license"], **system_meta(p["system_tags"])}
                       for p in chunk],
        )
    manifest = {"model": config.EMBED_MODEL, "collection": config.COLLECTION, "n_passages": len(passages),
                "passages_sha1": passages_digest(), "built": dt.datetime.now().isoformat(timespec="seconds"),
                "chromadb": chromadb.__version__}
    (config.INDEX_DIR / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(f"[index] wrote {col.count()} vectors to {config.INDEX_DIR}", file=sys.stderr)


if __name__ == "__main__":
    build()
