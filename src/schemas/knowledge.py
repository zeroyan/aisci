"""Knowledge base schemas for caching research materials."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class KnowledgeEntryMeta(BaseModel):
    """Metadata for a knowledge base entry."""

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    type: Literal["paper", "repo", "web_article", "method"]
    title: str
    source_url: str
    authors: list[str] = Field(default_factory=list)
    published: str | None = None  # ISO date string or year
    keywords: list[str] = Field(default_factory=list)
    spec_ids: list[str] = Field(default_factory=list)  # Associated ResearchSpec IDs
    run_ids: list[str] = Field(default_factory=list)  # Associated run IDs (empty=global)
    fetched_at: datetime = Field(default_factory=lambda: datetime.now())
    status: Literal["ok", "fetch_failed", "summarize_failed"] = "ok"
    relevance_score: float | None = None
    layer: Literal["global", "run-local"] = "global"


class KnowledgeEntry(BaseModel):
    """Complete knowledge base entry with content."""

    meta: KnowledgeEntryMeta
    summary: str  # LLM-generated summary
    key_points: list[str] = Field(default_factory=list)
    relevance_note: str = ""  # Relevance to current query
    raw_excerpt: str = ""  # Abstract or key passage
