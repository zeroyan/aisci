# AI-Scientist 集成修复总结

## 核心架构理解

### AI-Scientist 工作模式
AI-Scientist 不是"零起步"架构，而是"在模板+baseline 上迭代改进"：

1. **需要 baseline** → 读取 `run_0/final_info.json` 作为对比基准（硬依赖）
2. **生成改进想法** → 基于 baseline 提出改进方案
3. **运行实验** → 修改代码并运行，与 baseline 对比

### Baseline 格式要求
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

### Hybrid 模式正确流程
```
Phase 1: AiSci 生成 baseline（1 次迭代）
    ↓
Phase 2: 准备 AI-Scientist 模板（包含 baseline）
    ↓
Phase 3: AI-Scientist 基于 baseline 迭代改进
    ↓
Phase 4: AiSci 继续优化
```

## 已修复问题

### P0-1: API Key 安全问题 ✅
**问题**: API Key 被硬编码在代码中并打印到控制台
**修复**:
- 移除硬编码的 API key
- 从环境变量 `DEEPSEEK_API_KEY` 读取
- 如果未设置则抛出明确错误
- 移除调试日志中的 API key 打印

**文件**: `src/integrations/ai_scientist/adapter.py:97-105`

### P0-2: --skip-novelty-check 导致 KeyError ✅
**问题**: 使用 `--skip-novelty-check` 时，ideas 缺少 `novel` 字段导致崩溃
**修复**: 在 `launch_scientist.py` 中添加 else 分支，当跳过 novelty check 时自动为所有 ideas 添加 `novel: True`

**文件**: `external/ai-scientist-runtime/launch_scientist.py:365-368`

### P0-3: 结果目录路径错误 ✅
**问题**: 代码使用 `templates/<template>/results` 路径，但 AI-Scientist 实际输出到 `results/<experiment>/`
**修复**:
- 修正 `adapter.py` 中的结果检查路径
- 修正 `cli.py` 中的 ResultParser 路径

**文件**:
- `src/integrations/ai_scientist/adapter.py:169`
- `cli.py:416`

### P0-4: generic_ai_research_cn 缺少 baseline ⚠️
**问题**: 模板缺少必需的 `run_0/final_info.json` 文件
**状态**: 部分修复
**说明**:
- 该模板需要运行 baseline 实验生成 `run_0/final_info.json`
- 需要安装依赖: `numpy`, `torch`, `scikit-learn`
- 建议使用 `ai_toy_research_cn` 模板进行测试（已包含 baseline）

**临时方案**:
```bash
cd external/ai-scientist-runtime/templates/generic_ai_research_cn
.venv/bin/pip install numpy torch scikit-learn
.venv/bin/python experiment.py --out_dir=run_0
```

### P1-5: 排队逻辑修复 ✅
**问题**:
- 进程先启动再判断是否排队，导致资源浪费
- 没有自动调度器启动排队的任务

**修复**:
- 先检查并发限制，再决定是否启动进程
- 在 `get_status` 中添加自动调度逻辑
- 添加 `_try_start_pending_job` 方法自动启动排队任务

**文件**: `src/integrations/ai_scientist/adapter.py:105-140, 183, 271-332`

## 待修复问题

### P1-6: ResultParser 结构假设不匹配
**问题**: ResultParser 假设输出包含 `final_info.json`, `plots/`, `code/` 子目录，但实际输出结构可能不同
**影响**: 结果解析可能失败
**优先级**: P1（不影响核心功能，但影响结果获取）

### P1-7: SpecMapper 导入错误
**问题**: `spec_mapper.py` 导入了不存在的模块
**影响**: 动态模板生成功能不可用
**优先级**: P1（非 MVP 功能）

### P1-8: 数据契约不一致
**问题**: `TemplatePackage` 校验 `task` 字段，但 AI-Scientist 读取 `task_description`
**影响**: 模板验证可能失败
**优先级**: P1（影响模板生成）

### P1-9: 测试失败
**问题**: 9 个测试失败，主要是 orchestrator 接口签名变更后测试未同步
**影响**: CI/CD 流程
**优先级**: P1（不影响功能，但影响开发流程）

## 使用建议

### 1. 设置环境变量
```bash
export DEEPSEEK_API_KEY=your_api_key_here
```

### 2. 使用 ai_toy_research_cn 模板测试
```bash
cd external/ai-scientist-runtime
export DEEPSEEK_API_KEY=your_key
./.venv/bin/python launch_scientist.py \
  --experiment ai_toy_research_cn \
  --model deepseek-chat \
  --num-ideas 1 \
  --skip-novelty-check
```

### 3. 通过 AiSci CLI 使用
```bash
# 确保环境变量已设置
export DEEPSEEK_API_KEY=your_key

# 提交任务
python cli.py run start <run_id> \
  --engine ai-scientist \
  --num-ideas 1 \
  --writeup md \
  --model deepseek-chat

# 查看状态
python cli.py run external-status <run_id>

# 获取结果
python cli.py run external-fetch <run_id>
```

## 验证结果

### ✅ 已验证通过
1. API Key 从环境变量正确读取
2. `--skip-novelty-check` 不再报 KeyError
3. Ideas 成功生成（测试生成了 3 个 ideas）
4. 排队逻辑正常工作
5. 结果路径正确

### ⚠️ 需要进一步测试
1. 完整的实验运行（需要安装所有依赖）
2. 结果解析和转换
3. Hybrid 模式
4. 多任务并发控制
