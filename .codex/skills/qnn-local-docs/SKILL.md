---
name: qnn-local-docs
description: Search and answer from a local Qualcomm QNN/QAIRT documentation database. Use when the user asks about QNN/QAIRT setup, qnn-onnx-converter, qnn-model-lib-generator, qnn-net-run, QNN backends, CPU/GPU/HTP/DSP inference, quantization, context binaries, deployment commands, or asks Codex to look up local QNN documentation.
---

# QNN Local Docs

Use this skill to answer QNN/QAIRT questions from the repository's local documentation database and original project notes.

## Safety Rule

Do not commit, paste, or upload the raw mirrored Qualcomm documentation. Raw fetched docs must stay under `artifacts/qnn_docs/`, which is ignored by git. It is okay to use short excerpts, source URLs, commands, and original Chinese summaries.

## First Check

From the repository root, check whether the local database exists:

```bash
test -f artifacts/qnn_docs/qnn_docs.sqlite && echo ready || echo missing
```

If missing, ask the user to run the pipeline on their machine, or run it if appropriate:

```bash
bash scripts/qnn_docs/qnn_docs_pipeline.sh
```

Equivalent manual steps:

```bash
python scripts/qnn_docs/fetch_qnn_docs.py
python scripts/qnn_docs/build_qnn_doc_db.py
```

## Search Workflow

For Chinese or natural-language questions, start with smart search. It expands Chinese intent into several QNN keyword queries, searches SQLite FTS, and merges results:

```bash
python scripts/qnn_docs/smart_search_qnn_docs.py "HTP 怎么跑模型，需要量化吗" --show-queries --limit 8
python scripts/qnn_docs/smart_search_qnn_docs.py "qnn 环境怎么配置，Python 依赖怎么装" --show-queries --limit 8
python scripts/qnn_docs/smart_search_qnn_docs.py "ONNX 模型怎么转 QNN 并运行" --show-queries --limit 8
```

If the first result set is weak, add explicit QNN keywords with `--query`:

```bash
python scripts/qnn_docs/smart_search_qnn_docs.py "HTP 怎么跑模型" \
  --query "libQnnHtp.so retrieve_context" \
  --query "HTP quantized input_list context binary" \
  --limit 8
```

For exact lookup, use direct search:

```bash
python scripts/qnn_docs/search_qnn_docs.py "qnn-net-run backend input_list output_dir" --limit 8
python scripts/qnn_docs/search_qnn_docs.py "qnn-onnx-converter preserve_io input_list" --limit 8
python scripts/qnn_docs/search_qnn_docs.py "envsetup check-python-dependency" --limit 8
```

Use `--full` only after a page is clearly relevant:

```bash
python scripts/qnn_docs/search_qnn_docs.py "qnn-net-run backend input_list output_dir" --limit 2 --full
```

## Answer Style

- Answer in Chinese by default.
- Prefer copy-pasteable commands and concrete paths.
- Mention the local page title and official source URL when making a documentation-specific claim.
- Treat smart search as retrieval only; inspect the snippets/pages and reason before answering.
- If the database is unavailable, fall back to the original repo summaries in `docs/`.
- Keep the project principle visible: first correctness, then performance.

## Useful Project Notes

Read `references/qnn_quick_summary.md` for a compact Chinese summary and common queries.

For deeper local context, inspect these repository files as needed:

- `docs/qnn_development_environment_setup.md`
- `docs/phase1_qnn_onnx_resnet_runbook.md`
- `docs/qnn_backend_inference_modes.md`
- `docs/phase1_assets_and_baseline.md`
