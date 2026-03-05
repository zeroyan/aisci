# Research: AI-Scientist 外部专家集成

**日期**: 2026-03-03
**状态**: Complete

## 研究目标

解决 Technical Context 中的关键技术决策和实现细节。

---

## 决策 1: 异步任务管理方案

### 问题
如何实现异步任务管理，使 AI-Scientist 任务不阻塞 CLI？

### 决策
使用 Python subprocess + 后台进程模式

### 理由
1. **简单性**: subprocess 是 Python 标准库，无需额外依赖
2. **隔离性**: 子进程独立运行，崩溃不影响主进程
3. **可控性**: 可以通过 PID 管理进程生命周期（查询状态、终止）
4. **兼容性**: 跨平台支持（macOS/Linux）

### 实现方案
```python
import subprocess
from pathlib import Path

def submit_job(template: str, num_ideas: int) -> str:
    """Submit async job, return job_id."""
    job_id = generate_job_id()
    log_path = Path(f"runs/{run_id}/external/logs/{job_id}.log")

    # 启动子进程（后台运行）
    process = subprocess.Popen(
        ["python", "launch_scientist.py", "--template", template, "--num-ideas", str(num_ideas)],
        cwd="external/ai-scientist-runtime",
        stdout=open(log_path, "w"),
        stderr=subprocess.STDOUT,
        start_new_session=True,  # 独立会话，不受父进程影响
    )

    # 记录 PID 和状态
    job_store.save(JobRecord(
        job_id=job_id,
        pid=process.pid,
        status="running",
        log_path=str(log_path),
        start_time=datetime.now(),
    ))

    return job_id
```

### 替代方案
- **Celery**: 过重，需要 Redis/RabbitMQ
- **asyncio**: 仍然阻塞主进程，不适合长时间任务
- **multiprocessing**: 适合 CPU 密集型，但 AI-Scientist 是独立进程

---

## 决策 2: 状态轮询机制

### 问题
如何检查异步任务的运行状态？

### 决策
文件事件监听 + 定期轮询（双重机制）

### 理由
1. **文件事件**: 快速响应（AI-Scientist 写入 final_info.json 时触发）
2. **定期轮询**: 兜底机制（防止文件事件丢失）
3. **可配置**: 支持不同环境（生产 60s，测试 10s）

### 实现方案
```python
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class ResultWatcher(FileSystemEventHandler):
    def on_created(self, event):
        if event.src_path.endswith("final_info.json"):
            job_id = extract_job_id(event.src_path)
            self.callback(job_id, "completed")

def poll_status(job_id: str, interval: int = 60):
    """Poll job status every N seconds."""
    while True:
        record = job_store.load(job_id)

        # 检查进程是否存活
        if not psutil.pid_exists(record.pid):
            # 检查结果文件是否存在
            if result_exists(job_id):
                job_store.update(job_id, status="completed")
                break
            else:
                job_store.update(job_id, status="failed", error="Process died")
                break

        time.sleep(interval)
```

### 替代方案
- **仅轮询**: 延迟高，资源浪费
- **仅文件事件**: 不可靠（事件可能丢失）
- **HTTP webhook**: 需要修改 AI-Scientist 源码（违反约束）

---

## 决策 3: 并发控制策略

### 问题
如何限制并发任务数量（最多 1-2 个）？

### 决策
基于 JobStore 的简单队列机制

### 理由
1. **简单性**: 无需引入消息队列
2. **持久化**: 任务记录存储在 jobs.jsonl，重启不丢失
3. **可扩展**: 未来可升级为 Redis 队列

### 实现方案
```python
class JobStore:
    def __init__(self, max_concurrent: int = 2):
        self.max_concurrent = max_concurrent

    def can_submit(self) -> bool:
        """Check if can submit new job."""
        running_count = len([j for j in self.list_all() if j.status == "running"])
        return running_count < self.max_concurrent

    def submit_or_queue(self, job_record: JobRecord):
        """Submit job or add to queue."""
        if self.can_submit():
            job_record.status = "running"
            self._start_process(job_record)
        else:
            job_record.status = "pending"

        self.save(job_record)

    def on_job_complete(self, job_id: str):
        """Trigger next pending job when one completes."""
        self.update(job_id, status="completed")

        # 启动下一个 pending 任务
        pending_jobs = [j for j in self.list_all() if j.status == "pending"]
        if pending_jobs and self.can_submit():
            next_job = pending_jobs[0]
            self.submit_or_queue(next_job)
```

### 替代方案
- **无限制**: 资源耗尽风险
- **Celery 队列**: 过重
- **数据库队列**: 增加复杂度

---

## 决策 4: 结果解析策略

### 问题
如何解析 AI-Scientist 的输出目录结构？

### 决策
基于目录约定的解析器

### 理由
1. **AI-Scientist 输出格式固定**: `results/<template>/<timestamp>_<idea>/`
2. **关键文件已知**: report.md, final_info.json, plots/, code/
3. **版本锁定**: 锁定 AI-Scientist 版本，输出格式稳定

### 实现方案
```python
class ResultParser:
    def parse_result_dir(self, result_dir: Path) -> ExperimentResult:
        """Parse AI-Scientist output directory."""
        # 查找最新的 idea 目录
        idea_dirs = sorted(result_dir.glob("*_*"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not idea_dirs:
            raise ValueError(f"No idea directories found in {result_dir}")

        latest_idea = idea_dirs[0]

        # 提取关键文件
        report_path = latest_idea / "report.md"
        final_info_path = latest_idea / "run_0" / "final_info.json"
        plots_dir = latest_idea / "plots"
        code_dir = latest_idea / "code"

        # 读取 final_info.json
        with open(final_info_path) as f:
            final_info = json.load(f)

        # 转换为 ExperimentResult
        return ExperimentResult(
            run_id=extract_run_id(result_dir),
            engine="ai-scientist",
            status="completed",
            report=report_path.read_text() if report_path.exists() else None,
            metrics=final_info.get("metrics", {}),
            artifacts=self.extract_artifacts(latest_idea),
            metadata={
                "idea_name": latest_idea.name,
                "timestamp": final_info.get("timestamp"),
            },
        )

    def extract_artifacts(self, idea_dir: Path) -> list[str]:
        """Extract artifact paths."""
        artifacts = []

        # 收集图表
        if (idea_dir / "plots").exists():
            artifacts.extend(str(p) for p in (idea_dir / "plots").glob("*.png"))

        # 收集代码
        if (idea_dir / "code").exists():
            artifacts.extend(str(p) for p in (idea_dir / "code").glob("*.py"))

        return artifacts
```

### 替代方案
- **AI-Scientist API**: 不存在，AI-Scientist 是 CLI 工具
- **修改 AI-Scientist 输出**: 违反"不修改源码"约束

---

## 决策 5: 动态模板生成方案

### 问题
如何根据 ResearchSpec 动态生成 AI-Scientist 模板？

### 决策
通用模板骨架 + 动态填充

### 理由
1. **课题可变**: 不同研究课题需要不同的 prompt 和 seed_ideas
2. **模板结构固定**: AI-Scientist 模板格式固定（prompt.json, seed_ideas.json, experiment.py, plot.py）
3. **避免重模板绑定**: 一个通用骨架支持所有课题

### 实现方案
```python
class SpecMapper:
    def generate_dynamic_template(self, spec: ResearchSpec, output_dir: Path) -> str:
        """Generate dynamic template, return template_name."""
        template_name = f"dynamic_{spec.spec_id}"
        template_dir = output_dir / template_name
        template_dir.mkdir(parents=True, exist_ok=True)

        # 1. 生成 prompt.json
        prompt = {
            "system": "You are an AI research assistant.",
            "task": spec.objective,
            "constraints": [c.dict() for c in spec.constraints],
            "metrics": [m.dict() for m in spec.metrics],
        }
        (template_dir / "prompt.json").write_text(json.dumps(prompt, indent=2))

        # 2. 生成 seed_ideas.json（从 spec 提取或 LLM 生成）
        seed_ideas = self._generate_seed_ideas(spec)
        (template_dir / "seed_ideas.json").write_text(json.dumps(seed_ideas, indent=2))

        # 3. 复制通用 experiment.py 和 plot.py
        shutil.copy(
            "external/ai-scientist-runtime/templates/generic_ai_research_cn/experiment.py",
            template_dir / "experiment.py"
        )
        shutil.copy(
            "external/ai-scientist-runtime/templates/generic_ai_research_cn/plot.py",
            template_dir / "plot.py"
        )

        return template_name

    def _generate_seed_ideas(self, spec: ResearchSpec) -> list[dict]:
        """Generate 2-3 seed ideas from spec."""
        # 简单版本：从 spec.objective 提取关键词
        # 未来版本：调用 LLM 生成
        return [
            {"name": f"Idea 1: {spec.title}", "description": spec.objective},
            {"name": f"Idea 2: Baseline", "description": "Baseline approach"},
        ]
```

### 替代方案
- **预定义多个模板**: 维护成本高，不灵活
- **完全手动**: 用户体验差
- **LLM 生成全部代码**: 不可靠，AI-Scientist 已有代码生成能力

---

## 决策 6: 版本锁定机制

### 问题
如何锁定 AI-Scientist 版本以确保兼容性？

### 决策
Git submodule + 版本标签

### 理由
1. **精确版本控制**: Git submodule 锁定特定 commit
2. **易于升级**: 更新 submodule 指向新版本
3. **文档化**: 在 README 中明确支持的版本

### 实现方案
```bash
# 初始化 submodule
cd aisci
git submodule add https://github.com/SakanaAI/AI-Scientist.git external/ai-scientist-runtime
cd external/ai-scientist-runtime
git checkout v1.2.0  # 锁定特定版本
cd ../..
git add .gitmodules external/ai-scientist-runtime
git commit -m "feat: add AI-Scientist v1.2.0 as submodule"
```

在 `src/integrations/ai_scientist/adapter.py` 中添加版本检查：
```python
SUPPORTED_VERSIONS = ["v1.2.0", "v1.2.1"]

def check_version(self) -> bool:
    """Check if AI-Scientist version is supported."""
    version_file = self.runtime_dir / "VERSION"
    if not version_file.exists():
        logger.warning("AI-Scientist version file not found")
        return False

    version = version_file.read_text().strip()
    if version not in SUPPORTED_VERSIONS:
        logger.error(f"Unsupported AI-Scientist version: {version}")
        return False

    return True
```

### 替代方案
- **pip 安装**: AI-Scientist 不是 pip 包
- **Docker 镜像**: 过重，增加复杂度
- **不锁定版本**: 兼容性风险高

---

## 决策 7: 本地大模型配置

### 问题
AI-Scientist 需要配置 LLM 模型，如何选择合适的模型进行测试？

### 决策
使用 Ollama + qwen3（本地模型）

### 理由
1. **成本低**: 本地运行，无 API 调用费用
2. **调试方便**: 不受网络限制，响应快
3. **易于切换**: 验证通过后可轻松切换到 DeepSeek 或其他云端模型
4. **隐私保护**: 数据不离开本地

### 实现方案

#### 1. Ollama 配置
```bash
# 安装 Ollama
brew install ollama  # macOS
# 或
curl -fsSL https://ollama.com/install.sh | sh  # Linux

# 启动服务
ollama serve

# 拉取 qwen3 模型
ollama pull qwen3
```

#### 2. AI-Scientist 配置
在 `external/ai-scientist-runtime/.env` 中配置：
```bash
LLM_BACKEND=ollama
LLM_MODEL=qwen3
OLLAMA_BASE_URL=http://localhost:11434
```

#### 3. CLI 参数传递
```python
# cli.py
@run_app.command("start")
def run_start(
    run_id: str,
    engine: str = typer.Option("aisci"),
    model: str = typer.Option("ollama/qwen3", help="LLM model name"),
    ...
):
    if engine == "ai-scientist":
        adapter.submit_job(
            template=template_name,
            model=model,  # 传递给 AI-Scientist
            ...
        )
```

#### 4. 模型切换
切换到 DeepSeek（未来）：
```bash
# 修改 .env
LLM_BACKEND=openai_compatible
LLM_MODEL=deepseek-chat
OPENAI_API_BASE=https://api.deepseek.com/v1
OPENAI_API_KEY=sk-xxx
```

或通过 CLI 参数：
```bash
python cli.py run start exp001 --engine ai-scientist --model deepseek-chat
```

### 替代方案
- **GPT-4**: 成本高（$0.03/1K tokens），测试阶段不划算
- **Claude**: 需要 API key，有速率限制
- **本地 LLaMA**: 性能较弱，不如 qwen3

### 模型对比

| 模型 | 成本 | 速度 | 质量 | 适用场景 |
|------|------|------|------|---------|
| ollama/qwen3 | 免费 | 快 | 中 | 测试、开发 |
| deepseek-chat | 低 | 中 | 高 | 生产 |
| gpt-4 | 高 | 快 | 高 | 关键实验 |

---

## 总结

所有关键技术决策已完成，无 NEEDS CLARIFICATION 项。可以进入 Phase 1 设计阶段。

### 核心技术栈确认
- **异步任务**: subprocess + 后台进程
- **状态监控**: watchdog（文件事件）+ psutil（进程检查）
- **并发控制**: JobStore 简单队列
- **结果解析**: 基于目录约定的解析器
- **模板生成**: 通用骨架 + 动态填充
- **版本管理**: Git submodule + 版本检查
- **LLM 模型**: Ollama + qwen3（测试），可切换到 DeepSeek（生产）

### 新增依赖
- `watchdog`（文件事件监听，可选）
- `psutil`（进程管理）
- `ollama`（本地 LLM 服务）

需要更新 `requirements.txt`。
