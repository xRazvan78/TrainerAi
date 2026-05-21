"""
Lightweight RAG quality eval — not a pytest, run as:

    python scripts/eval_rag.py
    python scripts/eval_rag.py --top-k 4 --threshold 0.4 --json eval-out.json

Loads a curated query set, calls the RAG service, prints per-query top-1
hit + similarity + source video, and an aggregate top-1 source-match rate.
Exit code 0 on success regardless of score; CI is not gated on this.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


class EvalQuery(TypedDict):
    query: str
    expected_tool: str
    expected_video_substr: str


EVAL_QUERIES: list[EvalQuery] = [
    {"query": "how do I draw a straight line", "expected_tool": "LINE",
     "expected_video_substr": "line"},
    {"query": "how do I round corners between two lines", "expected_tool": "FILLET",
     "expected_video_substr": "fillet"},
    {"query": "cutting off lines that extend past an intersection", "expected_tool": "TRIM",
     "expected_video_substr": "trim"},
    {"query": "make a parallel copy of a line at a fixed distance", "expected_tool": "OFFSET",
     "expected_video_substr": "offset"},
    {"query": "how do I draw a circle by specifying a centre and radius", "expected_tool": "CIRCLE",
     "expected_video_substr": "circle"},
    {"query": "how do I create reusable symbols I can insert multiple times", "expected_tool": "BLOCK",
     "expected_video_substr": "block"},
    {"query": "how do I fill an area with a hatch pattern", "expected_tool": "HATCH",
     "expected_video_substr": "hatch"},
    {"query": "how do I add measurements to my drawing", "expected_tool": "DIMENSION",
     "expected_video_substr": "dim"},
    {"query": "how do I organise objects so I can hide groups of them", "expected_tool": "LAYER",
     "expected_video_substr": "layer"},
    {"query": "how do I make a mirrored copy of a shape", "expected_tool": "MIRROR",
     "expected_video_substr": "mirror"},
    {"query": "how do I rotate an object around a point", "expected_tool": "ROTATE",
     "expected_video_substr": "rotate"},
    {"query": "how do I extend a line until it touches another line", "expected_tool": "EXTEND",
     "expected_video_substr": "extend"},
    {"query": "how do I cut a 45-degree corner between two lines", "expected_tool": "CHAMFER",
     "expected_video_substr": "chamfer"},
    {"query": "what's the command line at the bottom of AutoCAD for", "expected_tool": "general",
     "expected_video_substr": "intro"},
    {"query": "how do I scale a drawing up or down", "expected_tool": "SCALE",
     "expected_video_substr": "scale"},
]


async def evaluate(top_k: int, threshold: float) -> list[dict]:
    from app.db.postgres import create_pool
    from app.services.embedder_service import embed_text
    from app.db.crud import query_similar_embeddings

    pool = await create_pool()
    results: list[dict] = []
    try:
        for item in EVAL_QUERIES:
            vector = embed_text(item["query"])
            hits = await query_similar_embeddings(
                pool, embedding=vector, min_similarity=threshold, limit=top_k,
            )
            top = hits[0] if hits else None
            if top is None:
                results.append({
                    "query": item["query"],
                    "expected_tool": item["expected_tool"],
                    "expected_video_substr": item["expected_video_substr"],
                    "top1": None,
                    "tool_match": False,
                    "video_match": False,
                })
                continue

            metadata = top.get("metadata") or {}
            if isinstance(metadata, str):
                import json as _json
                metadata = _json.loads(metadata)
            tool_hit = (metadata.get("active_tool_hint") or "").upper()
            source_video = (metadata.get("source_video") or "").lower()
            results.append({
                "query": item["query"],
                "expected_tool": item["expected_tool"],
                "expected_video_substr": item["expected_video_substr"],
                "top1": {
                    "doc_id": top.get("doc_id"),
                    "similarity": float(top.get("similarity_score", 0.0)),
                    "source_video": source_video,
                    "active_tool_hint": tool_hit,
                    "snippet": (top.get("content") or "")[:140],
                },
                "tool_match": tool_hit == item["expected_tool"].upper(),
                "video_match": item["expected_video_substr"].lower() in source_video,
            })
    finally:
        await pool.close()
    return results


def print_report(results: list[dict]) -> None:
    n = len(results)
    tool_hits = sum(1 for r in results if r["tool_match"])
    video_hits = sum(1 for r in results if r["video_match"])
    print(f"\nRAG eval — {n} queries\n" + "=" * 60)
    for r in results:
        marker = "+" if r["video_match"] else "-"
        top = r["top1"]
        if top is None:
            print(f" {marker}  no hit | query: {r['query']!r}")
            continue
        print(
            f" {marker}  sim={top['similarity']:.3f} "
            f"video={top['source_video']:<40} "
            f"tool={top['active_tool_hint']:<8} | {r['query']!r}"
        )
    print("=" * 60)
    print(f" top-1 video-match: {video_hits}/{n} ({100*video_hits/n:.0f}%)")
    print(f" top-1 tool-match : {tool_hits}/{n}  ({100*tool_hits/n:.0f}%)")


def main() -> None:
    ap = argparse.ArgumentParser(description="RAG quality eval for the AutoCAD knowledge base")
    ap.add_argument("--top-k", type=int, default=4)
    ap.add_argument("--threshold", type=float, default=0.4,
                    help="Lower than rag_service default (0.72); we want to see near-misses too.")
    ap.add_argument("--json", help="Optional path to write the raw results JSON")
    args = ap.parse_args()

    results = asyncio.run(evaluate(args.top_k, args.threshold))
    print_report(results)

    if args.json:
        out_path = Path(args.json)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(results, indent=2))
        print(f"\nResults written to {out_path}")


if __name__ == "__main__":
    main()
