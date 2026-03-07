# Feature Specification: Idea-to-Project Generator

**Feature Branch**: `005-idea-to-project-generator`
**Created**: 2026-03-07
**Status**: Draft
**Input**: Transform vague research ideas into executable scientific projects through evidence search, knowledge consolidation, and interactive clarification

## Overview

The Idea-to-Project Generator transforms vague research ideas into fully executable scientific projects. Instead of requiring users to manually write `research_spec.json` and `experiment_plan.json`, users provide a natural language description of their research idea, and the system automatically generates a complete, ready-to-execute project package through evidence-based research, knowledge consolidation, and interactive clarification.

**Core Value**: Lower the barrier to entry for scientific experimentation by automating the project setup phase while ensuring quality through evidence-based decision making.

## User Scenarios & Testing

### User Story 1 - Basic Idea-to-Project Conversion (Priority: P1)

A researcher has a vague idea ("I want to improve Transformer speed on long texts") and wants to quickly start experimenting without manually researching baselines, writing specs, or configuring experiments.

**Why this priority**: This is the core value proposition - converting ideas to executable projects. Without this, the feature has no value.

**Independent Test**: User provides a one-sentence idea, system generates `research_spec.json` + `experiment_plan.json`, and the user can immediately run `cli.py run start <project_id>` successfully.

**Acceptance Scenarios**:

1. **Given** user provides "I want to improve Transformer speed on long texts"
   **When** system processes the idea
   **Then** system generates a valid ResearchSpec with clear objectives, metrics, and constraints

2. **Given** system has generated a ResearchSpec
   **When** user confirms the spec
   **Then** system outputs `research_spec.json`, `experiment_plan.json`, and `evidence_report.md` to `runs/proj_<id>/`

3. **Given** project package is generated
   **When** user runs `cli.py run start proj_<id>`
   **Then** experiment executes successfully without errors

---

### User Story 2 - Evidence-Based Research (Priority: P1)

A researcher wants their project to be grounded in existing literature and methods, not just LLM hallucinations. The system must search for relevant papers, code repositories, and baselines before generating the project.

**Why this priority**: Critical for scientific validity. Without evidence search, the system would generate unreliable projects based on LLM guesses.

**Independent Test**: System searches academic papers and code repositories, generates an evidence report with citations, and uses this evidence to inform the ResearchSpec generation.

**Acceptance Scenarios**:

1. **Given** user provides a research idea
   **When** system searches for evidence
   **Then** system finds at least 5 relevant papers and 3 code repositories

2. **Given** evidence is found
   **When** system generates ResearchSpec
   **Then** ResearchSpec includes baseline methods from the evidence

3. **Given** evidence is collected
   **When** system generates evidence report
   **Then** report includes paper titles, authors, citations, and relevance scores

---

### User Story 3 - Interactive Clarification (Priority: P1)

A researcher's initial idea is missing key information (e.g., target metric, budget, dataset). The system asks targeted questions to fill gaps rather than making arbitrary assumptions.

**Why this priority**: Essential for generating accurate, user-aligned projects. Without clarification, the system would make wrong assumptions about user intent.

**Independent Test**: System identifies missing information, asks 2-5 clarifying questions, incorporates user answers, and generates a complete ResearchSpec.

**Acceptance Scenarios**:

1. **Given** user provides incomplete idea "improve model performance"
   **When** system analyzes the idea
   **Then** system identifies missing information (metric, baseline, dataset)

2. **Given** missing information is identified
   **When** system asks clarifying questions
   **Then** questions are specific, actionable, and limited to 5 or fewer

3. **Given** user answers clarifying questions
   **When** system incorporates answers
   **Then** generated ResearchSpec reflects all user-provided information

---

### User Story 4 - Knowledge Consolidation (Priority: P2)

A researcher searches for the same topic multiple times. The system should cache search results to avoid redundant API calls and provide faster responses.

**Why this priority**: Improves efficiency and reduces costs, but not critical for core functionality.

**Independent Test**: System searches for "Transformer optimization" twice, second search returns cached results instantly without external API calls.

**Acceptance Scenarios**:

1. **Given** user searches for a topic for the first time
   **When** system completes the search
   **Then** results are saved to global knowledge base (`scientist/<topic>/`)

2. **Given** same topic is searched again
   **When** system checks knowledge base
   **Then** cached results are returned without external API calls

3. **Given** cached results exist
   **When** results are older than 30 days
   **Then** system refreshes the cache with new search

---

### User Story 5 - Multiple Candidate Proposals (Priority: P2)

A researcher wants to see different approaches (conservative, balanced, aggressive) before committing to one direction.

**Why this priority**: Provides user choice and transparency, but a single proposal would still be functional.

**Independent Test**: System generates 3 candidate ResearchSpecs with different risk/reward profiles, user selects one, and selected spec is used for project generation.

**Acceptance Scenarios**:

1. **Given** evidence is collected
   **When** system generates proposals
   **Then** system creates 3 distinct ResearchSpecs (conservative, balanced, aggressive)

2. **Given** 3 proposals are generated
   **When** user reviews proposals
   **Then** each proposal clearly explains its approach, risks, and expected outcomes

3. **Given** user selects a proposal
   **When** system proceeds with generation
   **Then** selected proposal is used as the basis for the final project package

---

### User Story 6 - Readiness Validation (Priority: P3)

Before finalizing the project, the system validates that the generated spec is executable (metrics are measurable, baseline is available, dependencies are installable).

**Why this priority**: Nice-to-have quality gate, but not blocking for MVP. Users can discover issues during execution.

**Independent Test**: System checks generated ResearchSpec against readiness criteria, identifies issues, and either auto-fixes or prompts user for corrections.

**Acceptance Scenarios**:

1. **Given** ResearchSpec is generated
   **When** system runs readiness check
   **Then** system validates metrics are measurable, baseline exists, and dependencies are available

2. **Given** readiness check fails
   **When** system identifies issues
   **Then** system provides specific, actionable feedback

3. **Given** readiness check passes
   **When** system finalizes project
   **Then** project package is marked as "ready to execute"

---

### Edge Cases

- **What happens when no relevant papers are found?**
  System falls back to general best practices and clearly marks the project as "exploratory" with higher risk.

- **What happens when user provides contradictory constraints?**
  (e.g., "achieve 99% accuracy with $5 budget in 1 hour")
  System detects infeasibility, explains the conflict, and asks user to adjust constraints.

- **What happens when evidence search returns too many results?**
  System ranks by relevance and recency, returns top 10 papers and top 5 code repos.

- **What happens when user skips all clarifying questions?**
  System uses reasonable defaults (documented in evidence report) and proceeds with generation.

- **What happens when knowledge base is corrupted or unavailable?**
  System falls back to direct API search and logs a warning.

## Requirements

### Functional Requirements

#### Idea Intake
- **FR-001**: System MUST accept natural language research ideas (1-3 sentences minimum)
- **FR-002**: System MUST parse ideas to extract key entities (task, model, dataset, metric)
- **FR-003**: System MUST identify missing critical information (objective, metric, baseline, constraints)
- **FR-004**: System MUST classify idea type (performance improvement, new method, problem solving, constraint-driven)

#### Interactive Clarification
- **FR-005**: System MUST generate targeted clarifying questions for missing information
- **FR-006**: System MUST limit clarifying questions to 5 or fewer
- **FR-007**: System MUST provide multiple-choice options for each question where applicable
- **FR-008**: System MUST allow users to skip questions and use defaults
- **FR-009**: System MUST incorporate user answers into the final ResearchSpec

#### Evidence Search
- **FR-010**: System MUST search academic papers (arXiv, Semantic Scholar)
- **FR-011**: System MUST search code repositories (GitHub, Papers with Code)
- **FR-012**: System MUST check local knowledge base before external API calls
- **FR-013**: System MUST rank search results by relevance, citations, and recency
- **FR-014**: System MUST extract baseline methods from search results
- **FR-015**: System MUST identify common failure modes from literature

#### Knowledge Consolidation
- **FR-016**: System MUST save search results to global knowledge base (`scientist/<topic>/`)
- **FR-017**: System MUST save project-specific evidence to local knowledge base (`runs/<proj_id>/knowledge/`)
- **FR-018**: System MUST generate evidence report with citations and summaries
- **FR-019**: System MUST cache search results for 30 days
- **FR-020**: System MUST support manual cache invalidation

#### Project Generation
- **FR-021**: System MUST generate valid ResearchSpec JSON conforming to existing schema
- **FR-022**: System MUST generate valid ExperimentPlan JSON conforming to existing schema
- **FR-023**: System MUST include baseline method recommendations in ExperimentPlan
- **FR-024**: System MUST set reasonable default constraints if not specified (budget: $100, time: 24h, iterations: 10)
- **FR-025**: System MUST generate evidence report in Markdown format

#### Multiple Proposals (P2)
- **FR-026**: System SHOULD generate 3 candidate ResearchSpecs (conservative, balanced, aggressive)
- **FR-027**: System SHOULD clearly label risk/reward profile of each proposal
- **FR-028**: System SHOULD allow user to select one proposal or request regeneration

#### Readiness Validation (P3)
- **FR-029**: System SHOULD validate metrics are measurable
- **FR-030**: System SHOULD validate baseline method is accessible
- **FR-031**: System SHOULD validate dependencies are installable
- **FR-032**: System SHOULD validate budget is reasonable for the task
- **FR-033**: System SHOULD provide actionable feedback for failed checks

### Key Entities

- **IdeaRecord**: Represents a parsed research idea with extracted entities (task, model, dataset, metric), idea type, and missing information flags

- **EvidencePackage**: Collection of search results including papers (title, authors, abstract, citations, URL), code repositories (name, stars, description, URL), baseline methods, and common failure modes

- **EvidenceReport**: Markdown document summarizing search findings, key papers, recommended baselines, identified risks, and citation list

- **ResearchSpec**: Existing schema extended with evidence metadata (source papers, baseline references, risk assessment)

- **ExperimentPlan**: Existing schema extended with baseline implementation guidance

- **KnowledgeCache**: Cached search results with topic, timestamp, results, and expiration date

## Success Criteria

### Measurable Outcomes

- **SC-001**: Users can generate a complete project package from a one-sentence idea in under 5 minutes (including clarification time)

- **SC-002**: 90% of generated ResearchSpecs are executable without manual editing

- **SC-003**: Evidence search finds relevant papers for 95% of research ideas (measured by user confirmation)

- **SC-004**: Knowledge cache reduces search time by 80% for repeated topics

- **SC-005**: Generated projects include at least 3 baseline method recommendations

- **SC-006**: Users successfully execute generated projects on first attempt 85% of the time

- **SC-007**: Clarifying questions are limited to 5 or fewer for 95% of ideas

- **SC-008**: Evidence reports include citations for all claims and recommendations

## Assumptions

- Users have basic understanding of their research domain (can answer clarifying questions)
- External APIs (arXiv, Semantic Scholar, GitHub) are available and responsive
- Users have necessary API keys configured (if required by search services)
- Generated projects will be executed using existing Spec001/003/004 infrastructure
- Knowledge base storage has sufficient capacity (estimated 1GB per 1000 cached topics)
- Users prefer evidence-based recommendations over pure LLM generation

## Dependencies

- **Spec002 (Plan Baseline MVP)**: Reuses KnowledgeStore for caching and retrieval
- **Spec001 (Research Copilot MVP)**: Generated projects must be compatible with ExperimentLoop
- **External APIs**: arXiv API, Semantic Scholar API, GitHub API, Papers with Code
- **LLM**: Requires LLM for idea parsing, question generation, and proposal synthesis

## Out of Scope

- **Automatic topic discovery**: System does not proactively suggest research ideas (user must provide initial idea)
- **Full literature review**: System provides evidence summary, not comprehensive literature review
- **Baseline code generation**: System recommends baselines but does not generate implementation code
- **Multi-user collaboration**: Single-user workflow only (no shared projects or collaborative editing)
- **Real-time paper monitoring**: Knowledge cache is static, not continuously updated
- **Custom search sources**: Limited to predefined APIs (arXiv, Semantic Scholar, GitHub, Papers with Code)

## Non-Functional Requirements

- **Performance**: Evidence search completes within 30 seconds for 95% of queries
- **Reliability**: System gracefully handles API failures with fallback to cached results or defaults
- **Usability**: CLI provides clear progress indicators during search and generation
- **Maintainability**: Evidence search logic is modular and supports adding new sources
- **Cost**: Knowledge caching reduces external API costs by 80% for repeated topics
