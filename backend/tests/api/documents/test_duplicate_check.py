import importlib.util
import sys
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import OperationalError


BACKEND_ROOT = Path(__file__).resolve().parents[3]
DOCUMENTS_MODULE_PATH = BACKEND_ROOT / "src" / "api" / "documents" / "documents.py"


def load_documents_module():
    sys.path.insert(0, str(BACKEND_ROOT.parent))
    spec = importlib.util.spec_from_file_location(
        "documents_under_test", DOCUMENTS_MODULE_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


@pytest.mark.asyncio
async def test_check_duplicate_falls_back_when_checksum_lookup_fails():
    module = load_documents_module()
    existing_document = SimpleNamespace(
        id="doc-1",
        title="Existing doc",
        filename="existing.pdf",
        document_type=module.DocumentType.PDF,
        file_size_bytes=1024,
        mime_type="application/pdf",
        processing_status=module.ProcessingStatus.COMPLETED,
        tags=["existing"],
        is_public=False,
        created_at=datetime(2026, 4, 13, 12, 0, 0),
        updated_at=datetime(2026, 4, 13, 12, 5, 0),
        uploaded_by_user_id="user-1",
        organization_id="org-1",
    )
    db = AsyncMock()
    db.execute.side_effect = [
        OperationalError("select checksum", {}, Exception("missing column")),
        ScalarResult(existing_document),
    ]

    response = await module.check_duplicate(
        body=module.DuplicateCheckRequest(sha256="a" * 64),
        current_user=SimpleNamespace(id="user-1"),
        organization=SimpleNamespace(id="org-1"),
        db=db,
    )

    assert response.exists is True
    assert response.document is not None
    assert response.document.id == "doc-1"
    assert response.document.document_type == "pdf"
    assert response.document.processing_status == "completed"
    assert db.execute.await_count == 2
