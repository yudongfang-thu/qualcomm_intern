# QNN 本地文档数据库与 Claude Code Skill

> 目的：不把 Qualcomm 原始手册镜像上传到 GitHub。到公司机器后现场抓取公开文档、建立本地数据库，再让 Claude Code skill 检索本地数据库回答问题。

## 1. 为什么这样做

不建议把原始 Qualcomm 文档镜像上传到 public GitHub。

更稳的方案：

```text
GitHub 只放:
  原创中文总结
  抓取脚本
  SQLite 建库脚本
  检索脚本
  Claude Code skill

公司机器本地生成:
  raw_html/
  pages_md/
  qnn_corpus.local.md
  qnn_docs.sqlite
```

生成目录在：

```text
artifacts/qnn_docs/
```

这个目录已经被 `.gitignore` 忽略，不会提交。

## 2. 一键使用

在公司机器上：

```bash
git clone https://github.com/yudongfang-thu/qualcomm_intern.git
cd qualcomm_intern
bash scripts/qnn_docs/qnn_docs_pipeline.sh
```

这个命令会：

1. 根据 `docs/qnn_outline.tsv` 下载 QNN 页面。
2. 转成本地 Markdown。
3. 建立 SQLite FTS 搜索数据库。
4. 跑一个测试搜索。

## 3. 分步执行

抓取文档：

```bash
python scripts/qnn_docs/fetch_qnn_docs.py
```

只抓前 5 页测试：

```bash
python scripts/qnn_docs/fetch_qnn_docs.py --limit 5
```

建立数据库：

```bash
python scripts/qnn_docs/build_qnn_doc_db.py
```

搜索：

```bash
python scripts/qnn_docs/search_qnn_docs.py "qnn-net-run backend input_list" --limit 5
```

看完整页面：

```bash
python scripts/qnn_docs/search_qnn_docs.py "qnn-onnx-converter preserve_io" --limit 2 --full
```

## 4. Claude Code Skill 位置

Skill 放在：

```text
.claude/skills/qnn-local-docs/SKILL.md
```

辅助摘要：

```text
.claude/skills/qnn-local-docs/references/qnn_quick_summary.md
```

如果 Claude Code 支持项目内 skills，它会在相关问题触发这个 skill。否则你也可以直接让 Claude Code 读取这个文件：

```text
请使用 .claude/skills/qnn-local-docs/SKILL.md 的流程回答我的 QNN 问题。
```

## 5. 常用搜索示例

```bash
python scripts/qnn_docs/search_qnn_docs.py "QNN_SDK_ROOT envsetup check-python-dependency"
python scripts/qnn_docs/search_qnn_docs.py "qnn-onnx-converter input_network output_path"
python scripts/qnn_docs/search_qnn_docs.py "qnn-model-lib-generator target architecture"
python scripts/qnn_docs/search_qnn_docs.py "qnn-net-run model backend input_list output_dir"
python scripts/qnn_docs/search_qnn_docs.py "CPU GPU HTP DSP backend library"
python scripts/qnn_docs/search_qnn_docs.py "HTP quantized input_list context binary"
```

## 6. 注意事项

- 不要提交 `artifacts/qnn_docs/`。
- 不要把 `qnn_corpus.local.md` 上传到 GitHub。
- 回答问题时尽量引用官方 source URL。
- 只把中文总结、命令手册、脚本和 skill 留在 public repo。
