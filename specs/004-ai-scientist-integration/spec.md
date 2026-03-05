# Spec 004: AI-Scientist 外部专家集成

**版本**: 2.0.0
**状态**: Draft
**创建日期**: 2026-03-03
**负责人**: TBD

---

## 概述

将 **AI-Scientist** 作为"外部专家执行引擎"集成到 AiSci 系统中，**不替换现有 aisci 执行链**，而是作为可选的外部专家提供补充能力。

### 核心定位

- **AI-Scientist**: 外部专家执行引擎（异步任务模式）
- **AiSci**: 主控系统，负责任务调度、结果回传、后续精修
- **集成方式**: 子进程适配 + 异步任务 + 结果回传（MCP 放到第二阶段）

### 核心目标

1. **引擎路由**: 支持 `--engine aisci|ai-scientist|hybrid` 三种模式
2. **异步任务**: ai-scientist 模式启动异步任务，立即返回 job_id，不阻塞 CLI
3. **结果回传**: 将外部结果标准化为 `ExperimentResult(engine="ai-scientist")`
4. **Hybrid 模式**: 外部专家先跑，aisci 后精修（RevisionAgent + Orchestrator）

---

## 已确认的 6 个关键决策

### 决策 0: 本地大模型配置
- **模型**: Ollama + qwen3（测试阶段）
- **原因**: 本地运行，成本低，方便调试
- **后续**: 验证通过后可切换到 DeepSeek 或其他模型
- **配置**: 通过环境变量或配置文件指定模型名称

### 决策 1: 固定运行目录
- **路径**: `/Users/zeroyan/Desktop/AiProj/aisci/external/ai-scientist-runtime`
- **原因**: 统一管理，避免路径混乱

### 决策 2: 默认 Markdown 输出
- **参数**: `--writeup md`
- **原因**: 快速验证跑通结果，形式美化不重要
- **说明**: 测试阶段只用 md 格式，不使用 latex（避免复杂依赖）

### 决策 3: 验证阶段只跑 2-3 轮
- **参数**: `--num-ideas 2` 或 `--num-ideas 3`
- **原因**: 默认 50 轮太长，验证阶段追求速度

### 决策 4: Hybrid 顺序与 Baseline 要求
- **顺序**: AiSci 生成 baseline → AI-Scientist 迭代改进 → AiSci 精修
- **原因**:
  - AI-Scientist 需要 `run_0/final_info.json` 作为对比基准（硬依赖）
  - 利用 AiSci 快速生成可运行的 baseline
  - 利用 AI-Scientist 的探索能力进行迭代改进
  - 最后用 AiSci 进行精细优化
- **实现**:
  - Phase 1: AiSci 运行 1 次迭代生成 baseline
  - Phase 2: 将 baseline 结果写入 `run_0/final_info.json`
  - Phase 3: AI-Scientist 基于 baseline 迭代改进
  - Phase 4: AiSci 继续优化

### 决策 5: 回调机制
- **第一版**: 文件事件 + 状态轮询
- **第二版**: HTTP webhook（规划中）

### 决策 6: 动态模板生成
- **方案**: 不做重模板绑定，使用通用模板骨架 `generic_ai_research_cn`
- **原因**: 课题可变，模板结构不变，支持任意课题

---

## Clarifications

### Session 2026-03-03

- Q: 当 AI-Scientist 异步任务失败时（如进程崩溃、OOM、API 限流），系统应该如何处理？ → A: 失败时立即标记 failed 并记录失败原因，不自动重试，系统可回退到 aisci 引擎继续运行
- Q: 对于状态轮询，需要明确轮询间隔和超时策略 → A: 可配置的轮询间隔和超时，生产环境默认 60s 轮询/24h 超时，测试环境默认 10s 轮询/2h 超时
- Q: 当用户同时提交多个 AI-Scientist 任务时，系统是否需要限制并发数量？ → A: 限制并发为 1-2 个任务，超出排队
- Q: 在 Hybrid 模式下，当 AI-Scientist 任务运行时，aisci 系统应该如何等待外部任务完成？ → A: 阻塞等待 + 定期输出进度（如每分钟）
- Q: AI-Scientist 版本兼容性策略 → A: 锁定特定版本，文档说明支持的版本

---

## 用户故事

### US-1: 引擎路由选择（P1）
**作为** 科研人员
**我希望** 可以选择使用不同的执行引擎
**以便** 根据任务特点选择最合适的工具

**验收标准**:
- [ ] CLI 支持 `--engine aisci|ai-scientist|hybrid` 参数
- [ ] `aisci` 模式：使用现有 ExperimentLoop（默认）
- [ ] `ai-scientist` 模式：启动异步任务，返回 job_id
- [ ] `hybrid` 模式：三阶段流程
  - Phase 1: AiSci 生成 baseline（1 次迭代）
  - Phase 2: AI-Scientist 基于 baseline 迭代改进
  - Phase 3: AiSci 继续精修

**重要说明**:
- AI-Scientist 需要 `run_0/final_info.json` 作为 baseline（硬依赖）
- Hybrid 模式会自动生成 baseline，无需手动准备
- Baseline 格式要求：
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

---

### US-2: 异步任务管理（P1）
**作为** 科研人员
**我希望** AI-Scientist 任务不阻塞 CLI
**以便** 可以继续其他工作

**验收标准**:
- [ ] `run start --engine ai-scientist` 立即返回 job_id
- [ ] 新增 CLI 命令：`run external-status <run_id>` 查看任务状态
- [ ] 新增 CLI 命令：`run external-fetch <run_id>` 获取结果
- [ ] 任务状态包括：pending/running/completed/failed
- [ ] 失败时记录详细错误信息（进程退出码、stderr、异常堆栈）
- [ ] 失败后不自动重试，可选回退到 aisci 引擎继续运行

---

### US-3: 结果标准化与回传（P1）
**作为** 系统集成者
**我希望** 外部结果能标准化为统一格式
**以便** 后续处理和对比

**验收标准**:
- [ ] 解析 AI-Scientist 输出目录 `results/<template>/<timestamp>_<idea>/`
- [ ] 提取：report.md、run_*/final_info.json、图表、代码
- [ ] 转换为 `ExperimentResult(engine="ai-scientist")`
- [ ] 落盘到 `runs/<run_id>/external/ai_scientist/`

---

### US-4: Hybrid 模式精修（P1）
**作为** 科研人员
**我希望** 外部专家结果能被 aisci 进一步优化
**以便** 获得更好的最终结果

**验收标准**:
- [ ] Hybrid 模式：先运行 ai-scientist（阻塞等待）
- [ ] 等待期间定期输出进度（每分钟更新状态）
- [ ] 将外部结果喂给 RevisionAgent 生成修订建议
- [ ] 使用 Orchestrator 继续运行 aisci 引擎
- [ ] 生成对比报告（外部 vs aisci）

---

### US-5: 动态模板生成（P2）
**作为** 系统集成者
**我希望** 根据 ResearchSpec 动态生成模板
**以便** 支持任意课题而不绑定特定模板

**验收标准**:
- [ ] 创建通用模板骨架 `generic_ai_research_cn`
- [ ] 根据 ResearchSpec 动态生成：
  - `prompt.json`（研究目标）
  - `seed_ideas.json`（2-3 个 idea）
  - `experiment.py`（统一接口）
  - `plot.py`（标准图）
- [ ] 复制到 `external/ai-scientist-runtime/templates/<dynamic_name>/`

---

## 功能需求

### FR-1: 引擎路由器
**模块**: `cli.py`

**接口设计**:
```python
@run_app.command("start")
def run_start(
    run_id: str,
    engine: str = typer.Option("aisci", help="aisci|ai-scientist|hybrid"),
    num_ideas: int = typer.Option(2, help="AI-Scientist ideas count"),
    writeup: str = typer.Option("md", help="md|latex"),
    ...
):
    """Start experiment with specified engine."""
    if engine == "aisci":
        # 使用现有 ExperimentLoop
        pass
    elif engine == "ai-scientist":
        # 启动异步任务
        job_id = ai_scientist_adapter.submit_job(...)
        typer.echo(f"Job submitted: {job_id}")
    elif engine == "hybrid":
        # 先跑外部，再跑 aisci
        pass
```

---

### FR-2: AI-Scientist 适配器
**模块**: `src/integrations/ai_scientist/adapter.py`

**职责**:
- 检查 AI-Scientist 安装状态
- 拼接命令行参数
- 启动子进程（异步）
- 检查 venv 环境

**接口**:
```python
class AIScientistAdapter:
    def __init__(self, runtime_dir: Path):
        self.runtime_dir = runtime_dir

    def is_installed(self) -> bool:
        """Check if AI-Scientist is installed."""
        pass

    def submit_job(
        self,
        template: str,
        num_ideas: int,
        writeup: str,
        model: str,
    ) -> str:
        """Submit async job, return job_id."""
        pass

    def get_status(self, job_id: str) -> JobStatus:
        """Get job status."""
        pass

    def cancel_job(self, job_id: str) -> bool:
        """Cancel running job."""
        pass
```

---

### FR-3: 任务存储
**模块**: `src/integrations/ai_scientist/job_store.py`

**职责**:
- 记录 job_id/pid/status/log_path/start_time/end_time
- 持久化到 `runs/<run_id>/external/jobs.jsonl`
- 并发控制：限制最多 1-2 个任务同时运行，超出排队

**数据结构**:
```python
@dataclass
class JobRecord:
    job_id: str
    run_id: str
    pid: int
    status: Literal["pending", "running", "completed", "failed"]
    log_path: str
    start_time: datetime
    end_time: datetime | None
    error: str | None
```

**并发控制**:
- 最大并发数：2（可配置）
- 超出并发限制的任务状态为 `pending`，等待运行中任务完成

---

### FR-4: 结果解析器
**模块**: `src/integrations/ai_scientist/result_parser.py`

**职责**:
- 解析 `results/<template>/<timestamp>_<idea>/` 目录
- 提取 report.md、final_info.json、图表、代码
- 转换为 `ExperimentResult`

**接口**:
```python
class ResultParser:
    def parse_result_dir(self, result_dir: Path) -> ExperimentResult:
        """Parse AI-Scientist output directory."""
        pass

    def extract_artifacts(self, result_dir: Path) -> list[str]:
        """Extract artifact paths (plots, code, report)."""
        pass
```

---

### FR-5: Spec 映射器
**模块**: `src/integrations/ai_scientist/spec_mapper.py`

**职责**:
- ResearchSpec → 模板任务包（template_name + prompt.json + seed_ideas.json）
- 动态生成通用模板

**接口**:
```python
class SpecMapper:
    def map_to_template_package(
        self,
        spec: ResearchSpec,
        plan: ExperimentPlan | None,
    ) -> TemplatePackage:
        """Map ResearchSpec to template package."""
        pass

    def generate_dynamic_template(
        self,
        spec: ResearchSpec,
        output_dir: Path,
    ) -> str:
        """Generate dynamic template, return template_name."""
        pass
```

**TemplatePackage**:
```python
@dataclass
class TemplatePackage:
    template_name: str
    prompt_json: dict
    seed_ideas_json: list[dict]
    runtime_args: dict  # num_ideas, writeup, model, etc.
```

---

### FR-6: 回调机制
**模块**: `src/integrations/ai_scientist/callbacks.py`

**职责**:
- 文件事件监听（第一版）
- 状态轮询（可配置间隔和超时）
- 任务完成通知

**配置参数**:
- 生产环境：60s 轮询间隔，24h 超时
- 测试环境：10s 轮询间隔，2h 超时

**接口**:
```python
class JobCallbacks:
    def watch_job(self, job_id: str, callback: Callable, poll_interval: int = 60, timeout: int = 86400):
        """Watch job status, call callback on completion.

        Args:
            poll_interval: Polling interval in seconds (default: 60s for production)
            timeout: Timeout in seconds (default: 86400s = 24h)
        """
        pass

    def poll_status(self, job_id: str, interval: int = 60):
        """Poll job status every N seconds (default: 60s)."""
        pass
```

---

## 数据流

### 最小闭环（第一版）

```
用户输入
    ↓
CLI: run start --engine ai-scientist
    ↓
SpecMapper: ResearchSpec → TemplatePackage
    ↓
Adapter: 动态生成模板 → external/ai-scientist-runtime/templates/<name>/
    ↓
Adapter: 启动子进程 → launch_scientist.py
    ↓
JobStore: 记录 job_id/pid/status
    ↓
CLI: 返回 job_id（不阻塞）
    ↓
用户: run external-status <run_id>（查看状态）
    ↓
Callbacks: 文件事件监听 + 状态轮询
    ↓
任务完成
    ↓
ResultParser: 解析 results/<template>/<timestamp>_<idea>/
    ↓
转换为 ExperimentResult(engine="ai-scientist")
    ↓
落盘到 runs/<run_id>/external/ai_scientist/
    ↓
用户: run external-fetch <run_id>（获取结果）
```

### Hybrid 模式流程

```
用户输入
    ↓
CLI: run start --engine hybrid
    ↓
Step 1: 运行 ai-scientist（异步）
    ↓
等待完成 + 获取结果
    ↓
Step 2: 将外部结果喂给 RevisionAgent
    ↓
生成修订建议 → ExperimentPlan v+1
    ↓
Step 3: 使用 Orchestrator 运行 aisci 引擎
    ↓
Step 4: 生成对比报告
    ↓
输出：外部结果 + aisci 结果 + 对比分析
```

---

## 技术设计

### 目录结构

```
aisci/
├── external/
│   └── ai-scientist-runtime/          # 固定运行目录
│       ├── launch_scientist.py
│       ├── templates/
│       │   └── generic_ai_research_cn/  # 通用模板骨架
│       │       ├── prompt.json
│       │       ├── seed_ideas.json
│       │       ├── experiment.py
│       │       └── plot.py
│       └── results/                   # AI-Scientist 输出
│           └── <template>/
│               └── <timestamp>_<idea>/
│                   ├── report.md
│                   ├── run_0/final_info.json
│                   ├── plots/
│                   └── code/
├── src/
│   └── integrations/
│       └── ai_scientist/
│           ├── adapter.py             # 适配器
│           ├── job_store.py           # 任务存储
│           ├── result_parser.py       # 结果解析
│           ├── spec_mapper.py         # Spec 映射
│           └── callbacks.py           # 回调机制
└── runs/
    └── <run_id>/
        └── external/
            └── ai_scientist/
                ├── jobs.jsonl         # 任务记录
                ├── result.json        # ExperimentResult
                └── artifacts/         # 图表、代码、报告
```

### 命令行接口

```bash
# 1. 使用 ai-scientist 引擎（异步）
python cli.py run start exp001 --engine ai-scientist --num-ideas 2 --writeup md
# 输出: Job submitted: job_abc123

# 2. 查看任务状态
python cli.py run external-status exp001
# 输出: Status: running, Progress: 1/2 ideas completed

# 3. 获取结果
python cli.py run external-fetch exp001
# 输出: Result saved to runs/exp001/external/ai_scientist/

# 4. Hybrid 模式
python cli.py run start exp001 --engine hybrid --num-ideas 2
# 输出: Running ai-scientist... → Running aisci... → Comparison report generated

# 5. 取消任务
python cli.py run external-cancel exp001
# 输出: Job cancelled: job_abc123
```

---

## 实现优先级

### Phase 1: 最小闭环（P1）
**目标**: 打通异步任务 + 结果回传

**任务**:
- [ ] T001: 创建 `src/integrations/ai_scientist/` 模块结构
- [ ] T002: 实现 `AIScientistAdapter` 基础功能
- [ ] T003: 实现 `JobStore` 任务记录
- [ ] T004: 实现 `ResultParser` 结果解析
- [ ] T005: CLI 添加 `--engine` 参数
- [ ] T006: CLI 添加 `external-status` 命令
- [ ] T007: CLI 添加 `external-fetch` 命令
- [ ] T008: 端到端测试（ai-scientist 模式）

### Phase 2: 动态模板生成（P1）
**目标**: 支持任意课题

**任务**:
- [ ] T009: 创建 `generic_ai_research_cn` 通用模板骨架
- [ ] T010: 实现 `SpecMapper.map_to_template_package()`
- [ ] T011: 实现 `SpecMapper.generate_dynamic_template()`
- [ ] T012: 测试动态模板生成

### Phase 3: Hybrid 模式（P1）
**目标**: AiSci baseline → AI-Scientist 迭代 → AiSci 精修

**前置条件**:
- AI-Scientist 需要 `run_0/final_info.json` 作为 baseline（硬依赖）
- Baseline 必须包含可对比的指标（如 `{"experiment": {"means": {"score": 0.5}}}`）

**流程**:
1. **Phase 1: 生成 Baseline**
   - 使用 AiSci 运行 1 次迭代
   - 生成初始可运行代码和结果
   - 将结果写入 `run_0/final_info.json`

2. **Phase 2: AI-Scientist 迭代**
   - 准备模板（包含 baseline）
   - 提交 AI-Scientist 异步任务
   - 基于 baseline 生成改进想法并实验

3. **Phase 3: AiSci 精修**
   - 获取 AI-Scientist 最佳结果
   - 使用 RevisionAgent 继续优化
   - 生成最终对比报告

**任务**:
- [ ] T013: 实现 baseline 生成逻辑（AiSci 1 次迭代）
- [ ] T014: 实现模板准备（包含 baseline 写入）
- [ ] T015: 实现 hybrid 模式流程编排
- [ ] T016: 集成 RevisionAgent 进行精修
- [ ] T017: 生成三阶段对比报告
- [ ] T018: 端到端测试（hybrid 模式）

### Phase 4: 回调机制（P2）
**目标**: 任务完成自动通知

**任务**:
- [ ] T018: 实现文件事件监听
- [ ] T019: 实现状态轮询
- [ ] T020: 测试回调机制

---

## 非功能需求

### NFR-1: 隔离性
- AI-Scientist 代码放在 `external/ai-scientist-runtime/`
- 不修改 AI-Scientist 源码
- AI-Scientist 故障不影响 aisci 核心功能

### NFR-2: 性能
- 适配层开销 < 5%
- 结果转换延迟 < 1s
- 异步任务不阻塞 CLI

### NFR-3: 可维护性
- 适配层代码独立模块
- 清晰的接口文档
- 版本锁定：
  - 锁定特定 AI-Scientist 版本（通过 git submodule 或 requirements.txt）
  - 文档明确说明支持的版本（如 v1.2.0）
  - 升级前需验证兼容性

### NFR-4: 可测试性
- 单元测试覆盖率 > 80%
- 集成测试覆盖所有 CLI 命令
- 端到端测试覆盖 3 种引擎模式

---

## 成功指标

- [ ] AI-Scientist 集成成功率 > 95%
- [ ] 异步任务不阻塞 CLI（立即返回 job_id）
- [ ] 结果回传准确率 100%
- [ ] Hybrid 模式完成 5+ 案例验证
- [ ] 动态模板支持任意课题

---

## 风险与依赖

### 风险
- AI-Scientist 更新可能破坏兼容性（需版本锁定）
- 异步任务管理复���度（进程监控、状态同步）
- 动态模板生成可能不适配所有课题（需迭代优化）

### 依赖
- Spec 001: ResearchSpec 格式稳定
- Spec 003: ExperimentResult 格式统一
- AI-Scientist 代码库（`external/ai-scientist-runtime/`）
- Python subprocess 模块（异步任务）

---

## 第二阶段规划（MCP 路线）

### 目标
- 彻底解耦 aisci 和 AI-Scientist
- 通过 MCP 协议调用外部服务

### 架构
```
AiSci CLI
    ↓
MCP Client
    ↓
MCP Server (FastAPI)
    ↓
AIScientistAdapter
    ↓
external/ai-scientist-runtime
```

### MCP 工具
- `submit_job`: 提交任务
- `get_status`: 查看状态
- `get_result`: 获取结果
- `cancel_job`: 取消任务

---

## 参考资料

- AI-Scientist GitHub: https://github.com/SakanaAI/AI-Scientist
- AI-Scientist 论文: https://arxiv.org/abs/2408.06292
- Spec 001: ResearchSpec 定义
- Spec 003: ExperimentResult 定义

---

## 变更历史

| 版本 | 日期 | 变更内容 | 负责人 |
|------|------|----------|--------|
| 2.0.0 | 2026-03-03 | 重写规格，明确"外部专家"定位，添加异步任务、hybrid 模式、动态模板 | TBD |
| 1.0.0 | 2026-03-02 | 初始版本（已废弃） | TBD |
