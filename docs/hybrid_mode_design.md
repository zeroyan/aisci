# Hybrid 模式设计文档

## 核心理解

### AI-Scientist 的工作模式
AI-Scientist 不是"零起步"架构，而是"在模板+baseline 上迭代改进"：

1. **硬依赖 baseline** → 必须有 `run_0/final_info.json` 作为对比基准
2. **生成改进想法** → 基于 baseline 的指标提出改进方案
3. **运行实验** → 修改代码并运行，与 baseline 对比
4. **评估改进** → 计算相对于 baseline 的提升

### 为什么需要 Baseline？

AI-Scientist 的核心逻辑（`launch_scientist.py:185`）：
```python
with open(osp.join(base_dir, "run_0", "final_info.json"), "r") as f:
    baseline_results = json.load(f)
```

如果没有这个文件，会直接报错：
```
FileNotFoundError: [Errno 2] No such file or directory: 'templates/generic_ai_research_cn/run_0/final_info.json'
```

## Hybrid 模式设计

### 三阶段流程

```
┌─────────────────────────────────────────────────────────────┐
│ Phase 1: AiSci 生成 Baseline                                │
│ - 运行 1 次迭代                                              │
│ - 生成初始可运行代码                                         │
│ - 获取初始指标（如 accuracy: 0.5）                           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 2: 准备 AI-Scientist 模板                             │
│ - 创建模板目录                                               │
│ - 写入 experiment.py（从 baseline 代码）                     │
│ - 写入 run_0/final_info.json（从 baseline 指标）            │
│ - 写入 plot.py, prompt.json, seed_ideas.json                │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 3: AI-Scientist 迭代改进                               │
│ - 读取 baseline 指标                                         │
│ - 生成改进想法（如：调整超参数、改进模型结构）               │
│ - 运行实验并与 baseline 对比                                 │
│ - 选择最佳改进方案                                           │
└─────────────────────────────────────────────────────────────┘
                            ↓
┌─────────────────────────────────────────────────────────────┐
│ Phase 4: AiSci 精修                                          │
│ - 获取 AI-Scientist 最佳结果                                 │
│ - 使用 RevisionAgent 继续优化                                │
│ - 生成最终对比报告                                           │
└─────────────────────────────────────────────────────────────┘
```

### Baseline 格式要求

```json
{
  "experiment": {
    "means": {
      "accuracy": 0.75,
      "loss": 0.25,
      "f1_score": 0.70
    }
  }
}
```

**关键点**：
- 必须有 `"experiment"` 键
- 必须有 `"means"` 子键
- 指标名称和值要与实验代码输出一致

### 模板目录结构

```
templates/generic_ai_research_cn/
├── experiment.py          # 实验代码（从 baseline 复制）
├── plot.py               # 绘图代码
├── prompt.json           # 任务描述
├── seed_ideas.json       # 初始想法
└── run_0/                # Baseline 结果
    └── final_info.json   # Baseline 指标（硬依赖）
```

## 实现计划

### Phase 1: Baseline 生成（T055-T057）

**目标**：使用 AiSci 生成可运行的 baseline

**步骤**：
1. 调用 `ExperimentLoop.run(max_iterations=1)`
2. 获取 `ExperimentResult`
3. 提取 `metrics` 字典
4. 格式化为 AI-Scientist 要求的格式
5. 写入 `run_0/final_info.json`

**代码示例**：
```python
# Run baseline
loop = ExperimentLoop(
    llm_client=llm_client,
    sandbox=sandbox,
    artifact_store=artifact_store,
    max_iterations=1,  # Only baseline
)
baseline_result = loop.run(spec=spec, plan=plan, run_id=run_id)

# Format baseline
baseline_info = {
    "experiment": {
        "means": baseline_result.metrics
    }
}

# Write to template
baseline_dir = template_dir / "run_0"
baseline_dir.mkdir(exist_ok=True)
(baseline_dir / "final_info.json").write_text(
    json.dumps(baseline_info, indent=2)
)
```

### Phase 2: 模板准备（T058-T061）

**目标**：创建完整的 AI-Scientist 模板

**步骤**：
1. 创建模板目录
2. 复制 baseline 代码到 `experiment.py`
3. 生成 `plot.py`（标准绘图代码）
4. 生成 `prompt.json`（从 spec.objective）
5. 生成 `seed_ideas.json`（从 spec 或 plan）
6. 验证所有文件存在

### Phase 3: AI-Scientist 执行（T062-T065）

**目标**：运行 AI-Scientist 并等待完成

**步骤**：
1. 调用 `AIScientistAdapter.submit_job()`
2. 阻塞等待（使用 `JobCallbacks.poll_status()`）
3. 定期输出进度（每分钟）
4. 完成后获取结果（使用 `ResultParser`）

### Phase 4: AiSci 精修（T066-T070）

**目标**：基于 AI-Scientist 结果继续优化

**步骤**：
1. 将 AI-Scientist 结果喂给 `RevisionAgent`
2. 生成修订建议（新的 `ExperimentPlan`）
3. 使用 `Orchestrator` 运行 AiSci 引擎
4. 生成三阶段对比报告
5. 计算改进指标

## 关键决策

### 决策 1: Baseline 生成策略
- **选择**：AiSci 运行 1 次迭代
- **原因**：
  - 快速生成可运行代码
  - 获得真实的初始指标
  - 避免手动编写 baseline
- **替代方案**：
  - ❌ 手动编写 baseline：工作量大，容易出错
  - ❌ 使用空 baseline：AI-Scientist 无法对比

### 决策 2: 模板复用策略
- **选择**：从 baseline 代码生成模板
- **原因**：
  - 保证代码可运行
  - 保持一致性
  - 减少重复工作

### 决策 3: 等待策略
- **选择**：阻塞等待 + 定期输出进度
- **原因**：
  - 简化流程控制
  - 用户体验更好（实时反馈）
  - 避免复杂的异步协调

## 测试计划

### 单元测试
- [ ] 测试 baseline 生成
- [ ] 测试模板准备
- [ ] 测试格式转换

### 集成测试
- [ ] 测试完整 hybrid 流程
- [ ] 测试失败处理
- [ ] 测试对比报告生成

### 端到端测试
- [ ] 使用真实 ResearchSpec
- [ ] 验证三阶段都成功执行
- [ ] 验证最终结果优于 baseline

## 风险与缓解

### 风险 1: Baseline 质量差
- **影响**：AI-Scientist 改进空间小
- **缓解**：允许配置 baseline 迭代次数（默认 1，可调整）

### 风险 2: 格式不匹配
- **影响**：AI-Scientist 无法读取 baseline
- **缓解**：严格验证格式，提供清晰错误信息

### 风险 3: 流程中断
- **影响**：用户体验差
- **缓解**：
  - 每个阶段独立可恢复
  - 保存中间结果
  - 提供手动继续选项

## 参考资料

- AI-Scientist 源码：`external/ai-scientist-runtime/launch_scientist.py`
- Baseline 格式：`templates/ai_toy_research_cn/run_0/final_info.json`
- 相关 Issue：P0-4（generic_ai_research_cn 缺少 baseline）
