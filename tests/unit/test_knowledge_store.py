"""Unit tests for KnowledgeStore with cache-first logic."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.knowledge.store import KnowledgeStore
from src.schemas.knowledge import KnowledgeEntry, KnowledgeEntryMeta


def test_knowledge_store_save_and_search(tmp_path: Path) -> None:
    """Save entry and search by keywords."""
    store = KnowledgeStore(
        scientist_dir=tmp_path / "scientist",
        runs_dir=tmp_path / "runs",
    )

    # Create entry
    entry = KnowledgeEntry(
        meta=KnowledgeEntryMeta(
            type="paper",
            title="Test Paper",
            source_url="https://arxiv.org/abs/1234.5678",
            keywords=["contrastive", "learning"],
            layer="global",
        ),
        summary="Test summary",
        key_points=["Point 1", "Point 2"],
    )

    # Save
    saved_path = store.save(entry)
    assert saved_path.exists()
    assert "arxiv-org-abs-1234-5678" in saved_path.name

    # Search by keyword
    results = store.search(keywords=["contrastive"])
    assert len(results) == 1
    assert results[0].meta.title == "Test Paper"
    assert results[0].summary == "Test summary"


def test_knowledge_store_cache_first(tmp_path: Path) -> None:
    """Verify cache-first lookup (global before run-local)."""
    store = KnowledgeStore(
        scientist_dir=tmp_path / "scientist",
        runs_dir=tmp_path / "runs",
    )

    # Save global entry
    global_entry = KnowledgeEntry(
        meta=KnowledgeEntryMeta(
            type="paper",
            title="Global Paper",
            source_url="https://example.com/global",
            keywords=["test"],
            layer="global",
        ),
        summary="Global summary",
    )
    store.save(global_entry)

    # Save run-local entry
    local_entry = KnowledgeEntry(
        meta=KnowledgeEntryMeta(
            type="paper",
            title="Local Paper",
            source_url="https://example.com/local",
            keywords=["test"],
            layer="run-local",
        ),
        summary="Local summary",
    )
    store.save(local_entry, run_id="run_001")

    # Search without run_id: only global
    results = store.search(keywords=["test"])
    assert len(results) == 1
    assert results[0].meta.title == "Global Paper"

    # Search with run_id: both global and local
    results = store.search(keywords=["test"], run_id="run_001")
    assert len(results) == 2
    titles = {r.meta.title for r in results}
    assert titles == {"Global Paper", "Local Paper"}


def test_knowledge_store_fetch_failed_status(tmp_path: Path) -> None:
    """Entry with fetch_failed status should be saved (prevents retry)."""
    store = KnowledgeStore(scientist_dir=tmp_path / "scientist")

    entry = KnowledgeEntry(
        meta=KnowledgeEntryMeta(
            type="web_article",
            title="Failed Fetch",
            source_url="https://example.com/failed",
            keywords=["test"],
            status="fetch_failed",
            layer="global",
        ),
        summary="",  # Empty on failure
    )

    saved_path = store.save(entry)
    assert saved_path.exists()

    # Search should still find it
    results = store.search(keywords=["test"])
    assert len(results) == 1
    assert results[0].meta.status == "fetch_failed"
