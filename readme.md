## aisci

这个仓库用于构建一个参考 FARS 思路的多 Agent 科研系统（MVP）。

## 功能模块

### Phase 1A: 实验执行循环（已完成）
- Tool-use agent 模式：LLM 自主调用工具（write_file/run_bash/read_file/finish）
- 实验迭代循环：自动生成代码、执行、分析结果
- 沙箱执行：subprocess + venv 隔离

### Phase 1B: 方案生成与知识库（开发中）
- 知识库：两层 MD 文件缓存（scientist/ 全局 + runs/<run_id>/knowledge/ 本地）
- 网络检索：Tavily + arxiv + semanticscholar + trafilatura
- 方案生成：ResearchSpec → ExperimentPlan（MD 文档）
- 方案修订：实验报告 → 人机协同修订方案

## 文档入口

1. [FARS_落地操作手册](./docs/FARS_落地操作手册.md)
2. [AI-Scientist_代码解读与接入建议](./docs/AI-Scientist_代码解读与接入建议.md)

## 使用示例

```bash
# 创建实验 run
python cli.py run create --spec-file specs/001-research-copilot-mvp/spec.json

# 启动实验
python cli.py run start <run_id>

# 查看状态
python cli.py run status <run_id>

# 生成报告
python cli.py run report <run_id>
```

## 当前状态

1. 已接入 `.specify` 工作流（用于 `spec/plan/tasks` 管理）。
2. 已拉取 `SakanaAI/AI-Scientist` 到 `external/ai-scientist` 供本地集成与改造。
3. Phase 1A 完成：45 测试全部通过
4. Phase 1B 进行中：知识库 + 方案生成

## 下一步

1. 完成 Phase 1B：方案修订循环 + CLI 命令
2. Phase 1C：选题发现（多源选题与候选课题生成）
3. Phase 2：论文写作、自动审稿、方法论沉淀
