"""Web searcher: Tavily + arxiv + semanticscholar + trafilatura."""

from __future__ import annotations

import logging
import os

from src.schemas.knowledge import KnowledgeEntry, KnowledgeEntryMeta

logger = logging.getLogger(__name__)


class Searcher:
    """Multi-source web searcher for research materials."""

    def __init__(
        self,
        backend: str = "tavily",
        max_results: int = 5,
    ) -> None:
        """
        Args:
            backend: "tavily" or "duckduckgo"
            max_results: Max results per query
        """
        self.backend = backend
        self.max_results = max_results

    def search(
        self,
        query: str,
        search_type: str = "general",
    ) -> list[KnowledgeEntry]:
        """Search for research materials.

        Args:
            query: Search query
            search_type: "general", "paper", or "code"

        Returns:
            List of knowledge entries (may be empty on failure)
        """
        try:
            if search_type == "paper":
                return self._search_papers(query)
            elif search_type == "code":
                return self._search_code(query)
            else:
                return self._search_general(query)
        except Exception as e:
            logger.error(f"Search failed for '{query}': {e}")
            # Return empty list (non-blocking per FR-003)
            return []

    def _search_general(self, query: str) -> list[KnowledgeEntry]:
        """General web search using Tavily or DuckDuckGo."""
        if self.backend == "tavily" and os.getenv("TAVILY_API_KEY"):
            return self._search_tavily(query)
        else:
            return self._search_duckduckgo(query)

    def _search_tavily(self, query: str) -> list[KnowledgeEntry]:
        """Search using Tavily API."""
        try:
            from tavily import TavilyClient

            client = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
            results = client.search(
                query=query,
                search_depth="basic",
                max_results=self.max_results,
            )

            entries = []
            for result in results.get("results", []):
                entry = KnowledgeEntry(
                    meta=KnowledgeEntryMeta(
                        type="web_article",
                        title=result.get("title", "Untitled"),
                        source_url=result["url"],
                        keywords=query.split(),
                        relevance_score=result.get("score"),
                        status="ok",
                        layer="global",
                    ),
                    summary=result.get("content", "")[:500],
                    raw_excerpt=result.get("content", "")[:1000],
                )
                entries.append(entry)

            return entries
        except Exception as e:
            logger.warning(f"Tavily search failed: {e}")
            return []

    def _search_duckduckgo(self, query: str) -> list[KnowledgeEntry]:
        """Search using DuckDuckGo (fallback)."""
        try:
            from duckduckgo_search import DDGS

            with DDGS() as ddgs:
                results = list(ddgs.text(query, max_results=self.max_results))

            entries = []
            for result in results:
                entry = KnowledgeEntry(
                    meta=KnowledgeEntryMeta(
                        type="web_article",
                        title=result.get("title", "Untitled"),
                        source_url=result["href"],
                        keywords=query.split(),
                        status="ok",
                        layer="global",
                    ),
                    summary=result.get("body", "")[:500],
                    raw_excerpt=result.get("body", "")[:1000],
                )
                entries.append(entry)

            return entries
        except Exception as e:
            logger.warning(f"DuckDuckGo search failed: {e}")
            return []

    def _search_papers(self, query: str) -> list[KnowledgeEntry]:
        """Search academic papers using arxiv + semanticscholar."""
        entries = []

        # Try arxiv
        try:
            import arxiv

            client = arxiv.Client()
            search = arxiv.Search(
                query=query,
                max_results=self.max_results,
                sort_by=arxiv.SortCriterion.Relevance,
            )

            for paper in client.results(search):
                entry = KnowledgeEntry(
                    meta=KnowledgeEntryMeta(
                        type="paper",
                        title=paper.title,
                        source_url=paper.entry_id,
                        authors=[author.name for author in paper.authors],
                        published=paper.published.strftime("%Y-%m-%d"),
                        keywords=query.split(),
                        status="ok",
                        layer="global",
                    ),
                    summary=paper.summary[:500],
                    raw_excerpt=paper.summary[:1000],
                )
                entries.append(entry)
        except Exception as e:
            logger.warning(f"arxiv search failed: {e}")

        return entries

    def _search_code(self, query: str) -> list[KnowledgeEntry]:
        """Search code repositories (placeholder for GitHub API)."""
        # TODO: Implement GitHub API search
        logger.info(f"Code search not yet implemented: {query}")
        return []
