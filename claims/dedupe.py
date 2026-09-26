"""Merge near-duplicate draft claims and keep every source.

Only compares claims with the same site and system. Uses sentence-transformers
if it's installed, otherwise falls back to TF-IDF (scikit-learn), which is
cruder but needs no model download.

Drafts that repeat an already verified claim are dropped (and listed), since
review has already covered them.

Usage:
    python -m claims.dedupe                  # draft/claims.jsonl -> draft/claims_deduped.jsonl
    python -m claims.dedupe --threshold 0.8
"""

import argparse

from claims.common import (
    DEDUPED_PATH, DRAFT_PATH, GRADES, SOURCE_TYPES, VERIFIED_PATH,
    load_passages, read_jsonl, write_jsonl,
)

# thresholds are different because the two methods score differently
DEFAULT_THRESHOLDS = {"embeddings": 0.85, "tfidf": 0.55}


def similarity_matrix(texts):
    """Return (matrix, method). matrix[i][j] is cosine similarity."""
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        vectors = model.encode(texts, normalize_embeddings=True)
        return (vectors @ vectors.T).tolist(), "embeddings"
    except ImportError:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity
        vectors = TfidfVectorizer(stop_words="english", ngram_range=(1, 2)).fit_transform(texts)
        return cosine_similarity(vectors).tolist(), "tfidf"


def find_root(parents, i):
    while parents[i] != i:
        parents[i] = parents[parents[i]]
        i = parents[i]
    return i


def keeper_rank(claim, passages):
    # prefer the claim whose first source is the most direct kind of evidence,
    # then the shorter (usually tighter) statement
    first = passages.get(claim["sources"][0]["passage_id"], {})
    source_type = first.get("source_type", "reference")
    type_rank = SOURCE_TYPES.index(source_type) if source_type in SOURCE_TYPES else len(SOURCE_TYPES)
    return (type_rank, len(claim["statement"]))


def merge_group(group, passages):
    group = sorted(group, key=lambda c: keeper_rank(c, passages))
    keeper = dict(group[0])

    # union of sources, keeper's first so its quote still matches source 0
    seen = set()
    merged_sources = []
    for claim in group:
        for source in claim["sources"]:
            if source["passage_id"] not in seen:
                seen.add(source["passage_id"])
                merged_sources.append(source)
    keeper["sources"] = merged_sources

    grades = []
    for claim in group:
        if claim["grade"] not in grades:
            grades.append(claim["grade"])
    if len(grades) > 1:
        # don't pick for the reviewer, just make the disagreement loud
        keeper["grade_conflict"] = sorted(grades, key=GRADES.index)

    others = []
    for claim in group[1:]:
        others.append(claim["claim_id"])
    keeper["merged_from"] = sorted(set(keeper.get("merged_from", []) + others))
    return keeper


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--threshold", type=float, help="similarity to count as duplicate")
    args = parser.parse_args()

    drafts = read_jsonl(DRAFT_PATH)
    verified = read_jsonl(VERIFIED_PATH)
    passages = load_passages()
    if not drafts:
        print("no drafts yet, run claims.extract first")
        return

    # bucket by site and system so we never merge across them
    buckets = {}
    for claim in drafts:
        buckets.setdefault((claim["site"], claim["system"]), []).append(claim)
    verified_buckets = {}
    for claim in verified:
        verified_buckets.setdefault((claim["site"], claim["system"]), []).append(claim)

    output = []
    dropped_as_verified = []
    method_used = None
    merged_count = 0

    for key, claims in buckets.items():
        known = verified_buckets.get(key, [])
        texts = []
        for claim in claims + known:
            texts.append(claim["statement"])
        if len(texts) < 2:
            output.extend(claims)
            continue

        matrix, method_used = similarity_matrix(texts)
        threshold = args.threshold or DEFAULT_THRESHOLDS[method_used]

        # drafts that match a verified claim are already covered
        live = []
        for i, claim in enumerate(claims):
            best = 0.0
            best_id = None
            for j, known_claim in enumerate(known):
                score = matrix[i][len(claims) + j]
                if score > best:
                    best = score
                    best_id = known_claim["claim_id"]
            if best >= threshold:
                dropped_as_verified.append((claim["claim_id"], best_id, round(best, 2)))
            else:
                live.append(i)

        # union-find over the remaining drafts
        parents = {}
        for i in live:
            parents[i] = i
        for a in live:
            for b in live:
                if b <= a:
                    continue
                if matrix[a][b] >= threshold:
                    root_a = find_root(parents, a)
                    root_b = find_root(parents, b)
                    if root_a != root_b:
                        parents[root_b] = root_a

        groups = {}
        for i in live:
            groups.setdefault(find_root(parents, i), []).append(claims[i])
        for group in groups.values():
            if len(group) == 1:
                output.append(group[0])
            else:
                merged_count += len(group) - 1
                output.append(merge_group(group, passages))

    write_jsonl(DEDUPED_PATH, output)
    print(f"method: {method_used or 'n/a'}")
    print(f"{len(drafts)} drafts -> {len(output)} after merging {merged_count} duplicates")
    if dropped_as_verified:
        print(f"dropped {len(dropped_as_verified)} drafts that repeat verified claims:")
        for draft, verified_id, score in dropped_as_verified:
            print(f"  {draft} ~ {verified_id} ({score})")
    print(f"wrote {DEDUPED_PATH}")


if __name__ == "__main__":
    main()
