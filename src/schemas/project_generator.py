"""Project Generator schemas for Idea-to-Project conversion."""

from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel, Field


class IdeaRecord(BaseModel):
    """Represents a parsed research idea with extracted entities."""

    idea_id: str = Field(..., description="Unique identifier (UUID)")
    raw_text: str = Field(..., min_length=1, max_length=1000, description="Original user input")
    idea_type: Literal["performance_improvement", "new_method", "problem_solving", "constraint_driven"]
    entities: dict[str, str] = Field(default_factory=dict, description="Extracted entities (task, model, dataset, metric)")
    missing_info: list[str] = Field(default_factory=list, description="List of missing critical information")
    constraints: Optional[dict] = Field(None, description="User-provided constraints")
    created_at: datetime = Field(default_factory=datetime.now)


class ClarificationQuestion(BaseModel):
    """Represents a single clarifying question with options."""

    question_id: str
    question_text: str = Field(..., min_length=10, max_length=500)
    question_type: Literal["multiple_choice", "short_answer"]
    options: Optional[list[str]] = Field(None, description="Multiple choice options (2-5 items)")
    default_answer: Optional[str] = None
    required: bool = True
    context: str = Field(..., description="Why this question is being asked")


class PaperResult(BaseModel):
    """Represents a single academic paper from search results."""

    paper_id: str
    title: str
    authors: list[str]
    abstract: str
    citations: int = 0
    year: int
    url: str
    source: Literal["arxiv", "semantic_scholar"]
    relevance_score: float = Field(0.0, ge=0.0, le=1.0)


class CodeRepository(BaseModel):
    """Represents a code repository from search results."""

    repo_id: str
    name: str
    description: str
    stars: int = 0
    forks: int = 0
    url: str
    language: Optional[str] = None
    last_updated: Optional[datetime] = None
    source: Literal["github", "papers_with_code"]


class BaselineMethod(BaseModel):
    """Represents an extracted baseline method."""

    method_name: str
    paper_reference: str
    code_reference: Optional[str] = None
    description: str
    performance_metrics: dict[str, float] = Field(default_factory=dict)


class EvidencePackage(BaseModel):
    """Collection of search results from multiple sources."""

    package_id: str
    query: str
    papers: list[PaperResult] = Field(default_factory=list, max_length=10)
    code_repos: list[CodeRepository] = Field(default_factory=list, max_length=5)
    baselines: list[BaselineMethod] = Field(default_factory=list)
    common_failures: list[str] = Field(default_factory=list)
    search_timestamp: datetime = Field(default_factory=datetime.now)


class EvidenceReport(BaseModel):
    """Markdown document summarizing search findings."""

    report_id: str
    summary: str
    key_papers: list[str] = Field(default_factory=list, description="Paper IDs")
    recommended_baselines: list[str] = Field(default_factory=list)
    identified_risks: list[str] = Field(default_factory=list)
    citations: list[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.now)


class ResearchProposal(BaseModel):
    """Represents a single candidate research proposal."""

    proposal_id: str
    risk_profile: Literal["conservative", "balanced", "aggressive"]
    title: str = Field(..., min_length=10, max_length=200)
    objective: str = Field(..., min_length=20, max_length=500)
    approach: str = Field(..., min_length=50, max_length=1000)
    baseline_method: str
    expected_metrics: dict[str, float] = Field(default_factory=dict)
    risks: list[str] = Field(..., min_length=1, max_length=5)
    estimated_cost: float = Field(..., gt=0)
    estimated_time: str
    evidence_support: list[str] = Field(..., min_length=1, description="Supporting paper IDs")


class KnowledgeCache(BaseModel):
    """Cached search results with expiration."""

    cache_key: str = Field(..., min_length=3, max_length=100, pattern=r"^[a-z0-9_]+$")
    query: str
    results: EvidencePackage
    timestamp: datetime = Field(default_factory=datetime.now)
    expires_at: datetime
    hit_count: int = Field(0, ge=0)
