# AI-Scientist 代码解读与接入建议

> 本文基于本地克隆代码：`external/ai-scientist`  
> 检查日期：2026-02-27

## 1. 快速结论

`SakanaAI/AI-Scientist` 可以直接作为你 FARS 的“实验执行内核”，但不建议直接改它源码。  
最佳做法是：在你自己的 `src/tools/experiment_runner.py` 里调用它，把输入输出做标准化。

## 2. 代码入口与主流程

主入口是 `launch_scientist.py`，流程是：
1. `generate_ideas()`：生成研究想法
2. `check_idea_novelty()`：新颖性检查（文献检索）
3. `do_idea()`：对每个想法执行实验、写作、评审

核心观察：
1. 默认把实验模板放在 `templates/<experiment>`。
2. 结果输出在 `results/<experiment>/<timestamp>_<idea_name>/`。
3. 支持 `--parallel` 多进程 + 多 GPU。

## 3. 关键模块职责

`ai_scientist/generate_ideas.py`
1. 根据 `experiment.py` 和提示词生成 idea JSON。
2. 能做多轮反思优化。
3. 用 Semantic Scholar / OpenAlex 做新颖性检查。

`ai_scientist/perform_experiments.py`
1. 通过 aider 修改 `experiment.py` / `plot.py` / `notes.txt`。
2. 固定执行命令：`python experiment.py --out_dir=run_i`。
3. 读 `run_i/final_info.json` 作为结果。

`ai_scientist/perform_writeup.py`
1. 基于实验记录写 LaTeX。
2. 自动编译 `pdflatex` + `bibtex`。
3. 会做一些 LaTeX 错误修复。

`ai_scientist/perform_review.py`
1. 加载生成的 PDF。
2. 调用评审模型输出 review JSON。

`ai_scientist/llm.py`
1. 统一封装多模型调用。
2. 当前仓库里是 Chat Completions 风格接口。

## 4. 你最该复用的能力

优先复用：
1. `generate_ideas()` 的 idea 结构和多轮反思流程。
2. `perform_experiments()` 的“改代码 -> 执行 -> 读指标”闭环。
3. `perform_review()` 的自动审稿输出格式。

不建议第一版深改：
1. 不建议在它内部直接改模型 SDK 逻辑。
2. 不建议第一版就改写 LaTeX 流程。
3. 不建议第一版并行很多 idea（先 1-2 个）。

## 5. 和你 FARS 架构的映射关系

推荐映射：
1. FARS `PlannerAgent` -> AI-Scientist `generate_ideas`
2. FARS `ExperimentAgent` -> AI-Scientist `perform_experiments`
3. FARS `WriterAgent` -> AI-Scientist `perform_writeup`
4. FARS `ReviewerAgent` -> AI-Scientist `perform_review`

你要做的是“外层编排器”：
1. 统一输入协议（topic/spec/budget）
2. 调用 AI-Scientist
3. 统一输出协议（result/cost/risk/artifacts）

## 6. 已确认的运行前提（来自仓库代码）

1. Python 3.11 环境
2. GPU + PyTorch（CPU 跑会很慢）
3. LaTeX 依赖（至少 `pdflatex` 与 `chktex`）
4. API Key（OpenAI/Anthropic/Gemini 等）
5. 文献检索 key（可选 `S2_API_KEY`；或改用 OpenAlex）

## 7. 风险点（必须加治理）

这个仓库会让 LLM 修改并执行代码，风险很高，必须加：
1. 沙箱执行（Docker + 资源限制）
2. 禁网或白名单网络
3. 超时/重试/kill 开关
4. 运行预算上限
5. 结果可追溯（日志 + 输入快照）

## 8. 建议的最小接入步骤

1. 先只跑一个模板 + 一个 idea。
2. 先关闭并行（`--parallel 0`）。
3. 在你项目里写 `experiment_runner.py`，把它封装成单函数调用。
4. 把 AI-Scientist 输出路径映射到你自己的 `runs/<run_id>/artifacts/`。
5. 再接入你的 Writer/Reviewer 代理做二次复核。

## 9. 你可以直接执行的检查命令

```bash
# 查看入口参数
python external/ai-scientist/launch_scientist.py --help

# 查看支持模型枚举（手动读代码）
sed -n '1,220p' external/ai-scientist/ai_scientist/llm.py

# 查看实验执行逻辑
sed -n '1,260p' external/ai-scientist/ai_scientist/perform_experiments.py
```
