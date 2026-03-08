"""Evidence Searcher for multi-source academic and code search."""

import time
import uuid
from datetime import datetime
from typing import Optional

import arxiv
import requests

from src.llm.client import LLMClient
from src.schemas.project_generator import (
    BaselineMethod,
    CodeRepository,
    EvidencePackage,
    PaperResult,
)


class EvidenceSearcher:
    """Search for academic papers and code repositories."""

    def __init__(self, github_token: Optional[str] = None, llm_client: Optional[LLMClient] = None):
        """Initialize EvidenceSearcher.

        Args:
            github_token: GitHub API token (optional, increases rate limit)
            llm_client: LLM client for query optimization (optional)
        """
        self.github_token = github_token
        self.arxiv_client = arxiv.Client()
        self.llm_client = llm_client

    def search(
        self,
        query: str,
        max_papers: int = 10,
        max_repos: int = 5,
    ) -> EvidencePackage:
        """Search for evidence from multiple sources.

        Args:
            query: Search query string
            max_papers: Maximum papers to retrieve
            max_repos: Maximum code repositories to retrieve

        Returns:
            EvidencePackage with search results
        """
        package_id = f"evidence_{uuid.uuid4().hex[:8]}"

        # Optimize query for academic search
        optimized_query = self._optimize_query(query)

        # Search papers with delay between sources to avoid rate limits
        papers = []
        papers.extend(self._search_arxiv(optimized_query, max_papers // 2))

        # Add delay before Semantic Scholar to avoid rate limiting
        time.sleep(3.0)
        papers.extend(self._search_semantic_scholar(optimized_query, max_papers // 2))

        # Deduplicate and rank papers
        papers = self._deduplicate_papers(papers)
        papers = sorted(papers, key=lambda p: p.relevance_score, reverse=True)[:max_papers]

        # Search code repositories (use original query for better GitHub results)
        repos = []
        repos.extend(self._search_github(query, max_repos))

        # Extract baseline methods from papers
        baselines = self._extract_baselines(papers, repos)

        return EvidencePackage(
            package_id=package_id,
            query=query,
            papers=papers,
            code_repos=repos,
            baselines=baselines,
            common_failures=[],
            search_timestamp=datetime.now(),
        )

    def _optimize_query(self, query: str) -> str:
        """Optimize user query for academic search.

        Args:
            query: Original user query

        Returns:
            Optimized query with academic keywords
        """
        if not self.llm_client:
            # Fallback: simple keyword extraction
            return query

        prompt = f"""Extract 3-5 key academic search terms from this research idea:

"{query}"

Requirements:
1. Focus on technical terms, methods, and domains
2. Use terminology common in academic papers
3. Avoid vague words like "improve", "better", "faster"
4. Return ONLY the search terms separated by spaces (no explanation)

Example:
Input: "Improve Transformer inference speed"
Output: Transformer inference optimization acceleration efficiency

Your output:"""

        try:
            response, _cost = self.llm_client.complete(
                messages=[{"role": "user", "content": prompt}],
            )
            optimized = response.strip()

            # Validate output (should be short and keyword-like)
            if len(optimized.split()) <= 10 and len(optimized) < 200:
                return optimized
            else:
                return query
        except Exception as e:
            print(f"Query optimization failed: {e}, using original query")
            return query

    def _search_arxiv(self, query: str, max_results: int) -> list[PaperResult]:
        """Search arXiv for papers.

        Args:
            query: Search query
            max_results: Maximum results to return

        Returns:
            List of PaperResult objects
        """
        papers = []

        try:
            search = arxiv.Search(
                query=query,
                max_results=max_results,
                sort_by=arxiv.SortCriterion.Relevance,
            )

            for result in self.arxiv_client.results(search):
                paper = PaperResult(
                    paper_id=result.entry_id,
                    title=result.title,
                    authors=[author.name for author in result.authors],
                    abstract=result.summary,
                    citations=0,  # arXiv doesn't provide citation count
                    year=result.published.year,
                    url=result.entry_id,
                    source="arxiv",
                    relevance_score=0.8,  # Default relevance
                )
                papers.append(paper)

                # Rate limiting
                time.sleep(1.0 / 3)  # 3 requests per second

        except Exception as e:
            print(f"arXiv search failed: {e}")

        return papers

    def _search_semantic_scholar(self, query: str, max_results: int) -> list[PaperResult]:
        """Search Semantic Scholar for papers with retry logic.

        Args:
            query: Search query
            max_results: Maximum results to return

        Returns:
            List of PaperResult objects
        """
        papers = []
        max_retries = 3
        base_delay = 3.0  # Increased from 2.0 to 3.0 seconds

        for attempt in range(max_retries):
            try:
                url = "https://api.semanticscholar.org/graph/v1/paper/search"
                params = {
                    "query": query,
                    "limit": max_results,
                    "fields": "title,authors,abstract,citationCount,year,url",
                }

                response = requests.get(url, params=params, timeout=30)

                # Handle rate limiting specifically
                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)  # Exponential backoff
                        print(f"Semantic Scholar rate limit hit, retrying in {delay}s (attempt {attempt + 1}/{max_retries})")
                        time.sleep(delay)
                        continue
                    else:
                        print(f"Semantic Scholar rate limit exceeded after {max_retries} attempts, skipping")
                        return papers

                response.raise_for_status()
                data = response.json()

                for item in data.get("data", []):
                    paper = PaperResult(
                        paper_id=item.get("paperId", ""),
                        title=item.get("title", ""),
                        authors=[author.get("name", "") for author in item.get("authors", [])],
                        abstract=item.get("abstract", ""),
                        citations=item.get("citationCount", 0),
                        year=item.get("year", 2024),
                        url=item.get("url", ""),
                        source="semantic_scholar",
                        relevance_score=0.9,  # Semantic Scholar has good relevance
                    )
                    papers.append(paper)

                # Success, break retry loop
                break

            except requests.exceptions.RequestException as e:
                if attempt < max_retries - 1:
                    delay = base_delay * (2 ** attempt)
                    print(f"Semantic Scholar request failed: {e}, retrying in {delay}s")
                    time.sleep(delay)
                else:
                    print(f"Semantic Scholar search failed after {max_retries} attempts: {e}")
            except Exception as e:
                print(f"Semantic Scholar search failed: {e}")
                break

        return papers

    def _search_github(self, query: str, max_results: int) -> list[CodeRepository]:
        """Search GitHub for code repositories.

        Args:
            query: Search query
            max_results: Maximum results to return

        Returns:
            List of CodeRepository objects
        """
        repos = []

        try:
            url = "https://api.github.com/search/repositories"
            headers = {}
            if self.github_token:
                headers["Authorization"] = f"token {self.github_token}"

            params = {
                "q": query,
                "sort": "stars",
                "order": "desc",
                "per_page": max_results,
            }

            response = requests.get(url, params=params, headers=headers, timeout=30)
            response.raise_for_status()

            data = response.json()

            for item in data.get("items", []):
                repo = CodeRepository(
                    repo_id=str(item.get("id", "")),
                    name=item.get("full_name", ""),
                    description=item.get("description", ""),
                    stars=item.get("stargazers_count", 0),
                    forks=item.get("forks_count", 0),
                    url=item.get("html_url", ""),
                    language=item.get("language"),
                    last_updated=datetime.fromisoformat(item["updated_at"].replace("Z", "+00:00"))
                    if item.get("updated_at")
                    else None,
                    source="github",
                )
                repos.append(repo)

        except Exception as e:
            print(f"GitHub search failed: {e}")

        return repos

    def _deduplicate_papers(self, papers: list[PaperResult]) -> list[PaperResult]:
        """Remove duplicate papers based on title similarity.

        Args:
            papers: List of papers

        Returns:
            Deduplicated list of papers
        """
        seen_titles = set()
        unique_papers = []

        for paper in papers:
            # Normalize title for comparison
            normalized_title = paper.title.lower().strip()

            if normalized_title not in seen_titles:
                seen_titles.add(normalized_title)
                unique_papers.append(paper)

        return unique_papers

    def _extract_baselines(
        self,
        papers: list[PaperResult],
        repos: list[CodeRepository],
    ) -> list[BaselineMethod]:
        """Extract baseline methods from papers and repos.

        Args:
            papers: List of papers
            repos: List of code repositories

        Returns:
            List of BaselineMethod objects
        """
        baselines = []

        # Extract from top papers
        for paper in papers[:3]:
            # Simple heuristic: use paper title as method name
            method_name = paper.title.split(":")[0].strip()

            # Find matching code repo
            code_ref = None
            for repo in repos:
                if any(word in repo.name.lower() for word in method_name.lower().split()):
                    code_ref = repo.url
                    break

            baseline = BaselineMethod(
                method_name=method_name,
                paper_reference=paper.url,
                code_reference=code_ref,
                description=paper.abstract[:200] + "..." if len(paper.abstract) > 200 else paper.abstract,
                performance_metrics={},
            )
            baselines.append(baseline)

        return baselines[:3]  # Return top 3 baselines
