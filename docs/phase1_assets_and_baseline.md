# Phase 1 模型、样例输入和 Python baseline

> 目的：给 QNN 推理提供一个可对比的“原版模型结果”。没有 baseline，就很难判断 QNN 输出是否正确。

## 1. 推荐资产

Phase 1 先用图像分类模型，不要一开始就上 VLM。

推荐：

- 模型：ONNX Model Zoo `resnet50-v2-7.onnx`
- 输入图片：PyTorch Hub 示例 `dog.jpg`
- 标签：PyTorch Hub `imagenet_classes.txt`

仓库不直接保存大模型。请用脚本下载到本地 `artifacts/phase1_resnet/`。

## 2. 安装依赖

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
pip install numpy pillow onnx onnxruntime
```

如果你的机器默认 Python 太新导致 `onnxruntime` 安装失败，可以换 Python 3.10/3.11/3.12：

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python3 -m pip install --upgrade pip
pip install numpy pillow onnx onnxruntime
```

## 3. 下载模型、图片和标签

```bash
python scripts/phase1/download_resnet_assets.py
```

下载完成后应看到：

```text
artifacts/phase1_resnet/models/resnet50-v2-7.onnx
artifacts/phase1_resnet/images/dog.jpg
artifacts/phase1_resnet/labels/imagenet_classes.txt
```

## 4. 运行原版 ONNX Runtime 推理

```bash
python scripts/phase1/run_resnet50_onnx_baseline.py
```

这个脚本会做 5 件事：

1. 读取 ONNX 模型，自动识别第一个 input name。
2. 对图片做 ResNet 常见预处理：RGB、resize 256、center crop 224、ImageNet mean/std、NCHW float32。
3. 保存 QNN 可用输入：`input_0.raw`。
4. 保存 QNN input list：`input_list.txt` 和 `target_input_list.txt`。
5. 运行 ONNX Runtime baseline，并保存 `onnxruntime_output.npy/raw` 和 `baseline_result.json`。

关键输出路径：

```text
artifacts/phase1_resnet/inputs/input_0.raw
artifacts/phase1_resnet/inputs/input_list.txt
artifacts/phase1_resnet/inputs/target_input_list.txt
artifacts/phase1_resnet/baseline/onnxruntime_output.npy
artifacts/phase1_resnet/baseline/onnxruntime_output.raw
artifacts/phase1_resnet/baseline/baseline_result.json
```

## 5. 本机实测 baseline 结果

我在本仓库本机执行过一次，结果如下。你在高通机器上如果下载同一个模型和图片，正常情况下应该得到非常接近的结果。

```text
input_name: data
input_shape_from_onnx: [N, 3, 224, 224]
preprocessed_input_shape: [1, 3, 224, 224]
output_shape: [1, 1000]
```

Top-5：

| rank | index | label | value |
|---:|---:|---|---:|
| 1 | 258 | Samoyed | 15.503643 |
| 2 | 261 | keeshond | 11.235579 |
| 3 | 259 | Pomeranian | 10.939158 |
| 4 | 257 | Great Pyrenees | 10.184661 |
| 5 | 260 | chow | 9.860891 |

## 6. 如何接到 QNN 手册

运行完 baseline 后，在 QNN 手册中可以直接设置：

```bash
export MODEL_PATH="$PWD/artifacts/phase1_resnet/models/resnet50-v2-7.onnx"
export IMAGE_PATH="$PWD/artifacts/phase1_resnet/images/dog.jpg"
export INPUT_NAME=data
export INPUT_DIMS=1,3,224,224
```

如果 `baseline_result.json` 里显示 input name 不是 `data`，以 JSON 里的 `input_name` 为准。

QNN host 运行时可以直接用：

```bash
export QNN_INPUT_LIST="$PWD/artifacts/phase1_resnet/inputs/input_list.txt"
```

QNN target 运行时把下面两个文件推到设备同一个目录：

```text
artifacts/phase1_resnet/inputs/input_0.raw
artifacts/phase1_resnet/inputs/target_input_list.txt
```

## 7. QNN output 拉回后的自动对比

如果你已经跑完 `qnn-net-run`，并且 QNN 输出目录是：

```bash
export QNN_OUTPUT_DIR="$PWD/artifacts/phase1_resnet/qnn_host_cpu"
```

就运行：

```bash
python scripts/phase1/compare_qnn_with_baseline.py \
  --qnn-output "$QNN_OUTPUT_DIR" \
  --out artifacts/phase1_resnet/compare/qnn_vs_onnxruntime.json
```

如果你只有一个 `.raw` 文件，也可以直接传文件路径：

```bash
python scripts/phase1/compare_qnn_with_baseline.py \
  --qnn-output /path/to/qnn_output.raw
```

脚本会输出：

- `max_abs_error`
- `mean_abs_error`
- `cosine_similarity`
- ONNX Runtime top-k
- QNN top-k

## 8. 正确性判断

QNN output 拉回后，先比较：

- top-1/top-5 index 是否一致。
- cosine similarity 是否接近 1。
- max abs error 和 mean abs error 是否很小。

如果差距很大，优先查：

1. input name。
2. NCHW/NHWC layout。
3. RGB/BGR。
4. mean/std。
5. QNN converter 是否改变了输入 layout。

## 9. 资产来源

- ONNX ResNet50 v2: <https://github.com/onnx/models/tree/main/validated/vision/classification/resnet>
- PyTorch Hub sample image: <https://github.com/pytorch/hub/blob/master/images/dog.jpg>
- PyTorch Hub ImageNet labels: <https://raw.githubusercontent.com/pytorch/hub/master/imagenet_classes.txt>
