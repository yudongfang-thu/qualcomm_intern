# QNN 推理后端和运行方式速查

> 目的：回答“QNN 推理到底可以跑在 CPU、DSP 还是哪里？它们区别是什么？”

## 1. QNN 的核心概念：Backend

QNN/AI Engine Direct 通过 backend 和不同硬件交互。backend 通常是一个 shared library，例如：

```text
libQnnCpu.so
libQnnGpu.so
libQnnHtp.so
libQnnDsp.so
libQnnSaver.so
```

`qnn-net-run` 推理时，本质上就是：

```bash
qnn-net-run \
  --model ./libqnn_model.so \
  --backend ./libQnnCpu.so \
  --input_list ./input_list.txt \
  --output_dir ./output
```

你换 backend，就换 `--backend` 指向的 `.so`。

## 2. 手册列出的主要 backend

| Backend | 典型库 | 对应硬件/用途 | 是否真执行推理 | 对你当前任务的重要性 |
|---|---|---|---|---|
| CPU | `libQnnCpu.so` | Snapdragon CPU core | 是 | 第一优先，用来跑通 float baseline |
| GPU | `libQnnGpu.so` | Adreno GPU | 是 | 第二梯队，可做 float/FP16 性能尝试 |
| HTP | `libQnnHtp.so` + `libQnnHtpV##Stub.so` + `libQnnHtpV##Skel.so` | Hexagon Tensor Processor / NPU 类加速器 | 是 | 端侧高性能重点，后续部署重点 |
| DSP | `libQnnDsp.so` + `libQnnDspV##Stub.so` + `libQnnDspV##Skel.so` | Hexagon DSP | 是 | 老链路/特定平台可能用，但现在优先级通常低于 HTP |
| HTA | `libQnnHta.so` | Snapdragon HTA accelerator | 是 | 老/特定平台，先不用 |
| LPAI | `libQnnLpai.so` | Low Power AI engine | 是 | 低功耗/always-on 场景，VLA 暂不优先 |
| Saver | `libQnnSaver.so` | 记录 QNN API 调用 | 否 | 调试用，不产生真实推理结果 |

## 3. CPU backend

CPU backend 是最适合 Phase 1 的后端。

特点：

- 支持 float32 和 int8。
- host x86 和 target 设备都容易跑。
- 依赖最少，最适合验证模型转换、输入 raw、input_list、输出对比。
- 性能通常不是最好，但调试最稳。

典型命令：

```bash
qnn-net-run \
  --model ./libqnn_resnet50.so \
  --backend ./libQnnCpu.so \
  --input_list ./input_list.txt \
  --output_dir ./output
```

建议：

- Phase 1 第一目标永远先跑 CPU float。
- CPU float 正确后，再考虑 GPU/HTP。

## 4. GPU backend

GPU backend 对应 Adreno GPU。

特点：

- 适合部分视觉模型的加速。
- 支持不同 precision mode，例如 FP32、FP16、Hybrid。
- FP32 准确性最好但慢；FP16 更快但误差更大；Hybrid 是中间折中。
- Android target 上更常见；host x86 一般不是主要执行目标。

典型命令：

```bash
qnn-net-run \
  --model ./libqnn_model_float.so \
  --backend ./libQnnGpu.so \
  --input_list ./input_list.txt \
  --output_dir ./output
```

建议：

- 对 ResNet 这类视觉模型可以作为第二个实验。
- 如果 mentor 要求“浮点部署”，GPU backend 可能比 HTP 更自然，因为 HTP 的 float 支持受 SoC/SDK 限制。

## 5. HTP backend

HTP 是当前 Qualcomm AI 加速最重要的方向之一，可以粗略理解成 Hexagon NPU / tensor accelerator 相关后端。

特点：

- 高性能、低功耗，是端侧模型部署重点。
- 支持 quantized 8-bit 和 quantized 16-bit 网络。
- 部分 SoC/SDK 支持 HTP float：通常是 float32 网络使用 float16 math，具体要看平台支持。
- Android 设备上常见库组合包括：

```text
libQnnHtp.so
libQnnHtpPrepare.so
libQnnHtpV##Stub.so
libQnnHtpV##Skel.so
```

其中：

- `libQnnHtp.so`：CPU 侧 backend 入口。
- `libQnnHtpV##Stub.so`：CPU 侧代理，通过 RPC 和 HTP 侧通信。
- `libQnnHtpV##Skel.so`：HTP/Hexagon 侧真正执行相关逻辑。
- `libQnnHtpPrepare.so`：图构建、finalize、op package 注册等准备阶段可能需要。

典型命令，直接用 model `.so`：

```bash
qnn-net-run \
  --model ./libqnn_model_int8.so \
  --backend ./libQnnHtp.so \
  --input_list ./input_list.txt \
  --output_dir ./output
```

更常见的高性能方式是先生成 context binary，再执行：

```bash
qnn-context-binary-generator \
  --model ./libqnn_model_int8.so \
  --backend ./libQnnHtp.so \
  --binary_file ./model_htp_context.bin
```

然后：

```bash
qnn-net-run \
  --retrieve_context ./model_htp_context.bin \
  --backend ./libQnnHtp.so \
  --input_list ./input_list.txt \
  --output_dir ./output
```

建议：

- 不要一上来做 HTP。
- 先 CPU float 正确，再做 INT8，再尝试 HTP。
- HTP/DSP 在 QNN ONNX 教程里明确提醒：通常需要量化模型，并通过 `--input_list` 做量化校准。

## 6. DSP backend

DSP backend 对应 Hexagon DSP。

特点：

- 也属于 Hexagon 侧加速。
- 需要 stub/skel 这类 CPU 侧代理和 DSP 侧库。
- 可通过性能基础设施设置 voltage corner、DCVS、线程数等。
- 和 HTP 相比，你现在的 VLA/VLM 部署优先级通常没那么高，除非 mentor 明确说目标芯片主要走 DSP backend。

典型库：

```text
libQnnDsp.so
libQnnDspV##Stub.so
libQnnDspV##Skel.so
```

建议：

- 知道它存在即可。
- 只有当目标平台没有 HTP、或 mentor/平台文档明确要求 DSP 时再深入。

## 7. Saver backend

Saver 是特殊 backend。

特点：

- 不执行真实推理。
- 记录 QNN API 调用和 tensor 参数。
- 输出类似 `saver_output.c` 和 `params.bin`。
- 后续可以 replay 到真实 backend 上，用于支持和排错。

用途：

- 怀疑 QNN API 调用顺序不对。
- 需要把问题复现给 Qualcomm support。
- 需要比较“同一套 QNN API 调用在不同 backend 上是否失败”。

不要用 Saver 来做性能或正确性评估，因为它不是真正执行图。

## 8. 两种常见运行形态

### 8.1 直接加载模型 `.so`

这是最直观的方式：

```bash
qnn-net-run \
  --model ./libqnn_model.so \
  --backend ./libQnnCpu.so \
  --input_list ./input_list.txt \
  --output_dir ./output
```

适合：

- Phase 1。
- 调试转换流程。
- 快速验证输出。

### 8.2 加载 context binary

先把图准备好，保存为 binary，再执行：

```bash
qnn-net-run \
  --retrieve_context ./model_context.bin \
  --backend ./libQnnHtp.so \
  --input_list ./input_list.txt \
  --output_dir ./output
```

适合：

- HTP/LPAI 等需要减少初始化开销的场景。
- 部署时希望启动更快。
- 固定模型、固定平台、反复执行。

注意：

- context binary 通常和 backend、SoC/arch、SDK 版本强相关。
- 换芯片、换 HTP arch、换 SDK 版本后要重新生成。

## 9. 对当前 pi0/VLA 项目的建议顺序

建议不要平行探索所有 backend，而是按风险递增：

1. CPU backend + float model：验证转换、输入输出、baseline 对比。
2. CPU backend + int8 model：验证量化误差。
3. GPU backend + float/FP16：如果目标是浮点部署，可以尝试。
4. HTP backend + int8/context binary：端侧高性能重点。
5. HTP float：只有确认目标 SoC/SDK 支持后再做。
6. DSP/HTA/LPAI：除非 mentor 或平台说明要求，否则先放后面。
7. Saver：遇到难定位的 QNN API/backend 问题时使用。

一句话版：

```text
调试正确性：CPU
浮点加速尝试：GPU
端侧高性能重点：HTP
旧/特定 Hexagon 链路：DSP
低功耗 always-on：LPAI
调试记录：Saver
```

## 10. 与我们的 Phase 1 手册怎么衔接

Phase 1 使用 CPU backend 是故意的：

- CPU 支持 FP32。
- 命令最简单。
- 输出最容易和 ONNX Runtime baseline 对齐。
- 可以先把 layout、raw、input_list、top-k 全部确认。

当 CPU float 成功后，下一步不是马上上机械臂，而是：

1. 做 CPU int8 量化误差。
2. 再把同一个模型迁移到 GPU 或 HTP。
3. 比较 backend 之间的输出差异和 latency。

## 11. 参考

- Qualcomm QNN Backend 文档：<https://docs.qualcomm.com/doc/80-63442-10/topic/index_QNN.html>
- Qualcomm QNN CPU/GPU/HTP/DSP/LPAI/Saver backend 文档。
- Qualcomm QNN `qnn-net-run` 工具文档。
