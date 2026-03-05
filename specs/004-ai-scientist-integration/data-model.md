# Data Model: AI-Scientist 外部专家集成

**日期**: 2026-03-03
**状态**: Complete

---

## 核心实体

### 1. JobRecord（任务记录）

**用途**: 记录 AI-Scientist 异步任务的状态和元数据

**字段**:
```python
@dataclass
class JobRecord:
    job_id: str                    # 任务唯一标识（UUID）
    run_id: str                    # 关联的实验 run_id
    pid: int                       # 子进程 PID
    status: Literal["pending", "running", "completed", "failed"]
    log_path: str                  # 日志文件路径
    start_time: datetime           # 任务开始时间
    end_time: datetime | None      # 任务结束时间（None 表示未完成）
    error: str | None              # 错误信息（失败时记录）
    template_name: str             # 使用的模板名称
    num_ideas: int                 # 生成的 idea 数量
```

**验证规则**:
- `job_id`: 必须是有效的 UUID
- `status`: 只能是 4 个枚举值之一
- `pid`: 必须 > 0
- `start_time`: 必须 <= `end_time`（如果 end_time 不为 None）

**状态转换**:
```
pending → running → completed
                 → failed
```

**持久化**:
- 格式: JSONL（每行一个 JSON 对象）
- 路径: `runs/<run_id>/external/jobs.jsonl`
- 追加写入，不覆盖

---

### 2. TemplatePackage（模板任务包）

**用途**: 封装 ResearchSpec 到 AI-Scientist 模板的映射结果

**字段**:
```python
@dataclass
class TemplatePackage:
    template_name: str             # 模板名称（如 "dynamic_spec001"）
    prompt_json: dict              # prompt.json 内容
    seed_ideas_json: list[dict]    # seed_ideas.json 内容
    runtime_args: dict             # 运行时参数
        # {
        #   "num_ideas": 2,
        #   "writeup": "md",
        #   "model": "gpt-4",
        #   "parallel": 0,
        # }
```

**验证规则**:
- `template_name`: 必须是有效的目录名（无特殊字符）
- `prompt_json`: 必须包含 "system", "task" 字段
- `seed_ideas_json`: 至少包含 1 个 idea，最多 10 个
- `runtime_args.num_ideas`: 必须 >= 1 且 <= 10

**生成规则**:
- `prompt_json.task` 从 `ResearchSpec.objective` 提取
- `prompt_json.constraints` 从 `ResearchSpec.constraints` 转换
- `seed_ideas_json` 从 `ResearchSpec` 或 `ExperimentPlan` 提取

---

### 3. JobStatus（任务状态枚举）

**用途**: 标准化任务状态

**定义**:
```python
class JobStatus(str, Enum):
    PENDING = "pending"       # 排队中（等待并发槽位）
    RUNNING = "running"       # 运行中
    COMPLETED = "completed"   # 成功完成
    FAILED = "failed"         # 失败（进程崩溃、超时、错误）
```

**状态语义**:
- `PENDING`: 任务已提交，但因并发限制未启动
- `RUNNING`: 子进程正在运行
- `COMPLETED`: 子进程正常退出，结果文件存在
- `FAILED`: 子进程异常退出或超时

---

## 扩展现有实体

### ExperimentResult（实验结果）

**新增字段**:
```python
@dataclass
class ExperimentResult:
    # ... 现有字段 ...
    engine: str = "aisci"          # 新增：执行引擎（"aisci" | "ai-scientist" | "hybrid"）
    external_metadata: dict | None = None  # 新增：外部引擎元数据
        # {
        #   "job_id": "abc123",
        #   "template_name": "dynamic_spec001",
        #   "idea_name": "20260303_123456_idea_1",
        #   "ai_scientist_version": "v1.2.0",
        # }
```

**验证规则**:
- `engine`: 必须是 "aisci", "ai-scientist", "hybrid" 之一
- `external_metadata`: 当 `engine != "aisci"` 时必须提供

---

## 关系图

```
ResearchSpec
    ↓ (SpecMapper.map_to_template_package)
TemplatePackage
    ↓ (AIScientistAdapter.submit_job)
JobRecord (status=pending)
    ↓ (JobStore.submit_or_queue)
JobRecord (status=running)
    ↓ (JobCallbacks.poll_status)
JobRecord (status=completed/failed)
    ↓ (ResultParser.parse_result_dir)
ExperimentResult (engine="ai-scientist")
```

---

## 数据流示例

### 场景 1: 提交 AI-Scientist 任务

```python
# 1. 用户输入
spec = ResearchSpec(spec_id="exp001", objective="研究 XXX", ...)

# 2. 映射到模板
mapper = SpecMapper()
package = mapper.map_to_template_package(spec, plan=None)
# TemplatePackage(
#     template_name="dynamic_exp001",
#     prompt_json={"system": "...", "task": "研究 XXX"},
#     seed_ideas_json=[{"name": "Idea 1", ...}],
#     runtime_args={"num_ideas": 2, "writeup": "md"},
# )

# 3. 提交任务
adapter = AIScientistAdapter(runtime_dir=Path("external/ai-scientist-runtime"))
job_id = adapter.submit_job(
    template=package.template_name,
    num_ideas=package.runtime_args["num_ideas"],
    writeup=package.runtime_args["writeup"],
    model=package.runtime_args["model"],
)
# job_id = "abc123"

# 4. 记录任务
job_store = JobStore()
job_store.save(JobRecord(
    job_id=job_id,
    run_id="exp001",
    pid=12345,
    status="running",
    log_path="runs/exp001/external/logs/abc123.log",
    start_time=datetime.now(),
    end_time=None,
    error=None,
    template_name=package.template_name,
    num_ideas=2,
))
```

### 场景 2: 查询任务状态

```python
# 1. 查询任务记录
job_store = JobStore()
record = job_store.load(job_id="abc123")
# JobRecord(job_id="abc123", status="running", ...)

# 2. 检查进程状态
adapter = AIScientistAdapter(...)
status = adapter.get_status(job_id="abc123")
# JobStatus.RUNNING

# 3. 返回给用户
print(f"Status: {status}, Progress: 1/2 ideas completed")
```

### 场景 3: 获取结果

```python
# 1. 等待任务完成
job_store = JobStore()
record = job_store.load(job_id="abc123")
assert record.status == "completed"

# 2. 解析结果目录
parser = ResultParser()
result_dir = Path("external/ai-scientist-runtime/results/dynamic_exp001")
result = parser.parse_result_dir(result_dir)
# ExperimentResult(
#     run_id="exp001",
#     engine="ai-scientist",
#     status="completed",
#     report="...",
#     metrics={"accuracy": 0.95},
#     artifacts=["plots/fig1.png", "code/experiment.py"],
#     external_metadata={
#         "job_id": "abc123",
#         "template_name": "dynamic_exp001",
#         "idea_name": "20260303_123456_idea_1",
#     },
# )

# 3. 落盘到 runs 目录
result_path = Path(f"runs/{record.run_id}/external/ai_scientist/result.json")
result_path.write_text(result.model_dump_json(indent=2))
```

---

## 数据验证

### Pydantic 模型定义

```python
# src/schemas/ai_scientist.py

from datetime import datetime
from enum import Enum
from typing import Literal
from pydantic import BaseModel, Field, validator


class JobStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class JobRecord(BaseModel):
    job_id: str = Field(..., description="任务唯一标识")
    run_id: str = Field(..., description="关联的实验 run_id")
    pid: int = Field(..., gt=0, description="子进程 PID")
    status: JobStatus = Field(..., description="任务状态")
    log_path: str = Field(..., description="日志文件路径")
    start_time: datetime = Field(..., description="任务开始时间")
    end_time: datetime | None = Field(None, description="任务结束时间")
    error: str | None = Field(None, description="错误信息")
    template_name: str = Field(..., description="使用的模板名称")
    num_ideas: int = Field(..., ge=1, le=10, description="生成的 idea 数量")

    @validator("end_time")
    def end_time_after_start(cls, v, values):
        if v is not None and "start_time" in values:
            if v < values["start_time"]:
                raise ValueError("end_time must be after start_time")
        return v


class TemplatePackage(BaseModel):
    template_name: str = Field(..., description="模板名称")
    prompt_json: dict = Field(..., description="prompt.json 内容")
    seed_ideas_json: list[dict] = Field(..., description="seed_ideas.json 内容")
    runtime_args: dict = Field(..., description="运行时参数")

    @validator("seed_ideas_json")
    def validate_ideas_count(cls, v):
        if not (1 <= len(v) <= 10):
            raise ValueError("seed_ideas must contain 1-10 ideas")
        return v

    @validator("prompt_json")
    def validate_prompt_structure(cls, v):
        required_keys = {"system", "task"}
        if not required_keys.issubset(v.keys()):
            raise ValueError(f"prompt_json must contain keys: {required_keys}")
        return v
```

---

## 存储格式

### jobs.jsonl 示例

```jsonl
{"job_id":"abc123","run_id":"exp001","pid":12345,"status":"running","log_path":"runs/exp001/external/logs/abc123.log","start_time":"2026-03-03T10:00:00","end_time":null,"error":null,"template_name":"dynamic_exp001","num_ideas":2}
{"job_id":"def456","run_id":"exp002","pid":12346,"status":"pending","log_path":"runs/exp002/external/logs/def456.log","start_time":"2026-03-03T10:05:00","end_time":null,"error":null,"template_name":"dynamic_exp002","num_ideas":3}
{"job_id":"abc123","run_id":"exp001","pid":12345,"status":"completed","log_path":"runs/exp001/external/logs/abc123.log","start_time":"2026-03-03T10:00:00","end_time":"2026-03-03T12:30:00","error":null,"template_name":"dynamic_exp001","num_ideas":2}
```

**说明**:
- 每行一个 JSON 对象
- 同一个 job_id 可能有多条记录（状态更新时追加新行）
- 读取时取最新的记录（按 start_time 排序）

---

## 总结

定义了 3 个核心实体和 1 个扩展实体：
- `JobRecord`: 任务记录（持久化到 jobs.jsonl）
- `TemplatePackage`: 模板任务包（内存对象）
- `JobStatus`: 任务状态枚举
- `ExperimentResult`: 扩展现有实体，添加 engine 和 external_metadata 字段

所有实体均使用 Pydantic 进行验证，确保数据一致性。
