"""Knowledge Consolidator for caching and report generation."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from src.schemas.project_generator import (
    EvidencePackage,
    EvidenceReport,
    KnowledgeCache,
)


class KnowledgeConsolidator:
    """Manage knowledge cache and generate evidence reports."""

    def __init__(self, cache_dir: Path = Path("scientist")):
        """Initialize KnowledgeConsolidator.

        Args:
            cache_dir: Directory for knowledge cache
        """
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def check_cache(self, query: str) -> Optional[EvidencePackage]:
        """Check if cached results exist for query.

        Args:
            query: Search query

        Returns:
            Cached EvidencePackage or None
        """
        cache_key = self._normalize_query(query)
        cache_path = self.cache_dir / cache_key / "cache.json"

        if not cache_path.exists():
            return None

        try:
            cache_data = json.loads(cache_path.read_text())
            cache = KnowledgeCache(**cache_data)

            # Check if cache is expired
            if datetime.now() > cache.expires_at:
                return None

            # Update hit count
            cache.hit_count += 1
            cache_path.write_text(cache.model_dump_json(indent=2))

            return cache.results

        except Exception as e:
            print(f"Cache read failed: {e}")
            return None

    def save_cache(self, query: str, results: EvidencePackage, ttl_days: int = 30):
        """Save search results to cache.

        Args:
            query: Search query
            results: Evidence package to cache
            ttl_days: Time-to-live in days
        """
        cache_key = self._normalize_query(query)
        cache_dir = self.cache_dir / cache_key
        cache_dir.mkdir(parents=True, exist_ok=True)

        cache = KnowledgeCache(
            cache_key=cache_key,
            query=query,
            results=results,
            timestamp=datetime.now(),
            expires_at=datetime.now() + timedelta(days=ttl_days),
            hit_count=0,
        )

        cache_path = cache_dir / "cache.json"
        cache_path.write_text(cache.model_dump_json(indent=2))

    def generate_report(self, evidence: EvidencePackage) -> EvidenceReport:
        """Generate evidence report from search results.

        Args:
            evidence: Evidence package

        Returns:
            EvidenceReport with summary and citations
        """
        import uuid

        report_id = f"report_{uuid.uuid4().hex[:8]}"

        # Generate summary
        summary = self._generate_summary(evidence)

        # Extract key papers
        key_papers = [p.paper_id for p in evidence.papers[:5]]

        # Extract recommended baselines
        recommended_baselines = [b.method_name for b in evidence.baselines]

        # Identify risks
        identified_risks = self._identify_risks(evidence)

        # Generate citations
        citations = self._generate_citations(evidence)

        return EvidenceReport(
            report_id=report_id,
            summary=summary,
            key_papers=key_papers,
            recommended_baselines=recommended_baselines,
            identified_risks=identified_risks,
            citations=citations,
            generated_at=datetime.now(),
        )

    def _normalize_query(self, query: str) -> str:
        """Normalize query to cache key.

        Args:
            query: Search query

        Returns:
            Normalized cache key
        """
        import re

        # Convert to lowercase, remove special chars, replace spaces with underscores
        normalized = re.sub(r'[^a-z0-9\s]', '', query.lower())
        normalized = re.sub(r'\s+', '_', normalized.strip())
        return normalized[:100]  # Limit length

    def _generate_summary(self, evidence: EvidencePackage) -> str:
        """Generate summary from evidence.

        Args:
            evidence: Evidence package

        Returns:
            Summary text
        """
        num_papers = len(evidence.papers)
        num_repos = len(evidence.code_repos)
        num_baselines = len(evidence.baselines)

        summary = f"Found {num_papers} relevant papers, {num_repos} code repositories, and identified {num_baselines} baseline methods.\n\n"

        if evidence.baselines:
            summary += "Top baseline methods:\n"
            for baseline in evidence.baselines[:3]:
                summary += f"- {baseline.method_name}\n"

        return summary

    def _identify_risks(self, evidence: EvidencePackage) -> list[str]:
        """Identify potential risks from evidence.

        Args:
            evidence: Evidence package

        Returns:
            List of identified risks
        """
        risks = []

        if len(evidence.papers) < 3:
            risks.append("Limited research literature available - exploratory research")

        if len(evidence.code_repos) == 0:
            risks.append("No existing code implementations found - may need to implement from scratch")

        if len(evidence.baselines) == 0:
            risks.append("No clear baseline methods identified - difficult to establish performance comparison")

        # Check paper recency
        if evidence.papers:
            recent_papers = [p for p in evidence.papers if p.year >= 2022]
            if len(recent_papers) < len(evidence.papers) // 2:
                risks.append("Most papers are older (pre-2022) - field may have evolved")

        return risks

    def _generate_citations(self, evidence: EvidencePackage) -> list[str]:
        """Generate citation list from evidence.

        Args:
            evidence: Evidence package

        Returns:
            List of formatted citations
        """
        citations = []

        for paper in evidence.papers:
            authors_str = ", ".join(paper.authors[:3])
            if len(paper.authors) > 3:
                authors_str += " et al."

            citation = f"{authors_str}. ({paper.year}). {paper.title}. {paper.url}"
            citations.append(citation)

        return citations
