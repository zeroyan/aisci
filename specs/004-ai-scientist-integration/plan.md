# Implementation Plan: AI-Scientist 外部专家集成

**Branch**: `004-ai-scientist-integration` | **Date**: 2026-03-04 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/004-ai-scientist-integration/spec.md`

**Note**: This plan has been updated to reflect the corrected Hybrid mode design (AiSci baseline → AI-Scientist → AiSci refinement).

## Summary

将 AI-Scientist 作为外部专家执行引擎集成到 AiSci 系统中，支持三种执行模式：
1. **aisci 模式**：使用现有 ExperimentLoop（默认）
2. **ai-scientist 模式**：异步调用外部 AI-Scientist
3. **hybrid 模式**：三阶段流程（AiSci 生成 baseline → AI-Scientist 迭代改进 → AiSci 精修）

核心技术方案：
- 子进程适配器（subprocess）启动 AI-Scientist
- 异步任务管理（job_id + 状态轮询）
- 结果标准化（ExperimentResult 统一格式）
- Baseline 自动生成（Hybrid 模式前置步骤）

## Technical Context

**Language/Version**: Python 3.11+（宪法约定）
**Primary Dependencies**:
- 现有：pydantic, litellm, typer, pyyaml, ruff
- 新增：psutil（进程管理）, watchdog（文件监听）
**Storage**: 文件系统（runs/<run_id>/external/jobs.jsonl）
**Testing**: pytest（现有测试框架）
**Target Platform**: macOS/Linux（开发环境）
**Project Type**: CLI 工具 + 集成适配层
**Performance Goals**:
- 适配层开销 < 5%
- 结果转换延迟 < 1s
- 异步任务不阻塞 CLI
**Constraints**:
- 不修改 AI-Scientist 源码（仅通过适配层调用）
- AI-Scientist 需要 run_0/final_info.json 作为 baseline（硬依赖）
- 并发限制：最多 1-2 个 AI-Scientist 任务同时运行
**Scale/Scope**:
- 支持 3 种引擎模式
- 5 个核心模块（adapter, job_store, result_parser, spec_mapper, callbacks）
- 3 个 CLI 命令（external-status, external-fetch, external-cancel）

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Gate A: Spec 完整性 ✅
- ✅ 功能需求齐全（5 个用户故事）
- ✅ 成功指标明确（集成成功率 > 95%）
- ✅ 验收标准可测试

### Gate B: Schema 定义 ✅
- ✅ JobRecord 已定义（src/schemas/ai_scientist.py）
- ✅ TemplatePackage 已定义
- ✅ ExperimentResult 已扩展（engine 字段）

### Gate C: 模块化架构 ✅
- ✅ 独立模块（src/integrations/ai_scientist/）
- ✅ 不破坏现有功能（aisci 引擎保持独立）
- ✅ 通过文件传递数据（jobs.jsonl, result.json）

### 安全执行 ⚠️ **需要关注**
- ⚠️ AI-Scientist 在子进程中运行，但未完全隔离
- ⚠️ 当前使用 subprocess + venv，计划升级为 Docker
- ✅ 设置超时和资源限制（通过配置）
- ✅ 保存中间结果和日志

**评估结果**: 通过，但需在实现中注意安全执行的改进路径。

## Project Structure

### Documentation (this feature)

```text
specs/004-ai-scientist-integration/
├── spec.md              # 功能规格（已完成）
├── plan.md              # 本文件（实施计划）
├── research.md          # Phase 0 输出（技术调研）
├── data-model.md        # Phase 1 输出（数据模型）
├── quickstart.md        # Phase 1 输出（快速开始）
├── contracts/           # Phase 1 输出（接口契约）
└── tasks.md             # Phase 2 输出（任务分解）
```

### Source Code (repository root)

```text
aisci/
├── src/
│   ├── integrations/
│   │   └── ai_scientist/
│   │       ├── __init__.py
│   │       ├── adapter.py           # AI-Scientist 适配器（已实现）
│   │       ├── job_store.py         # 任务存储（已实现）
│   │       ├── result_parser.py     # 结果解析器（已实现）
│   │       ├── spec_mapper.py       # Spec 映射器（待实现）
│   │       └── callbacks.py         # 回调机制（待实现）
│   ├── schemas/
│   │   ├── ai_scientist.py          # JobRecord, TemplatePackage（已实现）
│   │   └── experiment.py            # ExperimentResult 扩展（已实现）
│   └── [现有模块保持不变]
├── external/
│   └── ai-scientist-runtime/        # AI-Scientist 代码库
│       ├── launch_scientist.py      # 入口脚本（已修复 novel 字段）
│       ├── templates/
│       │   ├── generic_ai_research_cn/  # 通用模板（待完善）
│       │   └── ai_toy_research_cn/      # 示例模板（已有 baseline）
│       └── results/                 # AI-Scientist 输出
├── runs/
│   └── <run_id>/
│       └── external/
│           ├── jobs.jsonl           # 任务记录
│           ├── logs/                # 任务日志
│           └── ai_scientist/        # 结果存储
├── cli.py                           # CLI 入口（已扩展 --engine 参数）
├── tests/
│   └── integration/
│       └── test_ai_scientist_integration.py  # 集成测试（待完善）
└── docs/
    ├── ai_scientist_fixes.md        # 修复总结
    └── hybrid_mode_design.md        # Hybrid 模式设计
```

**Structure Decision**:
- 采用单项目结构（Option 1）
- 集成模块放在 `src/integrations/ai_scientist/`
- 外部代码放在 `external/ai-scientist-runtime/`
- 遵循宪法约定的目录结构

## Complexity Tracking

> **无宪法违规，此部分留空**

## Phase 0: Research & Technical Decisions

### 关键技术决策

#### 决策 1: 子进程 vs MCP 协议
**选择**: 子进程适配（第一版）
**理由**:
- 快速验证集成可行性
- 避免引入额外的网络层复杂度
- AI-Scientist 本身就是 CLI 工具，适合子进程调用

**替代方案**: MCP 协议（第二阶段）
- 更彻底的解耦
- 支持远程调用
- 但增加开发和维护成本

#### 决策 2: Hybrid 模式流程
**选择**: AiSci baseline → AI-Scientist → AiSci 精修
**理由**:
- AI-Scientist 需要 `run_0/final_info.json` 作为 baseline（硬依赖）
- AiSci 可以快速生成可运行的 baseline（1 次迭代）
- 利用 AI-Scientist 的探索能力进行迭代改进
- 最后用 AiSci 进行精细优化

**关键发现**: AI-Scientist 不是"零起步"架构，而是"在模板+baseline 上迭代改进"

#### 决策 3: Baseline 格式
**选择**:
```json
{
  "experiment": {
    "means": {
      "metric1": 0.5,
      "metric2": 0.8
    }
  }
}
```
**理由**:
- AI-Scientist 源码硬编码读取此格式（launch_scientist.py:185）
- 必须包含 `experiment.means` 结构
- 指标名称需与实验代码输出一致

#### 决策 4: 并发控制策略
**选择**: 最多 1-2 个任务同时运行，超出排队
**理由**:
- AI-Scientist 任务资源消耗大（LLM 调用 + 实验运行）
- 避免系统过载
- 提供排队机制保证任务最终执行

**实现**:
- 先检查并发限制，再启动进程
- 任务完成后自动启动排队任务
- 使用 `_try_start_pending_job()` 方法调度

#### 决策 5: API Key 管理
**选择**: 环境变量（DEEPSEEK_API_KEY）
**理由**:
- 符合宪法安全约束
- 避免硬编码泄露
- 支持不同环境配置

**已修复**: 移除硬编码 API key，强制从环境变量读取

### 技术风险与缓解

| 风险 | 影响 | 缓解措施 | 状态 |
|------|------|----------|------|
| AI-Scientist 版本兼容性 | 高 | 锁定特定版本，文档说明 | ✅ 已实施 |
| Baseline 质量差 | 中 | 允许配置迭代次数（默认 1） | 📋 待实施 |
| 结果路径不匹配 | 高 | 使用 `results/<experiment>/` 路径 | ✅ 已修复 |
| 并发控制失效 | 中 | 先检查再启动，自动调度 | ✅ 已修复 |
| API Key 泄露 | 高 | 环境变量 + 日志脱敏 | ✅ 已修复 |

## Phase 1: Data Model & Contracts

### 核心实体

#### 1. JobRecord
**用途**: 记录 AI-Scientist 异步任务状态

```python
@dataclass
class JobRecord:
    job_id: str              # UUID
    run_id: str              # 关联的实验 run
    pid: int | None          # 进程 ID（pending 时为 None）
    status: JobStatus        # pending/running/completed/failed
    log_path: str            # 日志文件路径
    start_time: datetime     # 提交时间
    end_time: datetime | None  # 完成时间
    error: str | None        # 错误信息
    template_name: str       # 使用的模板名称
    num_ideas: int           # 生成的 idea 数量
```

**状态转换**:
```
pending → running → completed
                 → failed
```

**持久化**: `runs/<run_id>/external/jobs.jsonl`（每行一个 JSON 对象）

#### 2. TemplatePackage
**用途**: 封装动态生成的模板信息

```python
@dataclass
class TemplatePackage:
    template_name: str       # 模板名称（如 generic_ai_research_cn）
    prompt: dict             # prompt.json 内容
    seed_ideas: list[dict]   # seed_ideas.json 内容
    experiment_code: str     # experiment.py 代码
    plot_code: str | None    # plot.py 代码
```

#### 3. ExperimentResult 扩展
**用途**: 统一不同引擎的结果格式

```python
@dataclass
class ExperimentResult:
    # 现有字段...
    engine: str = "aisci"    # 新增：引擎标识
    external_metadata: dict | None = None  # 新增：外部引擎元数据
```

### 接口契约

#### CLI 命令契约

**1. run start --engine <mode>**
```bash
# 输入
python cli.py run start <run_id> \
  --engine aisci|ai-scientist|hybrid \
  --num-ideas 2 \
  --writeup md \
  --model deepseek-chat

# 输出（ai-scientist/hybrid 模式）
Job submitted: <job_id>
Check status with: python cli.py run external-status <run_id>

# 输出（aisci 模式）
[现有输出保持不变]
```

**2. run external-status <run_id>**
```bash
# 输入
python cli.py run external-status <run_id>

# 输出
External jobs for run <run_id>:

Job ID: <job_id>
  Status: running
  Progress: 1/2 ideas
  Elapsed: 120s
  Log: runs/<run_id>/external/logs/<job_id>.log
```

**3. run external-fetch <run_id>**
```bash
# 输入
python cli.py run external-fetch <run_id>

# 输出
Fetching results for job <job_id>...
✓ Results saved to runs/<run_id>/external/ai_scientist/
  Best code: runs/<run_id>/external/ai_scientist/code/experiment.py
  Report: runs/<run_id>/external/ai_scientist/report.md
  Metrics: {"accuracy": 0.85, "loss": 0.15}
```

**4. run external-cancel <run_id>**
```bash
# 输入
python cli.py run external-cancel <run_id>

# 输出
Cancelled job <job_id>
```

#### AI-Scientist 适配器契约

**AIScientistAdapter.submit_job()**
```python
def submit_job(
    run_id: str,
    spec: ResearchSpec,
    model: str,
    num_ideas: int,
    writeup: str,
    job_store: JobStore,
) -> str:
    """Submit AI-Scientist job.

    Returns:
        job_id (str): UUID of submitted job

    Raises:
        ValueError: If DEEPSEEK_API_KEY not set
        FileNotFoundError: If AI-Scientist runtime not found
    """
```

**AIScientistAdapter.get_status()**
```python
def get_status(
    job: JobRecord,
    job_store: JobStore,
) -> dict:
    """Get job status.

    Returns:
        {
            "status": "running",
            "progress": "1/2 ideas",
            "elapsed_time": "120s",
            "log_path": "...",
            "error": None
        }
    """
```

### Baseline 生成契约

**Hybrid 模式 Phase 1: Baseline 生成**
```python
# 输入
spec: ResearchSpec
plan: ExperimentPlan
max_iterations: int = 1

# 输出
baseline_result: ExperimentResult
baseline_info: dict = {
    "experiment": {
        "means": {
            "metric1": float,
            "metric2": float,
            ...
        }
    }
}

# 写入
template_dir / "run_0" / "final_info.json"
```

## Phase 2: Implementation Strategy

### MVP 范围（Phase 1-5）

**已完成**:
- ✅ 基础模块结构（adapter, job_store, result_parser）
- ✅ CLI 引擎路由（--engine 参数）
- ✅ 异步任务管理（submit_job, get_status, cancel_job）
- ✅ 结果标准化（ExperimentResult 扩展）
- ✅ 并发控制（先检查再启动 + 自动调度）
- ✅ 关键 Bug 修复（API key, novel 字段, 路径错误）

**待完成**:
- 📋 Hybrid 模式实现（baseline 生成 + 模板准备 + 精修）
- 📋 SpecMapper 实现（动态模板生成）
- 📋 Callbacks 实现（状态轮询 + 文件监听）
- 📋 完整的端到端测试

### 实现顺序

**Phase 6: Hybrid 模式（优先级 P1）**
1. T055-T057: Baseline 生成逻辑
2. T058-T061: 模板准备逻辑
3. T062-T065: AI-Scientist 执行与等待
4. T066-T070: AiSci 精修与对比报告

**Phase 7: 动态模板生成（优先级 P2）**
1. T064-T067: 通用模板骨架
2. T068-T075: SpecMapper 实现

**Phase 8: Polish & Integration**
1. T076-T079: 端到端测试
2. T080-T082: 文档完善
3. T083-T085: 性能优化

### 关键路径

```
Baseline 生成 → 模板准备 → AI-Scientist 执行 → 结果获取 → AiSci 精修
     ↓              ↓              ↓              ↓              ↓
  1 次迭代    写 run_0/      异步任务      ResultParser   RevisionAgent
             final_info                                  + Orchestrator
```

## Testing Strategy

### 单元测试
- adapter.py: 命令拼接、进程启动、状态检查
- job_store.py: 并发控制、持久化、状态转换
- result_parser.py: 目录解析、格式转换

### 集成测试
- CLI 命令：3 种引擎模式
- 异步任务：提交、查询、取消
- 结果回传：解析、转换、落盘

### 端到端测试
- Scenario 1: ai-scientist 模式（使用 ai_toy_research_cn）
- Scenario 2: hybrid 模式（完整三阶段流程）
- Scenario 3: 并发限制（提交 3 个任务，验证排队）
- Scenario 4: 失败处理（模拟 API 错误、进程崩溃）

## Rollout Plan

### Phase 1: MVP 验证（当前）
- 使用 ai_toy_research_cn 模板测试
- 验证 ai-scientist 模式基本功能
- 修复关键 Bug

### Phase 2: Hybrid 模式开发
- 实现 baseline 生成
- 实现模板准备
- 实现三阶段流程

### Phase 3: 生产就绪
- 完善错误处理
- 添加监控和日志
- 性能优化

### Phase 4: 扩展功能
- 动态模板生成
- MCP 协议支持
- 更多模板支持

## Success Metrics

- ✅ AI-Scientist 集成成功率 > 95%
- ✅ 异步任务不阻塞 CLI（立即返回 job_id）
- ✅ 结果回传准确率 100%
- 📋 Hybrid 模式完成 5+ 案例验证
- 📋 动态模板支持任意课题

## References

- [Spec 004](./spec.md)
- [AI-Scientist GitHub](https://github.com/SakanaAI/AI-Scientist)
- [修复总结](../../docs/ai_scientist_fixes.md)
- [Hybrid 模式设计](../../docs/hybrid_mode_design.md)
- [宪法](../../.specify/memory/constitution.md)
