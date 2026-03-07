# Data Model: Idea-to-Project Generator

**Feature**: 005-idea-to-project-generator
**Date**: 2026-03-07
**Status**: Complete

## Overview

This document defines the data entities and their relationships for the Idea-to-Project Generator. All entities are implemented as Pydantic v2 models with strict validation.

## Core Entities

### 1. IdeaRecord

Represents a parsed research idea with extracted entities and missing information flags.

**Purpose**: Capture user's initial idea and track what information is missing

**Fields**:
- `idea_id` (str): Unique identifier (UUID)
- `raw_text` (str): Original user input (1-1000 characters)
- `idea_type` (Literal["performance_improvement", "new_method", "problem_solving", "constraint_driven"]): Classified idea type
- `entities` (dict[str, str]): Extracted entities (task, model, dataset, metric)
- `missing_info` (list[str]): List of missing critical information (e.g., ["metric", "baseline"])
- `constraints` (Optional[Constraints]): User-provided constraints (budget, time, compute)
- `created_at` (datetime): Timestamp of creation

**Validation Rules**:
- `raw_text` must be 1-1000 characters
- `idea_type` must be one of the 4 defined types
- `entities` keys must be from: ["task", "model", "dataset", "metric", "method"]
- `missing_info` items must be from: ["objective", "metric", "baseline", "dataset", "constraints"]

**Relationships**:
- Input to ClarificationAgent
- Output from IntakeAgent

**Example**:
```json
{
  "idea_id": "idea_a3f8b2c1",
  "raw_text": "I want to improve Transformer speed on long texts",
  "idea_type": "performance_improvement",
  "entities": {
    "task": "long_text_processing",
    "model": "Transformer"
  },
  "missing_info": ["metric", "baseline", "dataset"],
  "constraints": null,
  "created_at": "2026-03-07T10:00:00Z"
}
```

---

### 2. ClarificationQuestion

Represents a single clarifying question with options.

**Purpose**: Capture questions to fill missing information

**Fields**:
- `question_id` (str): Unique identifier
- `question_text` (str): The question to ask user
- `question_type` (Literal["multiple_choice", "short_answer"]): Question format
- `options` (Optional[list[str]]): Multiple choice options (2-5 items)
- `default_answer` (Optional[str]): Default if user skips
- `required` (bool): Whether question must be answered
- `context` (str): Why this question is being asked

**Validation Rules**:
- `question_text` must be 10-500 characters
- If `question_type` is "multiple_choice", `options` must have 2-5 items
- `default_answer` must be in `options` if provided

**Relationships**:
- Output from ClarificationAgent
- Input to user interaction

**Example**:
```json
{
  "question_id": "q1",
  "question_text": "What metric do you want to optimize?",
  "question_type": "multiple_choice",
  "options": ["推理速度", "准确率", "内存占用", "训练成本"],
  "default_answer": "推理速度",
  "required": true,
  "context": "Need to define success criteria for the experiment"
}
```

---

### 3. EvidencePackage

Collection of search results from multiple sources.

**Purpose**: Aggregate evidence from papers, code, and existing knowledge

**Fields**:
- `package_id` (str): Unique identifier
- `query` (str): Original search query
- `papers` (list[PaperResult]): Academic papers (max 10)
- `code_repos` (list[CodeRepository]): Code repositories (max 5)
- `baselines` (list[BaselineMethod]): Extracted baseline methods
- `common_failures` (list[str]): Identified failure modes from literature
- `search_timestamp` (datetime): When search was performed
- `sources` (list[str]): APIs used (e.g., ["arxiv", "semantic_scholar", "github"])

**Validation Rules**:
- `papers` must have 0-10 items
- `code_repos` must have 0-5 items
- `baselines` must have at least 1 item if papers found
- `sources` must be from: ["arxiv", "semantic_scholar", "github", "papers_with_code", "cache"]

**Relationships**:
- Output from EvidenceSearcher
- Input to KnowledgeConsolidator and FormalizationAgent

**Example**:
```json
{
  "package_id": "evidence_x7y9z2",
  "query": "Transformer long text optimization",
  "papers": [...],
  "code_repos": [...],
  "baselines": [
    {
      "name": "FlashAttention",
      "paper_id": "arxiv:2205.14135",
      "description": "Fast and memory-efficient attention mechanism"
    }
  ],
  "common_failures": [
    "Memory overflow on sequences >8k tokens",
    "Quadratic complexity in sequence length"
  ],
  "search_timestamp": "2026-03-07T10:05:00Z",
  "sources": ["arxiv", "semantic_scholar", "github"]
}
```

---

### 4. PaperResult

Represents a single academic paper from search results.

**Purpose**: Store paper metadata and relevance information

**Fields**:
- `paper_id` (str): Unique identifier (e.g., "arxiv:2205.14135")
- `title` (str): Paper title
- `authors` (list[str]): Author names
- `abstract` (str): Paper abstract (max 2000 characters)
- `published_date` (date): Publication date
- `citations` (int): Citation count
- `url` (str): Paper URL
- `relevance_score` (float): Computed relevance (0.0-1.0)
- `source` (Literal["arxiv", "semantic_scholar"]): Source API

**Validation Rules**:
- `title` must be 10-500 characters
- `authors` must have at least 1 item
- `abstract` must be 50-2000 characters
- `citations` must be >= 0
- `relevance_score` must be 0.0-1.0
- `url` must be valid HTTP(S) URL

**Relationships**:
- Part of EvidencePackage
- Referenced in EvidenceReport

---

### 5. CodeRepository

Represents a code repository from search results.

**Purpose**: Store repository metadata and quality signals

**Fields**:
- `repo_id` (str): Unique identifier (e.g., "github:org/repo")
- `name` (str): Repository name
- `description` (str): Repository description
- `url` (str): Repository URL
- `stars` (int): Star count
- `forks` (int): Fork count
- `last_updated` (date): Last commit date
- `language` (str): Primary programming language
- `topics` (list[str]): Repository topics/tags
- `has_paper` (bool): Whether linked to a paper
- `paper_id` (Optional[str]): Linked paper ID if available

**Validation Rules**:
- `name` must be 1-100 characters
- `stars` and `forks` must be >= 0
- `url` must be valid HTTP(S) URL
- If `has_paper` is True, `paper_id` must be provided

**Relationships**:
- Part of EvidencePackage
- Referenced in EvidenceReport

---

### 6. BaselineMethod

Represents an extracted baseline method from evidence.

**Purpose**: Capture recommended baseline approaches

**Fields**:
- `name` (str): Method name (e.g., "FlashAttention")
- `paper_id` (Optional[str]): Source paper ID
- `code_url` (Optional[str]): Implementation URL
- `description` (str): Brief description (max 500 characters)
- `difficulty` (Literal["easy", "medium", "hard"]): Implementation difficulty
- `estimated_time` (str): Estimated implementation time (e.g., "2-3 days")

**Validation Rules**:
- `name` must be 3-100 characters
- `description` must be 10-500 characters
- At least one of `paper_id` or `code_url` must be provided

**Relationships**:
- Part of EvidencePackage
- Referenced in ExperimentPlan

---

### 7. EvidenceReport

Markdown document summarizing search findings.

**Purpose**: Human-readable summary of evidence for user review

**Fields**:
- `report_id` (str): Unique identifier
- `idea_id` (str): Associated idea ID
- `summary` (str): Executive summary (max 1000 characters)
- `key_papers` (list[str]): Top 5 paper titles with citations
- `recommended_baselines` (list[str]): Baseline method names
- `identified_risks` (list[str]): Potential risks and challenges
- `citations` (list[str]): Full citation list
- `generated_at` (datetime): Report generation timestamp

**Validation Rules**:
- `summary` must be 100-1000 characters
- `key_papers` must have 1-5 items
- `recommended_baselines` must have 1-3 items
- `identified_risks` must have 1-5 items

**Relationships**:
- Output from KnowledgeConsolidator
- Input to FormalizationAgent
- Saved to `runs/<proj_id>/knowledge/evidence_report.md`

---

### 8. ResearchProposal

Represents a single candidate research proposal.

**Purpose**: Capture one approach (conservative/balanced/aggressive)

**Fields**:
- `proposal_id` (str): Unique identifier
- `risk_profile` (Literal["conservative", "balanced", "aggressive"]): Risk level
- `title` (str): Proposal title
- `objective` (str): Research objective
- `approach` (str): High-level approach description
- `baseline_method` (str): Baseline to compare against
- `expected_metrics` (dict[str, float]): Expected metric values
- `risks` (list[str]): Identified risks
- `estimated_cost` (float): Estimated cost in USD
- `estimated_time` (str): Estimated time (e.g., "3-5 days")
- `evidence_support` (list[str]): Supporting paper IDs

**Validation Rules**:
- `title` must be 10-200 characters
- `objective` must be 20-500 characters
- `approach` must be 50-1000 characters
- `risks` must have 1-5 items
- `estimated_cost` must be > 0
- `evidence_support` must have at least 1 item

**Relationships**:
- Output from ProposalGenerator
- Input to user selection
- Converted to ResearchSpec after selection

---

### 9. KnowledgeCache

Cached search results with expiration.

**Purpose**: Store and retrieve cached evidence to reduce API calls

**Fields**:
- `cache_key` (str): Normalized topic string (lowercase, no special chars)
- `query` (str): Original search query
- `results` (EvidencePackage): Cached evidence package
- `timestamp` (datetime): Cache creation time
- `expires_at` (datetime): Cache expiration time (timestamp + 30 days)
- `hit_count` (int): Number of times cache was used

**Validation Rules**:
- `cache_key` must be 3-100 characters, alphanumeric + underscore only
- `expires_at` must be after `timestamp`
- `hit_count` must be >= 0

**Relationships**:
- Stored in KnowledgeStore (`scientist/<topic>/`)
- Retrieved by EvidenceSearcher before external API calls

**Storage Format**:
```text
scientist/<cache_key>/
├── metadata.json       # Cache metadata (timestamp, query, hit_count)
├── papers.json         # Cached paper results
└── code.json          # Cached code repository results
```

---

## Extended Entities (Existing Schemas)

### 10. ResearchSpec (Extended)

**New Fields Added**:
- `evidence_metadata` (dict): Evidence source information
  - `source_papers` (list[str]): Paper IDs used in spec generation
  - `baseline_references` (list[str]): Baseline method references
  - `risk_assessment` (str): Risk level and mitigation strategies
  - `generated_from_idea` (str): Original idea text

**Validation Rules**:
- `evidence_metadata` must be present for auto-generated specs
- `source_papers` must have at least 1 item
- `baseline_references` must have at least 1 item

---

### 11. ExperimentPlan (Extended)

**New Fields Added**:
- `baseline_guidance` (dict): Baseline implementation guidance
  - `method_name` (str): Baseline method name
  - `paper_reference` (str): Paper ID or URL
  - `code_reference` (Optional[str]): Code repository URL
  - `implementation_notes` (str): Step-by-step guidance
  - `estimated_time` (str): Implementation time estimate

**Validation Rules**:
- `baseline_guidance` must be present for auto-generated plans
- `method_name` must match one of the baselines from EvidencePackage

---

## Entity Relationships

```text
User Input (raw idea)
    ↓
IdeaRecord (parsed)
    ↓
ClarificationQuestion[] (if missing info)
    ↓
IdeaRecord (updated with answers)
    ↓
EvidencePackage (search results)
    ├── PaperResult[]
    ├── CodeRepository[]
    └── BaselineMethod[]
    ↓
EvidenceReport (summary)
    ↓
ResearchProposal[] (3 candidates)
    ↓
User Selection
    ↓
ResearchSpec (extended) + ExperimentPlan (extended)
```

## State Transitions

### IdeaRecord States

1. **Created**: Initial parsing complete, entities extracted
2. **Clarifying**: Missing information identified, questions generated
3. **Clarified**: User answered questions, ready for evidence search
4. **Researched**: Evidence collected, ready for proposal generation
5. **Proposed**: Proposals generated, awaiting user selection
6. **Finalized**: User selected proposal, spec/plan generated

### KnowledgeCache States

1. **Fresh**: Cache age < 30 days, can be used
2. **Stale**: Cache age >= 30 days, should be refreshed
3. **Expired**: Cache deleted or corrupted, must re-fetch

## Validation Summary

All entities use Pydantic v2 with:
- Strict type checking (`strict=True`)
- Field validation (`Field(...)` with constraints)
- Custom validators for complex rules (`@field_validator`)
- Serialization to JSON (`model_dump(mode="json")`)
- Deserialization from JSON (`model_validate(data)`)

## Storage Locations

| Entity | Storage Location | Format |
|--------|-----------------|--------|
| IdeaRecord | `runs/<proj_id>/idea.json` | JSON |
| ClarificationQuestion | In-memory (not persisted) | N/A |
| EvidencePackage | `runs/<proj_id>/knowledge/evidence.json` | JSON |
| EvidenceReport | `runs/<proj_id>/knowledge/evidence_report.md` | Markdown |
| ResearchProposal | `runs/<proj_id>/proposals.json` | JSON |
| KnowledgeCache | `scientist/<topic>/` | JSON (split files) |
| ResearchSpec | `runs/<proj_id>/spec/research_spec.json` | JSON |
| ExperimentPlan | `runs/<proj_id>/plan/experiment_plan.json` | JSON |

## Schema Versioning

All schemas include a `schema_version` field for future compatibility:
- Current version: `"1.0.0"`
- Version format: Semantic versioning (MAJOR.MINOR.PATCH)
- Breaking changes require MAJOR version bump
