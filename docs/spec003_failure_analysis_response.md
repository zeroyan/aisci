# Spec 003 失败分析报告确认（2026-03-03）

## 修复状态确认

### ✅ 已修复的问题

#### 1. run start --enable-orchestrator 参数不存在
**报告指出**: CLI 参数与实现不一致
**修复状态**: ✅ **已完全修复**
- 在 `cli.py:99-170` 添加了 `--enable-orchestrator` 和 `--num-branches` 参数
- 当启用时直接调用 BranchOrchestrator
- 修复了文档与代码漂移问题

**验证方式**:
```bash
python cli.py run start --help  # 现在会显示这些参数
```

#### 2. 隐藏故障 1: Planner/Critic LLM 接口不匹配
**报告指出**: 调用 `llm_client.call()` 但方法不存在
**修复状态**: ✅ **已完全修复**
- 在 `LLMClient` 添加了 `call()` 方法（`src/llm/client.py:132-154`）
- 作为 `complete()` 的别名，只返回响应文本
- 保持了与 Planner/Critic 的接口兼容性

#### 3. 隐藏故障 2: run create 与 orchestrator run 路径不一致
**报告指出**: 读写路径不匹配导致找不到文件
**修复状态**: ✅ **已完全修复**
- 统一了路径为 `spec/research_spec.json` 和 `plan/experiment_plan.json`
- 使用 `PlanSerializer.from_json()` 加载 JSON 格式
- 修复了 `cli.py:125-130` 的路径读取逻辑

---

### ⚠️ 未修复的核心问题

#### 问题 2: orchestrator run 成功但无实际执行

**报告指出**:
- `BranchOrchestrator.run()` 是 TODO 占位
- 返回固定的 0 cost / 0 time / 0 iterations
- `BranchExecutor` 也有占位执行路径

**修复状态**: ⚠️ **确认未修复（设计决策）**

**原因分析**:
这是 Spec 003 的**核心功能缺失**，不是简单的 bug 修复，而是需要完整实现的功能模块。涉及：

1. **PEC 循环实现** (`branch_executor.py:69-115`)
   - Planner 生成方案
   - Executor 执行代码
   - Critic 评估结果
   - 循环迭代直到成功或达到限制

2. **分支并行执行** (`branch_orchestrator.py:77`)
   - 使用 multiprocessing.Pool 并行运行多个分支
   - 动态预算调度
   - 实时状态监控

3. **实验记忆集成**
   - 记录每次尝试
   - 语义相似度搜索
   - 跨分支知识聚合

**为什么测试没拦住**:
报告正确指出了测试的局限性：

```python
# test_multi_branch.py:63
# 只断言"创建了 3 个分支目录"
assert result.run_id == "test_run"
assert result.total_cost_usd >= 0.0  # 允许为 0！

# 没有断言：
# assert result.iterations > 0  # 应该有实际迭代
# assert result.total_cost_usd > 0  # 应该有实际成本
```

---

## 测试覆盖问题分析

### 当前测试的问题

1. **集成测试过于宽松**
   - 只验证"结构存在"，不验证"真实执行"
   - `total_cost_usd >= 0.0` 允许占位返回通过
   - 没有检查 iterations 是否 > 0

2. **单元测试依赖 mock**
   - `test_planner_agent.py:15` 使用 `mock_llm_client.call()`
   - 与真实 `LLMClient` 接口脱节
   - 修复后这个问题已解决（添加了 `call()` 方法）

3. **缺少端到端测试**
   - 没有测试完整的 PEC 循环
   - 没有测试真实的 LLM 调用
   - 没有测试分支并行执行

### 建议的测试改进

#### 1. 加强集成测试断言

```python
def test_multi_branch_execution_real(orchestrator_config, test_spec, test_plan, tmp_path):
    """Test with real execution expectations."""
    result = orchestrator.run(spec=test_spec, plan=test_plan, run_id="test_run", runs_dir=tmp_path)

    # 严格断言
    assert result.iterations > 0, "Should have at least one iteration"
    assert result.total_cost_usd > 0, "Should have non-zero cost"
    assert result.total_time_seconds > 0, "Should have non-zero time"

    # 验证分支目录存在且有内容
    for i in range(1, 4):
        branch_dir = tmp_path / "test_run" / f"branch_{i:03d}"
        assert branch_dir.exists()
        assert (branch_dir / "memory" / "attempts.jsonl").exists()
        assert (branch_dir / "memory" / "attempts.jsonl").stat().st_size > 0
```

#### 2. 添加 PEC 循环端到端测试

```python
@pytest.mark.integration
@pytest.mark.slow
def test_pec_loop_end_to_end(real_llm_client):
    """Test complete PEC loop with real LLM."""
    # 使用真实 LLM 客户端
    # 验证 Planner -> Executor -> Critic 完整流程
    # 断言至少完成一次完整循环
```

#### 3. 添加占位检测测试

```python
def test_no_placeholder_execution():
    """Ensure orchestrator doesn't return placeholder results."""
    result = orchestrator.run(...)

    # 如果返回 0/0/0，测试应该失败
    if result.iterations == 0 and result.total_cost_usd == 0 and result.total_time_seconds == 0:
        pytest.fail("Orchestrator returned placeholder result - core execution not implemented")
```

---

## 影响评估确认

报告的影响评估**完全正确**：

### 1. 功能可用性
- ✅ 编排骨架已完成（目录结构、配置、接口）
- ❌ 多分支实验执行**不可用**（核心逻辑未实现）
- ❌ 预算调度、记忆、Docker 隔离**未形成闭环**

### 2. 用户体验
- ❌ 按 README 操作会失败（返回 0 结果）
- ❌ 容易误判为环境问题（实际是功能未实现）
- ✅ CLI 参数现在可用（修复后）

### 3. 测试可信度
- ⚠️ 300/300 tests passing **不代表功能可用**
- ⚠️ 测试主要覆盖"结构正确性"，未覆盖"执行正确性"
- ⚠️ 需要加强集成测试和端到端测试

---

## 修复优先级建议

### P0 - 阻塞发布
1. **实现 BranchExecutor PEC 循环**
   - 文件: `src/orchestrator/branch_executor.py:69-115`
   - 工作量: 2-3 天
   - 依赖: Planner, Critic, ExperimentMemory 已实现

2. **实现 BranchOrchestrator 并行执行**
   - 文件: `src/orchestrator/branch_orchestrator.py:77`
   - 工作量: 1-2 天
   - 依赖: BranchExecutor 完成

3. **加强集成测试**
   - 添加严格断言（iterations > 0, cost > 0）
   - 添加占位检测
   - 工作量: 1 天

### P1 - 重要但不阻塞
4. **端到端测试**
   - 使用真实 LLM 的完整流程测试
   - 工作量: 1-2 天

5. **文档更新**
   - 明确标注当前功能状态
   - 添加"已知限制"章节
   - 工作量: 0.5 天

---

## 总结

### 修复完成度
- ✅ **CLI 接口问题**: 已修复
- ✅ **LLM 接口问题**: 已修复
- ✅ **路径不一致问题**: 已修复
- ⚠️ **核心执行逻辑**: 未实现（需要 3-5 天工作量）

### 测试状态
- ✅ 所有单元测试通过
- ✅ 所有集成测试通过
- ⚠️ 测试覆盖不足，未捕获核心功能缺失

### 建议
1. **短期**: 在 README 添加"已知限制"章节，明确标注核心执行逻辑未实现
2. **中期**: 完成 P0 任务（PEC 循环 + 并行执行 + 测试加强）
3. **长期**: 添加端到端测试，确保功能真实可用

**感谢详细的失败分析报告，帮助我们识别了测试覆盖的盲区！** 🙏
