# Qualcomm QNN / QAIRT SDK 学习笔记

> 学习对象：Qualcomm 官方文档 `80-63442-10` 中 `index_QNN.html` 对应的 QNN 子树。  
> 扫描时间：2026-05-25。  
> 官方页面最后发布时间：2026-05-06。  
> 文档导航版本：`AJ`，标题为 `Qualcomm AI Runtime (QAIRT) SDK`。  
> 本地扫描范围：QNN 子树 126 个目录节点，去重后 111 个 HTML topic。

官方入口：<https://docs.qualcomm.com/doc/80-63442-10/topic/index_QNN.html>

## 0. 我对这份文档的总理解

QNN 现在在文档里更多被放在 **Qualcomm AI Runtime，简称 QAIRT** 的大框架下理解。它不是一个训练框架，也不是一个单纯的模型格式转换器，而是一套面向 Qualcomm 芯片上 AI 推理部署的 SDK：它把 TensorFlow、TFLite、PyTorch、ONNX 等来源的模型转换成 QNN 可表达的 graph，再通过统一 C API 调用不同硬件 backend，例如 CPU、GPU、DSP、HTP、HTA、LPAI。

我作为学习者读下来，应该先抓住这条主线：

```text
训练框架模型
  -> converter / qairt-converter
  -> QNN graph 表达，model.cpp / model.bin / model_net.json
  -> 可选 quantization
  -> model library 或 context binary
  -> backend library 运行在目标设备
  -> qnn-net-run / sample app / 自己的 C/C++ app
  -> profiling / benchmark / debugger
```

QNN 的核心价值是：**用统一 API 屏蔽不同 Qualcomm IP core 的差异，同时仍然允许 backend-specific 配置和极细粒度性能调优**。也就是说，它既像硬件抽象层，又没有把所有硬件细节藏起来。真正做性能、功耗、内存占用和 custom op 时，仍然要懂 backend。

## 1. 文档结构地图

这份 QNN 子树可以按学习顺序重排为下面几大块。

| 块 | 原文入口 | 我理解的作用 |
|---|---|---|
| 入门与总览 | Introduction, Overview | 知道 QNN/QAIRT 是什么，处在 AI software stack 哪一层 |
| 安装与环境 | Setup, Linux Setup, Windows Setup | 配 host、target、Python、toolchain、SDK 路径 |
| Backend | CPU, GPU, DSP, HTP, HTA, LPAI, Saver | 理解模型最后跑在哪个硬件上，以及各 backend 的限制 |
| Converter | Converters, qairt-converter | 把训练框架模型变成 QNN 表达 |
| Quantization | Quantization, QAIRT Quantization Specification | 决定模型数值精度、encoding、override、mixed precision |
| Tools | general_tools | 查每个命令行工具做什么、在哪个平台支持 |
| Tutorials | conversion tutorial, sample app, saver, shared buffer | 按端到端步骤跑通模型 |
| Benchmarking | qnn_bench.py | 做性能测试、profiling、结果解读 |
| Operations | SupportedOps, OpDef supplement | 查不同 backend 支持哪些 op、数据类型、限制 |
| Op Packages | op package 生成、schema、自定义 op | 当内置 op 不够时扩展 backend 能力 |
| API | API overview, usage guidelines, supported APIs, error codes | 面向真正集成 QNN 的 C API 调用模型 |
| Revision History / Glossary | revision, glossary | 查版本变化和术语 |

一个很重要的阅读策略：**先不要扎进 API reference**。先跑通 converter + qnn-net-run，再回头看 QnnBackend/QnnContext/QnnGraph/QnnTensor 这些 API，会更容易理解。

## 2. 核心概念速记

### QNN / QAIRT

文档中的 QNN SDK 是 Qualcomm AI Engine Direct SDK 的一部分，目标是让模型能在 Qualcomm 芯片的多个 AI 相关 IP core 上运行。它不是负责训练的，而是偏部署、推理、backend 适配和性能分析。

### Host 和 Target

文档反复区分：

- **Host machine**：开发机，用来准备模型、转换模型、编译 sample app 或生成 context binary。
- **Target device**：真正执行推理的设备，里面有 CPU/GPU/DSP/HTP/LPAI 等 IP core。

Windows on Snapdragon 场景下，同一台机器可能既是 host 又是 target。

### Backend

Backend 是实现 QNN API 的 shared library。不同 backend 对应不同硬件核心。应用侧通常通过统一 QNN API 和 backend library 交互。

常见 backend：

- `QnnCpu`：CPU backend。
- `QnnGpu`：Adreno GPU backend。
- `QnnDsp`：Hexagon DSP backend。
- `QnnHtp`：Hexagon Tensor Processor backend，是文档中最重点、最复杂的一块。
- `QnnHta`：HTA backend。
- `QnnLpai`：低功耗 AI backend，适合 always-on、语音、sensor hub 等场景。
- `QnnSaver`：不执行图，而是记录 QNN API 调用，便于 replay 和 debug。

### Context / Graph / Tensor / Node

QNN API 的 mental model：

- `QnnBackend`：顶层 backend handle。
- `QnnDevice`：描述设备和硬件资源，部分 backend 有 specialization。
- `QnnContext`：graph 的执行环境，可缓存成 binary 以加快加载。
- `QnnGraph`：模型计算图，由 node 和 tensor 连接而成。
- `QnnTensor`：输入、输出、中间值、静态参数。
- `QnnOpPackage`：向 backend 注册额外 op 的机制。
- `QnnProfile`：性能 profiling。
- `QnnMem`：注册外部分配的内存，做 shared buffer 等场景会用到。

基础调用顺序可以记成：

```text
load backend library
  -> QnnBackend_create
  -> optional QnnBackend_registerOpPackage
  -> QnnContext_create / QnnContext_createFromBinary
  -> QnnGraph_create
  -> create tensors
  -> QnnGraph_addNode
  -> QnnGraph_finalize
  -> QnnGraph_execute / QnnGraph_executeAsync
  -> QnnContext_free
  -> QnnBackend_free
```

文档提醒：node 要按 dependency order 添加；graph finalize 后不能再修改；tensor name 在 context 内要唯一。

## 3. Setup：环境搭建要点

Setup 文档的核心不是“安装一个包”这么简单，而是要根据 host/target/backend 组合配置工具链。

需要关注：

- Python 版本：文档大量工具依赖 Python，当前文档强调 Python 3.10 环境。
- 建议使用 virtualenv，避免污染系统 Python。
- Python package 有固定验证版本，例如 numpy、protobuf、onnx、onnxruntime、pandas、matplotlib 等。
- SDK 提供 `check-python-dependency` 和 `check-linux-dependency.sh` 这类脚本检查依赖。
- Linux 上 x86_64 target 编译 artifact 需要 clang++，文档提到该 release 验证过 clang-14。
- ML framework 版本需要匹配，例如 TensorFlow、TFLite、PyTorch、ONNX、ONNX Runtime、ONNX Simplifier。
- custom op package 编译会涉及 make、Android NDK、交叉编译 toolchain 等。

环境变量上，旧文档和很多工具仍会看到 `QNN_SDK_ROOT`；revision history 里提到 `QAIRT_SDK_ROOT` 成为新的主环境变量，`QNN_SDK_ROOT` 和 `SNPE_ROOT` 进入 deprecated 路径，但目前仍兼容。实际工作里最好问 mentor 当前项目用哪一个变量作为标准。

## 4. 端到端部署流水线

### Step 1：选择模型来源

QNN converter 支持的主要来源：

- TensorFlow
- TFLite
- PyTorch
- ONNX

文档更推荐把不同框架先转到统一 IR，再经过 shared 的 optimizer、quantizer、QNN converter backend，最后生成 QNN model 表达。

### Step 2：转换模型

Converter 通用流程：

```text
framework model
  -> frontend translation
  -> common IR
  -> optional graph optimization
  -> optional quantization
  -> QNN converter backend lowering
  -> model.cpp / model.bin / model_net.json
```

重要输出：

- `model.cpp`：包含 QNN graph 组装代码，典型函数有 `QnnModel_composeGraphs` 和 `QnnModel_freeGraphsInfo`。
- `model.bin`：当参数不直接放在 C++ 中时保存二进制权重等数据。
- `model_net.json`：模型结构的 JSON 表示，便于检查 op、tensor、quant params、MAC 等信息。

我理解 `model.cpp` 不是“模型推理程序”，而是“用 QNN API 描述模型 graph 的代码”。后续还要编译成 model library 或生成 context binary，再交给 backend 执行。

### Step 3：决定是否量化

这一步取决于 backend：

| Backend | 文档给出的常见选择 |
|---|---|
| CPU | 通常选择 non-quantized；文档说 quantized model 当前和 CPU backend 不兼容 |
| GPU | 通常选择 non-quantized；quantized model 当前和 GPU backend 不兼容 |
| DSP | 需要 quantized model |
| HTP | 需要 quantized model；也支持部分 FP16/BF16 场景 |
| HTA | 需要 quantized model |
| LPAI | 支持 quantized 8-bit 和 quantized 16-bit 网络 |

量化的基础公式围绕 `encoding-min`、`encoding-max`、`scale`、`offset`。核心约束：

- 覆盖输入浮点范围。
- 最小 range 至少 0.0001。
- 浮点 0 必须能被精确表示。
- 常见默认是 TensorFlow-style fixed point。

还要理解：

- quantization modes：TF、symmetric、enhanced、TF adjusted。
- quantization schemas：signed/unsigned symmetric/asymmetric。
- quantization overrides：手动指定部分 tensor 的 encoding 或数据类型。
- per-channel overrides：对权重等更细粒度地控制量化。
- mixed precision / FP16：某些路径下兼顾精度和性能。

### Step 4：编译或生成可运行 artifact

常见工具：

- `qnn-model-lib-generator`：把转换输出编译成 model library。
- `qnn-context-binary-generator`：生成 context binary，加速目标端加载。
- `qnn-op-package-generator`：从 XML OpDef 生成 op package skeleton。
- `qnn-net-run`：直接运行模型做验证。
- `qnn-throughput-net-run`：吞吐测试。

这里我会把 artifact 分成三种：

- **源码级表达**：`model.cpp`、`model.bin`、`model_net.json`。
- **可链接/可加载表达**：model shared library。
- **预编译上下文表达**：context binary，适合减少 graph prepare/finalize 的时间。

### Step 5：在 target 上执行

最短验证路径通常是：

```text
准备 input_list.txt
准备 input raw files
选择 backend library
执行 qnn-net-run
检查 output_dir
```

真正集成应用时，则会通过 C/C++ app 加载 backend library、model library/context binary，然后调用 QNN API。

### Step 6：profiling / benchmarking / debug

性能相关工具：

- `qnn_bench.py`：自动推送模型和输入到设备，运行多轮测试，生成 CSV/JSON。
- `qnn-profile-viewer`：看 profiling 结果。
- `qnn-platform-validator`：验证 target 平台环境。
- `qnn-accuracy-debugger` / `qairt-accuracy-debugger`：分析精度差异。
- `qnn-architecture-checker`：检查模型结构是否适合目标 backend。
- `QnnSaver`：记录 API call 和 tensor 数据，后续 replay。

Benchmark 配置文件是 JSON，里面指定 model、device、backend、input、repeat 次数、profiling level 等。结果里的关键指标包括 init、finalize、de-init、total inference time，以及 detailed profiling 下的 per-layer 统计。

## 5. Backend 逐个理解

### CPU backend

CPU backend 比较适合：

- 功能验证。
- FP32 模型。
- 需要 debug callback 拿中间输出的场景。
- 某些没有硬件加速要求的 fallback。

文档提到 CPU 支持 quantized 8-bit 和 float 32-bit networks，但 quantization 页面又提醒 CPU 通常选择 non-quantized。这里要区分“op/table 支持能力”和“推荐部署路线”。实际项目里应以目标 release、目标 SoC 和 SupportedOps 表为准。

CPU backend 还有 QMX 配置，可通过 context/graph custom config 或 backend extensions 控制。

### GPU backend

GPU backend 关注点：

- Adreno GPU。
- kernel persistence：kernel registry / kernel repository，用于减少初始化时间。
- precision mode：
  - FP32：最好精度，性能较低。
  - FP16：最好性能，精度可能下降。
  - Hybrid：FP16 数据、FP32 accumulator，折中。
  - User provided：默认，不主动优化 native tensor 数据类型。
- performance hints：
  - HIGH：高性能、高功耗，默认。
  - NORMAL：平衡。
  - LOW：低功耗、延迟更高。
- 可通过 backend extensions 配置。

GPU 更像“非量化浮点模型的加速执行路径”，调优重点是精度模式、kernel cache、性能 hint 和 op 限制。

### DSP backend

DSP backend 面向 Hexagon DSP。文档强调：

- DSP 有 CPU 侧 stub 和 DSP 侧 skel 的 RPC 模式。
- 可以配置 DSP arch。
- 可配置 signed process domain。
- Performance Infrastructure API 可控制 voltage corner、DCVS mode、线程数等。

DSP 的使用要特别小心目标 SoC、Hexagon arch 和 skel/stub 是否匹配。

### HTP backend

HTP 是 QNN 文档里最重点的一块。它支持量化 8-bit 和 16-bit 网络，并在部分 SoC 上支持 FP16、BF16。

HTP 的关键词：

- `QnnHtp` backend library。
- `QnnHtpPrepare`：负责图 compose/finalize 等 prepare 功能，只有调用相关操作时才需要在 device 上存在。
- `QnnHtpV##Stub` / `libQnnHtpV##Skel.so`：CPU 侧和 HTP 侧通过 RPC 配合。
- HTP arch / SoC model 配置：context binary 如果给不同 HTP arch 用，结果可能不确定。
- VTCM / TCM / shared buffer / qmem graph。
- Graph priority、yielding/pre-emption、SSR、multi-graph switching。
- LLM native KV cache、MaskedSoftmax、Monolithic LSTM 等更高级能力。

HTP 学习建议：

1. 先跑通 HTP backend 的普通 quantized model。
2. 再理解 context binary 和 x86 prepare / target execute。
3. 然后看 VTCM、shared buffer、profiling。
4. 最后再进 custom op package 和 optimization grammar。

### HTA backend

HTA 是较老或特定平台的 AI 加速 backend。文档仍列在 backend 中，但 QNN 子树对 HTP/LPAI/GPU 的内容明显更多。实际项目如果目标 SoC 不用 HTA，可以先知道它存在即可。

### LPAI backend

LPAI 是 Low Power AI，适合低功耗、深嵌入 always-on 场景，例如：

- Always-on voice。
- Voice/music on IoT。
- ASR、speech caption。
- Always-on camera。
- Sensor hub。

LPAI 流程和 HTP 类似，也有 model generation、execution、profiling、troubleshooting。它支持 x86 Linux/Windows 的 simulator / prepare library，也支持 ARM / aDSP execution 路径。学习时重点看 JSON 配置、离线 model generation 和 target execution。

### Saver backend

Saver 不执行 graph，而是把 QNN API 调用记录成：

- `saver_output.c`
- `params.bin`

用途：

- 检查 API 调用顺序。
- 检查参数是否合理。
- 在其他 backend 上 replay。
- 复现 bug 给支持团队或自己做 debug。

我觉得 Saver 是理解 QNN API 的好工具：它能把“框架或工具隐式做了什么”变成可读的 C 调用。

## 6. Converter 与 `qairt-converter`

老的 converter 名称包括：

- `qnn-tensorflow-converter`
- `qnn-tflite-converter`
- `qnn-pytorch-converter`
- `qnn-onnx-converter`

新的统一方向是 `qairt-converter`。它覆盖 basic conversion、I/O layout、YAML 自定义输入输出、QAT encodings、float model、quantization overrides、quantized model、QDQ model、BF16 graph generation、dry run 等。

理解 converter 时，我会看四件事：

1. 输入模型是否是 supported framework/version。
2. 输入输出 layout 和 dtype 是否需要改。
3. 是否需要 calibration data 做 quantization。
4. 输出 artifact 后续要走 model lib 还是 context binary。

文档还提到 custom I/O、preserve I/O、disconnected input preservation 等功能。这些功能的意义是：转换器默认会做图优化和布局调整，但有时应用侧要求输入输出名字、shape、layout 保持一致，这时需要显式配置。

## 7. Quantization：为什么它是部署核心

QNN 量化不只是“把 FP32 变 INT8”。它决定：

- backend 能不能跑。
- 模型大小。
- 推理速度。
- 精度损失。
- 某些 op 是否能被 backend 接受。

基础概念：

- `encoding-min` / `encoding-max`：浮点范围。
- `scale`：固定点步长。
- `offset`：让浮点 0 可精确表示的整数偏移。
- bitwidth：常见 8-bit，也有 16-bit、packed 4-bit 等能力。

对实际工作最有用的几个问题：

- 我的目标 backend 是否要求 quantized model？
- calibration set 是否覆盖真实输入分布？
- 哪些 tensor/op 需要 override？
- 是否要 per-channel quantization？
- 是否要 mixed precision 或 FP16？
- 转换后的 `model_net.json` 里 quant params 是否合理？

HTP 相关性能 guideline 里还单独提到 A16、INT4 weights、activation fusion、TCM/VTCM、channel 数等，这说明量化策略和模型结构会强烈影响 HTP 性能。

## 8. Op、SupportedOps 与 Op Packages

QNN 的 op 支持不是“全 backend 一致”。必须查：

- `SupportedOps.html`
- `CpuOpDefSupplement.html`
- `GpuOpDefSupplement.html`
- `HtpOpDefSupplement.html`
- `DspOpDefSupplement.html`
- `LpaiOpDefSupplement.html`

SupportedOps 表会告诉你：

- 某个 op 在哪个 backend 支持。
- 支持哪些数据类型。
- 是否有 backend-specific 限制。
- op definition revision history。

当内置 op 不满足需求时，用 Op Package：

- Op Package 是一组外部 operation 的 shared library。
- backend 通过 `QnnBackend_registerOpPackage()` 注册。
- 多个 op package 可以注册到同一个 backend。
- 生命周期和 backend 绑定，可被多个 context/graph 使用。
- 所有 op package 需要实现 `QnnOpPackage.h` 定义的接口。

HTP custom op package 更复杂，涉及：

- package interface file。
- op implementation files。
- HTP core headers。
- op registration macros。
- tensor property，如 flat/crouton layout、TCM/main memory placement。
- optimization rule registration。
- parameter order。

我的理解：custom op package 是 QNN 的扩展机制，但不是入门第一阶段要写的东西。先会查 SupportedOps 和跑通内置 op，再看 custom op。

## 9. API 层：真正集成时要懂的结构

QNN API 是 C-style API，便于跨平台。文档中 API version 为：

```text
QNN_API_VERSION_MAJOR = 2
QNN_API_VERSION_MINOR = 34
QNN_API_VERSION_PATCH = 0
```

文档也说明 API 是 source-level backward compatible，但不保证 ABI binary backward compatible。

核心 API component：

| Component | 用途 |
|---|---|
| `QnnBackend` | backend 初始化、op package registry |
| `QnnDevice` | 多设备/多 core、性能控制 |
| `QnnContext` | graph 执行环境，可 binary cache |
| `QnnGraph` | 创建、添加 node/tensor、finalize、execute |
| `QnnTensor` | graph/context tensor，静态权重、输入输出、中间值 |
| `QnnOpPackage` | custom op package 接口 |
| `QnnProfile` | profiling |
| `QnnLog` | 日志 |
| `QnnProperty` | backend capability discovery |
| `QnnMem` | 外部内存注册 |
| `QnnSignal` | 控制执行和取消等 |

对应用开发者来说，最重要的分水岭是：

- **converter/tool 用户**：多数时候只需要会用命令行工具。
- **runtime 集成者**：需要理解 API call flow。
- **backend/custom op 开发者**：需要深入 backend specialization 和 op package。

## 10. HTP 性能与设计 guideline

HTP 相关文档非常多，我把它们归纳成几类。

### 模型结构建议

- 避免低 depth activation，因为可能导致并行度不足或内存/布局效率差。
- 能用 space-to-depth transformation 的地方可以考虑重排以改善性能。
- 注意 channel 数对 HTP 友好程度。
- 选择 activation function 时考虑 backend 支持和融合机会。

### 内存建议

- TCM/VTCM 是 HTP 性能的重要资源。
- 减少 TCM requirement 可能影响性能和功能。
- VTCM sharing / windowing 是高级优化点。
- Shared buffer 和 Qmem graph 适合减少拷贝，但对 graph 类型和 API 使用有要求。

### 精度与量化建议

- A16 vs FP16 不是简单谁更好，要看性能、功耗、融合和精度。
- INT4 weights 可减小权重带宽和模型大小，但要检查 backend 支持和精度影响。
- QDQ、QAT encodings、overrides 都可能影响最终 HTP graph。

### 运行时建议

- Graph priority、yielding/pre-emption 影响多任务场景。
- SSR 处理 subsystem restart。
- Batch inference / multi-threaded inference 可能提高吞吐。
- HTP session/artifact 使用方式会影响初始化、缓存和可复现性。

## 11. Debug / Benchmark / Profiling 体系

我会把 QNN 的问题排查分成三类。

### 转换失败

常见关注点：

- 原始模型 op 是否被 converter 支持。
- shape/layout/dtype 是否能推断。
- ONNX/TFLite/TensorFlow/PyTorch 版本是否匹配。
- 是否需要 custom op output shape/datatype inference。
- 是否需要 preserve I/O 或 custom I/O YAML。
- quantization override 是否冲突。

### 运行失败

常见关注点：

- backend library 路径是否对。
- target arch / SoC / HTP version 是否匹配。
- skel/stub 是否完整。
- context binary 是否由正确 arch 生成。
- input raw 文件 shape/type 是否和 graph input 匹配。
- op package 是否注册。

### 精度或性能异常

工具路径：

- 用 `qnn-net-run` 最小复现。
- 用 `qnn_bench.py` 固化性能指标。
- 用 detailed profiling 看 per-layer。
- 用 `qnn-profile-viewer` 分析 profile。
- 用 accuracy debugger 查中间层差异。
- 用 Saver 记录 API call，必要时 replay。

## 12. 我会怎样安排学习顺序

### 第 1 天：建立全局图

- 读 Introduction、Overview、Setup。
- 知道 host/target/backend/converter/context binary 是什么。
- 把环境变量、Python venv、SDK 目录结构理清。

### 第 2 天：跑通最小闭环

- 选一个官方 tutorial，例如 CNN/ONNX to QNN。
- 转换模型。
- 生成 model library。
- 用 CPU backend 或 HTP backend 跑 `qnn-net-run`。
- 看输出文件和 log。

### 第 3 天：理解 backend 差异

- 重点读 Backend、CPU、GPU、HTP。
- 把每个 backend 的 library 名字、精度要求、典型用途写成表。
- 查 SupportedOps，理解为什么有些模型不能直接跑。

### 第 4 天：理解量化

- 读 Quantization。
- 用小模型做一次 quantized conversion。
- 看 `model_net.json` 里的 tensor quant params。
- 试着解释 scale/offset/encoding 的意义。

### 第 5 天：性能和调试

- 跑 `qnn_bench.py`。
- 尝试 basic 和 detailed profiling。
- 看 CSV/JSON 输出。
- 了解 Saver 怎么记录和 replay。

### 第 6 天以后：高级内容

- HTP VTCM/shared buffer。
- custom op package。
- optimization grammar。
- LPAI 或 GPU tuning mode，按项目需要深入。

## 13. 可以问 mentor 的问题

我建议你明天可以带着这些问题去问，会显得不是“只看了目录”，而是真的在建立工作上下文：

1. 我们当前项目主要 target backend 是 HTP、GPU、CPU 还是 LPAI？
2. 当前模型是 ONNX/TFLite/PyTorch 哪种来源？转换链路用 `qnn-onnx-converter` 还是 `qairt-converter`？
3. 我们部署时用 model library 还是 context binary？
4. 当前项目对量化的要求是什么？INT8、A16、FP16、BF16、INT4 weights 有没有用到？
5. 我们是否需要 custom op package，还是全部 op 都在 SupportedOps 中？
6. 性能评估标准是 latency、throughput、power 还是 memory footprint？
7. debug 时团队常用 `qnn-net-run`、`qnn_bench.py`、accuracy debugger、Saver 中哪几个？
8. 项目现在使用 `QNN_SDK_ROOT` 还是 `QAIRT_SDK_ROOT` 作为主环境变量？
9. 目标 SoC 的 SOC model、Hexagon arch、HTP arch 是什么？
10. 有没有内部已经整理好的 backend config、input_list、benchmark config 模板？

## 14. 关键文件和命令速查

常见 SDK 路径：

```text
<QNN_SDK_ROOT>/bin
<QNN_SDK_ROOT>/lib/<target-platform>
<QNN_SDK_ROOT>/include/QNN
<QNN_SDK_ROOT>/examples
<QNN_SDK_ROOT>/benchmarks/QNN
```

常见命令/工具：

```text
check-python-dependency
check-linux-dependency.sh
qairt-converter
qnn-onnx-converter
qnn-tflite-converter
qnn-tensorflow-converter
qnn-pytorch-converter
qnn-model-lib-generator
qnn-context-binary-generator
qnn-op-package-generator
qnn-net-run
qnn-throughput-net-run
qnn_bench.py
qnn-profile-viewer
qnn-platform-validator
qnn-accuracy-debugger
qairt-accuracy-debugger
qnn-architecture-checker
qnn-context-binary-utility
```

常见 backend library 名字：

```text
QnnCpu / libQnnCpu.so / QnnCpu.dll
QnnGpu / libQnnGpu.so / QnnGpu.dll
QnnDsp / libQnnDsp.so / QnnDspV##Stub / libQnnDspV##Skel.so
QnnHtp / libQnnHtp.so / QnnHtpPrepare / QnnHtpV##Stub / libQnnHtpV##Skel.so
QnnHta / libQnnHta.so
QnnLpai / libQnnLpai.so / QnnLpaiPrepare_v## / QnnLpaiSim_v## / QnnLpaiStub
QnnSaver / libQnnSaver.so / QnnSaver.dll
```

## 15. 本次扫描产物

为了避免只凭网页记忆，我在本地生成了这些辅助文件：

- `qnn_indexmain.json`：官方导航 JSON。
- `qnn_outline.tsv`：QNN 子树目录。
- `qnn_pages_html/`：111 个 topic 的原始 HTML。
- `qnn_pages_md/`：111 个 topic 的 Markdown 正文抽取。
- `qnn_corpus.md`：合并后的英文语料。

如果后面 mentor 让你聚焦某一块，例如 HTP、converter、quantization、benchmark，我可以继续基于这些本地语料帮你做二级笔记或面试式问答。

## 16. 参考入口

- QNN 首页：<https://docs.qualcomm.com/doc/80-63442-10/topic/index_QNN.html>
- Introduction：<https://docs.qualcomm.com/doc/80-63442-10/topic/general_introduction.html>
- Overview：<https://docs.qualcomm.com/doc/80-63442-10/topic/QNN_general_overview.html>
- Setup：<https://docs.qualcomm.com/doc/80-63442-10/topic/general_setup.html>
- Backend：<https://docs.qualcomm.com/doc/80-63442-10/topic/backend.html>
- Converters：<https://docs.qualcomm.com/doc/80-63442-10/topic/converters.html>
- Quantization：<https://docs.qualcomm.com/doc/80-63442-10/topic/quantization.html>
- Tools：<https://docs.qualcomm.com/doc/80-63442-10/topic/general_tools.html>
- Tutorials：<https://docs.qualcomm.com/doc/80-63442-10/topic/general_tutorials.html>
- Benchmarking：<https://docs.qualcomm.com/doc/80-63442-10/topic/benchmarking.html>
- API overview：<https://docs.qualcomm.com/doc/80-63442-10/topic/api_overview.html>
- Op Packages：<https://docs.qualcomm.com/doc/80-63442-10/topic/op_packages.html>
- Revision History：<https://docs.qualcomm.com/doc/80-63442-10/topic/general_revision_history.html>
