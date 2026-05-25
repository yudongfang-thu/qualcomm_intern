#!/usr/bin/env python3
"""Compare QNN raw output against the ONNX Runtime baseline output."""

from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path

import numpy as np


def find_raw(path: Path) -> Path:
    if path.is_file():
        return path
    matches = [Path(p) for p in glob.glob(str(path / "**" / "*.raw"), recursive=True)]
    if not matches:
        raise FileNotFoundError(f"No .raw output found under {path}")
    matches.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return matches[0]


def load_labels(path: Path | None) -> list[str] | None:
    if path is None or not path.exists():
        return None
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def topk_items(values: np.ndarray, labels: list[str] | None, k: int) -> list[dict[str, object]]:
    flat = values.reshape(-1)
    top = flat.argsort()[-k:][::-1]
    items = []
    for rank, index in enumerate(top.tolist(), start=1):
        item: dict[str, object] = {"rank": rank, "index": int(index), "value": float(flat[index])}
        if labels is not None and index < len(labels):
            item["label"] = labels[index]
        items.append(item)
    return items


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, default=Path("artifacts/phase1_resnet/baseline/onnxruntime_output.npy"))
    parser.add_argument("--qnn-output", type=Path, required=True, help="QNN .raw file or a directory containing .raw outputs")
    parser.add_argument("--labels", type=Path, default=Path("artifacts/phase1_resnet/labels/imagenet_classes.txt"))
    parser.add_argument("--topk", type=int, default=5)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    baseline = np.load(args.baseline).reshape(-1).astype(np.float32)
    qnn_raw = find_raw(args.qnn_output)
    qnn = np.fromfile(qnn_raw, dtype=np.float32).reshape(-1)

    n = min(len(baseline), len(qnn))
    if n == 0:
        raise ValueError("Empty baseline or QNN output")

    baseline = baseline[:n]
    qnn = qnn[:n]
    diff = baseline - qnn
    cosine = float(np.dot(baseline, qnn) / (np.linalg.norm(baseline) * np.linalg.norm(qnn) + 1e-12))
    labels = load_labels(args.labels)

    result = {
        "baseline": str(args.baseline.resolve()),
        "qnn_output": str(qnn_raw.resolve()),
        "num_values_compared": int(n),
        "max_abs_error": float(np.max(np.abs(diff))),
        "mean_abs_error": float(np.mean(np.abs(diff))),
        "cosine_similarity": cosine,
        "baseline_topk": topk_items(baseline, labels, args.topk),
        "qnn_topk": topk_items(qnn, labels, args.topk),
    }

    text = json.dumps(result, ensure_ascii=False, indent=2)
    print(text)
    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

