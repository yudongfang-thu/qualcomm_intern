#!/usr/bin/env python3
"""Build a local SQLite FTS database from locally fetched QNN Markdown pages."""

from __future__ import annotations

import argparse
import re
import sqlite3
from pathlib import Path


DEFAULT_PAGES_DIR = Path("artifacts/qnn_docs/pages_md")
DEFAULT_DB = Path("artifacts/qnn_docs/qnn_docs.sqlite")


def parse_page(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    title_match = re.search(r"^#\s+(.+)$", text, flags=re.M)
    topic_match = re.search(r"^- Topic ID:\s+`?([^`\n]+)`?", text, flags=re.M)
    source_match = re.search(r"^- Source:\s+(.+)$", text, flags=re.M)
    path_match = re.search(r"^- Path:\s+(.+)$", text, flags=re.M)
    return {
        "topic_id": topic_match.group(1).strip() if topic_match else path.stem + ".html",
        "title": title_match.group(1).strip() if title_match else path.stem,
        "source_url": source_match.group(1).strip() if source_match else "",
        "topic_path": path_match.group(1).strip() if path_match else "",
        "content": text,
        "local_path": str(path),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pages-dir", type=Path, default=DEFAULT_PAGES_DIR)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = parser.parse_args()

    if not args.pages_dir.exists():
        raise SystemExit(f"Pages directory not found: {args.pages_dir}. Run fetch_qnn_docs.py first.")

    pages = sorted(args.pages_dir.glob("*.md"))
    if not pages:
        raise SystemExit(f"No Markdown pages found under {args.pages_dir}. Run fetch_qnn_docs.py first.")

    args.db.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(args.db)
    try:
        conn.executescript(
            """
            DROP TABLE IF EXISTS pages;
            DROP TABLE IF EXISTS pages_fts;

            CREATE TABLE pages (
                id INTEGER PRIMARY KEY,
                topic_id TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                topic_path TEXT,
                source_url TEXT,
                local_path TEXT,
                content TEXT NOT NULL
            );

            CREATE VIRTUAL TABLE pages_fts USING fts5(
                title,
                topic_path,
                content,
                content='pages',
                content_rowid='id',
                tokenize='unicode61'
            );
            """
        )

        for page_path in pages:
            page = parse_page(page_path)
            cursor = conn.execute(
                """
                INSERT INTO pages(topic_id, title, topic_path, source_url, local_path, content)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    page["topic_id"],
                    page["title"],
                    page["topic_path"],
                    page["source_url"],
                    page["local_path"],
                    page["content"],
                ),
            )
            rowid = cursor.lastrowid
            conn.execute(
                "INSERT INTO pages_fts(rowid, title, topic_path, content) VALUES (?, ?, ?, ?)",
                (rowid, page["title"], page["topic_path"], page["content"]),
            )
        conn.commit()
    finally:
        conn.close()

    print(f"pages_indexed={len(pages)}")
    print(f"db={args.db}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

