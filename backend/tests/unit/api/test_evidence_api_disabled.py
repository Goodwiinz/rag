"""The evidence API stays unpublished until it uses real, tenant-scoped sources."""


def test_fabricated_evidence_api_is_not_published() -> None:
    from src.main import app

    published_paths = app.openapi()["paths"]

    assert not any(path.startswith("/api/v1/evidence") for path in published_paths)
