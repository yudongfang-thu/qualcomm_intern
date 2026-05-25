#!/usr/bin/env python3
"""Validate the Phase 1 Python baseline artifacts and preprocessing pipeline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import onnx
import onnx.checker
import onnxruntime as ort


EXPECTED_INPUT_NAME = "data"
EXPECTED_INPUT_BYTES = 1 * 3 * 224 * 224 * 4
EXPECTED_OUTPUT_SHAPE = [1, 1000]
EXPECTED_TOP5 = [258, 261, 259, 257, 260]


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", type=Path, default=Path("artifacts/phase1_resnet"))
    parser.add_argument("--model", type=Path, default=None)
    parser.add_argument("--image", type=Path, default=None)
    parser.add_argument("--input-name", default=EXPECTED_INPUT_NAME)
    args = parser.parse_args()

    workdir = args.workdir
    model_path = args.model or workdir / "models" / "resnet50-v2-7.onnx"
    image_path = args.image or workdir / "images" / "dog.jpg"
    input_raw = workdir / "inputs" / "input_0.raw"
    input_list = workdir / "inputs" / "input_list.txt"
    target_input_list = workdir / "inputs" / "target_input_list.txt"
    output_npy = workdir / "baseline" / "onnxruntime_output.npy"
    output_raw = workdir / "baseline" / "onnxruntime_output.raw"
    result_json = workdir / "baseline" / "baseline_result.json"

    print("[check] files exist")
    for path in [model_path, image_path, input_raw, input_list, target_input_list, output_npy, output_raw, result_json]:
        assert_true(path.exists(), f"Missing required file: {path}")
        assert_true(path.stat().st_size > 0, f"Empty file: {path}")

    print("[check] ONNX model structure")
    model = onnx.load(model_path)
    onnx.checker.check_model(model)
    graph_input_names = [value_info.name for value_info in model.graph.input]
    assert_true(args.input_name in graph_input_names, f"Input name '{args.input_name}' not in graph inputs: {graph_input_names}")

    print("[check] raw input size and input_list format")
    assert_true(input_raw.stat().st_size == EXPECTED_INPUT_BYTES, f"input_0.raw size should be {EXPECTED_INPUT_BYTES}, got {input_raw.stat().st_size}")
    assert_true(input_list.read_text(encoding="utf-8").startswith(f"{args.input_name}:="), "input_list.txt should start with '<input_name>:='")
    assert_true(target_input_list.read_text(encoding="utf-8").strip() == f"{args.input_name}:=input_0.raw", "target_input_list.txt format mismatch")

    print("[check] baseline result json")
    result = json.loads(result_json.read_text(encoding="utf-8"))
    assert_true(result["input_name"] == args.input_name, f"baseline_result.json input_name mismatch: {result['input_name']}")
    assert_true(result["preprocessed_input_shape"] == [1, 3, 224, 224], "preprocessed input shape mismatch")
    assert_true(result["output_shape"] == EXPECTED_OUTPUT_SHAPE, f"output shape mismatch: {result['output_shape']}")
    top5 = [item["index"] for item in result["top5"]]
    assert_true(top5 == EXPECTED_TOP5, f"top5 mismatch: expected {EXPECTED_TOP5}, got {top5}")

    print("[check] npy/raw output consistency")
    y_npy = np.load(output_npy).astype(np.float32)
    y_raw = np.fromfile(output_raw, dtype=np.float32).reshape(y_npy.shape)
    assert_true(np.array_equal(y_npy, y_raw), "onnxruntime_output.npy and .raw are not exactly equal")

    print("[check] rerun ONNX Runtime and compare")
    x = np.fromfile(input_raw, dtype=np.float32).reshape(1, 3, 224, 224)
    session = ort.InferenceSession(str(model_path), providers=["CPUExecutionProvider"])
    y_rerun = np.asarray(session.run(None, {args.input_name: x})[0], dtype=np.float32)
    assert_true(list(y_rerun.shape) == EXPECTED_OUTPUT_SHAPE, f"rerun output shape mismatch: {list(y_rerun.shape)}")
    max_abs = float(np.max(np.abs(y_rerun - y_npy)))
    assert_true(max_abs == 0.0, f"rerun output differs from saved baseline, max_abs={max_abs}")

    rerun_top5 = y_rerun.reshape(-1).argsort()[-5:][::-1].tolist()
    assert_true(rerun_top5 == EXPECTED_TOP5, f"rerun top5 mismatch: expected {EXPECTED_TOP5}, got {rerun_top5}")

    print("[pass] baseline pipeline validation passed")
    print(json.dumps({
        "model": str(model_path.resolve()),
        "image": str(image_path.resolve()),
        "input_name": args.input_name,
        "input_raw_bytes": input_raw.stat().st_size,
        "output_shape": list(y_npy.shape),
        "top5": rerun_top5,
        "rerun_max_abs_error": max_abs,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

