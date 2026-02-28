# Implementation Plan: AI 自主实验闭环 (Phase 1A)

**Branch**: `001-research-copilot-mvp` | **Date**: 2026-02-28 | **Spec**: `/specs/001-research-copilot-mvp/spec.md`
**Input**: Feature specification from `/specs/001-research-copilot-mvp/spec.md`

## Summary

实现 AI 自主实验最小闭环：给定已确认的 ResearchSpec（± ExperimentPlan），
AI Agent 在沙箱中自主执行"生成代码 → 运行 → 分析 → 决策"循环，
命中停止条件后输出可追溯的 ExperimentReport。

技术方案：Python CLI 应用，Pydantic 做契约校验，litellm 统一 LLM 调用，
subprocess + venv 做 MVP 沙箱，文件系统做工件持久化。

## Technical Context

**Language/Version**: Python 3.11+（宪法约定）
**Primary Dependencies**: pydantic, litellm, typer, pyyaml, ruff
**Storage**: 文件系统（JSON/日志，`runs/<run_id>/` 目录结构）
**Testing**: pytest + pytest-cov
**Target Platform**: macOS / Linux（本地 CLI）
**Project Type**: CLI 工具
**Performance Goals**: 单次迭代 ≤30 分钟（SC-003）
**Constraints**: 单次 run 成本 ≤$50 USD（可配置），最大迭代次数可配置
**Scale/Scope**: 单用户单 run，MVP 阶段无并发需求

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| 原则 | 状态 | 说明 |
|------|------|------|
| 一、模块化架构 | ✅ PASS | 6 个独立模块（schemas/agents/sandbox/llm/storage/service），模块间通过 JSON 文件传递 |
| 二、Schema 先行 | ✅ PASS | `contracts.md` 已定义全部数据结构，Pydantic models 做运行时校验 |
| 三、安全执行 | ✅ PASS | 沙箱隔离执行 + 超时 + 资源上限 + 强制终止，MVP 用 subprocess+venv，后续升级 Docker |
| Python 环境管理 | ✅ PASS | `.venv/` 固定路径，requirements.txt 管理依赖 |
| Gate A（Spec 完整性） | ✅ PASS | spec.md 含 9 条 FR + 4 条 SC + 边界情况 |
| Gate B（Schema 定义） | ✅ PASS | contracts.md v1.1.0 完整定义数据/状态/错误/工件/服务契约 |
| Gate C（可运行验证） | ⏳ 待实现 | 实现后需至少 1 个端到端示例通过 |

**宪法违规**: 无。所有核心原则满足。

## Project Structure

### Documentation (this feature)

```text
specs/001-research-copilot-mvp/
├── plan.md              # 本文件
├── research.md          # Phase 0 技术调研
├── data-model.md        # Phase 1 数据模型
├── spec.md              # 功能规格
├── contracts.md         # Phase 1A 补充契约
├── checklists/          # 验收检查清单
└── tasks.md             # 实现任务拆分（由 /speckit.tasks 生成）
```

### Source Code (repository root)

```text
aisci/
├── src/
│   ├── schemas/              # 领域模型（Pydantic models = 可执行 Schema）
│   │   ├── __init__.py
│   │   ├── research_spec.py  # ResearchSpec, ExperimentPlan
│   │   ├── experiment.py     # ExperimentIteration, ExperimentRun
│   │   ├── report.py         # ExperimentReport
│   │   ├── sandbox_io.py     # SandboxRequest, SandboxResponse, AgentDecision
│   │   ├── errors.py         # AiSciError 统一错误结构
│   │   └── state.py          # ExperimentRun 状态机
│   │
│   ├── agents/               # 能力模块
│   │   └── experiment/       # Phase 1A 实验 Agent
│   │       ├── __init__.py
│   │       ├── loop.py       # plan→codegen→execute→analyze→decide 主循环
│   │       ├── codegen.py    # LLM 生成/修改实验代码
│   │       └── analyzer.py   # LLM 分析结果 + 做决策
│   │
│   ├── sandbox/              # 沙箱执行层
│   │   ├── __init__.py
│   │   ├── base.py           # SandboxExecutor 抽象基类
│   │   └── subprocess_sandbox.py  # MVP: subprocess + venv 实现
│   │
│   ├── llm/                  # LLM 调用抽象层
│   │   ├── __init__.py
│   │   └── client.py         # 统一调用接口 + 重试 + 降级 + cost 追踪
│   │
│   ├── storage/              # 工件存储层
│   │   ├── __init__.py
│   │   └── artifact.py       # runs/<run_id>/ 目录管理、JSON 读写
│   │
│   └── service/              # 服务接口层
│       ├── __init__.py
│       └── run_service.py    # CreateRun/StartRun/ControlRun/GetRun/GetRunReport
│
├── prompts/                  # Agent 系统提示词
│   ├── codegen_system.md     # 代码生成提示词
│   └── analyzer_system.md    # 结果分析提示词
│
├── configs/                  # 配置
│   └── default.yaml          # 默认配置（模型、预算、超时、重试策略）
│
├── cli.py                    # CLI 入口（typer）
│
├── tests/
│   ├── unit/                 # 单元测试
│   ├── integration/          # 集成测试
│   ├── contract/             # 契约校验测试
│   └── fixtures/             # 测试用 spec/plan JSON 样例
│
├── runs/                     # 运行产物（.gitignore）
├── requirements.txt          # 运行依赖
└── requirements-dev.txt      # 开发依赖
```

**Structure Decision**: 采用宪法约定的 `src/` 单项目结构，Phase 1A 不含前端。
模块划分沿用宪法的 `agents/`、`llm/`、`schemas/` 命名，新增 `sandbox/`、`storage/`、`service/` 三个 Phase 1A 特有模块。`orchestrator/` 留给后续 Phase 的流水线编排。

## Complexity Tracking

> 无宪法违规，此节无需填写。

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| N/A | N/A | N/A |
