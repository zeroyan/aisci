# Implementation Plan: 002-plan-baseline-mvp

**分支**: `main`
**依赖**: 001-research-copilot-mvp（已完成）

---

## Phase 0：Tool-Use Agent 升级（前置）

> 升级 001 的实验执行模型，为 002 方案修订循环奠基。

### T-001：新增 Tool-Use Schema
- 文件：`src/schemas/tool_use.py`
- 新增：`ToolCall`, `ToolResult`, `ToolTurn`, `FinishResult`, `ToolIterationRecord`
- 废弃标记：`CodeSnapshot`, `AgentDecision`（保留兼容，加 `Deprecated` 注释）

### T-002：实现 ToolDispatcher
- 文件：`src/agents/experiment/tool_dispatcher.py`
- 包装 `SubprocessSandbox`，将 tool call 路由到对应沙箱操作
- 工具：`write_file(path, content)`, `run_bash(cmd)`, `read_file(path)`, `finish(summary, artifacts, success)`

### T-003：实现 ToolAgent（替换 CodegenAgent + AnalyzerAgent）
- 文件：`src/agents/experiment/tool_agent.py`
- 循环：LLM call（带 tools 参数）→ ToolDispatcher → append ToolTurn → 直到 finish 或 max_turns
- 使用 litellm `tools` 参数（OpenAI function calling 格式）

### T-004：更新 ExperimentLoop
- 文件：`src/agents/experiment/loop.py`
- 替换 `CodegenAgent` + `AnalyzerAgent` 调用为 `ToolAgent`
- 输出 `ToolIterationRecord` 替换 `IterationRecord`

### T-005：更新测试
- 更新 `tests/` 中涉及 `CodegenAgent`、`AnalyzerAgent`、`IterationRecord` 的测试
- 新增 `ToolAgent` 单元测试（mock LLM + mock sandbox）

---

## Phase 1：知识库

### T-006：新增 KnowledgeEntry Schema
- 文件：`src/schemas/knowledge.py`
- 新增：`KnowledgeEntryMeta`, `KnowledgeEntry`

### T-007：实现 KnowledgeStore
- 文件：`src/knowledge/store.py`
- 两层查找：`scientist/` → `runs/<run_id>/knowledge/` → 网络检索
- 去重键：`source_url`；写入时按 `layer` 选择目录
- 依赖：`python-frontmatter`

### T-008：实现 Searcher
- 文件：`src/knowledge/searcher.py`
- 主：Tavily（`TAVILY_API_KEY` 存在时）；fallback：duckduckgo-search
- 学术：arxiv + semanticscholar
- 网页提取：trafilatura + httpx
- 失败不抛异常，返回空列表 + 记录 `status: fetch_failed`

### T-009：扩展 Config
- 文件：`configs/default.yaml`
- 新增 `knowledge:` 节：`scientist_dir`, `search_backend`, `max_results_per_query`
- `scientist_dir` 默认 `scientist/`，可配置为 Obsidian vault 子目录

### T-010：知识库测试
- mock Tavily / arxiv 响应，验证 cache-first 逻辑
- 验证 `fetch_failed` 条目写入后不重复检索

---

## Phase 2：方案生成

### T-011：扩展 ExperimentPlan Schema
- 文件：`src/schemas/research_spec.py`（或拆分为 `experiment_plan.py`）
- 新增：`TechnicalApproach`, `RevisionEntry`
- 扩展：`PlanStep`（`depends_on`, `estimated_minutes`），`ExperimentPlan`（`version`, `updated_at`, `revision_history`, `technical_approach`）

### T-012：实现 ExperimentPlan MD 序列化
- 文件：`src/schemas/plan_serializer.py`
- `to_markdown(plan: ExperimentPlan) -> str`：生成符合 contracts/experiment-plan.md 格式的 MD
- `from_markdown(md: str) -> ExperimentPlan`：解析 `PLAN_JSON` 注释 + front-matter

### T-013：实现 PlanAgent
- 文件：`src/agents/plan/plan_agent.py`
- 输入：`ResearchSpec` + `KnowledgeStore` 检索结果
- 输出：`ExperimentPlan`（写入 `runs/<run_id>/plan.md`）
- 调用 `LLMClient`，prompt 注入知识库摘要

### T-014：方案生成测试
- mock LLM 响应，验证 MD 输出格式符合 contract
- 验证知识库内容注入 prompt

---

## Phase 3：方案修订循环

### T-015：实现 RevisionAgent
- 文件：`src/agents/plan/revision_agent.py`
- 输入：`ExperimentPlan` + 实验报告（`runs/<run_id>/report.md`）
- 输出：修订建议（追加到 plan.md 的 `## 修订建议` 节）
- 人类确认后，调用 `plan_serializer` 更新 plan.md，`version +1`，追加 `RevisionEntry`

### T-016：CLI 扩展
- 文件：`cli.py`
- 新增命令：`plan generate <spec_id>`，`plan revise <run_id>`，`plan show <run_id>`

### T-017：修订循环测试
- 验证 `version` 递增，`revision_history` 追加
- 验证人工编辑 MD 后 `from_markdown` 能正确解析

---

## 依赖顺序

```
T-001 → T-002 → T-003 → T-004 → T-005
T-006 → T-007 → T-008 → T-009 → T-010
T-011 → T-012 → T-013 → T-014
T-014 → T-015 → T-016 → T-017
T-005（Phase 0 完成）→ T-013（Phase 2 开始）
T-010（Phase 1 完成）→ T-013
```

## 新增依赖（pyproject.toml）

```toml
"tavily-python>=0.5",
"duckduckgo-search>=6.0",
"arxiv>=2.1",
"semanticscholar>=0.8",
"trafilatura>=1.12",
"httpx>=0.27",
"python-frontmatter>=1.1",
```
