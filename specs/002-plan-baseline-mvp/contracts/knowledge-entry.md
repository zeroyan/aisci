# Contract: KnowledgeEntry MD 文档格式

**版本**: 1.0
**适用**: 002-plan-baseline-mvp

---

## 文件路径

```
scientist/<slug>.md                    # 全局层（跨实验）
runs/<run_id>/knowledge/<slug>.md      # 本地层（实验专属）
```

`<slug>` = `source_url` 的 URL-safe slug（截断至 80 字符）。

## 格式规范

```markdown
---
id: "<12位hex>"
type: "paper" | "repo" | "web_article" | "method"
title: "<标题>"
source_url: "<URL>"
authors: ["<author1>", "<author2>"]
published: "<YYYY-MM-DD 或 YYYY>"
keywords: ["<kw1>", "<kw2>"]
spec_ids: ["<spec_id>"]
run_ids: ["<run_id>"]
fetched_at: "<ISO8601>"
status: "ok" | "fetch_failed" | "summarize_failed"
relevance_score: <0.0-1.0 或省略>
layer: "global" | "run-local"
---

## 摘要

<LLM 生成的中文摘要，200-400 字>

## 要点

- <要点 1>
- <要点 2>

## 与查询的相关性

<说明该条目与触发检索的查询/实验的关联>

## 原文摘录

> <abstract 或正文关键段落，英文保留原文>
```

## 约束

1. `source_url` 是去重键，同一 URL 只存一条（全局层优先）。
2. `status: fetch_failed` 时，摘要/要点/摘录可为空，但必须写入文件（防止重复检索）。
3. `layer: global` 的条目写入 `scientist/`；`layer: run-local` 写入 `runs/<run_id>/knowledge/`。
4. 查找顺序：先 `scientist/`，再 `runs/<run_id>/knowledge/`，均未命中才发起网络检索。
