# Spec 003: 实验执行架构升级

**版本**: 1.0.0
**状态**: Draft
**创建日期**: 2026-03-02
**负责人**: TBD

---

## 概述

在 Spec 001（研究规格管理）和 Spec 002（实验方案生成）的基础上，本规格聚焦**实验执行层的架构升级**，引入多分支并行搜索、角色分离、预算调度和结构化记忆机制，提升实验探索的效率和质量。

**核心目标**：
- 从单线程执行升级为多分支并行搜索
- 分离 Planner（方案生成）和 Critic（评估反馈）角色
- 引入 Budget Scheduler 实现动态资源分配和早停
- 建立 Experiment Memory 记录探索历史和失败经验
- 强化安全隔离（命令白名单 → Docker 容器 → 资源限制）

**与现有功能的关系**：
- Spec 001: 提供 ResearchSpec 输入
- Spec 002: 提供 ExperimentPlan 输入
- Spec 003: **独立升级执行引擎**，不依赖外部集成

---

## Clarifications

### Session 2026-03-02

- Q: 分支初始化策略？ → A: 基于 ExperimentPlan 生成 N 个变体（不同超参/方法），每个分支一个变体。N 最多 3 个（考虑 token 消耗和系统负载）
- Q: Planner-Critic 循环终止条件？ → A: 固定最大轮次（5 轮）+ 早停（连续 2 次无改进则停止）。失败后生成实验报告，记录失败原因作为宝贵资源
- Q: 分支间知识共享机制？ → A: 只读共享全局知识库 + 分支本地写入（避免并发冲突）
- Q: Docker 容器镜像选择？ → A: Python 官方镜像 + 按需安装依赖（根据 requirements.txt）
- Q: 记忆检索相似度算法？ → A: 基于嵌入的语义相似度（具体实现后续优化）

---

## 用户故事

### US-1: 多分支并行搜索（P1）
**作为** 科研人员
**我希望** 系统能同时探索多个实验方向（不同超参、不同实现方案）
**以便** 在有限时间内找到更优解，而不是串行尝试

**验收标准**：
- [ ] 支持配置并行分支数（默认 3 个，最多 3 个分支，考虑 token 消耗）
- [ ] 基于 ExperimentPlan 生成分支变体（不同超参组合、不同实现方法）
- [ ] 每个分支独立运行，互不干扰（独立工作空间）
- [ ] 分支只读访问全局知识库，写入本地记忆（避免并发冲突）
- [ ] 支持动态调整分支优先级（根据中间结果）

---

### US-2: Planner 与 Critic 角色分离（P1）
**作为** 系统架构师
**我希望** 将"生成方案"和"评估反馈"解耦
**以便** 提升方案质量，支持多轮迭代优化

**验收标准**：
- [ ] Planner: 根据当前状态生成下一步行动方案（工具调用序列）
- [ ] Executor: 执行 Planner 生成的方案，返回结果
- [ ] Critic: 评估执行结果，给出反馈（成功/失败/需改进）
- [ ] 支持 Planner-Executor-Critic 循环（最多 5 轮）
- [ ] 早停机制：连续 2 次无改进则停止
- [ ] 失败后生成实验报告，记录失败原因和尝试过的方案

---

### US-3: Budget Scheduler 动态资源分配（P2）
**作为** 项目管理者
**我希望** 系统能根据分支表现动态分配计算预算
**以便** 避免在低效分支上浪费资源，提前终止无望方向

**验收标准**：
- [ ] 支持配置总预算（LLM tokens、执行时间、迭代次数）
- [ ] 根据分支中间结果动态调整预算分配
- [ ] 支持早停策略（连续 2 次失败、超时、预算耗尽）
- [ ] 记录预算使用情况（每个分支的成本）
- [ ] 失败分支生成实验报告（失败原因、尝试过的方案、建议）

---

### US-4: Experiment Memory 结构化记忆（P2）
**作为** 科研人员
**我希望** 系统能记录所有尝试过的方案、失败原因和成功经验
**以便** 避免重复错误，加速后续实验

**验收标准**：
- [ ] 记录每个分支的完整执行历史（代码变更、工具调用、结果）
- [ ] 记录失败案例和错误信息（结构化存储）
- [ ] 支持跨 run 的记忆检索（"之前是否尝试过类似方案"）
- [ ] 检索算法：基于嵌入的语义相似度（具体实现后续优化）
- [ ] 生成实验报告时自动引用记忆内容

---

### US-5: 安全隔离升级（P1）
**作为** 系统管理员
**我希望** 实验执行环境有多层安全防护
**以便** 防止恶意代码或错误命令破坏宿主系统

**验收标准**：
- [ ] 短期：增强命令白名单（检测危险模式如 `rm -rf /`）
- [ ] 中期：Docker 容器隔离（每个分支独立容器，基于 Python 官方镜像）
- [ ] 按需安装依赖（根据实验的 requirements.txt）
- [ ] 长期：资源限制（CPU、内存、磁盘、网络）
- [ ] 支持配置安全策略（严格模式 vs 宽松模式）

---

## 功能需求

### FR-1: BranchOrchestrator 编排器
- 管理多个并行分支的生命周期（创建、调度、终止）
- **分支初始化**：基于 ExperimentPlan 生成最多 3 个变体（不同超参组合、不同实现方法）
- 分配独立工作空间（`runs/<run_id>/branches/<branch_id>/`）
- **知识共享**：全局知识库只读访问，分支本地写入（避免并发冲突）
- 收集所有分支结果，汇总分支本地记忆到全局知识库
- **支持引擎抽象**：通过 `EngineAdapter` 接口支持不同执行引擎（自研/AI-Scientist）

### FR-2: Planner Agent
- 输入：当前状态（代码、结果、Critic 反馈）
- 输出：下一步行动方案（工具调用序列）
- 支持多轮规划（根据 Critic 反馈调整，最多 5 轮）
- 早停机制：连续 2 次无改进则停止当前分支

### FR-3: Critic Agent
- 输入：执行结果（代码输出、错误信息）
- 输出：评估反馈（成功/失败/需改进 + 具体建议）
- 支持多维度评估（正确性、效率、代码质量）

### FR-4: Budget Scheduler
- 跟踪每个分支的资源消耗（tokens、时间、迭代次数）
- 根据中间结果动态调整预算分配
- 实现早停策略（连续 2 次失败、超时、预算耗尽）
- 失败分支生成实验报告（失败原因、尝试历史、改进建议）

### FR-5: Experiment Memory
- 结构化存储：
  - 全局知识库：`scientist/knowledge/`（只读，所有 run 共享）
  - 分支本地记忆：`runs/<run_id>/branches/<branch_id>/memory/`（读写）
    - `attempts.jsonl`: 每次尝试的完整记录
    - `failures.jsonl`: 失败案例和错误信息
    - `successes.jsonl`: 成功案例和关键参数
- 支持检索接口（"查找类似失败案例"）
  - 检索算法：基于嵌入的语义相似度（具体实现后续优化）
- Orchestrator 汇总：run 结束后将分支记忆合并到全局知识库

### FR-6: 安全隔离层
- 命令白名单：检测危险命令模式
- Docker 容器：每个分支独立容器
  - 基础镜像：Python 官方镜像（如 `python:3.11-slim`）
  - 依赖安装：根据实验的 requirements.txt 按需安装
  - 网络隔离：默认无网络访问
  - 存储隔离：只挂载工作目录
- 资源限制：CPU、内存、磁盘、网络带宽
- 超时机制：单次执行、总执行时间

---

## 非功能需求

### NFR-1: 性能
- 多分支并行执行，总耗时目标：
  - P50: 不超过单分支的 1.3 倍
  - P95: 不超过单分支的 2.0 倍
- 分支间通信延迟目标：
  - P50: < 100ms
  - P95: < 500ms
- **注意**：实际性能受 LLM API 限流和容器开销影响，需实测调优

### NFR-2: 可扩展性
- 支持配置分支数（默认 3 个，最多 3 个分支）
- 支持插件化工具注册（Adaptive Tool Registry）

### NFR-3: 可观测性
- 实时显示每个分支的状态（运行中/成功/失败）
- 记录详细日志（每个分支独立日志文件）

### NFR-4: 安全性
- Docker 容器默认无网络访问（需显式配置）
- 禁止访问宿主文件系统（除挂载的工作目录）

---

## 技术设计要点

### 架构图
```
ResearchSpec + ExperimentPlan
         ↓
  BranchOrchestrator
         ↓
  ┌──────┴──────┬──────┬──────┐
Branch 1    Branch 2  Branch 3  ...
  ↓           ↓         ↓
Planner → Executor → Critic
  ↑           ↓         ↓
  └───── Feedback ──────┘
         ↓
  Budget Scheduler (动态调整)
         ↓
  Experiment Memory (记录)
         ↓
  Final Report (汇总)
```

### 数据流
1. **输入**: ResearchSpec + ExperimentPlan
2. **分支创建**: Orchestrator 创建 N 个分支，分配初始预算
3. **并行执行**: 每个分支独立运行 Planner-Executor-Critic 循环
4. **动态调度**: Scheduler 根据中间结果调整预算，终止低效分支
5. **记忆更新**: 每次尝试写入 Experiment Memory
6. **结果汇总**: Orchestrator 收集所有分支结果，生成报告

### 关键接口
- `BranchOrchestrator.run(spec, plan, config) -> BranchResults`
- `Planner.generate_plan(state, feedback) -> ActionPlan`
- `Critic.evaluate(result) -> Feedback`
- `BudgetScheduler.allocate(branches) -> BudgetAllocation`
- `ExperimentMemory.record(attempt) -> None`
- `ExperimentMemory.search(query) -> List[Attempt]`

### 统一结果格式（ExperimentResult）

为了支持多引擎（自研 + AI-Scientist），需定义统一的结果 schema：

```python
class ExperimentResult(BaseModel):
    """统一的实验结果格式，供所有执行引擎使用。"""

    run_id: str
    engine: Literal["aisci", "ai-scientist"]  # 执行引擎
    status: Literal["success", "failed", "timeout"]

    # 核心结果
    best_code_path: str | None  # 最佳代码版本路径
    metrics: dict[str, float]   # 实验指标（与 ResearchSpec.metrics 对应）
    artifacts: list[str]         # 生成的文件（图表、日志等）

    # 执行信息
    total_cost_usd: float
    total_time_seconds: float
    iterations: int

    # 可选：论文（AI-Scientist 特有）
    paper_latex: str | None = None
    paper_pdf: str | None = None

    # 元数据
    created_at: datetime
    engine_version: str  # 引擎版本（便于追溯）
```

**设计原则**：
- 字段最小化：只包含必需信息
- 引擎无关：两个引擎都能填充
- 可扩展：通过 `artifacts` 支持任意文件

---

## 实现优先级

**Phase 1: 核心架构（P1）**
- 定义 `ExperimentResult` 统一结果格式（供所有引擎使用）
- 定义 `EngineAdapter` 抽象接口（支持多引擎）
- BranchOrchestrator 基础框架
- Planner/Critic 角色分离
- 多分支并行执行

**Phase 2: 智能调度（P2）**
- Budget Scheduler
- 早停策略
- Experiment Memory

**Phase 3: 安全强化（P1）**
- Docker 容器隔离
- 资源限制
- 命令白名单增强

---

## 成功指标

- [ ] 多分支并行搜索成功率 > 单分支（对比实验）
- [ ] 平均找到可行解的时间减少 30%+
- [ ] 预算利用率 > 80%（避免浪费在低效分支）
- [ ] 零安全事故（无宿主系统破坏）

---

## 风险与依赖

**风险**：
- Docker 容器开销可能影响性能（需实测）
- 多分支并行可能导致 LLM API 限流（需配置 rate limit）

**依赖**：
- Spec 001: ResearchSpec 格式稳定
- Spec 002: ExperimentPlan 格式稳定
- Docker 环境（本地或云端）

---

## 参考资料

- AI-Scientist 论文: 多分支搜索、Ensemble Review
- OpenAI Function Calling: 工具调用模式
- Docker 安全最佳实践

---

## 变更历史

| 版本 | 日期 | 变更内容 | 负责人 |
|------|------|----------|--------|
| 1.0.0 | 2026-03-02 | 初始版本，定义核心架构升级方向 | TBD |
