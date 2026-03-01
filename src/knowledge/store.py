"""Knowledge base store: cache-first lookup with MD file storage."""

from __future__ import annotations

import logging
from pathlib import Path

import frontmatter

from src.schemas.knowledge import KnowledgeEntry, KnowledgeEntryMeta

logger = logging.getLogger(__name__)


class KnowledgeStore:
    """Two-layer knowledge base with cache-first lookup."""

    def __init__(
        self,
        scientist_dir: str | Path = "scientist",
        runs_dir: str | Path = "runs",
    ) -> None:
        """
        Args:
            scientist_dir: Global knowledge base directory
            runs_dir: Runs directory (for run-local knowledge)
        """
        self.scientist_dir = Path(scientist_dir)
        self.runs_dir = Path(runs_dir)
        self.scientist_dir.mkdir(parents=True, exist_ok=True)

    def search(
        self,
        keywords: list[str],
        run_id: str | None = None,
    ) -> list[KnowledgeEntry]:
        """Search knowledge base by keywords (cache-first).

        Args:
            keywords: Search keywords
            run_id: Optional run ID for run-local search

        Returns:
            List of matching knowledge entries
        """
        # Search global layer first
        hits = self._search_in_dir(self.scientist_dir, keywords)

        # Search run-local layer if run_id provided
        if run_id:
            run_kb_dir = self.runs_dir / run_id / "knowledge"
            if run_kb_dir.exists():
                hits.extend(self._search_in_dir(run_kb_dir, keywords))

        return hits

    def save(
        self,
        entry: KnowledgeEntry,
        run_id: str | None = None,
    ) -> Path:
        """Save knowledge entry to appropriate layer.

        Args:
            entry: Knowledge entry to save
            run_id: Optional run ID (determines layer)

        Returns:
            Path to saved file
        """
        # Determine target directory
        if entry.meta.layer == "global":
            target_dir = self.scientist_dir
        else:
            if not run_id:
                raise ValueError("run_id required for run-local entries")
            target_dir = self.runs_dir / run_id / "knowledge"

        target_dir.mkdir(parents=True, exist_ok=True)

        # Generate filename from URL
        slug = self._url_to_slug(entry.meta.source_url)
        file_path = target_dir / f"{slug}.md"

        # Write MD with frontmatter
        post = frontmatter.Post(
            self._entry_to_markdown_body(entry),
            **entry.meta.model_dump(mode="json"),
        )
        file_path.write_text(frontmatter.dumps(post), encoding="utf-8")

        logger.info(f"Saved knowledge entry: {file_path}")
        return file_path

    def _search_in_dir(
        self,
        directory: Path,
        keywords: list[str],
    ) -> list[KnowledgeEntry]:
        """Search for entries matching keywords in a directory."""
        if not directory.exists():
            return []

        hits = []
        keyword_set = {kw.lower() for kw in keywords}

        for md_file in directory.glob("*.md"):
            try:
                post = frontmatter.load(md_file)
                meta_dict = post.metadata

                # Check keyword overlap
                entry_keywords = {
                    kw.lower() for kw in meta_dict.get("keywords", [])
                }
                if entry_keywords & keyword_set:
                    # Parse entry
                    meta = KnowledgeEntryMeta(**meta_dict)
                    entry = self._markdown_to_entry(post.content, meta)
                    hits.append(entry)
            except Exception as e:
                logger.warning(f"Failed to parse {md_file}: {e}")
                continue

        return hits

    def _url_to_slug(self, url: str) -> str:
        """Convert URL to filesystem-safe slug."""
        import re

        # Remove protocol
        slug = re.sub(r"^https?://", "", url)
        # Replace non-alphanumeric with dash
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", slug)
        # Truncate to 80 chars
        slug = slug[:80].strip("-")
        return slug or "unknown"

    def _entry_to_markdown_body(self, entry: KnowledgeEntry) -> str:
        """Convert entry to markdown body (without frontmatter)."""
        body = f"## 摘要\n\n{entry.summary}\n\n"

        if entry.key_points:
            body += "## 要点\n\n"
            body += "\n".join(f"- {point}" for point in entry.key_points)
            body += "\n\n"

        if entry.relevance_note:
            body += f"## 与查询的相关性\n\n{entry.relevance_note}\n\n"

        if entry.raw_excerpt:
            body += f"## 原文摘录\n\n> {entry.raw_excerpt}\n"

        return body

    def _markdown_to_entry(
        self,
        body: str,
        meta: KnowledgeEntryMeta,
    ) -> KnowledgeEntry:
        """Parse markdown body into KnowledgeEntry."""
        # Simple parsing: extract sections
        summary = ""
        key_points = []
        relevance_note = ""
        raw_excerpt = ""

        sections = body.split("## ")
        for section in sections:
            if section.startswith("摘要"):
                summary = section.replace("摘要", "").strip()
            elif section.startswith("要点"):
                content = section.replace("要点", "").strip()
                key_points = [
                    line.strip("- ").strip()
                    for line in content.split("\n")
                    if line.strip().startswith("-")
                ]
            elif section.startswith("与查询的相关性"):
                relevance_note = section.replace("与查询的相关性", "").strip()
            elif section.startswith("原文摘录"):
                raw_excerpt = section.replace("原文摘录", "").strip().strip(">").strip()

        return KnowledgeEntry(
            meta=meta,
            summary=summary,
            key_points=key_points,
            relevance_note=relevance_note,
            raw_excerpt=raw_excerpt,
        )
