# Phase 0 技术调研：Phase 1A 自主实验闭环

**日期**: 2026-02-28
**关联**: `/specs/001-research-copilot-mvp/plan.md`

## 调研项

### 1. LLM 调用库选型

**决策**: litellm

**理由**:
- 宪法要求"统一抽象层，当前对接 OpenAI/Anthropic/DeepSeek，接口设计须支持未来切换"
- litellm 提供统一 `completion()` 接口，支持 100+ 模型提供商
- 内置 token 计数和 cost 追踪，直接满足 FR-007（成本记录）
- 支持 fallback 模型和重试策略，满足 contracts 中的 LLM 降级需求

**备选方案**:
- `openai` SDK 直接调用：只支持 OpenAI 格式 API，切换提供商需自行适配 → 不满足宪法
- `anthropic` SDK：同上，仅支持单一提供商
- 自建抽象层：重复造轮子，litellm 已解决此问题

### 2. 数据校验库选型

**决策**: pydantic v2

**理由**:
- 宪法要求 Schema 先行，contracts.md 已定义完整 JSON 结构
- Pydantic model = 可执行的 JSON Schema，天然满足 Gate B
- v2 性能大幅提升（Rust core），序列化/反序列化内置
- 与 litellm 和 typer 生态兼容良好

**备选方案**:
- dataclasses + 手动校验：缺少 JSON Schema 导出，校验逻辑分散 → 维护成本高
- attrs + cattrs：功能类似 Pydantic 但生态小，文档少
- jsonschema 库：只做校验不做建模，仍需额外 ORM → 过于底层

### 3. CLI 框架选型

**决策**: typer

**理由**:
- Phase 1A 是 CLI 工具，需要 CreateRun/StartRun/ControlRun 等命令
- typer 基于类型注解自动生成帮助文档和参数解析
- 与 Pydantic 配合良好（都基于 type hints）
- 后续加 FastAPI HTTP 层时，两者同生态（FastAPI 作者同为 tiangolo）

**备选方案**:
- argparse：标准库但 boilerplate 多，子命令支持弱
- click：typer 的底层，手动装饰器写法更繁琐

### 4. 沙箱方案（MVP）

**决策**: subprocess + venv（MVP），接口抽象支持后续 Docker 替换

**理由**:
- contracts 4.5 节已列出三种方案，建议 MVP 从 subprocess + venv 起步
- 本地开发阶段无需 Docker 开销，降低启动门槛
- 抽象 `SandboxExecutor` 基类，后续只需新增 `DockerSandbox` 子类

**风险**:
- subprocess 隔离性低，恶意代码可访问宿主文件系统
- 缓解措施：MVP 阶段仅运行自己生成的可信代码，后续 Docker 化解决

**备选方案**:
- Docker（直接）：隔离性好但增加 MVP 复杂度，需处理镜像构建/GPU 映射
- Modal/E2B（云沙箱）：隔离性最好但增加外部依赖和成本，不适合 MVP

### 5. 同步 vs 异步

**决策**: 同步执行（MVP）

**理由**:
- Phase 1A 是单用户单 run，Agent 循环本质是顺序的（codegen → execute → analyze → decide）
- 沙箱执行用 `subprocess.run()` 阻塞等待即可
- 无并发需求，async 增加复杂度无收益

**备选方案**:
- asyncio：允许并行执行多个实验，但 MVP 不需要，YAGNI

### 6. 配置管理

**决策**: YAML 配置文件 + 环境变量（API keys）

**理由**:
- 宪法要求 API Key 通过环境变量或 .env 注入
- 实验配置（预算、超时、重试策略）用 YAML，可读性好
- python-dotenv 加载 .env，PyYAML 解析配置

**配置优先级**: CLI 参数 > 环境变量 > configs/default.yaml

## 依赖清单

### 运行依赖 (requirements.txt)

| 包 | 版本 | 用途 |
|----|------|------|
| pydantic | >=2.0 | 数据模型 + Schema 校验 |
| litellm | >=1.0 | 统一 LLM 调用 |
| typer | >=0.9 | CLI 框架 |
| pyyaml | >=6.0 | 配置文件解析 |
| python-dotenv | >=1.0 | .env 文件加载 |

### 开发依赖 (requirements-dev.txt)

| 包 | 版本 | 用途 |
|----|------|------|
| pytest | >=7.0 | 测试框架 |
| pytest-cov | >=4.0 | 覆盖率 |
| ruff | >=0.4 | lint + format（宪法约定） |

## 所有 NEEDS CLARIFICATION 已解决

无未解决项。Technical Context 中所有选型已确定。
