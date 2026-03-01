<div align="center">

# 🔬 AiSci

**AI-Driven Autonomous Scientific Research Assistant**

[![Python 3.13+](https://img.shields.io/badge/python-3.13+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-60%20passed-brightgreen.svg)](tests/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

[English](#) | [简体中文](#)

</div>

---

## 📖 Overview

**AiSci** 是一个面向"方案强、代码弱"团队的 AI 科研助手，通过多 Agent 协作自动化科研流程的关键环节。

### 核心能力

- 🤖 **自主实验执行**：AI Agent 自动编写代码、运行实验、分析结果
- 📋 **智能方案生成**：基于研究目标和知识库自动生成实验方案
- 🔄 **方案迭代优化**：根据实验结果提供修订建议，支持人机协同改进
- 📚 **知识库管理**：自动检索和缓存相关文献、技术文档

### 与现有工具的差异

| 特性 | AiSci | AI Scientist | FARS |
|------|-------|--------------|------|
| 实验自动化 | ✅ | ✅ | ❌ |
| 方案生成 | ✅ | ❌ | ✅ |
| 知识库沉淀 | ✅ | ❌ | ❌ |
| 方案修订循环 | ✅ | ❌ | ❌ |
| 工具调用模式 | Tool-use | Code generation | Multi-agent |

---

## ✨ Features

### ✅ 已实现功能

#### 🔄 实验执行循环 (Spec 001)
- **Tool-Use Agent 模式**：LLM 自主调用工具（`write_file`/`run_bash`/`read_file`/`finish`）
- **自动化实验流程**：代码生成 → 沙箱执行 → 结果分析 → 迭代优化
- **沙箱隔离**：基于 subprocess + venv 的安全执行环境
- **成本控制**：预算限制、超时保护、失败重试机制
- **实验报告**：自动生成结构化实验报告

#### 📋 方案生成与知识库 (Spec 002)
- **智能方案生成**：从 ResearchSpec 自动生成 ExperimentPlan（Markdown 格式）
- **两层知识库**：
  - 全局知识库（`scientist/`）：跨项目共享
  - 本地知识库（`runs/<run_id>/knowledge/`）：实验特定
- **多源检索**：Tavily、DuckDuckGo、arXiv、Semantic Scholar
- **方案修订循环**：基于实验结果生成修订建议，支持版本管理
- **CLI 工具**：`plan generate`、`plan show`、`plan revise` 命令

### 🚧 规划中功能

#### 📊 选题发现 (Spec 003)
- 多源���题挖掘（arXiv、Papers with Code、GitHub Trending）
- 候选课题评估与排序
- 研究空白识别

#### 📝 论文写作 (Spec 004)
- 自动生成论文初稿
- 图表自动生成
- 参考文献管理

---

## 🚀 Quick Start

### 环境要求

- Python 3.13+
- 虚拟环境（推荐使用 venv）

### 安装

```bash
# 克隆仓库
git clone https://github.com/yourusername/aisci.git
cd aisci

# 创建虚拟环境
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt

# 配置 API Keys（可选）
cp .env.example .env
# 编辑 .env 文件，填入你的 API keys
```

### 基础使用

#### 1. 生成实验方案

```bash
# 从研究规格生成方案
python cli.py plan generate tests/fixtures/sample_research_spec.json

# 查看生成的方案
python cli.py plan show <run_id>
```

#### 2. 运行实验

```bash
# 创建实验 run
python cli.py run create --spec tests/fixtures/sample_research_spec.json

# 启动实验（自动执行）
python cli.py run start <run_id>

# 查看实验状态
python cli.py run status <run_id>

# 生成实验报告
python cli.py run report <run_id>
```

#### 3. 迭代优化方案

```bash
# 基于实验结果生成修订建议
python cli.py plan revise <run_id>

# 审阅建议后应用修订（版本 +1）
python cli.py plan revise <run_id> --apply
```

### 完整工作流示例

```bash
# 1. 生成方案
python cli.py plan generate my_spec.json --run-id exp001

# 2. 创建实验
python cli.py run create --spec my_spec.json --plan runs/exp001/plan.md

# 3. 运行实验
python cli.py run start exp001

# 4. 查看结果
python cli.py run report exp001

# 5. 优化方案
python cli.py plan revise exp001 --apply

# 6. 使用新方案重新实验
python cli.py run create --spec my_spec.json --plan runs/exp001/plan.md
```

---

## 🏗️ Project Architecture

### 目录结构

```
aisci/
├── cli.py                      # CLI 入口
├── src/
│   ├── agents/                 # Agent 实现
│   │   ├── experiment/         # 实验执行 Agent
│   │   │   ├── loop.py         # 实验循环控制
│   │   │   ├── tool_agent.py   # Tool-use Agent
│   │   │   └── tool_dispatcher.py  # 工具调度器
│   │   └── plan/               # 方案生成 Agent
│   │       ├── plan_agent.py   # 方案生成
│   │       └── revision_agent.py  # 方案修订
│   ├── llm/                    # LLM 客户端
│   │   └── client.py           # LiteLLM 封装（重试+回退）
│   ├── sandbox/                # 沙箱执行
│   │   ├── base.py             # 抽象接口
│   │   └── subprocess_sandbox.py  # Subprocess 实现
│   ├── knowledge/              # 知识库
│   │   ├── store.py            # 知识存储
│   │   └── searcher.py         # 多源检索
│   ├── schemas/                # 数据模型（Pydantic）
│   ├── service/                # 业务服务
│   └── storage/                # 持久化存储
├── tests/                      # 测试（60 个测试）
│   ├── unit/                   # 单元测试
│   └── integration/            # 集成测试
├── configs/                    # 配置文件
├── docs/                       # 文档
└── specs/                      # 功能规格
    ├── 001-research-copilot-mvp/
    └── 002-plan-baseline-mvp/
```

### 核心组件

#### 1. Agent 层
- **ToolAgent**：基于 LLM 的工具调用 Agent，支持自主决策
- **PlanAgent**：方案生成 Agent，结合知识库生成实验方案
- **RevisionAgent**：方案修订 Agent，基于实验结果提供改进建议

#### 2. LLM 层
- **LLMClient**：统一的 LLM 接口，支持多模型（Claude、GPT、Ollama）
- 重试机制：超时重试、速率限制重试
- 回退策略：主模型失败自动切换到备用模型
- 成本追踪：自动累计 token 使用和成本

#### 3. 沙箱层
- **SandboxExecutor**：抽象接口，支持多种沙箱实现
- **SubprocessSandbox**：基于 subprocess + venv 的轻量级沙箱
- 安全隔离：工作目录隔离、命令白名单、超时保护

#### 4. 知识库层
- **KnowledgeStore**：两层缓存架构（全局 + 本地）
- **Searcher**：多源检索（Tavily、DuckDuckGo、arXiv、Semantic Scholar）
- 缓存优先：避免重复检索，降低成本

### 数据流

```
ResearchSpec (JSON)
    ↓
PlanAgent + KnowledgeStore
    ↓
ExperimentPlan (Markdown)
    ↓
ExperimentLoop + ToolAgent
    ↓
ToolDispatcher → Sandbox
    ↓
ExperimentReport (JSON)
    ↓
RevisionAgent
    ↓
Updated ExperimentPlan (v2)
```

---

## 🧪 Testing

```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行单元测试
python -m pytest tests/unit/ -v

# 运行集成测试
python -m pytest tests/integration/ -v

# 查看测试覆盖率
python -m pytest tests/ --cov=src --cov-report=html
```

**测试统计**：
- 总测试数：60
- 单元测试：53
- 集成测试：7
- 通过率：100%

---

## 📚 Related Reading

### 参考项目

- **[FARS](https://github.com/Future-Artificial-Intelligence-Research-Society/FARS)** - 多 Agent 科研框架，本项目的主要灵感来源
- **[AI Scientist](https://github.com/SakanaAI/AI-Scientist)** - 自动化科研系统，参考其实验执行流程
- **[AutoGPT](https://github.com/Significant-Gravitas/AutoGPT)** - 自主 Agent 框架，参考其工具调用模式

### 技术文档

- [LiteLLM Documentation](https://docs.litellm.ai/) - 统一 LLM API 接口
- [Pydantic V2](https://docs.pydantic.dev/latest/) - 数据验证和序列化
- [Typer](https://typer.tiangolo.com/) - CLI 框架

### 相关论文

- [Generative Agents: Interactive Simulacra of Human Behavior](https://arxiv.org/abs/2304.03442)
- [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629)
- [Toolformer: Language Models Can Teach Themselves to Use Tools](https://arxiv.org/abs/2302.04761)

---

## 🛣️ Roadmap

### Phase 1: 基础能力 ✅
- [x] 实验执行循环（Spec 001）
- [x] 方案生成与知识库（Spec 002）

### Phase 2: 选题与论文 🚧
- [ ] 选题发现（Spec 003）
- [ ] 论文写作（Spec 004）

### Phase 3: 高级功能 📋
- [ ] 自动审稿
- [ ] 方法论沉淀
- [ ] 多实验并行
- [ ] 可视化看板

---

## 🤝 Contributing

欢迎贡献！请查看 [CONTRIBUTING.md](CONTRIBUTING.md) 了解详情。

### 开发流程

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/amazing-feature`)
3. 提交更改 (`git commit -m 'feat: add amazing feature'`)
4. 推送到分支 (`git push origin feature/amazing-feature`)
5. 创建 Pull Request

### 代码规范

- 使用 `ruff` 进行代码格式化和 lint
- 遵循 Conventional Commits 规范
- 所有新功能必须包含测试
- 测试覆盖率不低于 80%

---

## 📄 License

本项目采用 MIT 许可证 - 详见 [LICENSE](LICENSE) 文件

---

## 🙏 Acknowledgments

- 感谢 [FARS](https://github.com/Future-Artificial-Intelligence-Research-Society/FARS) 项目提供的设计思路
- 感谢 [AI Scientist](https://github.com/SakanaAI/AI-Scientist) 项目的实验执行流程参考
- 感谢所有贡献者的支持

---

<div align="center">

**如果这个项目对你有帮助，请给个 ⭐️ Star！**

[Report Bug](https://github.com/yourusername/aisci/issues) · [Request Feature](https://github.com/yourusername/aisci/issues)

</div>
