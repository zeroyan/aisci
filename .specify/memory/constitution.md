<!--
同步影响报告
- 版本变更: 2.0.0 → 3.0.0 (MAJOR: 删除可观测性和简单优先原则，新增 Python 环境管理规范，全文档中文化)
- 删除原则: Observability（可观测性）、Simplicity & YAGNI（简单优先）
- 保留原则: 模块化架构、Schema 先行、安全执行
- 变更: 全文档改为中文输出，代码注释保持英文
- 新增: Python 环境管理规范（固定路径、虚拟环境）
- 模板待更新: ⚠ plan-template.md (待同步), ⚠ spec-template.md (待同步), ⚠ tasks-template.md (待同步)
-->

# AiSci 项目宪法

## 核心原则

### 一、模块化架构

系统按独立模块组织，模块间松耦合。
- 每个模块必须可独立运行和测试，不依赖其他模块的运行时状态。
- 模块间数据传递通过文件（JSON/Markdown），禁止内存共享或全局状态。
- 新增模块不得破坏已有模块的独立可用性。

### 二、Schema 先行

模块间的输入输出格式必须先定义、后实现。
- 每个模块的输入输出必须有对应的 JSON Schema 定义。
- Schema 变更必须先更新定义文件，再修改实现代码。
- 不符合 Schema 的数据必须在模块入口处拒绝，不得静默忽略。

### 三、安全执行

系统会调用 LLM 生成并执行代码，必须有隔离和兜底机制。
- LLM 生成的代码必须在容器/沙箱中执行，禁止直接在宿主环境运行。
- 每次执行必须设置超时和资源上限（CPU/内存/磁盘）。
- 执行中止时必须保存已产生的中间结果和日志，不得全部丢失。
- 禁止执行未经白名单校验的系统命令和网络请求。

## 技术约束

### 技术栈
- 语言：Python 3.11+
- 代码风格：ruff（lint + format）
- LLM 调用：统一抽象层，当前对接云端 API（OpenAI/Anthropic/DeepSeek），接口设计须支持未来切换私有部署
- 数据存储：按需选择，文件系统或数据库均可，以实际场景为准
- 前端：功能实现为主，先简单能用，后续迭代优化
- 实验隔离：Docker

### Python 环境管理
- 使用系统 Python 路径（当前为 Python 3.11+），不额外安装独立 Python
- 项目虚拟环境固定路径：`<项目根目录>/.venv/`
- 创建方式：`python3 -m venv --system-site-packages .venv`（继承系统已安装的包，避免重复下载）
- 激活方式：`source .venv/bin/activate`
- 项目专属依赖在虚拟环境内安装，系统已有的包直接复用
- 依赖文件：`requirements.txt`（运行依赖）+ `requirements-dev.txt`（开发依赖）
- 安装依赖统一命令：`pip install -r requirements.txt -r requirements-dev.txt`
- 新增依赖后须更新 requirements 文件
- `.venv/` 目录加入 `.gitignore`，不提交到版本控制

### 依赖管理
- 新增第三方依赖须在提交描述中说明理由。
- 核心流程禁止依赖 GPU（GPU 仅限实验执行容器内部）。
- `external/` 目录存放外部参考代码（如 AI-Scientist），不直接修改其源码，通过适配层调用。

### 安全
- API Key 通过环境变量或 `.env` 文件注入，禁止硬编码或提交到版本控制。
- `.gitignore` 必须包含 `.env`、`.venv/`、`runs/`、`__pycache__/`。
- 用户输入传递给 LLM 前须经过基本校验（长度、格式）。

### 语言规范
- 所有文档（宪法、spec、plan、tasks、README 等）使用中文。
- 代码中的注释使用英文。
- 代码中的变量名、函数名、类名使用英文。
- commit message 使用英文，遵循 Conventional Commits 格式。

## 开发流程与质量门禁

### 开发流程
1. 功能开发遵循 speckit 流程：constitution → spec → plan → tasks → implement。
2. 每个模块须有至少一个可运行的示例（`examples/` 或 CLI 命令）。
3. 代码提交前须通过 `ruff check`。

### 质量门禁
- Gate A（Spec 完整性）：功能需求和成功指标齐全后才能进入 plan 阶段。
- Gate B（Schema 定义）：模块间接口 Schema 定义完成后才能开始实现。
- Gate C（可运行验证）：模块实现后须有至少一个端到端示例通过。

### 目录结构约定
```text
aisci/
├── .venv/                # Python 虚拟环境（gitignore）
├── src/                  # 源代码
│   ├── agents/           # 各能力模块
│   ├── orchestrator/     # 流水线编排
│   ├── llm/              # LLM 调用抽象层
│   └── schemas/          # JSON Schema 定义
├── prompts/              # 系统提示词
├── configs/              # 配置文件（模型、预算、重试策略）
├── runs/                 # 运行产物（gitignore）
├── tests/                # 测试
├── external/             # 外部参考代码
├── docs/                 # 文档
└── specs/                # speckit 功能规格
```

## 治理

1. 本宪法优先级高于临时开发习惯和口头约定。
2. 宪法修订须记录：修订动机、影响范围、版本变更说明。
3. 对违反核心原则的实现，默认拒绝合并。
4. 当原则间冲突时，优先级：安全执行 > Schema 先行 > 模块化架构。

**版本**: 3.0.0 | **生效日期**: 2026-02-27 | **最近修订**: 2026-02-27
