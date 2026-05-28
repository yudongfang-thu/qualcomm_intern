#!/usr/bin/env bash
set -euo pipefail

OUTDIR="${1:-artifacts/qnn_docs}"

python scripts/qnn_docs/fetch_qnn_docs.py --outdir "$OUTDIR"
python scripts/qnn_docs/build_qnn_doc_db.py --pages-dir "$OUTDIR/pages_md" --db "$OUTDIR/qnn_docs.sqlite"
python scripts/qnn_docs/smart_search_qnn_docs.py --db "$OUTDIR/qnn_docs.sqlite" "HTP 怎么跑模型，需要量化吗" --show-queries --limit 3
python scripts/qnn_docs/search_qnn_docs.py --db "$OUTDIR/qnn_docs.sqlite" "qnn-net-run backend" --limit 3
