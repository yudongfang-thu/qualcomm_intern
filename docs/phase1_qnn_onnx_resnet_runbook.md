# Phase 1：QNN ONNX/ResNet 浮点部署照抄手册

> 目标：在不接机械臂的情况下，先把一个 ONNX 图像分类模型跑通 QNN 流程。  
> 推荐顺序：host CPU float -> Qualcomm target CPU float -> INT8 quantization -> HTP。  
> 这份文档尽量写成可以逐条复制的命令。你只需要先改少数几个路径变量。

## 0. 你要先知道的 4 件事

1. `qnn-onnx-converter`：把 ONNX 模型转成 QNN C++ 源码和权重文件，输出一般是 `.cpp` 和 `.bin`。
2. `qnn-model-lib-generator`：把 `.cpp/.bin` 编译成目标平台可加载的 `.so` 模型库。
3. `qnn-net-run`：Qualcomm 提供的命令行推理程序，加载模型 `.so` 和 backend `.so` 执行推理。
4. `libQnnCpu.so`：CPU backend。Phase 1 先用它跑浮点，最稳。

不要一开始就上 HTP/DSP。QNN 文档提醒：HTP/DSP target 必须用量化模型并提供 `--input_list` 做校准/量化。第一天先用 CPU float 打通链路。

## 1. 路径变量：先复制这一段

在 Qualcomm 机器上打开 terminal，先找 SDK：

```bash
find /opt "$HOME" /local/mnt/workspace -maxdepth 6 -type f -name qnn-onnx-converter 2>/dev/null | head
```

如果输出类似：

```text
/some/path/qairt/2.xx.x/bin/x86_64-linux-clang/qnn-onnx-converter
```

就这样设置：

```bash
export QNN_ONNX_CONVERTER=/some/path/qairt/2.xx.x/bin/x86_64-linux-clang/qnn-onnx-converter
export QNN_SDK_ROOT="$(cd "$(dirname "$(dirname "$(dirname "$QNN_ONNX_CONVERTER")")")" && pwd)"
```

如果 mentor 已经告诉你 SDK 路径，也可以直接设置：

```bash
export QNN_SDK_ROOT=/some/path/qairt/2.xx.x
```

然后设置固定变量：

```bash
export QNN_HOST_ARCH=x86_64-linux-clang
export WORKDIR="$HOME/qnn_phase1_resnet"
mkdir -p "$WORKDIR"/{models,images,inputs,outputs,qnn_artifacts,scripts,logs}

export PATH="$QNN_SDK_ROOT/bin/$QNN_HOST_ARCH:$PATH"
export LD_LIBRARY_PATH="$QNN_SDK_ROOT/lib/$QNN_HOST_ARCH:${LD_LIBRARY_PATH:-}"
```

确认 SDK 目录正确：

```bash
echo "QNN_SDK_ROOT=$QNN_SDK_ROOT"
ls "$QNN_SDK_ROOT/bin/$QNN_HOST_ARCH/qnn-onnx-converter"
ls "$QNN_SDK_ROOT/bin/$QNN_HOST_ARCH/qnn-net-run"
ls "$QNN_SDK_ROOT/lib/$QNN_HOST_ARCH/libQnnCpu.so"
```

## 2. 检查 QNN 工具是否可用

```bash
"$QNN_SDK_ROOT/bin/$QNN_HOST_ARCH/qnn-onnx-converter" --help | head -40
python3 "$QNN_SDK_ROOT/bin/$QNN_HOST_ARCH/qnn-model-lib-generator" -h | head -40
"$QNN_SDK_ROOT/bin/$QNN_HOST_ARCH/qnn-net-run" --help | head -60
```

如果 `qnn-model-lib-generator` 报 CMake 或 compiler 错，说明 host 编译工具链没配好，先把报错保存：

```bash
python3 "$QNN_SDK_ROOT/bin/$QNN_HOST_ARCH/qnn-model-lib-generator" -h > "$WORKDIR/logs/model_lib_generator_help.txt" 2>&1
```

## 3. Python 环境

```bash
python3 -m venv "$WORKDIR/venv"
source "$WORKDIR/venv/bin/activate"
python3 -m pip install --upgrade pip
pip3 install numpy onnx onnxruntime onnxsim pandas pillow requests
```

如果 SDK 里有依赖检查脚本，也跑一下：

```bash
if [ -x "$QNN_SDK_ROOT/bin/check-python-dependency" ]; then
  "$QNN_SDK_ROOT/bin/check-python-dependency" || true
fi
```

## 4. 下载 ResNet ONNX 和测试图片

优先用 mentor 给你的模型。如果没有，就先用 ONNX Model Zoo 的 ResNet50：

```bash
cd "$WORKDIR/models"
wget -O resnet50-v2-7.onnx \
  "https://github.com/onnx/models/raw/main/validated/vision/classification/resnet/model/resnet50-v2-7.onnx"

export MODEL_PATH="$WORKDIR/models/resnet50-v2-7.onnx"
```

下载一张测试图片：

```bash
cd "$WORKDIR/images"
wget -O dog.jpg "https://github.com/pytorch/hub/raw/master/images/dog.jpg"
export IMAGE_PATH="$WORKDIR/images/dog.jpg"
```

如果你是从本仓库开始，推荐直接使用配套脚本下载模型、图片、标签，并运行 Python baseline：

```bash
python scripts/phase1/download_resnet_assets.py
python scripts/phase1/run_resnet50_onnx_baseline.py
```

详细说明见 [phase1_assets_and_baseline.md](phase1_assets_and_baseline.md)。

如果公司网络不能访问 GitHub，就用任意一张本地 jpg，并设置：

```bash
export IMAGE_PATH=/path/to/your/image.jpg
```

## 5. 查看 ONNX 输入输出信息

复制执行：

```bash
python3 - <<'PY'
import onnx
import os

model_path = os.environ["MODEL_PATH"]
model = onnx.load(model_path)

def shape_of(value_info):
    dims = []
    tensor_type = value_info.type.tensor_type
    for d in tensor_type.shape.dim:
        if d.dim_value:
            dims.append(str(d.dim_value))
        elif d.dim_param:
            dims.append(d.dim_param)
        else:
            dims.append("?")
    return dims

print("MODEL:", model_path)
print("IR version:", model.ir_version)
print("Opset:", [(o.domain or "ai.onnx", o.version) for o in model.opset_import])
print("\nInputs:")
for x in model.graph.input:
    print(" ", x.name, shape_of(x))
print("\nOutputs:")
for y in model.graph.output:
    print(" ", y.name, shape_of(y))
PY
```

常见 ResNet50 v2 的输入是：

```text
data [1, 3, 224, 224]
```

如果你的输出不一样，把下面两个变量改掉：

```bash
export INPUT_NAME=data
export INPUT_DIMS=1,3,224,224
```

如果上一步打印的 input name 不是 `data`，例如是 `input`，就用：

```bash
export INPUT_NAME=input
export INPUT_DIMS=1,3,224,224
```

## 6. 生成模型输入 raw

ResNet 通常需要 NCHW、float32、ImageNet mean/std normalize。这里先生成一个 `input_0.raw`：

```bash
python3 - <<'PY'
import os
import numpy as np
from PIL import Image

image_path = os.environ["IMAGE_PATH"]
out_path = os.path.join(os.environ["WORKDIR"], "inputs", "input_0.raw")

img = Image.open(image_path).convert("RGB")
img = img.resize((256, 256))
w, h = img.size
left = (w - 224) // 2
top = (h - 224) // 2
img = img.crop((left, top, left + 224, top + 224))

x = np.asarray(img).astype("float32") / 255.0
mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
x = (x - mean) / std
x = np.transpose(x, (2, 0, 1))[None, ...]  # NHWC -> NCHW, add batch
x.astype("float32").tofile(out_path)

print("saved", out_path)
print("shape", x.shape, "dtype", x.dtype)
print("min/max", float(x.min()), float(x.max()))
PY
```

生成 host 运行用的 input list：

```bash
printf "%s:=%s\n" "$INPUT_NAME" "$WORKDIR/inputs/input_0.raw" > "$WORKDIR/inputs/input_list.txt"
cat "$WORKDIR/inputs/input_list.txt"
```

生成 target 设备运行用的 input list。注意这里用相对路径，因为文件会被 push/scp 到设备同一个目录：

```bash
printf "%s:=input_0.raw\n" "$INPUT_NAME" > "$WORKDIR/inputs/target_input_list.txt"
cat "$WORKDIR/inputs/target_input_list.txt"
```

## 7. 跑 ONNX Runtime baseline

先保存一份 baseline，后面和 QNN output 比较：

```bash
python3 - <<'PY'
import os
import numpy as np
import onnxruntime as ort

model_path = os.environ["MODEL_PATH"]
input_name = os.environ["INPUT_NAME"]
raw_path = os.path.join(os.environ["WORKDIR"], "inputs", "input_0.raw")
out_dir = os.path.join(os.environ["WORKDIR"], "outputs", "onnxruntime")
os.makedirs(out_dir, exist_ok=True)

x = np.fromfile(raw_path, dtype=np.float32).reshape(1, 3, 224, 224)
sess = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
y = sess.run(None, {input_name: x})[0]

np.save(os.path.join(out_dir, "output.npy"), y)
y.astype("float32").tofile(os.path.join(out_dir, "output.raw"))

flat = y.reshape(-1)
top5 = flat.argsort()[-5:][::-1]
print("baseline output shape:", y.shape)
print("top5 indices:", top5.tolist())
print("top5 values:", flat[top5].tolist())
PY
```

## 8. ONNX -> QNN `.cpp/.bin`

先做 dry run，看是否有不支持的 op：

```bash
"$QNN_SDK_ROOT/bin/$QNN_HOST_ARCH/qnn-onnx-converter" \
  --input_network "$MODEL_PATH" \
  -d "$INPUT_NAME" "$INPUT_DIMS" \
  --preserve_io layout \
  --dry_run debug \
  > "$WORKDIR/logs/qnn_converter_dry_run.log" 2>&1

tail -80 "$WORKDIR/logs/qnn_converter_dry_run.log"
```

正式转换：

```bash
export QNN_MODEL_CPP="$WORKDIR/qnn_artifacts/resnet50_qnn_model.cpp"

"$QNN_SDK_ROOT/bin/$QNN_HOST_ARCH/qnn-onnx-converter" \
  --input_network "$MODEL_PATH" \
  -d "$INPUT_NAME" "$INPUT_DIMS" \
  --preserve_io layout \
  --output_path "$QNN_MODEL_CPP" \
  > "$WORKDIR/logs/qnn_converter_float.log" 2>&1

tail -80 "$WORKDIR/logs/qnn_converter_float.log"
ls -lh "$WORKDIR/qnn_artifacts"
```

这里用了 `--preserve_io layout`，目的是保留 ONNX 的 NCHW 输入布局，这样我们生成的 `1x3x224x224` raw 可以直接用。不要在这里单独使用 `--preserve_io`，因为它还会保留 datatype，后续 `qnn-net-run` 输入参数会更容易混乱。

转换成功后设置：

```bash
export QNN_MODEL_BASE="${QNN_MODEL_CPP%.cpp}"
ls -lh "$QNN_MODEL_BASE.cpp" "$QNN_MODEL_BASE.bin"
```

## 9. 生成 host CPU 可运行模型库

先在 host 上编译 `x86_64-linux-clang`，验证链路最方便：

```bash
python3 "$QNN_SDK_ROOT/bin/$QNN_HOST_ARCH/qnn-model-lib-generator" \
  -c "$QNN_MODEL_BASE.cpp" \
  -b "$QNN_MODEL_BASE.bin" \
  -t "$QNN_HOST_ARCH" \
  -l qnn_resnet50 \
  -o "$WORKDIR/qnn_artifacts/model_libs" \
  > "$WORKDIR/logs/model_lib_generator_host.log" 2>&1

tail -80 "$WORKDIR/logs/model_lib_generator_host.log"
find "$WORKDIR/qnn_artifacts/model_libs" -maxdepth 3 -name "*.so" -print
```

保存模型 `.so` 路径：

```bash
export HOST_MODEL_SO="$(find "$WORKDIR/qnn_artifacts/model_libs/$QNN_HOST_ARCH" -maxdepth 1 -name '*.so' | head -n 1)"
echo "$HOST_MODEL_SO"
```

## 10. 在 host 上运行 QNN CPU float

```bash
rm -rf "$WORKDIR/outputs/qnn_host_cpu"

"$QNN_SDK_ROOT/bin/$QNN_HOST_ARCH/qnn-net-run" \
  --model "$HOST_MODEL_SO" \
  --backend "$QNN_SDK_ROOT/lib/$QNN_HOST_ARCH/libQnnCpu.so" \
  --input_list "$WORKDIR/inputs/input_list.txt" \
  --output_dir "$WORKDIR/outputs/qnn_host_cpu" \
  --profiling_level basic \
  > "$WORKDIR/logs/qnn_net_run_host_cpu.log" 2>&1

tail -100 "$WORKDIR/logs/qnn_net_run_host_cpu.log"
find "$WORKDIR/outputs/qnn_host_cpu" -type f
```

如果这里失败，优先检查：

- `--model` 是否指向 `.so`。
- `--backend` 是否指向 `libQnnCpu.so`。
- `--input_list` 里是否是 `input_name:=raw_path`。
- raw 文件大小是否等于 `1*3*224*224*4 = 602112` bytes。

检查 raw 大小：

```bash
wc -c "$WORKDIR/inputs/input_0.raw"
```

## 11. 比较 ONNX Runtime 和 QNN host output

QNN output 文件名可能因模型输出 tensor 名不同而不同。下面脚本会自动找第一个 `.raw`：

如果你使用的是本仓库脚本，推荐直接运行：

```bash
python scripts/phase1/compare_qnn_with_baseline.py \
  --qnn-output "$WORKDIR/outputs/qnn_host_cpu" \
  --out "$WORKDIR/outputs/qnn_host_cpu_compare.json"
```

下面是无脚本版本，方便你在公司机器临时复制：

```bash
python3 - <<'PY'
import os
import glob
import numpy as np

workdir = os.environ["WORKDIR"]
baseline = np.load(os.path.join(workdir, "outputs", "onnxruntime", "output.npy")).reshape(-1).astype(np.float32)

raws = glob.glob(os.path.join(workdir, "outputs", "qnn_host_cpu", "**", "*.raw"), recursive=True)
if not raws:
    raise SystemExit("No QNN raw output found")

qnn_path = raws[0]
qnn = np.fromfile(qnn_path, dtype=np.float32).reshape(-1)

n = min(len(baseline), len(qnn))
baseline = baseline[:n]
qnn = qnn[:n]

diff = baseline - qnn
cos = float(np.dot(baseline, qnn) / (np.linalg.norm(baseline) * np.linalg.norm(qnn) + 1e-12))

print("QNN output:", qnn_path)
print("baseline len:", len(baseline), "qnn len:", len(qnn))
print("max_abs_error:", float(np.max(np.abs(diff))))
print("mean_abs_error:", float(np.mean(np.abs(diff))))
print("cosine_similarity:", cos)
print("baseline top5:", baseline.argsort()[-5:][::-1].tolist())
print("qnn top5:", qnn.argsort()[-5:][::-1].tolist())
PY
```

判断标准：

- 如果 top-5 基本一致，cosine similarity 接近 1，说明 float CPU 链路大概率正确。
- 如果差异很大，优先怀疑输入预处理或 layout。尤其检查 NCHW/NHWC、RGB/BGR、mean/std。

## 12. 编译 target 设备模型库

先查看 SDK 支持哪些 target：

```bash
ls "$QNN_SDK_ROOT/bin"
ls "$QNN_SDK_ROOT/lib"
```

常见情况：

- Android 设备：`aarch64-android`
- Linux aarch64 设备：可能是 `aarch64-oe-linux-gcc`、`aarch64-linux-gcc` 或公司定制目录

先手动设置一个。Android 示例：

```bash
export QNN_TARGET_ARCH=aarch64-android
```

Linux target 示例，请按实际目录改：

```bash
export QNN_TARGET_ARCH=aarch64-oe-linux-gcc
```

编译 target `.so`：

```bash
python3 "$QNN_SDK_ROOT/bin/$QNN_HOST_ARCH/qnn-model-lib-generator" \
  -c "$QNN_MODEL_BASE.cpp" \
  -b "$QNN_MODEL_BASE.bin" \
  -t "$QNN_TARGET_ARCH" \
  -l qnn_resnet50 \
  -o "$WORKDIR/qnn_artifacts/model_libs" \
  > "$WORKDIR/logs/model_lib_generator_target.log" 2>&1

tail -80 "$WORKDIR/logs/model_lib_generator_target.log"
find "$WORKDIR/qnn_artifacts/model_libs/$QNN_TARGET_ARCH" -maxdepth 1 -name "*.so" -print
```

保存 target 模型库路径：

```bash
export TARGET_MODEL_SO="$(find "$WORKDIR/qnn_artifacts/model_libs/$QNN_TARGET_ARCH" -maxdepth 1 -name '*.so' | head -n 1)"
echo "$TARGET_MODEL_SO"
```

## 13A. Android target：用 adb 跑 CPU backend

如果设备是 Android，用这段：

```bash
export DEVICE_DIR=/data/local/tmp/qnn_phase1_resnet

adb shell "mkdir -p $DEVICE_DIR"
adb push "$QNN_SDK_ROOT/bin/$QNN_TARGET_ARCH/qnn-net-run" "$DEVICE_DIR/"
adb push "$QNN_SDK_ROOT/lib/$QNN_TARGET_ARCH/libQnnCpu.so" "$DEVICE_DIR/"
adb push "$TARGET_MODEL_SO" "$DEVICE_DIR/"
adb push "$WORKDIR/inputs/input_0.raw" "$DEVICE_DIR/"
adb push "$WORKDIR/inputs/target_input_list.txt" "$DEVICE_DIR/input_list.txt"
```

执行：

```bash
adb shell "cd $DEVICE_DIR && chmod +x qnn-net-run && export LD_LIBRARY_PATH=$DEVICE_DIR:\$LD_LIBRARY_PATH && ./qnn-net-run \
  --model ./$(basename "$TARGET_MODEL_SO") \
  --backend ./libQnnCpu.so \
  --input_list ./input_list.txt \
  --output_dir ./output \
  --profiling_level basic" \
  > "$WORKDIR/logs/qnn_net_run_android_cpu.log" 2>&1

tail -100 "$WORKDIR/logs/qnn_net_run_android_cpu.log"
```

拉回结果：

```bash
rm -rf "$WORKDIR/outputs/qnn_android_cpu"
adb pull "$DEVICE_DIR/output" "$WORKDIR/outputs/qnn_android_cpu"
find "$WORKDIR/outputs/qnn_android_cpu" -type f
```

## 13B. Linux target：用 scp/ssh 跑 CPU backend

如果 target 是 Linux，用这段。先设置账号和 IP：

```bash
export TARGET_USER=your_user
export TARGET_IP=192.168.x.x
export DEVICE_DIR=/tmp/qnn_phase1_resnet
```

拷贝文件：

```bash
ssh "$TARGET_USER@$TARGET_IP" "mkdir -p $DEVICE_DIR"
scp "$QNN_SDK_ROOT/bin/$QNN_TARGET_ARCH/qnn-net-run" "$TARGET_USER@$TARGET_IP:$DEVICE_DIR/"
scp "$QNN_SDK_ROOT/lib/$QNN_TARGET_ARCH/libQnnCpu.so" "$TARGET_USER@$TARGET_IP:$DEVICE_DIR/"
scp "$TARGET_MODEL_SO" "$TARGET_USER@$TARGET_IP:$DEVICE_DIR/"
scp "$WORKDIR/inputs/input_0.raw" "$TARGET_USER@$TARGET_IP:$DEVICE_DIR/"
scp "$WORKDIR/inputs/target_input_list.txt" "$TARGET_USER@$TARGET_IP:$DEVICE_DIR/input_list.txt"
```

执行：

```bash
ssh "$TARGET_USER@$TARGET_IP" "cd $DEVICE_DIR && chmod +x qnn-net-run && export LD_LIBRARY_PATH=$DEVICE_DIR:\$LD_LIBRARY_PATH && ./qnn-net-run \
  --model ./$(basename "$TARGET_MODEL_SO") \
  --backend ./libQnnCpu.so \
  --input_list ./input_list.txt \
  --output_dir ./output \
  --profiling_level basic" \
  > "$WORKDIR/logs/qnn_net_run_linux_target_cpu.log" 2>&1

tail -100 "$WORKDIR/logs/qnn_net_run_linux_target_cpu.log"
```

拉回结果：

```bash
rm -rf "$WORKDIR/outputs/qnn_linux_target_cpu"
mkdir -p "$WORKDIR/outputs/qnn_linux_target_cpu"
scp -r "$TARGET_USER@$TARGET_IP:$DEVICE_DIR/output" "$WORKDIR/outputs/qnn_linux_target_cpu/"
find "$WORKDIR/outputs/qnn_linux_target_cpu" -type f
```

## 14. target output 与 baseline 对比

Android：

```bash
export QNN_TARGET_OUTPUT_DIR="$WORKDIR/outputs/qnn_android_cpu"
```

Linux：

```bash
export QNN_TARGET_OUTPUT_DIR="$WORKDIR/outputs/qnn_linux_target_cpu"
```

比较：

```bash
python3 - <<'PY'
import os
import glob
import numpy as np

workdir = os.environ["WORKDIR"]
target_dir = os.environ["QNN_TARGET_OUTPUT_DIR"]
baseline = np.load(os.path.join(workdir, "outputs", "onnxruntime", "output.npy")).reshape(-1).astype(np.float32)

raws = glob.glob(os.path.join(target_dir, "**", "*.raw"), recursive=True)
if not raws:
    raise SystemExit("No target QNN raw output found")

qnn_path = raws[0]
qnn = np.fromfile(qnn_path, dtype=np.float32).reshape(-1)
n = min(len(baseline), len(qnn))
baseline = baseline[:n]
qnn = qnn[:n]
diff = baseline - qnn
cos = float(np.dot(baseline, qnn) / (np.linalg.norm(baseline) * np.linalg.norm(qnn) + 1e-12))

print("target output:", qnn_path)
print("max_abs_error:", float(np.max(np.abs(diff))))
print("mean_abs_error:", float(np.mean(np.abs(diff))))
print("cosine_similarity:", cos)
print("baseline top5:", baseline.argsort()[-5:][::-1].tolist())
print("target qnn top5:", qnn.argsort()[-5:][::-1].tolist())
PY
```

## 15. 可选：INT8 量化转换

只有在 CPU float 已经稳定后再做这一节。

准备 calibration input list。这里先用同一张图演示，正式做时应使用多张代表性图片：

```bash
cp "$WORKDIR/inputs/input_list.txt" "$WORKDIR/inputs/calib_input_list.txt"
```

量化转换：

```bash
export QNN_QUANT_CPP="$WORKDIR/qnn_artifacts/resnet50_qnn_int8_model.cpp"

"$QNN_SDK_ROOT/bin/$QNN_HOST_ARCH/qnn-onnx-converter" \
  --input_network "$MODEL_PATH" \
  --input_list "$WORKDIR/inputs/calib_input_list.txt" \
  -d "$INPUT_NAME" "$INPUT_DIMS" \
  --preserve_io layout \
  --weights_bitwidth 8 \
  --act_bitwidth 8 \
  --output_path "$QNN_QUANT_CPP" \
  > "$WORKDIR/logs/qnn_converter_int8.log" 2>&1

tail -100 "$WORKDIR/logs/qnn_converter_int8.log"
ls -lh "$WORKDIR/qnn_artifacts"
```

编译量化模型：

```bash
export QNN_QUANT_BASE="${QNN_QUANT_CPP%.cpp}"

python3 "$QNN_SDK_ROOT/bin/$QNN_HOST_ARCH/qnn-model-lib-generator" \
  -c "$QNN_QUANT_BASE.cpp" \
  -b "$QNN_QUANT_BASE.bin" \
  -t "$QNN_HOST_ARCH" \
  -l qnn_resnet50_int8 \
  -o "$WORKDIR/qnn_artifacts/model_libs_int8" \
  > "$WORKDIR/logs/model_lib_generator_int8_host.log" 2>&1

tail -80 "$WORKDIR/logs/model_lib_generator_int8_host.log"
find "$WORKDIR/qnn_artifacts/model_libs_int8" -maxdepth 3 -name "*.so" -print
```

先用 CPU backend 跑量化模型。如果 output 默认是 float，后处理脚本可以继续按 float32 读：

```bash
export HOST_INT8_MODEL_SO="$(find "$WORKDIR/qnn_artifacts/model_libs_int8/$QNN_HOST_ARCH" -maxdepth 1 -name '*.so' | head -n 1)"
rm -rf "$WORKDIR/outputs/qnn_host_cpu_int8"

"$QNN_SDK_ROOT/bin/$QNN_HOST_ARCH/qnn-net-run" \
  --model "$HOST_INT8_MODEL_SO" \
  --backend "$QNN_SDK_ROOT/lib/$QNN_HOST_ARCH/libQnnCpu.so" \
  --input_list "$WORKDIR/inputs/input_list.txt" \
  --output_dir "$WORKDIR/outputs/qnn_host_cpu_int8" \
  --profiling_level basic \
  > "$WORKDIR/logs/qnn_net_run_host_cpu_int8.log" 2>&1

tail -100 "$WORKDIR/logs/qnn_net_run_host_cpu_int8.log"
```

## 16. 常见错误速查

### 16.1 找不到 `qnn-onnx-converter`

重新找 SDK：

```bash
find /opt "$HOME" /local/mnt/workspace -maxdepth 6 -type f -name qnn-onnx-converter 2>/dev/null | head -20
```

### 16.2 `No such file or directory: libQnnCpu.so`

检查 target arch 是否设置错：

```bash
echo "$QNN_TARGET_ARCH"
find "$QNN_SDK_ROOT/lib" -name libQnnCpu.so -print
```

### 16.3 `qnn-net-run` 输入报错

检查 input list 格式。单输入模型应类似：

```text
data:=/home/you/qnn_phase1_resnet/inputs/input_0.raw
```

target 设备上应类似：

```text
data:=input_0.raw
```

### 16.4 QNN 输出和 ONNX Runtime 差很多

按这个顺序查：

1. input name 是否正确。
2. raw shape 是否是 `1,3,224,224`。
3. 是否误用了 NHWC。
4. 图片是否 RGB 而不是 BGR。
5. mean/std 是否和模型训练预处理一致。
6. converter 是否改了 layout。必要时保留 `--preserve_io layout`。

### 16.5 HTP/DSP 跑不起来

Phase 1 不要急着查 HTP。先确认：

- CPU float 成功。
- INT8 量化模型成功。
- target 上存在 HTP backend 相关 `.so`。
- mentor 确认这块芯片/系统镜像允许使用 HTP/DSP runtime。

## 17. 你每天要保存的日志

建议每天结束执行：

```bash
cd "$WORKDIR"
tar -czf "qnn_phase1_logs_$(date +%Y%m%d_%H%M%S).tar.gz" logs outputs
ls -lh *.tar.gz
```

另外写一个 `phase1_error_report.md`，至少记录：

- SDK 路径和版本。
- host arch / target arch。
- 模型名称、输入输出 shape。
- ONNX Runtime top5。
- QNN host CPU top5。
- QNN target CPU top5。
- max abs error / mean abs error / cosine similarity。
- 当前 blocker。

## 18. 本手册依据

- Qualcomm QNN/QAIRT 文档入口：<https://docs.qualcomm.com/doc/80-63442-10/topic/index_QNN.html>
- QNN ONNX converter、model lib generator、qnn-net-run：Qualcomm QNN General Tools 文档。
- ONNX -> QNN 教程：Qualcomm ONNX to QNN Tutorial。
- CPU backend 运行方式：Qualcomm QNN CPU backend 教程。
- ResNet ONNX 示例：ONNX Model Zoo。
- 测试图片示例：PyTorch Hub 示例图片。
