#!/usr/bin/env python3
"""Search the local QNN SQLite FTS database."""

from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path


DEFAULT_DB = Path("artifacts/qnn_docs/qnn_docs.sqlite")


def fts_query(user_query: str, raw: bool) -> str:
    if raw:
        return user_query
    terms = []
    for term in user_query.split():
        if re.search(r"[^A-Za-z0-9_\u4e00-\u9fff]", term):
            escaped = term.replace('"', '""')
            terms.append(f'"{escaped}"')
        else:
            terms.append(term)
    return " ".join(terms)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", help="FTS query, e.g. 'qnn-net-run backend' or 'HTP quantized'")
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--limit", type=int, default=8)
    parser.add_argument("--full", action="store_true", help="Print full page content for each result")
    parser.add_argument("--raw-query", action="store_true", help="Use the query exactly as SQLite FTS syntax")
    args = parser.parse_args()

    if not args.db.exists():
        raise SystemExit(f"Database not found: {args.db}. Run build_qnn_doc_db.py first.")

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row
    try:
        query = fts_query(args.query, args.raw_query)
        rows = conn.execute(
            """
            SELECT
                pages.topic_id,
                pages.title,
                pages.topic_path,
                pages.source_url,
                pages.local_path,
                pages.content,
                snippet(pages_fts, 2, '[', ']', ' ... ', 24) AS snippet,
                bm25(pages_fts) AS score
            FROM pages_fts
            JOIN pages ON pages.id = pages_fts.rowid
            WHERE pages_fts MATCH ?
            ORDER BY score
            LIMIT ?
            """,
            (query, args.limit),
        ).fetchall()
    finally:
        conn.close()

    if not rows:
        print("No results.")
        return 1

    for index, row in enumerate(rows, start=1):
        print(f"\n## {index}. {row['title']}")
        print(f"- topic_id: {row['topic_id']}")
        print(f"- path: {row['topic_path']}")
        print(f"- source: {row['source_url']}")
        print(f"- local: {row['local_path']}")
        print(f"- score: {row['score']:.4f}")
        print()
        print(row["content"] if args.full else row["snippet"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
