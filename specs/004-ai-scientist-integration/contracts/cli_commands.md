# CLI 命令契约

**模块**: `cli.py`
**用途**: 定义用户与 AI-Scientist 集成功能的交互接口

---

## 命令 1: run start --engine

### 签名

```bash
python cli.py run start <run_id> [OPTIONS]
```

### 参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `run_id` | str | ✅ | - | 实验 run 的唯一标识 |
| `--engine` | str | ❌ | "aisci" | 执行引擎：aisci\|ai-scientist\|hybrid |
| `--num-ideas` | int | ❌ | 2 | AI-Scientist 生成的 idea 数量（1-10） |
| `--writeup` | str | ❌ | "md" | 报告格式：md\|latex（测试阶段固定用 md） |
| `--model` | str | ❌ | "ollama/qwen3" | LLM 模型名称（测试用 ollama/qwen3，后续可改为 deepseek） |

### 行为

#### engine=aisci（默认）
- 使用现有 ExperimentLoop 执行实验
- 阻塞执行，直到实验完成
- 输出：实验报告路径

#### engine=ai-scientist
- 启动异步 AI-Scientist 任务
- 立即返回 job_id
- 不阻塞 CLI
- 输出：job_id、日志路径

#### engine=hybrid
- 先运行 ai-scientist（阻塞等待）
- 每分钟输出进度
- 完成后运行 aisci 精修
- 输出：对比报告路径

### 输出格式

#### engine=ai-scientist
```
Job submitted: job_abc123
Status: running
Log: runs/exp001/external/logs/job_abc123.log

Use 'python cli.py run external-status exp001' to check progress.
```

#### engine=hybrid
```
[Step 1/4] Running AI-Scientist...
Job submitted: job_def456
Waiting for completion (blocking)...
Progress: 1/2 ideas completed (10m elapsed)
Progress: 2/2 ideas completed (25m elapsed)
[Step 2/4] AI-Scientist completed
[Step 3/4] Running RevisionAgent...
Generated 3 revision suggestions
[Step 4/4] Running aisci engine...
Experiment completed
[Step 5/4] Generating comparison report...
Comparison report saved to runs/exp002/comparison_report.md
```

### 错误处理

| 错误场景 | 退出码 | 错误信息 |
|---------|--------|---------|
| run_id 不存在 | 1 | `ERROR: Run 'exp001' not found` |
| AI-Scientist 未安装 | 1 | `ERROR: AI-Scientist not found at external/ai-scientist-runtime` |
| 并发限制已满 | 0 | `Job queued: job_abc123 (status: pending)` |
| 无效的 engine 值 | 1 | `ERROR: Invalid engine 'xxx'. Must be: aisci, ai-scientist, hybrid` |
| num-ideas 超出范围 | 1 | `ERROR: num-ideas must be between 1 and 10` |

### 示例

```bash
# 使用 aisci 引擎（默认）
python cli.py run start exp001

# 使用 ai-scientist 引擎
python cli.py run start exp001 --engine ai-scientist --num-ideas 3

# 使用 hybrid 模式
python cli.py run start exp001 --engine hybrid --num-ideas 2 --writeup latex
```

---

## 命令 2: run external-status

### 签名

```bash
python cli.py run external-status <run_id>
```

### 参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `run_id` | str | ✅ | - | 实验 run 的唯一标识 |

### 行为

- 查询 `runs/<run_id>/external/jobs.jsonl` 获取最新任务记录
- 检查子进程状态（通过 PID）
- 检查结果文件是否存在
- 返回任务状态和进度信息

### 输出格式

#### 任务运行中
```
Status: running
Progress: 1/2 ideas completed
Elapsed time: 15m 30s
Log: runs/exp001/external/logs/job_abc123.log
```

#### 任务完成
```
Status: completed
Total time: 25m 45s
Result: runs/exp001/external/ai_scientist/result.json
Artifacts: 3 files (report.md, 2 plots)
```

#### 任务失败
```
Status: failed
Error: Process died with exit code 1
Log: runs/exp001/external/logs/job_abc123.log
Elapsed time: 5m 12s
```

#### 任务排队
```
Status: pending
Position in queue: 1
Waiting for: job_xyz789 to complete
```

### 错误处理

| 错误场景 | 退出码 | 错误信息 |
|---------|--------|---------|
| run_id 不存在 | 1 | `ERROR: Run 'exp001' not found` |
| 无外部任务记录 | 1 | `ERROR: No external jobs found for run 'exp001'` |

### 示例

```bash
python cli.py run external-status exp001
```

---

## 命令 3: run external-fetch

### 签名

```bash
python cli.py run external-fetch <run_id>
```

### 参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `run_id` | str | ✅ | - | 实验 run 的唯一标识 |

### 行为

- 检查任务是否完成（status=completed）
- 解析 AI-Scientist 输出目录
- 转换为 `ExperimentResult` 格式
- 落盘到 `runs/<run_id>/external/ai_scientist/`
- 复制 artifacts（报告、图表、代码）

### 输出格式

#### 成功
```
Fetching results for run: exp001
Parsing AI-Scientist output...
Found 2 ideas, using latest: 20260303_123456_idea_2
Extracting artifacts...
  - report.md (15 KB)
  - plots/fig1.png (120 KB)
  - plots/fig2.png (95 KB)
  - code/experiment.py (3 KB)
Result saved to: runs/exp001/external/ai_scientist/result.json
Artifacts copied to: runs/exp001/external/ai_scientist/artifacts/
```

#### 任务未完成
```
ERROR: Cannot fetch results - job is still running
Current status: running (1/2 ideas completed)
Use 'python cli.py run external-status exp001' to check progress.
```

### 错误处理

| 错误场景 | 退出码 | 错误信息 |
|---------|--------|---------|
| 任务未完成 | 1 | `ERROR: Cannot fetch results - job is still running` |
| 任务失败 | 1 | `ERROR: Cannot fetch results - job failed` |
| 结果目录不存在 | 1 | `ERROR: AI-Scientist output directory not found` |
| 解析失败 | 1 | `ERROR: Failed to parse AI-Scientist output: <reason>` |

### 示例

```bash
python cli.py run external-fetch exp001
```

---

## 命令 4: run external-cancel

### 签名

```bash
python cli.py run external-cancel <run_id>
```

### 参数

| 参数 | 类型 | 必需 | 默认值 | 说明 |
|------|------|------|--------|------|
| `run_id` | str | ✅ | - | 实验 run 的唯一标识 |

### 行为

- 查询任务记录获取 PID
- 终止子进程（SIGTERM，5 秒后 SIGKILL）
- 更新任务状态为 failed（error="Cancelled by user"）
- 保存中间结果（如果有）

### 输出格式

#### 成功取消
```
Cancelling job: job_abc123
Sending SIGTERM to process 12345...
Process terminated gracefully
Status updated to: failed (cancelled by user)
Partial results saved to: runs/exp001/external/ai_scientist/partial_result.json
```

#### 进程已结束
```
Job job_abc123 is not running (status: completed)
No action needed.
```

### 错误处理

| 错误场景 | 退出码 | 错误信息 |
|---------|--------|---------|
| 任务不存在 | 1 | `ERROR: No external job found for run 'exp001'` |
| 进程不存在 | 0 | `Job is not running (status: completed)` |
| 终止失败 | 1 | `ERROR: Failed to terminate process 12345` |

### 示例

```bash
python cli.py run external-cancel exp001
```

---

## 契约测试

### 测试用例 1: 正常流程

```bash
# 1. 提交任务
python cli.py run start exp001 --engine ai-scientist --num-ideas 2
# 预期: 返回 job_id，退出码 0

# 2. 查询状态
python cli.py run external-status exp001
# 预期: 显示 "running"，退出码 0

# 3. 等待完成（模拟）
sleep 1800  # 30 分钟

# 4. 获取结果
python cli.py run external-fetch exp001
# 预期: 结果保存成功，退出码 0
```

### 测试用例 2: 并发限制

```bash
# 1. 提交 3 个任务
python cli.py run start exp001 --engine ai-scientist &
python cli.py run start exp002 --engine ai-scientist &
python cli.py run start exp003 --engine ai-scientist &

# 2. 检查状态
python cli.py run external-status exp001  # 预期: running
python cli.py run external-status exp002  # 预期: running
python cli.py run external-status exp003  # 预期: pending
```

### 测试用例 3: 错误处理

```bash
# 1. 无效的 engine
python cli.py run start exp001 --engine invalid
# 预期: 错误信息，退出码 1

# 2. 不存在的 run_id
python cli.py run external-status exp999
# 预期: 错误信息，退出码 1

# 3. 取消已完成的任务
python cli.py run external-cancel exp001  # 假设已完成
# 预期: "Job is not running"，退出码 0
```

---

## 向后兼容性

### 现有命令不受影响

- `python cli.py run start <run_id>` 默认使用 aisci 引擎
- 不添加 `--engine` 参数时，行为与之前完全一致
- 新增的 `external-*` 命令不影响现有工作流

### 迁移路径

用户可以逐步迁移到新引擎：

1. **第一阶段**: 继续使用 aisci 引擎（默认）
2. **第二阶段**: 尝试 ai-scientist 引擎（单个实验）
3. **第三阶段**: 使用 hybrid 模式（获得最佳结果）

无需一次性迁移所有实验。
