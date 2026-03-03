# Spec 004: AI-Scientist 集成

**版本**: 1.0.0
**状态**: Draft
**创建日期**: 2026-03-02
**负责人**: TBD

---

## 概述

本规格定义如何将 **AI-Scientist** 作为可选的实验执行引擎集成到 AiSci 系统中，验证其多分支搜索和自动化论文生成能力，同时保持 AiSci 自研引擎的独立性。

**核心目标**：
- 将 AI-Scientist 封装为可选的 `ExperimentWorker` 实现
- 设计适配层：AiSci ResearchSpec → AI-Scientist idea format
- 验证 AI-Scientist 的多分支搜索效果（对比 Spec 003 自研引擎）
- 保持 JSON 格式通用性（两个引擎都能读取）
- 支持论文自动生成（AI-Scientist 特有能力）

**与现有功能的关系**：
- Spec 001: 提供 ResearchSpec 输入
- Spec 002: 提供 ExperimentPlan 输入（可选，AI-Scientist 有自己的规划）
- Spec 003: 并行选项，用户可选择自研引擎或 AI-Scientist
- Spec 004: **可选集成**，不影响核心功能

---

## 用户故事

### US-1: AI-Scientist 作为可选执行引擎（P1）
**作为** 科研人员
**我希望** 可以选择使用 AI-Scientist 执行实验
**以便** 利用其成熟的多分支搜索和论文生成能力

**验收标准**：
- [ ] CLI 支持 `--engine=ai-scientist` 参数（需先在 cli.py 中实现 engine 选项）
- [ ] 自动检测 AI-Scientist 是否安装（`external/ai-scientist/`）
- [ ] 如果未安装，提示用户安装或回退到自研引擎
- [ ] 执行结果格式与自研引擎一致（便于对比）

---

### US-2: ResearchSpec 到 AI-Scientist Idea 的转换（P1）
**作为** 系统集成者
**我希望** AiSci 的 ResearchSpec 能自动转换为 AI-Scientist 的 idea 格式
**以便** 无缝对接两个系统

**验收标准**：
- [ ] 实现 `ResearchSpecAdapter.to_ai_scientist_idea(spec) -> dict`
- [ ] 映射关系（基于真实 ResearchSpec schema）：
  - `title` → `Name` (idea name)
  - `objective` → `Experiment` (实验描述主体)
  - `hypothesis` → 嵌入到 `Experiment` 中
  - `metrics` → 用于验证结果
  - `constraints` → 转换为配置参数
- [ ] 生成的 idea JSON 能被 AI-Scientist 直接读取

---

### US-3: AI-Scientist 结果回传（P1）
**作为** 科研人员
**我希望** AI-Scientist 的执行结果能回传到 AiSci 系统
**以便** 统一管理所有实验记录

**验收标准**：
- [ ] 解析 AI-Scientist 输出目录（`results/<idea_name>/`）
- [ ] 提取关键信息：
  - 最佳代码版本
  - 实验结果（图表、指标）
  - 生成的论文 LaTeX（如果有）
- [ ] 转换为统一的结果格式（需在 Spec 003 中定义 `ExperimentResult` schema）
- [ ] 存储到 `runs/<run_id>/ai_scientist_output/`

---

### US-4: 论文自动生成（P2）
**作为** 科研人员
**我希望** 利用 AI-Scientist 的论文生成能力
**以便** 快速产出初稿，减少写作时间

**验收标准**：
- [ ] 支持 `--generate-paper` 参数
- [ ] 调用 AI-Scientist 的论文生成流程（`launch_scientist.py --writeup latex`）
- [ ] 输出 LaTeX 源码和编译后的 PDF
- [ ] 论文内容包含：实验设计、结果分析、图表

---

### US-5: 双引擎对比实验（P2）
**作为** 研究者
**我希望** 能同时运行自研引擎和 AI-Scientist
**以便** 对比两者的效果和效率

**验收标准**：
- [ ] 支持 `--engine=both` 参数
- [ ] 并行运行两个引擎（独立工作空间）
- [ ] 生成对比报告：
  - 成功率
  - 平均耗时
  - LLM 成本
  - 结果质量（人工评估）

---

## 功能需求

### FR-1: AI-Scientist 适配器
- 检测 AI-Scientist 安装状态（检查 `external/ai-scientist/launch_scientist.py`）
- 封装 AI-Scientist 的命令行接口
- 处理环境变量和配置文件

**CLI 接口设计**（需在 cli.py 中实现）：
```python
# 在 cli.py 的 run start 命令中添加 --engine 参数
@run_app.command("start")
def run_start(
    run_id: str,
    engine: str = "aisci",  # 新增：aisci | ai-scientist | both
    generate_paper: bool = False,  # 新增：是否生成论文
    ...
):
    """Start experiment execution with specified engine."""
    pass
```

### FR-2: ResearchSpec 转换器
- 实现 `ResearchSpecAdapter` 类
- 支持双向转换（AiSci ↔ AI-Scientist）
- 处理格式差异和缺失字段

### FR-3: 结果解析器
- 解析 AI-Scientist 输出目录结构
- 提取代码、结果、论文
- 转换为 AiSci 统一格式

### FR-4: 论文生成接口
- 调用 AI-Scientist 的论文生成流程：`launch_scientist.py --writeup latex`
- 实际执行链路：`launch_scientist.py` → `perform_writeup.py`
- 处理 LaTeX 编译错误（依赖 pdflatex）
- 支持自定义模板（如果 AI-Scientist 支持）

### FR-5: 双引擎编排器
- 管理两个引擎的并行执行
- 收集和对比结果
- 生成对比报告

---

## 非功能需求

### NFR-1: 兼容性
- 支持 AI-Scientist v1.0+（当前最新版本）
- 向后兼容：AI-Scientist 更新不影响 AiSci 核心功能

### NFR-2: 隔离性
- AI-Scientist 代码放在 `external/ai-scientist/`（小写，Linux 兼容）
- 不修改 AI-Scientist 源码（通过适配层调用）
- AI-Scientist 故障不影响自研引擎

### NFR-3: 性能
- 适配层开销 < 5%（相比直接调用 AI-Scientist）
- 结果转换延迟 < 1s

### NFR-4: 可维护性
- 适配层代码独立模块（`src/integrations/ai_scientist/`）
- 清晰的接口文档和示例
- 版本锁定：明确支持的 AI-Scientist 版本范围

---

## 技术设计要点

### 架构图
```
AiSci CLI
    ↓
  --engine=ai-scientist
    ↓
ResearchSpecAdapter
    ↓ (转换)
AI-Scientist Idea JSON
    ↓
AI-Scientist Executor
    ↓ (调用)
external/AI-Scientist/launch_scientist.py
    ↓ (输出)
results/<idea_name>/
    ↓ (解析)
ResultParser
    ↓ (转换)
AiSci ExperimentResult
    ↓ (存储)
runs/<run_id>/ai_scientist_output/
```

### 数据流
1. **输入**: AiSci ResearchSpec
2. **转换**: ResearchSpecAdapter → AI-Scientist idea JSON
3. **执行**: 调用 AI-Scientist CLI（`launch_scientist.py`）
4. **监控**: 实时读取 AI-Scientist 日志
5. **解析**: 提取结果、代码、论文
6. **回传**: 转换为 AiSci 格式，存储到 `runs/`

### 关键接口
- `AIScientistAdapter.is_installed() -> bool`
- `AIScientistAdapter.run(idea_json, config) -> AIScientistResult`
- `ResearchSpecAdapter.to_ai_scientist_idea(spec: ResearchSpec) -> dict`
- `ResearchSpecAdapter.from_ai_scientist_result(result) -> dict`  # 返回统一格式
- `PaperGenerator.generate(result, template) -> LaTeXPaper`

**注意**：`ExperimentResult` schema 需在 Spec 003 中定义，作为两个引擎的统一输出格式。

### AI-Scientist Idea 格式示例
```json
{
  "Name": "multi_style_adapter",
  "Title": "Multi-Style Adapter for Diffusion Models",
  "Experiment": "Investigate whether...",
  "Interestingness": 8,
  "Feasibility": 7,
  "Novelty": 6
}
```

### AiSci ResearchSpec 映射（真实 schema）
```python
# 基于 src/schemas/research_spec.py:40-57
{
  "spec_id": "...",
  "title": "...",              # → Name (idea name)
  "objective": "...",          # → Experiment (主体描述)
  "hypothesis": [...],         # → Experiment (嵌入假设)
  "metrics": [...],            # → 用于验证结果
  "constraints": {...},        # → 配置参数（max_cost_usd, timeout_minutes 等）
  "dataset_refs": [...],       # → 数据集引用
  "risk_notes": [...],         # → 风险提示
  "non_goals": [...],          # → 明确不做的事
  "status": "confirmed"
}
```

---

## 实现优先级

**Phase 1: 基础集成（P1）**
- AI-Scientist 适配器
- ResearchSpec 转换器
- 基本执行流程

**Phase 2: 结果回传（P1）**
- 结果解析器
- 格式转换
- 存储到 `runs/`

**Phase 3: 高级功能（P2）**
- 论文生成
- 双引擎对比
- 自定义模板

---

## 成功指标

- [ ] AI-Scientist 集成成功率 > 95%（无崩溃）
- [ ] ResearchSpec 转换准确率 100%（所有字段正确映射）
- [ ] 论文生成成功率 > 80%（LaTeX 编译通过）
- [ ] 双引擎对比实验完成 10+ 案例

---

## 风险与依赖

**风险**：
- AI-Scientist 更新可能破坏兼容性（需版本锁定）
- AI-Scientist 依赖较多（aider、LaTeX 环境）
- 论文生成质量依赖 LLM 能力（可能需要人工修订）

**依赖**：
- Spec 001: ResearchSpec 格式稳定
- AI-Scientist 代码库（`external/AI-Scientist/`）
- LaTeX 环境（论文生成）
- aider CLI（AI-Scientist 依赖）

**外部依赖安装**：
```bash
# 克隆 AI-Scientist（注意小写路径）
git clone https://github.com/SakanaAI/AI-Scientist.git external/ai-scientist

# 安装依赖
cd external/ai-scientist
pip install -r requirements.txt

# 安装 aider
pip install aider-chat

# 安装 LaTeX（macOS）
brew install --cask mactex
```

---

## 参考资料

- AI-Scientist GitHub: https://github.com/SakanaAI/AI-Scientist
- AI-Scientist 论文: https://arxiv.org/abs/2408.06292
- aider 文档: https://aider.chat/docs/

---

## 变更历史

| 版本 | 日期 | 变更内容 | 负责人 |
|------|------|----------|--------|
| 1.0.0 | 2026-03-02 | 初始版本，定义 AI-Scientist 集成方案 | TBD |
