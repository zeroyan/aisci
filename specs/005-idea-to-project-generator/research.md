# Research: Idea-to-Project Generator

**Feature**: 005-idea-to-project-generator
**Date**: 2026-03-07
**Status**: Complete

## Research Questions

### Q1: How to implement multi-source academic paper search?

**Decision**: Use dedicated API clients for each source (arXiv, Semantic Scholar)

**Rationale**:
- arXiv API: Official Python client (`arxiv` package) with good documentation
- Semantic Scholar API: Official Python client (`semanticscholar` package) with citation data
- Both APIs are free for academic use with reasonable rate limits
- Dedicated clients handle pagination, rate limiting, and error handling

**Alternatives Considered**:
- **Web scraping**: Rejected due to fragility and legal concerns
- **Unified search API (e.g., CrossRef)**: Rejected due to limited coverage and slower response times
- **Google Scholar API**: Rejected due to lack of official API and ToS restrictions

**Implementation Notes**:
- arXiv: 3 requests/second rate limit, use `arxiv.Search()` with query string
- Semantic Scholar: 100 requests/second rate limit, use `/paper/search` endpoint
- Cache results in KnowledgeStore to minimize API calls

---

### Q2: How to implement code repository search?

**Decision**: Use GitHub API + Papers with Code scraping

**Rationale**:
- GitHub API: Official PyGithub client with comprehensive search capabilities
- Papers with Code: No official API, but structured HTML allows reliable scraping
- GitHub provides code quality signals (stars, forks, last update)
- Papers with Code links papers to implementations

**Alternatives Considered**:
- **GitLab/Bitbucket**: Rejected due to smaller ML/AI community presence
- **Hugging Face**: Considered for future addition, but not in MVP scope
- **Direct code search engines**: Rejected due to lack of paper-code linkage

**Implementation Notes**:
- GitHub: Use `search/repositories` endpoint with topic filters (e.g., `topic:transformer`)
- Papers with Code: Parse HTML from `https://paperswithcode.com/search?q=<query>`
- Limit to top 5 repositories by stars/relevance

---

### Q3: How to generate clarifying questions from incomplete ideas?

**Decision**: Use LLM with structured prompts + template-based fallback

**Rationale**:
- LLM can understand context and generate relevant questions
- Structured prompts ensure questions are specific and actionable
- Template-based fallback for common missing information (metric, baseline, dataset)
- Limit to 5 questions to avoid user fatigue

**Alternatives Considered**:
- **Rule-based question generation**: Rejected due to lack of flexibility
- **Pre-defined question templates only**: Rejected due to inability to handle diverse ideas
- **Unlimited questions**: Rejected due to poor user experience

**Implementation Notes**:
- Prompt template: "Given research idea: {idea}, identify missing information from: objective, metric, baseline, dataset, constraints"
- LLM generates questions in JSON format: `[{"question": "...", "options": [...]}]`
- Fallback templates for common cases (e.g., "What metric do you want to optimize?")

---

### Q4: How to cache and retrieve evidence from knowledge base?

**Decision**: Reuse existing KnowledgeStore with topic-based indexing

**Rationale**:
- KnowledgeStore already implements file-based caching with JSON storage
- Topic-based indexing allows efficient retrieval by research area
- 30-day expiration balances freshness with API cost reduction
- Global knowledge base (`scientist/`) shared across projects

**Alternatives Considered**:
- **Database (SQLite/PostgreSQL)**: Rejected due to added complexity for file-based system
- **Vector database (Chroma/Pinecone)**: Rejected as overkill for exact topic matching
- **No caching**: Rejected due to high API costs and slow response times

**Implementation Notes**:
- Cache key: normalized topic string (lowercase, remove special chars)
- Cache structure: `scientist/<topic>/papers.json`, `scientist/<topic>/code.json`
- Metadata: `{"timestamp": "...", "query": "...", "results": [...]}`
- Expiration check: compare `timestamp` with current time

---

### Q5: How to generate multiple candidate proposals (conservative/balanced/aggressive)?

**Decision**: Use LLM with different risk profiles in system prompts

**Rationale**:
- LLM can understand risk/reward tradeoffs
- System prompts guide generation toward different profiles
- Conservative: replicate existing work with small improvements
- Balanced: combine multiple approaches
- Aggressive: explore novel directions

**Alternatives Considered**:
- **Rule-based proposal generation**: Rejected due to lack of creativity
- **Single proposal only**: Rejected due to lack of user choice
- **User-defined risk profile**: Deferred to P2 (future enhancement)

**Implementation Notes**:
- Conservative prompt: "Generate a low-risk research plan that replicates {baseline} with incremental improvements"
- Balanced prompt: "Generate a moderate-risk research plan that combines {baseline1} and {baseline2}"
- Aggressive prompt: "Generate a high-risk research plan that explores novel approaches beyond {baseline}"
- Each proposal includes: objective, metrics, baseline, risks, expected outcomes

---

### Q6: How to validate generated ResearchSpec is executable?

**Decision**: Implement readiness checker with 5 validation rules (P3 feature)

**Rationale**:
- Metrics measurability: check if metrics have clear evaluation methods
- Baseline availability: check if baseline code/paper is accessible
- Dependencies installable: check if required packages exist in PyPI
- Budget reasonableness: check if budget aligns with task complexity
- Failure criteria clarity: check if failure conditions are well-defined

**Alternatives Considered**:
- **No validation**: Rejected due to risk of generating unusable specs
- **Full simulation**: Rejected due to high computational cost
- **Manual review only**: Rejected due to poor user experience

**Implementation Notes**:
- Validation rules implemented as separate functions
- Each rule returns: `{"passed": bool, "message": str, "suggestion": str}`
- Aggregate results into ReadinessReport
- P3 priority: implement after core functionality is stable

---

## Technology Decisions

### External API Clients

| API | Client Library | Rate Limit | Cost |
|-----|---------------|------------|------|
| arXiv | `arxiv` (official) | 3 req/s | Free |
| Semantic Scholar | `semanticscholar` (official) | 100 req/s | Free |
| GitHub | `PyGithub` (official) | 5000 req/hour (authenticated) | Free |
| Papers with Code | Custom scraper (BeautifulSoup) | No official limit | Free |

### LLM Usage

- **Idea parsing**: Extract entities (task, model, dataset, metric)
- **Question generation**: Generate 2-5 clarifying questions
- **Proposal synthesis**: Generate 3 candidate ResearchSpecs
- **Evidence summarization**: Summarize search results into evidence report

**Estimated token usage per project**:
- Idea parsing: ~500 tokens
- Question generation: ~1000 tokens
- Proposal synthesis: ~3000 tokens (3 proposals)
- Evidence summarization: ~2000 tokens
- **Total**: ~6500 tokens (~$0.01 per project with GPT-4)

### Knowledge Base Structure

```text
scientist/                          # Global knowledge base
├── transformer_optimization/       # Topic-based directory
│   ├── papers.json                # Cached paper search results
│   ├── code.json                  # Cached code search results
│   └── metadata.json              # Cache metadata (timestamp, query)
└── ...

runs/<proj_id>/knowledge/          # Project-specific knowledge
├── evidence_report.md             # Generated evidence report
├── sources.json                   # Citation list
└── clarifications.json            # User answers to questions
```

## Best Practices

### Evidence Search

1. **Query construction**: Use specific keywords from idea (task + model + method)
2. **Result ranking**: Sort by relevance (citations × recency weight)
3. **Deduplication**: Remove duplicate papers across sources
4. **Filtering**: Exclude papers older than 5 years (configurable)

### Interactive Clarification

1. **Question prioritization**: Ask about objective → metric → baseline → constraints
2. **Multiple choice preferred**: Provide 3-5 options when possible
3. **Skip option**: Always allow users to skip with defaults
4. **Context preservation**: Show user's original idea in each question

### Proposal Generation

1. **Evidence-based**: All proposals must reference specific papers/code
2. **Risk labeling**: Clearly mark conservative/balanced/aggressive
3. **Tradeoff explanation**: Explain pros/cons of each approach
4. **Baseline requirement**: Every proposal must have a baseline method

### Knowledge Consolidation

1. **Cache invalidation**: Refresh cache after 30 days
2. **Manual refresh**: Support `--force-refresh` flag
3. **Partial caching**: Cache papers and code separately
4. **Error handling**: Fall back to direct API on cache corruption

## Open Questions

None. All research questions resolved.

## References

- arXiv API Documentation: https://info.arxiv.org/help/api/index.html
- Semantic Scholar API: https://api.semanticscholar.org/
- GitHub REST API: https://docs.github.com/en/rest
- Papers with Code: https://paperswithcode.com/
- Existing KnowledgeStore implementation: `src/knowledge/store.py`
