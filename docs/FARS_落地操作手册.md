# FARS 项目落地操作手册（从 0 到 1）

> 目标：做一个参考 FARS 思路的“AI 科研流水线”，让多个 AI 协同完成：选题拆解、文献检索、实验执行、论文草稿、审稿复核。
>  
> 适用人群：不会从 0 搭科研 Agent 系统的个人开发者。
>  
> 当前日期基准：2026-02-27。

## 1. 先明确你要做的不是“全自动发论文”，而是“自动化研究助理”

第一版（MVP）必须控制目标，避免一上来做太大。

MVP 的成功定义（满足 4 条就算成功）：
1. 输入一个研究题目，系统能自动生成研究计划（spec）。
2. 系统能自动跑至少 1 条可复现实验（有日志和结果文件）。
3. 系统能自动生成一版论文草稿（Markdown 即可）。
4. 有“复核 agent”指出漏洞并打分，人类能决定是否采纳。

## 2. 推荐总架构

采用 4 层结构：

1. `Spec 层`：使用你仓库现有 `.specify` 模板和脚本管需求与任务。
2. `Agent 编排层`：5 个角色 agent（Planner / Literature / Experiment / Writer / Reviewer）。
3. `实验执行层`：接入 `SakanaAI/AI-Scientist`（先 v1，后 v2）。
4. `治理层`：证据追溯、人工闸门、失败重试。

一句话理解：`spec 管“做什么”`，`AI-Scientist 管“怎么做实验”`，`多 agent 管“谁先谁后如何协作”`。

## 3. 目录结构（先搭出来）

在仓库里建立下面结构：

```text
aisci/
├─ .specify/                      # 已存在，继续用
├─ docs/
│  ├─ FARS_落地操作手册.md
│  └─ operating_sop.md            # 日常操作SOP（后续生成）
├─ specs/                         # 由 .specify 流程自动创建
├─ external/
│  └─ ai-scientist/               # clone SakanaAI/AI-Scientist
├─ src/
│  ├─ orchestrator/               # 多agent编排
│  ├─ agents/                     # 各角色agent实现
│  ├─ tools/                      # 文献检索、实验调用、写作工具
│  └─ schemas/                    # 输入输出JSON Schema
├─ runs/                          # 每次实验运行结果
├─ prompts/                       # 系统提示词与角色提示词
├─ configs/                       # 模型、预算、重试策略
└─ readme.md
```

## 4. 环境准备（第 0 天）

## 4.1 系统依赖

建议：
1. Python 3.11+
2. Git
3. 建议 Docker（用于隔离实验）

检查命令：

```bash
python3 --version
git --version
docker --version
```

## 4.2 初始化 Python 环境（仓库根目录）

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

## 4.3 准备环境变量模板

新建 `.env.example`（后续你自己填 key）：

```env
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
GEMINI_API_KEY=
SERPAPI_API_KEY=
SEMANTIC_SCHOLAR_API_KEY=
MAX_BUDGET_USD=20
DEFAULT_MODEL=gpt-5
```

不要把真实 key 提交到 git。

## 5. 用你现有 `.specify` 工作流做“研究规格化”（第 1 天）

你的仓库已经有 `.specify/scripts/bash/*.sh`，直接用。

## 5.1 创建研究特性分支（建议）

```bash
git checkout -b 001-research-agent-mvp
```

## 5.2 创建 feature 目录（推荐脚本）

```bash
bash .specify/scripts/bash/create-new-feature.sh "Build FARS-like multi-agent research MVP"
```

执行后会在 `specs/001-.../` 生成规格目录。

## 5.3 初始化计划模板

```bash
bash .specify/scripts/bash/setup-plan.sh
```

## 5.4 检查前置文件是否齐全

```bash
bash .specify/scripts/bash/check-prerequisites.sh
```

## 5.5 必填文档（先写最小版）

在 `specs/001-.../` 中补齐：
1. `spec.md`：研究目标、范围、不做什么。
2. `plan.md`：技术路线、里程碑、风险。
3. `tasks.md`：可执行任务拆分（每项 ≤ 0.5 天）。

建议你在 `spec.md` 明确以下字段：
1. 研究问题（Question）
2. 假设（Hypothesis）
3. 成功指标（Metrics）
4. 数据与限制（Dataset & Constraints）
5. 交付物（Deliverables）

## 6. 接入 AI-Scientist（第 2 天）

## 6.1 拉取外部仓库

```bash
mkdir -p external
git clone https://github.com/SakanaAI/AI-Scientist external/ai-scientist
```

如果你后续要尝试 v2，再额外 clone：

```bash
git clone https://github.com/SakanaAI/AI-Scientist-v2 external/ai-scientist-v2
```

## 6.2 建议的集成方式（不要魔改上游）

原则：把上游当“黑盒执行器”，你只做适配层。

在你项目里新增：
1. `src/tools/experiment_runner.py`
2. `src/schemas/experiment_task.schema.json`
3. `src/schemas/experiment_result.schema.json`

`experiment_runner.py` 责任：
1. 接收标准化任务 JSON。
2. 组装 AI-Scientist 命令。
3. 执行并收集结果文件。
4. 输出标准化结果 JSON（含耗时、成本、指标、失败原因）。

## 6.3 先跑通一个“固定实验模板”

不要一开始开放探索。先固定：
1. 任务：单一小实验（例如文本分类 baseline 对比）。
2. 数据：一个小数据集（可快速重复）。
3. 指标：1-2 个（如 Accuracy/F1）。
4. 预算：严格限额。

通过标准：同一任务重跑 3 次，成功率 >= 80%。

## 7. 多 Agent 编排（第 3~4 天）

## 7.1 角色定义（固定 5 个）

1. `PlannerAgent`
输入：`spec.md`  
输出：`research_plan.json`

2. `LiteratureAgent`
输入：研究问题  
输出：`evidence_table.md`（文献、结论、证据等级）

3. `ExperimentAgent`
输入：`research_plan.json`  
输出：`experiment_result.json`

4. `WriterAgent`
输入：计划 + 文献 + 实验结果  
输出：`paper_draft.md`

5. `ReviewerAgent`
输入：`paper_draft.md` + 证据  
输出：`review_report.md`（问题列表+置信度）

## 7.2 编排顺序（先串行再并行）

第一版只做串行：
1. Planner -> Literature -> Experiment -> Writer -> Reviewer

稳定后再并行：
1. Literature 与 Experiment 并行
2. Writer 汇总
3. Reviewer 审核

## 7.3 失败重试规则（必须写死）

每个 agent 都要有：
1. 超时（如 15 分钟）
2. 最大重试次数（如 2 次）
3. 失败产物保存（错误日志 + 输入快照）

## 8. 统一输入输出协议（避免多 agent 扯皮）

每个 agent 的 I/O 都用 JSON Schema 约束，最少包含：

1. `task_id`
2. `input_artifacts`
3. `output_artifacts`
4. `assumptions`
5. `risks`
6. `cost_estimate`
7. `status`（success/failed/needs_human）

这样你才能做审计、回放、复现实验。

## 9. 结果落盘规范（第 4 天必须完成）

每次运行生成：

```text
runs/2026-02-27-<topic-id>/
├─ inputs/
├─ logs/
├─ artifacts/
│  ├─ evidence_table.md
│  ├─ experiment_result.json
│  ├─ paper_draft.md
│  └─ review_report.md
└─ run_summary.json
```

`run_summary.json` 最少包含：
1. 任务主题
2. 总耗时
3. 模型调用次数
4. 估算花费
5. 成功/失败
6. 人工介入点

## 10. 质量门禁（第 5 天）

没有门禁，系统会胡说八道。

发布前必须全部通过：
1. 结论可追溯：每个关键结论都能回链到文献或实验结果。
2. 可复现：同输入可重跑得到同级别结论。
3. 预算可控：单次运行不超过设定成本。
4. 审稿可读：`review_report.md` 至少包含“重大问题/次要问题/建议实验”。

## 11. 第一周详细执行清单（按天）

Day 1：
1. 建环境（venv + .env.example）
2. 跑 `.specify` 建立 `spec.md/plan.md/tasks.md`
3. 定义 MVP 成功指标

Day 2：
1. 集成 AI-Scientist（黑盒调用）
2. 跑通 1 个固定实验模板
3. 输出标准化 `experiment_result.json`

Day 3：
1. 实现 Planner/Literature/Experiment 三个 agent
2. 跑串行编排
3. 保存完整日志与产物

Day 4：
1. 加 Writer/Reviewer
2. 自动生成 `paper_draft.md` 和 `review_report.md`
3. 完成失败重试机制

Day 5：
1. 做 3 次端到端测试
2. 统计成功率、耗时、成本
3. 记录 TOP 10 失败原因并修复前 3 个

## 12. 最小可用命令流（你可直接照抄）

```bash
# 1) 初始化
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip

# 2) 建 spec
git checkout -b 001-research-agent-mvp
bash .specify/scripts/bash/create-new-feature.sh "Build FARS-like multi-agent research MVP"
bash .specify/scripts/bash/setup-plan.sh
bash .specify/scripts/bash/check-prerequisites.sh

# 3) 接入实验引擎
mkdir -p external
git clone https://github.com/SakanaAI/AI-Scientist external/ai-scientist

# 4) 第一次运行（示意）
# python -m src.orchestrator.main --topic "your topic" --max-budget 20

# 5) 查看产物
# ls -R runs/
```

## 13. 常见坑与规避

1. 坑：一开始就让 agent 自由探索。  
规避：先固定实验模板和指标，稳定后再放开。

2. 坑：没有统一输出协议，后面无法串联。  
规避：先写 schema，再写 agent。

3. 坑：只看“写得像论文”，不看证据链。  
规避：Reviewer 强制检查“结论 -> 证据”映射。

4. 坑：成本失控。  
规避：每个 agent 配预算上限和降级模型策略。

## 14. 你下一步马上该做什么

就做 3 件事，不要分心：
1. 按第 5 节把 `spec.md/plan.md/tasks.md` 补完。
2. 按第 6 节接好 AI-Scientist 黑盒调用并跑通一次。
3. 只实现串行 3 agent（Planner/Literature/Experiment），先拿到可运行闭环。

完成这三步后，再扩展 Writer/Reviewer。
