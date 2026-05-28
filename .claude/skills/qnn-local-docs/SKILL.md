---
name: qnn-local-docs
description: Use this skill when answering questions about Qualcomm QNN/QAIRT docs, qnn-onnx-converter, qnn-net-run, QNN backends, setup, quantization, HTP/DSP/GPU/CPU deployment, or local QNN documentation search. It uses a local-only SQLite documentation database built from official Qualcomm public docs fetched on the user's machine.
---

# QNN Local Docs

Use this skill for QNN/QAIRT documentation lookup and deployment guidance.

## Safety Rule

Do not commit or paste the raw mirrored Qualcomm documentation. Raw fetched docs must stay under `artifacts/qnn_docs/`, which is ignored by git. It is okay to use short excerpts, summaries, commands, and source URLs.

## First Check

From the repository root, check whether the local database exists:

```bash
test -f artifacts/qnn_docs/qnn_docs.sqlite && echo ready || echo missing
```

If missing, ask the user to run:

```bash
python scripts/qnn_docs/fetch_qnn_docs.py
python scripts/qnn_docs/build_qnn_doc_db.py
```

Or run the full pipeline:

```bash
bash scripts/qnn_docs/qnn_docs_pipeline.sh
```

## Search Workflow

Search the database before answering detailed QNN questions:

```bash
python scripts/qnn_docs/search_qnn_docs.py "qnn-net-run backend" --limit 8
python scripts/qnn_docs/search_qnn_docs.py "qnn-onnx-converter preserve_io input_list" --limit 8
python scripts/qnn_docs/search_qnn_docs.py "HTP quantized model context binary" --limit 8
```

Use `--full` only when a result page is clearly relevant and you need page details:

```bash
python scripts/qnn_docs/search_qnn_docs.py "check-python-dependency envsetup" --limit 2 --full
```

## Answer Style

- Answer in Chinese by default.
- Prefer copy-pasteable commands.
- Mention the local page title/source URL when making a specific documentation claim.
- If the local database is missing and cannot be fetched, fall back to the repository's original Chinese summaries in `docs/`.
- Keep the main development principle visible: first correctness, then performance.

## Useful Repository Summaries

For concise project context, read:

- `docs/qnn_development_environment_setup.md`
- `docs/phase1_qnn_onnx_resnet_runbook.md`
- `docs/qnn_backend_inference_modes.md`
- `.claude/skills/qnn-local-docs/references/qnn_quick_summary.md`

