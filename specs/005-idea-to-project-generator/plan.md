# Implementation Plan: Idea-to-Project Generator

**Branch**: `005-idea-to-project-generator` | **Date**: 2026-03-07 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/005-idea-to-project-generator/spec.md`

**Note**: This template is filled in by the `/speckit.plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Transform vague research ideas into executable scientific projects through evidence-based research, knowledge consolidation, and interactive clarification. The system accepts natural language ideas, searches academic papers and code repositories, asks clarifying questions, and generates complete project packages (ResearchSpec + ExperimentPlan + Evidence Report) ready for execution by existing Spec001/003/004 infrastructure.

**Core Technical Approach**:
- Reuse existing KnowledgeStore (Spec002) for caching and retrieval
- Implement multi-source evidence search (arXiv, Semantic Scholar, GitHub, Papers with Code)
- Build interactive clarification agent with LLM-powered question generation
- Generate multiple candidate proposals (conservative/balanced/aggressive)
- Output standard project packages compatible with existing execution engines

## Technical Context

**Language/Version**: Python 3.11+
**Primary Dependencies**:
- LiteLLM (LLM abstraction)
- Pydantic v2 (data validation)
- Existing KnowledgeStore (Spec002)
- External APIs: arXiv, Semantic Scholar, GitHub, Papers with Code

**Storage**: File system (JSON for specs/plans, Markdown for reports, existing KnowledgeStore structure)
**Testing**: pytest (unit + integration tests)
**Target Platform**: CLI tool (Linux/macOS)
**Project Type**: CLI tool with agent-based workflow
**Performance Goals**:
- Evidence search completes within 30 seconds for 95% of queries
- End-to-end project generation in under 5 minutes
- Knowledge cache reduces search time by 80% for repeated topics

**Constraints**:
- Must reuse existing KnowledgeStore structure
- Must generate output compatible with Spec001/003/004
- Must handle external API failures gracefully
- Clarifying questions limited to 5 or fewer

**Scale/Scope**:
- Support 1000+ cached topics in knowledge base
- Handle 10+ concurrent project generations
- Process ideas ranging from 1 sentence to 3 paragraphs

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

### Gate A: 模块化架构 ✅ PASS

- **独立模块**: 新增 `src/agents/project_generator/` 模块，独立于现有 experiment 和 plan agents
- **数据传递**: 通过文件传递（JSON/Markdown），不依赖内存共享
- **不破坏现有模块**: 复用 KnowledgeStore，不修改其接口

### Gate B: Schema 先行 ✅ PASS

- **输入 Schema**: IdeaRecord (新增)
- **输出 Schema**: ResearchSpec (现有，扩展 evidence metadata), ExperimentPlan (现有，扩展 baseline guidance)
- **中间 Schema**: EvidencePackage, EvidenceReport, KnowledgeCache (新增)
- **Schema 定义**: 所有 Schema 在 Phase 1 完成前定义

### Gate C: 安全执行 ✅ PASS

- **无代码执行**: 本模块不执行 LLM 生成的代码，仅生成项目配置
- **外部 API 调用**: 有超时和重试机制
- **资源限制**: 搜索结果限制（top 10 papers, top 5 repos）

### 依赖管理 ✅ PASS

- **新增依赖**:
  - `arxiv` (arXiv API client)
  - `semanticscholar` (Semantic Scholar API client)
  - `PyGithub` (GitHub API client)
- **理由**: 必需的外部 API 客户端，无合适替代
- **无 GPU 依赖**: 纯 CPU 操作

### 安全 ✅ PASS

- **API Keys**: 通过环境变量注入（ARXIV_API_KEY, SEMANTIC_SCHOLAR_API_KEY, GITHUB_TOKEN）
- **用户输入校验**: 想法长度限制（1-1000 字符），基本格式校验

## Project Structure

### Documentation (this feature)

```text
specs/005-idea-to-project-generator/
├── plan.md              # This file (/speckit.plan command output)
├── research.md          # Phase 0 output (/speckit.plan command)
├── data-model.md        # Phase 1 output (/speckit.plan command)
├── quickstart.md        # Phase 1 output (/speckit.plan command)
├── contracts/           # Phase 1 output (/speckit.plan command)
│   └── cli_commands.md  # CLI command specifications
└── tasks.md             # Phase 2 output (/speckit.tasks command - NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
src/
├── agents/
│   └── project_generator/          # New module for Spec005
│       ├── __init__.py
│       ├── intake_agent.py         # Idea parsing and entity extraction
│       ├── clarification_agent.py  # Interactive question generation
│       ├── evidence_searcher.py    # Multi-source evidence search
│       ├── knowledge_consolidator.py # Cache management and report generation
│       ├── formalization_agent.py  # ResearchSpec generation
│       ├── proposal_generator.py   # Multiple candidate generation
│       └── readiness_checker.py    # Validation gate (P3)
├── schemas/
│   └── project_generator.py        # New schemas: IdeaRecord, EvidencePackage, etc.
├── knowledge/
│   └── store.py                     # Existing KnowledgeStore (reused)
└── llm/
    └── client.py                    # Existing LLMClient (reused)

tests/
├── unit/
│   └── test_project_generator/
│       ├── test_intake_agent.py
│       ├── test_clarification_agent.py
│       ├── test_evidence_searcher.py
│       ├── test_knowledge_consolidator.py
│       ├── test_formalization_agent.py
│       └── test_proposal_generator.py
└── integration/
    └── test_project_generator_e2e.py

cli.py                               # Add new command: project generate
```

**Structure Decision**: Single project structure (Option 1) with new `project_generator` module under `src/agents/`. This follows the existing pattern of `experiment/` and `plan/` agents, maintaining consistency with the codebase architecture.

## Complexity Tracking

> No constitution violations requiring justification.

