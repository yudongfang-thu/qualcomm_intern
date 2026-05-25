# QNN/QAIRT 开发环境配置照抄手册

> 目标：把上机第一天的环境配置步骤写成可以逐条复制的命令。  
> 范围：Linux host 为主，覆盖 ONNX 转换、CPU backend、Android/Linux target、后续 HTP/DSP 准备。

## 0. 先分清 host 和 target

QNN 文档里有两个概念：

- host machine：你开发、转换模型、编译模型库的机器，通常是 Ubuntu/x86 Linux。
- target device：真正跑推理的 Qualcomm 设备，可能是 Android、Ubuntu、OpenEmbedded Linux、QNX 等。

Phase 1 推荐：

```text
host: Linux x86_64
target first try: host itself with CPU backend
target second try: Qualcomm device with CPU backend
```

不要一开始就配置 HTP/DSP 的完整 Hexagon 工具链。先把 CPU backend 跑通。

## 1. 找到 SDK 目录

QNN/QAIRT SDK 解压后常见结构类似：

```text
qairt/
  2.xx.x.xxxxxx/
    bin/
    lib/
    include/
    examples/
```

先用 find 找：

```bash
find /opt "$HOME" /local/mnt/workspace -maxdepth 7 -type f -name envsetup.sh 2>/dev/null | head -20
```

如果看到：

```text
/some/path/qairt/2.xx.x.xxxxxx/bin/envsetup.sh
```

那么 SDK root 应该是：

```text
/some/path/qairt/2.xx.x.xxxxxx
```

设置：

```bash
export QAIRT_SDK_ROOT=/some/path/qairt/2.xx.x.xxxxxx
export QNN_SDK_ROOT="$QAIRT_SDK_ROOT"
```

说明：

- 新文档里更推荐 `QAIRT_SDK_ROOT`。
- `QNN_SDK_ROOT` 仍然会为了兼容旧教程和旧脚本被设置。
- 我们的脚本和手册继续使用 `QNN_SDK_ROOT`，因为 QNN 文档、示例、网上资料里这个变量更常见。

## 2. 用官方 envsetup.sh 设置环境

推荐使用官方脚本：

```bash
cd "$QAIRT_SDK_ROOT/bin"
source ./envsetup.sh
```

验证：

```bash
echo "QAIRT_SDK_ROOT=$QAIRT_SDK_ROOT"
echo "QNN_SDK_ROOT=$QNN_SDK_ROOT"
```

如果没有输出，手动设置：

```bash
export QAIRT_SDK_ROOT=/some/path/qairt/2.xx.x.xxxxxx
export QNN_SDK_ROOT="$QAIRT_SDK_ROOT"
export QNN_HOST_ARCH=x86_64-linux-clang
export PATH="$QNN_SDK_ROOT/bin/$QNN_HOST_ARCH:$QNN_SDK_ROOT/bin:$PATH"
export LD_LIBRARY_PATH="$QNN_SDK_ROOT/lib/$QNN_HOST_ARCH:${LD_LIBRARY_PATH:-}"
```

注意：`source ./envsetup.sh` 只对当前 terminal 生效。重新开 terminal 后需要重新 source。

## 3. 检查 SDK 文件结构

```bash
export QNN_HOST_ARCH=x86_64-linux-clang

ls "$QNN_SDK_ROOT/bin"
ls "$QNN_SDK_ROOT/bin/$QNN_HOST_ARCH"
ls "$QNN_SDK_ROOT/lib/$QNN_HOST_ARCH"
```

关键工具应该能找到：

```bash
ls "$QNN_SDK_ROOT/bin/$QNN_HOST_ARCH/qnn-onnx-converter"
ls "$QNN_SDK_ROOT/bin/$QNN_HOST_ARCH/qnn-net-run"
ls "$QNN_SDK_ROOT/bin/$QNN_HOST_ARCH/qnn-context-binary-generator" || true
ls "$QNN_SDK_ROOT/bin/$QNN_HOST_ARCH/qnn-profile-viewer" || true
ls "$QNN_SDK_ROOT/bin/$QNN_HOST_ARCH/qnn-model-lib-generator"
```

关键库应该能找到：

```bash
ls "$QNN_SDK_ROOT/lib/$QNN_HOST_ARCH/libQnnCpu.so"
ls "$QNN_SDK_ROOT/lib/$QNN_HOST_ARCH/libQnnHtp.so" || true
ls "$QNN_SDK_ROOT/lib/$QNN_HOST_ARCH/libQnnSaver.so" || true
```

## 4. 安装 Linux 系统依赖

QNN 文档建议使用 Ubuntu 22.04，且 Ubuntu 20.04 已经不是推荐支持版本。

先安装基础工具：

```bash
sudo apt-get update
sudo apt-get install -y build-essential make cmake wget unzip git openssh-client
```

安装 Python 3.10：

```bash
sudo apt-get install -y python3.10 python3.10-venv python3-distutils libpython3.10
```

安装/检查 clang：

```bash
sudo apt-get install -y clang-14
clang++-14 --version
```

如果有官方检查脚本，跑：

```bash
sudo bash "$QNN_SDK_ROOT/bin/check-linux-dependency.sh"
```

官方脚本可能会要求你按 Enter 确认安装。完成后通常会显示类似 `Done!!`。

检查 clang/toolchain：

```bash
"$QNN_SDK_ROOT/bin/envcheck" -c
```

## 5. 配 Python 虚拟环境

QNN 文档推荐 Python 3.10。建议不要污染系统 Python。

```bash
export QNN_WORKSPACE="$HOME/qnn_workspace"
mkdir -p "$QNN_WORKSPACE"
cd "$QNN_WORKSPACE"

python3.10 -m venv qnn_py310 --without-pip
source qnn_py310/bin/activate
python3 -m ensurepip --upgrade
python3 -m pip install --upgrade pip
```

确认 pip 在 venv 里：

```bash
which python
which pip3
python --version
```

运行 QNN Python 依赖检查：

```bash
python "$QNN_SDK_ROOT/bin/check-python-dependency"
```

如果你只做 ONNX/ResNet Phase 1，额外安装：

```bash
pip install numpy pillow onnx onnxruntime onnxsim pandas
```

如果公司网络慢，可以临时用清华源：

```bash
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple numpy pillow onnx onnxruntime onnxsim pandas
```

检查 ONNX 环境：

```bash
python - <<'PY'
import numpy
import onnx
import onnxruntime
print("numpy", numpy.__version__)
print("onnx", onnx.__version__)
print("onnxruntime", onnxruntime.__version__)
PY
```

可选检查全部框架依赖：

```bash
"$QNN_SDK_ROOT/bin/envcheck" -a
```

## 6. Android target 环境

如果 target 是 Android，通常需要：

- `adb`
- Android NDK r26c
- QNN target arch：`aarch64-android`

安装 adb：

```bash
sudo apt-get install -y android-tools-adb
adb version
adb devices
```

安装 Android NDK r26c：

```bash
cd "$HOME"
wget https://dl.google.com/android/repository/android-ndk-r26c-linux.zip
unzip android-ndk-r26c-linux.zip
export ANDROID_NDK_ROOT="$HOME/android-ndk-r26c"
export PATH="$ANDROID_NDK_ROOT:$PATH"
```

建议写入 `~/.bashrc`：

```bash
echo 'export ANDROID_NDK_ROOT="$HOME/android-ndk-r26c"' >> ~/.bashrc
echo 'export PATH="$ANDROID_NDK_ROOT:$PATH"' >> ~/.bashrc
```

检查 NDK：

```bash
"$QNN_SDK_ROOT/bin/envcheck" -n
```

设置 target arch：

```bash
export QNN_TARGET_ARCH=aarch64-android
```

检查 Android 侧 QNN 文件：

```bash
ls "$QNN_SDK_ROOT/bin/$QNN_TARGET_ARCH/qnn-net-run"
ls "$QNN_SDK_ROOT/lib/$QNN_TARGET_ARCH/libQnnCpu.so"
ls "$QNN_SDK_ROOT/lib/$QNN_TARGET_ARCH/libQnnGpu.so" || true
ls "$QNN_SDK_ROOT/lib/$QNN_TARGET_ARCH/libQnnHtp.so" || true
```

## 7. Linux target 环境

如果 target 是 Linux 设备，先在 target 上执行：

```bash
uname -a
cat /etc/os-release
gcc --version || true
whoami
ifconfig || ip addr
```

根据系统选择 `QNN_TARGET_ARCH`。QNN 教程列出的常见值：

| Target | QNN_TARGET_ARCH |
|---|---|
| host x86 Linux | `x86_64-linux-clang` |
| Android 64-bit | `aarch64-android` |
| Ubuntu aarch64 GCC 9.4 | `aarch64-ubuntu-gcc9.4` |
| Ubuntu aarch64 GCC 7.5 | `aarch64-ubuntu-gcc7.5` |
| OpenEmbedded GCC 11.2 | `aarch64-oe-linux-gcc11.2` |
| OpenEmbedded GCC 9.3 | `aarch64-oe-linux-gcc9.3` |
| OpenEmbedded GCC 8.2 | `aarch64-oe-linux-gcc8.2` |

例如：

```bash
export QNN_TARGET_ARCH=aarch64-oe-linux-gcc11.2
```

检查 SDK 里是否真的有这个目录：

```bash
ls "$QNN_SDK_ROOT/bin/$QNN_TARGET_ARCH"
ls "$QNN_SDK_ROOT/lib/$QNN_TARGET_ARCH"
```

配置 SSH：

```bash
export TARGET_USER=your_user
export TARGET_IP=192.168.x.x
ssh "$TARGET_USER@$TARGET_IP" "uname -a && whoami"
```

如果 target 是 Ubuntu 并且没有 ssh server：

```bash
sudo apt update
sudo apt install -y openssh-server
sudo systemctl start ssh
sudo systemctl enable ssh
```

## 8. HTP/DSP 后续环境

Phase 1 不建议先做这个，但你要知道它需要什么。

HTP/DSP 通常需要：

- Qualcomm Hexagon SDK
- Hexagon Tools
- clang++
- 正确的 Hexagon architecture，例如 V68/V69/V73/V75/V79/V81

环境变量通常类似：

```bash
export HEXAGON_SDK_ROOT=/path/to/Hexagon_SDK
export PATH="$HEXAGON_SDK_ROOT/tools/HEXAGON_Tools/Tools/bin:$PATH"
```

然后按照：

```bash
$HEXAGON_SDK_ROOT/docs/readme.html
```

里的说明完成安装检查。

注意：

- 不同 SoC 对应不同 Hexagon architecture。
- QNN 文档里 HTP/DSP 的 SDK/Tools 版本有对应表。
- Hexagon SDK Tools 有时不会自动包含在 Hexagon SDK 里，需要单独下载并放到 `$HEXAGON_SDK_ROOT/tools/HEXAGON_Tools/`。

## 9. 建议创建一个固定工作目录

不要在 SDK 目录里乱生成文件。建议：

```bash
export QNN_WORKSPACE="$HOME/qnn_workspace"
export QNN_PHASE1="$QNN_WORKSPACE/phase1_resnet"
mkdir -p "$QNN_PHASE1"/{models,images,inputs,outputs,qnn_artifacts,logs,scripts}
```

如果使用本仓库：

```bash
git clone https://github.com/yudongfang-thu/qualcomm_intern.git
cd qualcomm_intern
```

建议所有大文件放到：

```bash
artifacts/
```

这个目录已经在 `.gitignore` 里，不会被提交到 GitHub。

## 10. 一键环境检查脚本

复制下面整段，在 terminal 里跑：

```bash
set -e

echo "[1] SDK variables"
echo "QAIRT_SDK_ROOT=${QAIRT_SDK_ROOT:-}"
echo "QNN_SDK_ROOT=${QNN_SDK_ROOT:-}"

echo "[2] host arch"
export QNN_HOST_ARCH=${QNN_HOST_ARCH:-x86_64-linux-clang}
echo "QNN_HOST_ARCH=$QNN_HOST_ARCH"

echo "[3] tools"
ls "$QNN_SDK_ROOT/bin/$QNN_HOST_ARCH/qnn-onnx-converter"
ls "$QNN_SDK_ROOT/bin/$QNN_HOST_ARCH/qnn-model-lib-generator"
ls "$QNN_SDK_ROOT/bin/$QNN_HOST_ARCH/qnn-net-run"

echo "[4] libraries"
ls "$QNN_SDK_ROOT/lib/$QNN_HOST_ARCH/libQnnCpu.so"

echo "[5] python"
python --version
python - <<'PY'
import numpy, onnx, onnxruntime
print("numpy", numpy.__version__)
print("onnx", onnx.__version__)
print("onnxruntime", onnxruntime.__version__)
PY

echo "[6] qnn help"
"$QNN_SDK_ROOT/bin/$QNN_HOST_ARCH/qnn-onnx-converter" --help >/tmp/qnn_onnx_converter_help.txt
python "$QNN_SDK_ROOT/bin/$QNN_HOST_ARCH/qnn-model-lib-generator" -h >/tmp/qnn_model_lib_generator_help.txt
"$QNN_SDK_ROOT/bin/$QNN_HOST_ARCH/qnn-net-run" --help >/tmp/qnn_net_run_help.txt

echo "[PASS] basic QNN development environment is ready"
```

## 11. Phase 1 最小环境路径总结

最少需要确认这些路径：

```bash
echo "$QNN_SDK_ROOT"
echo "$QNN_SDK_ROOT/bin/x86_64-linux-clang/qnn-onnx-converter"
echo "$QNN_SDK_ROOT/bin/x86_64-linux-clang/qnn-model-lib-generator"
echo "$QNN_SDK_ROOT/bin/x86_64-linux-clang/qnn-net-run"
echo "$QNN_SDK_ROOT/lib/x86_64-linux-clang/libQnnCpu.so"
```

如果 target 是 Android，还要：

```bash
echo "$ANDROID_NDK_ROOT"
echo "$QNN_SDK_ROOT/bin/aarch64-android/qnn-net-run"
echo "$QNN_SDK_ROOT/lib/aarch64-android/libQnnCpu.so"
```

如果 target 是 Linux，还要：

```bash
echo "$QNN_TARGET_ARCH"
echo "$QNN_SDK_ROOT/bin/$QNN_TARGET_ARCH/qnn-net-run"
echo "$QNN_SDK_ROOT/lib/$QNN_TARGET_ARCH/libQnnCpu.so"
```

## 12. 常见问题

### 12.1 `QNN_SDK_ROOT` 为空

重新执行：

```bash
cd /some/path/qairt/2.xx.x.xxxxxx/bin
source ./envsetup.sh
echo "$QNN_SDK_ROOT"
```

### 12.2 `qnn-onnx-converter` 找不到

```bash
find "$QNN_SDK_ROOT" -name qnn-onnx-converter -type f
```

### 12.3 `qnn-model-lib-generator` 编译失败

优先检查：

```bash
"$QNN_SDK_ROOT/bin/envcheck" -c
clang++-14 --version
cmake --version
```

如果编译 Android target，还要检查：

```bash
"$QNN_SDK_ROOT/bin/envcheck" -n
echo "$ANDROID_NDK_ROOT"
```

### 12.4 Python 包版本冲突

重新建 venv，避免污染：

```bash
deactivate || true
rm -rf "$QNN_WORKSPACE/qnn_py310"
python3.10 -m venv "$QNN_WORKSPACE/qnn_py310" --without-pip
source "$QNN_WORKSPACE/qnn_py310/bin/activate"
python3 -m ensurepip --upgrade
python3 -m pip install --upgrade pip
python "$QNN_SDK_ROOT/bin/check-python-dependency"
pip install numpy pillow onnx onnxruntime onnxsim pandas
```

## 13. 参考

- Qualcomm QNN/QAIRT Setup 文档。
- Qualcomm QNN Linux Setup 文档。
- Qualcomm ONNX to QNN tutorial。
- Qualcomm Linux host to Linux/Android/QNX target tutorial。
