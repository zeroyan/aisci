# Research: 002-plan-baseline-mvp

生成日期: 2026-03-01

---

## 1. Tool-Use Agent 模式（替换 CodegenAgent）

**Decision**: 用 tool-use 模式替换 `CodegenAgent` + `AnalyzerAgent` 的三段式调用。

**Rationale**:
- 现有 `CodegenAgent._parse_response()` 强制要求 `{files, entrypoint}` JSON，LLM 稍有偏差即抛异常。
- `consecutive_failure_limit=3` 在 3 次失败后直接终止，无法自我修正。
- tool-use 模式让 LLM 自主决定调用哪个工具、调用几次，天然支持多步骤自我修正。

**Alternatives considered**:
- 保留 CodegenAgent，放宽 JSON 解析（正则 fallback）→ 治标不治本，LLM 仍无法自主决策步骤顺序。
- 引入 LangGraph / CrewAI → 过重，与现有 litellm + pydantic 栈不兼容，YAGNI。

**Design**:
```
ToolAgent
  ├── tools: [write_file, run_bash, read_file, finish]
  ├── ToolDispatcher → wraps SubprocessSandbox (复用现有沙箱)
  └── 循环: LLM call → tool dispatch → append ToolTurn → 直到 finish 或 max_turns
```

litellm `tools` 参数支持 OpenAI function calling 格式，跨 provider 兼容。

---

## 2. ExperimentPlan 文档格式

**Decision**: ExperimentPlan 以 MD 文档输出，YAML front-matter 存元数据，正文为人类可读内容，HTML 注释嵌入 JSON 用于程序化 round-trip 解析。

**Rationale**:
- MD 是人机对齐媒介（人直接编辑，AI 读取），Obsidian 兼容。
- YAML front-matter 是 Obsidian 标准，支持属性面板展示。
- HTML 注释嵌入 JSON 不影响渲染，保留结构化数据供程序解析。

**Format**:
```markdown
---
plan_id: "plan-xxx"
spec_id: "spec-yyy"
version: 1
created_at: "2026-03-01T10:00:00Z"
updated_at: "2026-03-01T10:00:00Z"
---
# 实验方案：{title}
## 技术路线
...
## 评估指标
...
## 步骤
...
<!-- PLAN_JSON: {"steps": [...], "revision_history": [...]} -->
```

**Alternatives considered**:
- 纯 JSON 存储 → 不可人工编辑，不 Obsidian 兼容。
- 纯 MD 无结构化数据 → 程序解析困难，版本追踪缺失。

---

## 3. 网络检索库选型

**Decision**: Tavily（主）+ arxiv + semanticscholar（学术）+ trafilatura（网页提取）+ duckduckgo-search（fallback）

| 用途 | 库 | 说明 |
|---|---|---|
| 通用网络搜索 | `tavily-python` | LLM 优化，返回清洁文本，需 `TAVILY_API_KEY` |
| 通用搜索 fallback | `duckduckgo-search` | 免费无 key，但有频率限制，仅作备用 |
| 学术论文 | `arxiv` | 官方 Python 库，免费，无 key |
| 引用排名论文 | `semanticscholar` | 返回引用数、开放 PDF，免费 |
| 网页内容提取 | `trafilatura` | HTML→Markdown，优于 newspaper3k |
| HTTP 客户端 | `httpx` | 异步友好，已在栈中 |
| Frontmatter 解析 | `python-frontmatter` | 读写 MD YAML front-matter |

**Rationale**:
- Tavily 专为 agent 设计，`include_raw_content=True` 一次调用返回全文，无需额外抓取。
- DuckDuckGo 在 agent 循环中频率限制问题严重（多个开源项目 issue 确认），仅作 fallback。
- arxiv + semanticscholar 覆盖学术场景，免费且稳定。
- trafilatura 在 HTML 正文提取 benchmark 中持续领先。

---

## 4. 知识库结构

**Decision**: 两层 MD 文件结构，YAML front-matter 作索引，keyword 匹配作缓存查找。

**Rationale**:
- MVP 规模（< 500 条）下，glob + frontmatter keyword 匹配 < 50ms，无需向量数据库。
- Obsidian 兼容：`scientist/` 可直接作为 vault 子文件夹，frontmatter 在属性面板可见。
- 升级路径：条目增长后可加 `chromadb`/`lancedb` 作可选索引层，存储格式不变。

**两层结构**:
```
runs/<run_id>/knowledge/   # 本次实验专属（实验特定数据、中间结果）
scientist/                 # 全局跨实验记忆（已读论文、方法论、baseline 缓存）
  └── 路径可配置，可指向 Obsidian vault 独立文件夹
```

**查找策略**: 先查 `scientist/`（全局缓存），再查 `runs/<run_id>/knowledge/`（本地缓存），均未命中才发起网络检索。

**去重键**: `source_url`（每个 URL 只存一条）。

**Alternatives considered**:
- ChromaDB 向量检索 → MVP 过重，embedding 成本高，Obsidian 不兼容。
- SQLite 全文检索 → 不 Obsidian 兼容，增加依赖。
