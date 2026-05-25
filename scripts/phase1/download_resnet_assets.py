#!/usr/bin/env python3
"""Download Phase 1 ResNet ONNX model, sample image, and optional labels."""

from __future__ import annotations

import argparse
import sys
import urllib.request
from pathlib import Path


DEFAULT_MODEL_URL = (
    "https://github.com/onnx/models/raw/main/validated/vision/classification/"
    "resnet/model/resnet50-v2-7.onnx"
)
DEFAULT_IMAGE_URL = "https://github.com/pytorch/hub/raw/master/images/dog.jpg"
DEFAULT_LABELS_URL = "https://raw.githubusercontent.com/pytorch/hub/master/imagenet_classes.txt"


def download(url: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and output_path.stat().st_size > 0:
        print(f"[skip] {output_path} already exists ({output_path.stat().st_size} bytes)")
        return

    print(f"[download] {url}")
    print(f"[to]       {output_path}")
    with urllib.request.urlopen(url) as response:
        total = int(response.headers.get("Content-Length") or 0)
        read = 0
        with output_path.open("wb") as f:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                read += len(chunk)
                if total:
                    pct = read * 100 / total
                    print(f"\r  {read / 1024 / 1024:.1f} MiB / {total / 1024 / 1024:.1f} MiB ({pct:.1f}%)", end="")
                else:
                    print(f"\r  {read / 1024 / 1024:.1f} MiB", end="")
        print()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workdir", type=Path, default=Path("artifacts/phase1_resnet"))
    parser.add_argument("--model-url", default=DEFAULT_MODEL_URL)
    parser.add_argument("--image-url", default=DEFAULT_IMAGE_URL)
    parser.add_argument("--labels-url", default=DEFAULT_LABELS_URL)
    args = parser.parse_args()

    download(args.model_url, args.workdir / "models" / "resnet50-v2-7.onnx")
    download(args.image_url, args.workdir / "images" / "dog.jpg")
    download(args.labels_url, args.workdir / "labels" / "imagenet_classes.txt")

    print("\nEnvironment variables for later commands:")
    print(f"export MODEL_PATH='{(args.workdir / 'models' / 'resnet50-v2-7.onnx').resolve()}'")
    print(f"export IMAGE_PATH='{(args.workdir / 'images' / 'dog.jpg').resolve()}'")
    print(f"export LABELS_PATH='{(args.workdir / 'labels' / 'imagenet_classes.txt').resolve()}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())

