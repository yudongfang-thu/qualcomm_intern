#!/usr/bin/env python3
"""Fetch public Qualcomm QNN documentation pages into a local-only cache.

This script intentionally writes downloaded documentation under artifacts/.
Do not commit the generated raw HTML, Markdown, corpus, or database files.
"""

from __future__ import annotations

import argparse
import html
import re
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path


DEFAULT_OUTLINE = Path("docs/qnn_outline.tsv")
DEFAULT_OUTDIR = Path("artifacts/qnn_docs")
DEFAULT_BASE = "https://docs.qualcomm.com/bundle/publicresource/80-63442-10/topics/"
DEFAULT_REFERER = "https://docs.qualcomm.com/doc/80-63442-10/topic/index_QNN.html"


@dataclass(frozen=True)
class Topic:
    depth: int
    topic_id: str
    title: str
    path: str


class ArticleMarkdownParser(HTMLParser):
    """Small HTML-to-readable-Markdown converter for local search."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0
        self.in_pre = False
        self.in_code = False
        self.link_href: str | None = None

    def write(self, text: str) -> None:
        if self.skip_depth:
            return
        if text:
            self.parts.append(text)

    def newline(self, count: int = 1) -> None:
        if self.skip_depth:
            return
        self.parts.append("\n" * count)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag in {"script", "style", "noscript"}:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag in {"h1", "h2", "h3", "h4"}:
            level = {"h1": 1, "h2": 2, "h3": 3, "h4": 4}[tag]
            self.newline(2)
            self.write("#" * level + " ")
        elif tag in {"p", "div", "section", "article", "tr"}:
            self.newline(1)
        elif tag == "br":
            self.newline(1)
        elif tag in {"ul", "ol"}:
            self.newline(1)
        elif tag == "li":
            self.newline(1)
            self.write("- ")
        elif tag == "pre":
            self.in_pre = True
            self.newline(2)
            self.write("```text\n")
        elif tag == "code" and not self.in_pre:
            self.in_code = True
            self.write("`")
        elif tag == "a":
            self.link_href = attrs_dict.get("href")
        elif tag in {"td", "th"}:
            self.write(" | ")
        elif tag == "img":
            alt = attrs_dict.get("alt") or "Image"
            self.write(f"[{alt}]")

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript"} and self.skip_depth:
            self.skip_depth -= 1
            return
        if self.skip_depth:
            return
        if tag in {"h1", "h2", "h3", "h4", "p", "div", "section", "article", "ul", "ol", "tr"}:
            self.newline(1)
        elif tag == "pre":
            self.write("\n```")
            self.newline(2)
            self.in_pre = False
        elif tag == "code" and self.in_code:
            self.write("`")
            self.in_code = False
        elif tag == "a":
            if self.link_href and not self.link_href.startswith("#"):
                self.write(f" ({self.link_href})")
            self.link_href = None

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        if self.in_pre:
            self.write(data)
        else:
            self.write(re.sub(r"\s+", " ", data))

    def get_markdown(self) -> str:
        text = "".join(self.parts)
        text = html.unescape(text)
        text = re.sub(r"[ \t]+\n", "\n", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r" {2,}", " ", text)
        return text.strip() + "\n"


def read_outline(path: Path) -> list[Topic]:
    topics: list[Topic] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        depth, topic_id, title, topic_path = line.split("\t", 3)
        clean_id = topic_id.split("#", 1)[0]
        if not clean_id.endswith(".html"):
            continue
        topics.append(Topic(int(depth), clean_id, title, topic_path))

    seen: dict[str, Topic] = {}
    for topic in topics:
        seen.setdefault(topic.topic_id, topic)
    return list(seen.values())


def fetch_url(url: str, referer: str, timeout: int) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 qnn-local-doc-cache",
            "Referer": referer,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def extract_article(raw_html: str) -> str:
    raw_html = re.sub(r"<script\b.*?</script>", "", raw_html, flags=re.S | re.I)
    raw_html = re.sub(r"<style\b.*?</style>", "", raw_html, flags=re.S | re.I)
    patterns = [
        r'<div itemprop="articleBody">\s*(.*?)\s*</div>\s*</div>\s*</div>\s*</div>\s*</section>',
        r'<div itemprop="articleBody">\s*(.*?)\s*</div>\s*<div class=.topic-detail',
        r'<div itemprop="articleBody">\s*(.*?)\s*</main>',
    ]
    for pattern in patterns:
        match = re.search(pattern, raw_html, flags=re.S | re.I)
        if match:
            return match.group(1)
    return raw_html


def html_to_markdown(article: str) -> str:
    parser = ArticleMarkdownParser()
    parser.feed(article)
    parser.close()
    return parser.get_markdown()


def safe_name(topic_id: str) -> str:
    return topic_id.replace("/", "_").replace(".html", ".md")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outline", type=Path, default=DEFAULT_OUTLINE)
    parser.add_argument("--outdir", type=Path, default=DEFAULT_OUTDIR)
    parser.add_argument("--base-url", default=DEFAULT_BASE)
    parser.add_argument("--referer", default=DEFAULT_REFERER)
    parser.add_argument("--sleep", type=float, default=0.08)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--limit", type=int, default=0, help="Fetch only the first N topics for testing")
    parser.add_argument("--force", action="store_true", help="Re-fetch existing HTML pages")
    args = parser.parse_args()

    if not args.outline.exists():
        raise SystemExit(f"Outline not found: {args.outline}")

    html_dir = args.outdir / "raw_html"
    md_dir = args.outdir / "pages_md"
    html_dir.mkdir(parents=True, exist_ok=True)
    md_dir.mkdir(parents=True, exist_ok=True)

    topics = read_outline(args.outline)
    if args.limit:
        topics = topics[: args.limit]

    corpus_parts: list[str] = []
    failures: list[tuple[str, str]] = []
    for index, topic in enumerate(topics, start=1):
        url = urllib.parse.urljoin(args.base_url, urllib.parse.quote(topic.topic_id))
        html_path = html_dir / topic.topic_id
        md_path = md_dir / safe_name(topic.topic_id)
        source_url = urllib.parse.urljoin(args.referer.replace("index_QNN.html", ""), topic.topic_id)

        try:
            if html_path.exists() and not args.force:
                raw = html_path.read_text(encoding="utf-8", errors="replace")
                status = "cached"
            else:
                print(f"[{index}/{len(topics)}] fetch {topic.topic_id}", file=sys.stderr)
                raw = fetch_url(url, args.referer, args.timeout)
                html_path.write_text(raw, encoding="utf-8")
                status = "fetched"
                time.sleep(args.sleep)

            md = html_to_markdown(extract_article(raw))
            header = (
                f"# {topic.title}\n\n"
                f"- Topic ID: `{topic.topic_id}`\n"
                f"- Source: {source_url}\n"
                f"- Path: {topic.path}\n"
                f"- Fetch status: {status}\n\n"
            )
            md_path.write_text(header + md, encoding="utf-8")
            corpus_parts.append(f"\n\n---\n\n{header}{md}")
        except Exception as exc:  # noqa: BLE001 - CLI should continue and report failures.
            failures.append((topic.topic_id, repr(exc)))
            print(f"[warn] failed {topic.topic_id}: {exc}", file=sys.stderr)

    (args.outdir / "qnn_corpus.local.md").write_text("".join(corpus_parts).strip() + "\n", encoding="utf-8")
    (args.outdir / "fetch_failures.tsv").write_text(
        "\n".join(f"{topic_id}\t{error}" for topic_id, error in failures) + ("\n" if failures else ""),
        encoding="utf-8",
    )
    print(f"topics_requested={len(topics)} pages_ok={len(topics) - len(failures)} failures={len(failures)}")
    print(f"local_pages={md_dir}")
    print(f"local_corpus={args.outdir / 'qnn_corpus.local.md'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

