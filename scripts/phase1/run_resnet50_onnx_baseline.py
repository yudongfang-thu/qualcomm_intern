#!/usr/bin/env python3
"""Run original ONNX Runtime inference for Phase 1 QNN correctness checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import onnx
import onnxruntime as ort
from PIL import Image


def tensor_shape(value_info: onnx.ValueInfoProto) -> list[int | str]:
    dims: list[int | str] = []
    for dim in value_info.type.tensor_type.shape.dim:
        if dim.dim_value:
            dims.append(dim.dim_value)
        elif dim.dim_param:
            dims.append(dim.dim_param)
        else:
            dims.append("?")
    return dims


def resolve_input(model_path: Path, requested_name: str | None) -> tuple[str, list[int | str]]:
    model = onnx.load(model_path)
    inputs = list(model.graph.input)
    if not inputs:
        raise ValueError("ONNX model has no graph inputs")

    if requested_name is None:
        value_info = inputs[0]
        return value_info.name, tensor_shape(value_info)

    for value_info in inputs:
        if value_info.name == requested_name:
            return value_info.name, tensor_shape(value_info)
    names = ", ".join(value_info.name for value_info in inputs)
    raise ValueError(f"Input '{requested_name}' not found. Available inputs: {names}")


def preprocess_image(image_path: Path, image_size: int = 224) -> np.ndarray:
    image = Image.open(image_path).convert("RGB")
    image = image.resize((256, 256))
    width, height = image.size
    left = (width - image_size) // 2
    top = (height - image_size) // 2
    image = image.crop((left, top, left + image_size, top + image_size))

    x = np.asarray(image).astype(np.float32) / 255.0
    mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
    std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
    x = (x - mean) / std
    x = np.transpose(x, (2, 0, 1))[None, ...]
    return np.ascontiguousarray(x, dtype=np.float32)


def load_labels(labels_path: Path | None) -> list[str] | None:
    if labels_path is None or not labels_path.exists():
        return None
    return [line.strip() for line in labels_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, default=Path("artifacts/phase1_resnet/models/resnet50-v2-7.onnx"))
    parser.add_argument("--image", type=Path, default=Path("artifacts/phase1_resnet/images/dog.jpg"))
    parser.add_argument("--labels", type=Path, default=Path("artifacts/phase1_resnet/labels/imagenet_classes.txt"))
    parser.add_argument("--input-name", default=None)
    parser.add_argument("--outdir", type=Path, default=Path("artifacts/phase1_resnet/baseline"))
    parser.add_argument("--qnn-input-dir", type=Path, default=Path("artifacts/phase1_resnet/inputs"))
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    args.qnn_input_dir.mkdir(parents=True, exist_ok=True)

    input_name, input_shape = resolve_input(args.model, args.input_name)
    x = preprocess_image(args.image)

    input_raw = args.qnn_input_dir / "input_0.raw"
    x.tofile(input_raw)
    (args.qnn_input_dir / "input_list.txt").write_text(f"{input_name}:={input_raw.resolve()}\n", encoding="utf-8")
    (args.qnn_input_dir / "target_input_list.txt").write_text(f"{input_name}:=input_0.raw\n", encoding="utf-8")

    session = ort.InferenceSession(str(args.model), providers=["CPUExecutionProvider"])
    outputs = session.run(None, {input_name: x})
    y = np.asarray(outputs[0], dtype=np.float32)

    output_npy = args.outdir / "onnxruntime_output.npy"
    output_raw = args.outdir / "onnxruntime_output.raw"
    np.save(output_npy, y)
    y.tofile(output_raw)

    flat = y.reshape(-1)
    top5 = flat.argsort()[-5:][::-1]
    labels = load_labels(args.labels)

    top5_items = []
    for rank, index in enumerate(top5.tolist(), start=1):
        item = {"rank": rank, "index": int(index), "value": float(flat[index])}
        if labels is not None and index < len(labels):
            item["label"] = labels[index]
        top5_items.append(item)

    result = {
        "model": str(args.model.resolve()),
        "image": str(args.image.resolve()),
        "input_name": input_name,
        "input_shape_from_onnx": input_shape,
        "preprocessed_input_shape": list(x.shape),
        "preprocessed_input_dtype": str(x.dtype),
        "qnn_input_raw": str(input_raw.resolve()),
        "qnn_input_list": str((args.qnn_input_dir / "input_list.txt").resolve()),
        "qnn_target_input_list": str((args.qnn_input_dir / "target_input_list.txt").resolve()),
        "output_shape": list(y.shape),
        "output_dtype": str(y.dtype),
        "output_npy": str(output_npy.resolve()),
        "output_raw": str(output_raw.resolve()),
        "top5": top5_items,
    }
    result_path = args.outdir / "baseline_result.json"
    result_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

