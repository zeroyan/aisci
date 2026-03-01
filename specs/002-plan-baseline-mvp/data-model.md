# Data Model: 002-plan-baseline-mvp

---

## 1. Tool-Use Agent 相关 Schema（替换 CodegenAgent）

### ToolCall
```python
class ToolCall(BaseModel):
    tool_name: str                    # "write_file" | "run_bash" | "read_file" | "finish"
    arguments: dict[str, Any]
    call_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
```

### ToolResult
```python
class ToolResult(BaseModel):
    call_id: str
    tool_name: str
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    error: str | None = None          # dispatch 层异常（非沙箱错误）
```

### ToolTurn
```python
class ToolTurn(BaseModel):
    turn_index: int
    calls: list[ToolCall]
    results: list[ToolResult]
    llm_reasoning: str | None = None  # LLM 在 tool call 前的 text 输出（可选）
```

### FinishResult
```python
class FinishResult(BaseModel):
    summary: str                      # 实验结论摘要
    artifacts: list[str] = []         # 产出文件路径列表
    success: bool = True
    failure_reason: str | None = None
```

### ToolIterationRecord（替换现有 IterationRecord）
```python
class ToolIterationRecord(BaseModel):
    run_id: str
    iteration_index: int
    turns: list[ToolTurn]
    finish_result: FinishResult | None = None
    total_turns: int = 0
    started_at: datetime
    finished_at: datetime | None = None
    status: Literal["running", "finished", "failed", "timeout"] = "running"
```

---

## 2. ExperimentPlan 扩展

### TechnicalApproach（新增）
```python
class TechnicalApproach(BaseModel):
    framework: str                    # 主要框架/库（如 "PyTorch", "scikit-learn"）
    baseline_methods: list[str] = []  # 参考 baseline 方法名
    key_references: list[str] = []    # 关键论文 URL 或 arxiv ID
    implementation_notes: str = ""    # 技术实现要点
```

### PlanStep（扩展现有）
```python
class PlanStep(BaseModel):
    step_id: str
    title: str
    description: str
    depends_on: list[str] = []        # 依赖的 step_id 列表（新增）
    estimated_minutes: int | None = None  # 预估耗时（新增）
    status: Literal["pending", "running", "done", "failed"] = "pending"
```

### RevisionEntry（新增）
```python
class RevisionEntry(BaseModel):
    version: int
    revised_at: datetime
    revised_by: Literal["human", "ai"]
    summary: str                      # 本次修订摘要
    trigger: str | None = None        # 触发原因（如 run_id 或人工说明）
```

### ExperimentPlan（扩展现有）
```python
class ExperimentPlan(BaseModel):
    plan_id: str
    spec_id: str
    version: int = 1                  # 修订版本号（新增）
    title: str
    method_summary: str
    technical_approach: TechnicalApproach  # 新增
    evaluation_protocol: str
    steps: list[PlanStep]
    baseline: str | None = None
    revision_history: list[RevisionEntry] = []  # 新增
    created_at: datetime
    updated_at: datetime              # 新增
```

---

## 3. 知识库 Schema

### KnowledgeEntryMeta
```python
class KnowledgeEntryMeta(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    type: Literal["paper", "repo", "web_article", "method"]
    title: str
    source_url: str
    authors: list[str] = []
    published: str | None = None      # ISO date string
    keywords: list[str] = []
    spec_ids: list[str] = []          # 关联的 ResearchSpec ID
    run_ids: list[str] = []           # 关联的 run ID（空=全局）
    fetched_at: datetime = Field(default_factory=datetime.utcnow)
    status: Literal["ok", "fetch_failed", "summarize_failed"] = "ok"
    relevance_score: float | None = None
    layer: Literal["global", "run-local"] = "global"
```

### KnowledgeEntry（完整条目，含正文）
```python
class KnowledgeEntry(BaseModel):
    meta: KnowledgeEntryMeta
    summary: str                      # LLM 生成的摘要
    key_points: list[str] = []        # 要点列表
    relevance_note: str = ""          # 与当前查询的相关性说明
    raw_excerpt: str = ""             # 原文摘录（abstract 或正文片段）
```

---

## 4. 废弃 Schema（002 完成后移除）

| 废弃 | 替换为 |
|---|---|
| `CodeSnapshot` | `ToolCall` (write_file tool) |
| `SandboxRequest.code_snapshot` | `ToolDispatcher` |
| `AgentDecision` | `FinishResult` |
| `IterationRecord` | `ToolIterationRecord` |
