"""Security guardrails for pre-public CI configuration."""

from __future__ import annotations

import pathlib

import pytest

pytestmark = pytest.mark.unit

_REPO = pathlib.Path(__file__).parents[3]


def test_ci_workflow_generates_supabase_jwts_instead_of_committing_tokens():
    text = (_REPO / ".github/workflows/test-pipeline.yml").read_text()

    assert "Generate CI Supabase JWTs" in text
    assert "SERVICE_ROLE_JWT=$SERVICE_ROLE_JWT" in text
    assert "NEXT_PUBLIC_SUPABASE_ANON_KEY=${{ steps.supabase-jwts.outputs.anon }}" in text
    assert "eyJhbGci" not in text


def test_ci_compose_requires_supplied_anon_jwt():
    text = (_REPO / "config/docker-compose/docker-compose.ci.yml").read_text()

    assert "NEXT_PUBLIC_SUPABASE_ANON_KEY: ${NEXT_PUBLIC_SUPABASE_ANON_KEY:?" in text
    assert "eyJhbGci" not in text
