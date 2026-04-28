"""Smoke tests for scripts/backup/backup_vector_store.py.

These cover the two regressions fixed under issue #368:

1. ``points_count`` is ``None`` for empty collections, which previously crashed
   ``client.scroll(limit=points_count)`` with ``TypeError``.
2. ``cleanup_old_backups`` parsed timestamps from ``Path.stem``, which only
   strips the outer ``.gz`` from ``.tar.gz`` files — leaving ``"HHMMSS.tar"``
   in the last segment and silently skipping every old backup.

The tests load the module by file path so they don't depend on the
``scripts/`` package being importable from anywhere on ``sys.path``. They
mock the Qdrant client entirely, so no live database is required (issue #370).
"""

from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = REPO_ROOT / "scripts" / "backup" / "backup_vector_store.py"


@pytest.fixture(scope="module")
def backup_module():
    spec = importlib.util.spec_from_file_location(
        "backup_vector_store_under_test", MODULE_PATH
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


@pytest.fixture
def backup_manager(backup_module, tmp_path, monkeypatch):
    """A VectorStoreBackup with the Qdrant client replaced by a MagicMock."""
    monkeypatch.setattr(backup_module, "QdrantClient", MagicMock())
    config = {
        "backup_dir": str(tmp_path),
        "host": "localhost",
        "port": 6333,
        "retention_days": 30,
    }
    return backup_module.VectorStoreBackup(config)


@pytest.mark.asyncio
async def test_backup_empty_collection_does_not_crash(backup_manager, tmp_path):
    """Issue #368: empty collections (points_count=None) must not raise."""
    backup_path = tmp_path / "qdrant_backup_run"
    backup_path.mkdir()

    backup_manager.client.get_collection.return_value = SimpleNamespace(
        points_count=None,
        config=SimpleNamespace(
            vectors_config=SimpleNamespace(to_dict=lambda: {"size": 1, "distance": "Cosine"})
        ),
    )

    result = await backup_manager._backup_collection("empty_col", backup_path)

    assert result["points_count"] == 0
    assert backup_manager.client.scroll.call_count == 0  # never called on empty
    points_file = backup_path / "collections" / "empty_col" / "points.jsonl.gz"
    assert points_file.exists()


def test_cleanup_old_backups_parses_tar_gz_timestamp(backup_manager, tmp_path):
    """Issue #368: old backups must actually be deleted, not silently skipped."""
    old_ts = (datetime.now() - timedelta(days=90)).strftime("%Y%m%d_%H%M%S")
    fresh_ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    old_backup = tmp_path / f"qdrant_backup_{old_ts}.tar.gz"
    fresh_backup = tmp_path / f"qdrant_backup_{fresh_ts}.tar.gz"
    old_backup.write_bytes(b"")
    fresh_backup.write_bytes(b"")

    backup_manager.cleanup_old_backups()

    assert not old_backup.exists(), "old .tar.gz backup should have been deleted"
    assert fresh_backup.exists(), "fresh .tar.gz backup should have been retained"
