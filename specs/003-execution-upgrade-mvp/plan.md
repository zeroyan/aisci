# Implementation Plan: 实验执行架构升级

**Feature**: 003-execution-upgrade-mvp
**Version**: 1.0.0
**Status**: Planning
**Created**: 2026-03-02

---

## Executive Summary

本计划定义 Spec 003（实验执行架构升级）的技术实现方案，引入多分支并行搜索、Planner/Critic 角色分离、Budget Scheduler、Experiment Memory 和 Docker 安全隔离，提升实验探索效率和质量。

**核心交付物**：
- BranchOrchestrator 编排器（支持最多 3 个并行分支）
- Planner/Critic/Executor 三角色架构
- Budget Scheduler 动态资源分配
- Experiment Memory 结构化记忆系统
- Docker 容器安全隔离层

---

## Technical Context

### Technology Stack

| 组件 | 技术选型 | 版本 | 说明 |
|------|---------|------|------|
| 语言 | Python | 3.11+ | 符合 Constitution 要求 |
| 并发模型 | asyncio + multiprocessing | stdlib | 分支并行执行 |
| 容器化 | Docker Python SDK | 7.0+ | 容器管理和隔离 |
| 嵌入模型 | sentence-transformers | 2.2+ | 记忆检索相似度计算 |
| 数据序列化 | Pydantic | 2.x | Schema 定义和验证 |
| LLM 调用 | litellm | 现有 | 复用现有 LLMClient |
| 日志 | structlog | 24.x | 结构化日志 |

### Key Dependencies

**新增依赖**：
```txt
# requirements.txt 新增
docker>=7.0.0                    # Docker 容器管理
sentence-transformers>=2.2.0     # 嵌入模型（记忆检索）
structlog>=24.0.0                # 结构化日志
```

**现有依赖**（复用）：
- pydantic: Schema 定义
- litellm: LLM 调用
- pyyaml: 配置文件

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     BranchOrchestrator                       │
│  - 创建最多 3 个分支（基于 ExperimentPlan 变体）              │
│  - 管理全局知识库（只读）和分支本地记忆（读写）                │
│  - 收集结果并汇总                                            │
└────────────┬────────────────────────────────────────────────┘
             │
      ┌──────┴──────┬──────────┬──────────┐
      │             │          │          │
   Branch 1      Branch 2   Branch 3    ...
      │             │          │
      ↓             ↓          ↓
┌─────────────────────────────────────┐
│  Planner → Executor → Critic Loop   │
│  - 最多 5 轮                         │
│  - 早停：连续 2 次无改进              │
│  - 失败生成实验报告                  │
└─────────────┬───────────────────────┘
              │
              ↓
┌─────────────────────────────────────┐
│       Budget Scheduler               │
│  - 跟踪资源消耗                      │
│  - 动态调整预算                      │
│  - 早停策略                          │
└─────────────┬───────────────────────┘
              │
              ↓
┌─────────────────────────────────────┐
│      Experiment Memory               │
│  - 全局知识库（只读）                 │
│  - 分支本地记忆（读写）               │
│  - 语义相似度检索                    │
└─────────────────────────────────────┘
              │
              ↓
┌─────────────────────────────────────┐
│      Docker 安全隔离层               │
│  - Python 官方镜像                   │
│  - 按需安装依赖                      │
│  - 资源限制                          │
└─────────────────────────────────────┘
```

### Integration Points

**输入**：
- `ResearchSpec` (from Spec 001)
- `ExperimentPlan` (from Spec 002)
- 配置文件：`configs/execution.yaml`

**输出**：
- `ExperimentResult` (统一结果格式)
- 分支报告：`runs/<run_id>/branches/<branch_id>/report.md`
- 汇总报告：`runs/<run_id>/final_report.md`

**与现有模块的关系**：
- 复用 `src/llm/client.py` (LLMClient)
- 复用 `src/schemas/` (ResearchSpec, ExperimentPlan)
- 复用 `src/storage/artifact.py` (ArtifactStore)
- 新增 `src/orchestrator/` (BranchOrchestrator)
- 新增 `src/agents/planner/` (Planner, Critic)
- 新增 `src/scheduler/` (BudgetScheduler)
- 新增 `src/memory/` (ExperimentMemory)
- 新增 `src/sandbox/docker_sandbox.py` (DockerSandbox)

---

## Constitution Check

### ✅ 模块化架构
- **符合**：BranchOrchestrator、Planner、Critic、Scheduler、Memory 均为独立模块
- **符合**：模块间通过文件传递数据（JSON/JSONL）
- **符合**：每个模块可独立测试

### ✅ Schema 先行
- **符合**：所有新增数据结构均使用 Pydantic 定义
- **符合**：ExperimentResult、BranchConfig、BudgetAllocation 等 schema 先定义
- **符合**：模块入口处验证输入 schema

### ✅ 安全执行
- **符合**：Docker 容器隔离（Phase 3 实现）
- **符合**：资源限制（CPU、内存、磁盘）
- **符合**：超时机制（单次执行、总执行时间）
- **符合**：命令白名单增强

### ⚠️ 技术栈
- **符合**：Python 3.11+
- **符合**：ruff 代码风格
- **符合**：LLM 调用复用现有 LLMClient
- **注意**：新增 Docker 依赖，需确保开发和生产环境都有 Docker

### 评估结果
**PASS** - 所有核心原则符合，技术栈符合 Constitution v3.1.0 要求。

---

## Phase 0: Research & Unknowns

### Research Topics

#### R1: Docker Python SDK 最佳实践
**问题**：如何使用 Docker Python SDK 安全地管理容器生命周期？

**研究内容**：
- 容器创建、启动、停止、删除的完整流程
- 资源限制配置（CPU、内存、磁盘）
- 网络隔离配置
- 卷挂载最佳实践
- 错误处理和清理机制

**决策**（基于研究）：
- 使用 `docker.from_env()` 连接本地 Docker daemon
- 容器配置：
  ```python
  container_config = {
      "image": "python:3.11-slim",
      "mem_limit": "2g",
      "cpu_quota": 100000,  # 1 CPU
      "network_disabled": True,
      "volumes": {workspace: {"bind": "/workspace", "mode": "rw"}},
      "working_dir": "/workspace",
  }
  ```
- 使用 context manager 确保容器清理

#### R2: 分支并行执行策略
**问题**：如何高效地并行执行 3 个分支，避免 LLM API 限流？

**研究内容**：
- asyncio vs multiprocessing 选择
- LLM API 限流处理（rate limiting）
- 分支间通信机制
- 错误隔离和传播

**决策**（基于研究）：
- 使用 `multiprocessing.Pool` 并行执行分支（进程隔离）
- 每个分支独立的 LLMClient 实例（避免共享状态）
- 配置 LLM API rate limit：`max_requests_per_minute=20`（分摊到 3 个分支）
- 分支间不直接通信，通过文件系统共享只读知识库

#### R3: 语义相似度检索实现
**问题**：如何实现高效的记忆检索（"查找类似失败案例"）？

**研究内容**：
- sentence-transformers 模型选择
- 嵌入向量存储和检索
- 相似度计算方法
- 性能优化

**决策**（基于研究）：
- 模型：`all-MiniLM-L6-v2`（轻量级，适合本地运行）
- 存储：JSONL + 嵌入向量缓存（`.npy` 文件）
- 相似度：余弦相似度（`cosine_similarity`）
- 检索：Top-K 最相似（K=5）
- **注意**：具体实现后续可优化（用户反馈）

---

## Phase 1: Data Model & Contracts

### Core Entities

#### 1. BranchConfig
```python
class BranchConfig(BaseModel):
    """分支配置。"""

    branch_id: str  # 分支唯一标识
    variant_params: dict[str, Any]  # 变体参数（超参、方法选择等）
    initial_budget: BudgetAllocation  # 初始预算分配
    workspace_path: Path  # 工作空间路径
```

#### 2. BudgetAllocation
```python
class BudgetAllocation(BaseModel):
    """预算分配。"""

    max_tokens: int  # 最大 token 数
    max_time_seconds: float  # 最大执行时间（秒）
    max_iterations: int  # 最大迭代次数
```

#### 3. PlannerOutput
```python
class PlannerOutput(BaseModel):
    """Planner 输出。"""

    action_plan: list[ToolCall]  # 工具调用序列
    reasoning: str  # 推理过程
```

#### 4. CriticFeedback
```python
class CriticFeedback(BaseModel):
    """Critic 反馈。"""

    status: Literal["success", "failed", "needs_improvement"]
    score: float  # 0-1 评分
    feedback: str  # 具体反馈
    suggestions: list[str]  # 改进建议
```

#### 5. BranchResult
```python
class BranchResult(BaseModel):
    """单个分支的执行结果。"""

    branch_id: str
    status: Literal["success", "failed", "timeout"]
    iterations: int  # 实际迭代次数
    cost_usd: float  # 实际成本
    time_seconds: float  # 实际耗时
    best_code_path: str | None  # 最佳代码路径
    metrics: dict[str, float]  # 实验指标
    report_path: str  # 分支报告路径
```

#### 6. ExperimentResult
```python
class ExperimentResult(BaseModel):
    """统一的实验结果格式（已在 spec 中定义）。"""

    run_id: str
    engine: Literal["aisci", "ai-scientist"]
    status: Literal["success", "failed", "timeout"]

    # 核心结果
    best_code_path: str | None
    metrics: dict[str, float]
    artifacts: list[str]

    # 执行信息
    total_cost_usd: float
    total_time_seconds: float
    iterations: int

    # 可选：论文
    paper_latex: str | None = None
    paper_pdf: str | None = None

    # 元数据
    created_at: datetime
    engine_version: str
```

#### 7. MemoryEntry
```python
class MemoryEntry(BaseModel):
    """记忆条目。"""

    entry_id: str
    timestamp: datetime
    branch_id: str
    iteration: int

    # 尝试内容
    code_snapshot: str  # 代码快照
    tool_calls: list[ToolCall]  # 工具调用
    result: str  # 执行结果

    # 评估
    critic_feedback: CriticFeedback

    # 嵌入向量（用于检索）
    embedding: list[float] | None = None
```

### Directory Structure

```
runs/<run_id>/
├── config.yaml                    # 运行配置
├── branches/
│   ├── branch_001/
│   │   ├── workspace/             # 工作空间（挂载到容器）
│   │   ├── memory/
│   │   │   ├── attempts.jsonl    # 所有尝试
│   │   │   ├── failures.jsonl    # 失败案例
│   │   │   ├── successes.jsonl   # 成功案例
│   │   │   └── embeddings.npy    # 嵌入向量缓存
│   │   ├── logs/
│   │   │   └── branch.log         # 分支日志
│   │   └── report.md              # 分支报告
│   ├── branch_002/
│   └── branch_003/
├── final_report.md                # 汇总报告
└── experiment_result.json         # ExperimentResult

scientist/knowledge/               # 全局知识库（只读）
├── failures.jsonl                 # 历史失败案例
├── successes.jsonl                # 历史成功案例
└── embeddings.npy                 # 嵌入向量缓存
```

### Interface Contracts

#### CLI Interface (扩展现有 cli.py)

```python
# cli.py 新增命令组
orchestrator_app = typer.Typer(help="Multi-branch orchestration")
app.add_typer(orchestrator_app, name="orchestrator")

@orchestrator_app.command("run")
def orchestrator_run(
    run_id: str,
    num_branches: int = 3,  # 默认 3 个分支
    max_iterations: int = 5,  # 最多 5 轮
    max_cost_usd: float = 10.0,  # 最大成本
    enable_docker: bool = False,  # 是否启用 Docker（Phase 3）
):
    """Run multi-branch experiment orchestration."""
    pass
```

#### Python API

```python
# src/orchestrator/branch_orchestrator.py
class BranchOrchestrator:
    def run(
        self,
        spec: ResearchSpec,
        plan: ExperimentPlan,
        config: OrchestratorConfig,
    ) -> ExperimentResult:
        """执行多分支实验。"""
        pass
```

---

## Phase 2: Implementation Strategy

### Phase 2A: 核心架构（P1）

**目标**：实现 BranchOrchestrator、Planner/Critic、基础并行执行

**任务**：
1. 定义所有 Pydantic schemas（`src/schemas/orchestrator.py`）
2. 实现 BranchOrchestrator 框架（`src/orchestrator/branch_orchestrator.py`）
3. 实现 Planner Agent（`src/agents/planner/planner_agent.py`）
4. 实现 Critic Agent（`src/agents/planner/critic_agent.py`）
5. 实现 Executor（复用现有 ToolAgent，扩展支持 Planner 输出）
6. 实现分支并行执行（multiprocessing）
7. 实现分支变体生成（基于 ExperimentPlan）
8. 单元测试（每个模块独立测试）

**验收标准**：
- 3 个分支能并行执行
- Planner-Executor-Critic 循环正常工作
- 最多 5 轮，早停机制生效

### Phase 2B: 智能调度（P2）

**目标**：实现 Budget Scheduler 和 Experiment Memory

**任务**：
1. 实现 BudgetScheduler（`src/scheduler/budget_scheduler.py`）
2. 实现早停策略（连续 2 次无改进）
3. 实现 ExperimentMemory（`src/memory/experiment_memory.py`）
4. 实现语义相似度检索（sentence-transformers）
5. 实现失败报告生成（`src/orchestrator/report_generator.py`）
6. 实现全局知识库和分支本地记忆的读写分离
7. 实现 run 结束后的记忆汇总
8. 集成测试（完整流程测试）

**验收标准**：
- Budget Scheduler 能动态调整预算
- 早停策略正确触发
- 记忆检索返回相似案例
- 失败分支生成实验报告

### Phase 2C: 安全强化（P1）

**目标**：实现 Docker 容器隔离

**任务**：
1. 实现 DockerSandbox（`src/sandbox/docker_sandbox.py`）
2. 容器生命周期管理（创建、启动、停止、清理）
3. 资源限制配置（CPU、内存、磁盘）
4. 网络隔离配置
5. 卷挂载和工作空间管理
6. 依赖安装（根据 requirements.txt）
7. 错误处理和容器清理
8. 安全测试（危险命令检测、资源限制验证）

**验收标准**：
- 每个分支在独立容器中运行
- 资源限制生效
- 危险命令被阻止
- 容器正确清理（无泄漏）

---

## Testing Strategy

### Unit Tests
- 每个模块独立测试（Planner、Critic、Scheduler、Memory）
- Mock LLM 调用
- Mock Docker 容器

### Integration Tests
- 完整的 Planner-Executor-Critic 循环
- 多分支并行执行
- 记忆检索和汇总
- Docker 容器隔离

### End-to-End Tests
- 使用真实 LLM API（小规模测试）
- 使用真实 Docker 容器
- 验证完整流程（从 ResearchSpec 到 ExperimentResult）

---

## Risks & Mitigations

| 风险 | 影响 | 缓解措施 |
|------|------|---------|
| Docker 容器开销影响性能 | 高 | 实测性能，优化容器配置，考虑容器复用 |
| LLM API 限流导致分支阻塞 | 中 | 配置 rate limit，实现重试机制，考虑降级到 2 个分支 |
| 记忆检索性能瓶颈 | 低 | 使用轻量级模型，缓存嵌入向量，后续可升级到向量数据库 |
| 分支间资源竞争 | 中 | 使用进程隔离，配置资源限制，监控资源使用 |
| 容器清理失败导致资源泄漏 | 中 | 使用 context manager，实现清理脚本，监控容器数量 |

---

## Dependencies & Prerequisites

**外部依赖**：
- Docker Engine（本地或云端）
- Python 3.11+
- 足够的系统资源（至少 8GB RAM，推荐 16GB）

**内部依赖**：
- Spec 001: ResearchSpec 格式稳定 ✅
- Spec 002: ExperimentPlan 格式稳定 ✅
- 现有 LLMClient ✅
- 现有 ArtifactStore ✅

---

## Rollout Plan

### Phase 1: MVP（2 周）
- 实现 Phase 2A（核心架构）
- 不启用 Docker（使用现有 subprocess sandbox）
- 支持 2-3 个分支并行
- 基础的 Planner-Critic 循环

### Phase 2: 完整功能（2 周）
- 实现 Phase 2B（智能调度）
- 实现 Phase 2C（Docker 隔离）
- 完整的记忆检索和报告生成
- 端到端测试

### Phase 3: 优化与监控（1 周）
- 性能优化
- 监控和日志完善
- 文档和示例
- 用户反馈收集

---

## Success Metrics

- [ ] 多分支并行搜索成功率 > 单分支（对比实验）
- [ ] 平均找到可行解的时间减少 30%+
- [ ] 预算利用率 > 80%
- [ ] 零安全事故（无宿主系统破坏）
- [ ] 单元测试覆盖率 > 80%
- [ ] 集成测试通过率 100%

---

## Next Steps

1. ✅ Spec 完成并澄清
2. ✅ Plan 完成
3. ⏭️ 生成 tasks.md（`/speckit.tasks`）
4. ⏭️ 开始实现（`/speckit.implement`）

---

## Appendix

### Configuration Example

```yaml
# configs/execution.yaml
orchestrator:
  num_branches: 3
  max_iterations: 5
  early_stop_threshold: 2  # 连续 2 次无改进

budget:
  max_cost_usd: 10.0
  max_time_seconds: 3600
  max_tokens_per_branch: 50000

docker:
  enabled: false  # Phase 3 启用
  image: "python:3.11-slim"
  mem_limit: "2g"
  cpu_quota: 100000

memory:
  embedding_model: "all-MiniLM-L6-v2"
  top_k: 5
  similarity_threshold: 0.7
```

### Quickstart Example

```python
from src.orchestrator import BranchOrchestrator
from src.schemas import ResearchSpec, ExperimentPlan, OrchestratorConfig

# 加载 spec 和 plan
spec = ResearchSpec.from_file("runs/run_001/research_spec.json")
plan = ExperimentPlan.from_file("runs/run_001/experiment_plan.md")

# 配置
config = OrchestratorConfig(
    num_branches=3,
    max_iterations=5,
    max_cost_usd=10.0,
)

# 执行
orchestrator = BranchOrchestrator()
result = orchestrator.run(spec, plan, config)

print(f"Status: {result.status}")
print(f"Best code: {result.best_code_path}")
print(f"Total cost: ${result.total_cost_usd:.2f}")
```

---

**Plan Version**: 1.0.0
**Last Updated**: 2026-03-02
**Status**: Ready for Task Generation
