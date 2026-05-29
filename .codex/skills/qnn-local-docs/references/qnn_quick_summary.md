# QNN 快速中文摘要

## 当前项目原则

```text
先跑起来，再跑得快。
先软件闭环，再硬件联调。
先 CPU/float 正确性，再 GPU/HTP/量化优化。
```

## 本地文档数据库

不要把原始 Qualcomm 文档镜像上传到 GitHub。到公司机器后现场运行：

```bash
python scripts/qnn_docs/fetch_qnn_docs.py
python scripts/qnn_docs/build_qnn_doc_db.py
python scripts/qnn_docs/smart_search_qnn_docs.py "HTP 怎么跑模型，需要量化吗" --show-queries
python scripts/qnn_docs/search_qnn_docs.py "qnn-net-run backend" --limit 5
```

生成内容：

```text
artifacts/qnn_docs/raw_html/
artifacts/qnn_docs/pages_md/
artifacts/qnn_docs/qnn_corpus.local.md
artifacts/qnn_docs/qnn_docs.sqlite
```

这些都是本地缓存，不提交。

## Phase 1 标准路线

1. 配 QNN/QAIRT 环境。
2. 下载 ResNet ONNX 和测试图片。
3. 用 ONNX Runtime 跑 Python baseline。
4. 用 `qnn-onnx-converter` 转 QNN `.cpp/.bin`。
5. 用 `qnn-model-lib-generator` 生成 `.so`。
6. 用 `qnn-net-run --backend libQnnCpu.so` 跑 CPU float。
7. 用 `compare_qnn_with_baseline.py` 对比 QNN output 与 baseline。

## 常用搜索词

```bash
python scripts/qnn_docs/smart_search_qnn_docs.py "qnn 环境怎么配置，Python 依赖怎么装" --show-queries
python scripts/qnn_docs/smart_search_qnn_docs.py "ONNX 模型怎么转 QNN 并运行" --show-queries
python scripts/qnn_docs/smart_search_qnn_docs.py "HTP 怎么跑模型，需要量化吗" --show-queries
python scripts/qnn_docs/search_qnn_docs.py "qnn-onnx-converter input_network input_dim preserve_io"
python scripts/qnn_docs/search_qnn_docs.py "qnn-model-lib-generator target output library"
python scripts/qnn_docs/search_qnn_docs.py "qnn-net-run input_list backend output_dir"
python scripts/qnn_docs/search_qnn_docs.py "HTP DSP target devices MUST use quantized models"
python scripts/qnn_docs/search_qnn_docs.py "envsetup check-python-dependency envcheck"
```
