#!/usr/bin/env python3
"""Natural-language helper for local QNN docs search.

This is not an LLM. It expands a Chinese/English question into several QNN
documentation keyword queries, runs SQLite FTS search, and merges results.
"""

from __future__ import annotations

import argparse
import re
import sqlite3
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path

from search_qnn_docs import DEFAULT_DB, fts_query


TERM_MAP: list[tuple[str, list[str]]] = [
    ("环境|配置|安装|依赖|python|venv|虚拟环境|env", ["envsetup", "check-python-dependency", "envcheck", "QNN_SDK_ROOT", "QAIRT_SDK_ROOT"]),
    ("转换|转化|onnx|converter|模型转换", ["qnn-onnx-converter", "input_network", "output_path", "input_dim", "preserve_io"]),
    ("编译|生成so|模型库|model lib|library", ["qnn-model-lib-generator", "target", "model library", "LIB_TARGETS"]),
    ("运行|推理|执行|inference|net-run", ["qnn-net-run", "model", "backend", "input_list", "output_dir"]),
    ("输入|input|raw|input_list|预处理|layout", ["input_list", "raw", "input_dim", "input_layout", "preserve_io", "NCHW", "NHWC"]),
    ("输出|output|结果|top|对比|正确性", ["output_dir", "use_native_output_files", "debug", "set_output_tensors"]),
    ("量化|quant|int8|校准|calibration", ["quantized", "input_list", "act_bitwidth", "weights_bitwidth", "calibration", "encoding"]),
    ("cpu", ["CPU", "libQnnCpu.so", "backend", "FP32", "INT8"]),
    ("gpu|adreno", ["GPU", "libQnnGpu.so", "precision", "FP16", "FP32", "performance hints"]),
    ("htp|npu|hexagon|tensor processor", ["HTP", "libQnnHtp.so", "context binary", "retrieve_context", "quantized"]),
    ("dsp|cdsp", ["DSP", "libQnnDsp.so", "Stub", "Skel", "signed process domain"]),
    ("saver|记录|replay|复现", ["Saver", "libQnnSaver.so", "saver_output.c", "params.bin", "replay"]),
    ("profile|profiling|性能|latency|延迟", ["profiling_level", "qnn-profile-viewer", "backend", "optrace", "latency"]),
    ("context|binary|缓存|离线|offline", ["qnn-context-binary-generator", "context binary", "retrieve_context", "offline_prepare"]),
    ("android|adb", ["aarch64-android", "Android NDK", "adb", "libQnnCpu.so", "qnn-net-run"]),
    ("linux|ubuntu|ssh|scp", ["Linux target", "QNN_TARGET_ARCH", "ssh", "scp", "aarch64-oe-linux-gcc"]),
]

PINNED_QUERIES = [
    "qnn-net-run backend input_list output_dir",
    "qnn-onnx-converter input_network output_path input_dim",
    "qnn-model-lib-generator target model library",
]


@dataclass
class Result:
    topic_id: str
    title: str
    topic_path: str
    source_url: str
    local_path: str
    best_score: float
    matched_queries: list[str] = field(default_factory=list)
    snippets: list[str] = field(default_factory=list)


def compact_terms(terms: list[str], max_terms: int = 6) -> str:
    seen: list[str] = []
    for term in terms:
        normalized = term.strip()
        if normalized and normalized not in seen:
            seen.append(normalized)
    return " ".join(seen[:max_terms])


def extract_ascii_terms(question: str) -> list[str]:
    terms = re.findall(r"[A-Za-z][A-Za-z0-9_.+-]*", question)
    return [term for term in terms if len(term) >= 2]


def build_queries(question: str, extra_queries: list[str], max_queries: int) -> list[str]:
    queries: list[str] = []

    ascii_terms = extract_ascii_terms(question)
    if ascii_terms:
        queries.append(compact_terms(ascii_terms))

    for pattern, terms in TERM_MAP:
        if re.search(pattern, question, flags=re.I):
            combined = ascii_terms + terms
            queries.append(compact_terms(combined))

    queries.extend(extra_queries)

    if len(queries) < 2:
        queries.extend(PINNED_QUERIES)
    elif any(re.search(r"运行|推理|执行|inference|net-run|backend", question, re.I) for _ in [0]):
        queries.append(PINNED_QUERIES[0])

    unique: list[str] = []
    for query in queries:
        if query and query not in unique:
            unique.append(query)
    return unique[:max_queries]


def search_one(conn: sqlite3.Connection, query: str, per_query_limit: int) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT
            pages.topic_id,
            pages.title,
            pages.topic_path,
            pages.source_url,
            pages.local_path,
            snippet(pages_fts, 2, '[', ']', ' ... ', 26) AS snippet,
            bm25(pages_fts) AS score
        FROM pages_fts
        JOIN pages ON pages.id = pages_fts.rowid
        WHERE pages_fts MATCH ?
        ORDER BY score
        LIMIT ?
        """,
        (fts_query(query, raw=False), per_query_limit),
    ).fetchall()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("question", help="Chinese/English question, e.g. 'HTP 怎么跑模型，需要量化吗'")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--query", action="append", default=[], help="Additional exact keyword query to try")
    parser.add_argument("--max-queries", type=int, default=6)
    parser.add_argument("--per-query-limit", type=int, default=5)
    parser.add_argument("--limit", type=int, default=8, help="Final merged result limit")
    parser.add_argument("--show-queries", action="store_true")
    args = parser.parse_args()

    if not args.db.exists():
        raise SystemExit(f"Database not found: {args.db}. Run build_qnn_doc_db.py first.")

    queries = build_queries(args.question, args.query, args.max_queries)
    if args.show_queries:
        print("# Expanded Queries")
        for query in queries:
            print(f"- {query}")
        print()

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    merged: OrderedDict[str, Result] = OrderedDict()
    try:
        for query in queries:
            try:
                rows = search_one(conn, query, args.per_query_limit)
            except sqlite3.OperationalError as exc:
                print(f"[warn] query failed: {query}: {exc}")
                continue
            for row in rows:
                key = row["topic_id"]
                if key not in merged:
                    merged[key] = Result(
                        topic_id=row["topic_id"],
                        title=row["title"],
                        topic_path=row["topic_path"],
                        source_url=row["source_url"],
                        local_path=row["local_path"],
                        best_score=float(row["score"]),
                    )
                result = merged[key]
                result.best_score = min(result.best_score, float(row["score"]))
                if query not in result.matched_queries:
                    result.matched_queries.append(query)
                snippet = row["snippet"]
                if snippet and snippet not in result.snippets:
                    result.snippets.append(snippet)
    finally:
        conn.close()

    results = sorted(merged.values(), key=lambda item: (item.best_score, -len(item.matched_queries)))[: args.limit]
    if not results:
        print("No results.")
        return 1

    for index, result in enumerate(results, start=1):
        print(f"\n## {index}. {result.title}")
        print(f"- topic_id: {result.topic_id}")
        print(f"- path: {result.topic_path}")
        print(f"- source: {result.source_url}")
        print(f"- local: {result.local_path}")
        print(f"- matched_queries: {' | '.join(result.matched_queries)}")
        print(f"- best_score: {result.best_score:.4f}")
        for snippet in result.snippets[:3]:
            print()
            print(snippet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

