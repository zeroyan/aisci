AI SCI
## aisci

这个仓库用于构建一个参考 FARS 思路的多 Agent 科研系统（MVP）。

## 文档入口

1. [FARS_落地操作手册](./docs/FARS_落地操作手册.md)
2. [AI-Scientist_代码解读与接入建议](./docs/AI-Scientist_代码解读与接入建议.md)

## 当前状态

1. 已接入 `.specify` 工作流（用于 `spec/plan/tasks` 管理）。
2. 已拉取 `SakanaAI/AI-Scientist` 到 `external/ai-scientist` 供本地集成与改造。

## 下一步（推荐顺序）

1. 完成 `specs/001-.../spec.md` 与 `plan.md`。
2. 新建 `src/tools/experiment_runner.py`，封装 AI-Scientist 调用。
3. 跑通单题闭环（Planner -> Literature -> Experiment -> Writer -> Reviewer）。
