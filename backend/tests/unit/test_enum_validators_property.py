"""
Property-based tests for src/shared/enums.py.

Verifies that all SQL-injection-prevention enums:
  1. Accept their own declared values (round-trip property).
  2. Reject arbitrary strings that are not declared values.

Uses Hypothesis to generate adversarial inputs automatically, including
strings that may resemble SQL injection payloads.
"""
import pytest
from hypothesis import given
from hypothesis import strategies as st

from src.shared.enums import (
    DocumentSortField,
    EntitySortField,
    JobSortField,
    OrganizationSortField,
    SearchSortField,
    SortOrder,
    UserSortField,
)

# ── Shared helpers ────────────────────────────────────────────────────────────

SQL_INJECTION_PAYLOADS = [
    "'; DROP TABLE documents; --",
    "1 OR 1=1",
    "UNION SELECT * FROM users",
    "' OR '1'='1",
    "1; SELECT * FROM information_schema.tables",
    "../etc/passwd",
    "\x00",
    "created_at; DROP TABLE documents; --",
    "ORDER BY 1--",
    "' AND 1=CONVERT(int,(SELECT TOP 1 table_name FROM information_schema.tables))--",
]


def non_member_text(enum_cls) -> st.SearchStrategy:
    """Return a strategy for arbitrary non-member strings for a given enum."""
    valid = {e.value for e in enum_cls}
    return st.text(min_size=1).filter(lambda s: s not in valid)


# ── DocumentSortField ─────────────────────────────────────────────────────────

VALID_DOCUMENT_SORT_FIELDS = [e.value for e in DocumentSortField]


@pytest.mark.unit
@given(value=st.sampled_from(VALID_DOCUMENT_SORT_FIELDS))
def test_document_sort_field_accepts_valid_values(value: str) -> None:
    assert DocumentSortField(value).value == value


@pytest.mark.unit
@given(value=non_member_text(DocumentSortField))
def test_document_sort_field_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError):
        DocumentSortField(value)


@pytest.mark.unit
@pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
def test_document_sort_field_rejects_sql_injection(payload: str) -> None:
    with pytest.raises(ValueError):
        DocumentSortField(payload)


# ── SortOrder ─────────────────────────────────────────────────────────────────

VALID_SORT_ORDERS = [e.value for e in SortOrder]


@pytest.mark.unit
@given(value=st.sampled_from(VALID_SORT_ORDERS))
def test_sort_order_accepts_valid_values(value: str) -> None:
    assert SortOrder(value).value == value


@pytest.mark.unit
@given(value=non_member_text(SortOrder))
def test_sort_order_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError):
        SortOrder(value)


@pytest.mark.unit
@pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
def test_sort_order_rejects_sql_injection(payload: str) -> None:
    with pytest.raises(ValueError):
        SortOrder(payload)


# ── EntitySortField ───────────────────────────────────────────────────────────

VALID_ENTITY_SORT_FIELDS = [e.value for e in EntitySortField]


@pytest.mark.unit
@given(value=st.sampled_from(VALID_ENTITY_SORT_FIELDS))
def test_entity_sort_field_accepts_valid_values(value: str) -> None:
    assert EntitySortField(value).value == value


@pytest.mark.unit
@given(value=non_member_text(EntitySortField))
def test_entity_sort_field_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError):
        EntitySortField(value)


@pytest.mark.unit
@pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
def test_entity_sort_field_rejects_sql_injection(payload: str) -> None:
    with pytest.raises(ValueError):
        EntitySortField(payload)


# ── JobSortField ──────────────────────────────────────────────────────────────

VALID_JOB_SORT_FIELDS = [e.value for e in JobSortField]


@pytest.mark.unit
@given(value=st.sampled_from(VALID_JOB_SORT_FIELDS))
def test_job_sort_field_accepts_valid_values(value: str) -> None:
    assert JobSortField(value).value == value


@pytest.mark.unit
@given(value=non_member_text(JobSortField))
def test_job_sort_field_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError):
        JobSortField(value)


@pytest.mark.unit
@pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
def test_job_sort_field_rejects_sql_injection(payload: str) -> None:
    with pytest.raises(ValueError):
        JobSortField(payload)


# ── SearchSortField ───────────────────────────────────────────────────────────

VALID_SEARCH_SORT_FIELDS = [e.value for e in SearchSortField]


@pytest.mark.unit
@given(value=st.sampled_from(VALID_SEARCH_SORT_FIELDS))
def test_search_sort_field_accepts_valid_values(value: str) -> None:
    assert SearchSortField(value).value == value


@pytest.mark.unit
@given(value=non_member_text(SearchSortField))
def test_search_sort_field_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError):
        SearchSortField(value)


@pytest.mark.unit
@pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
def test_search_sort_field_rejects_sql_injection(payload: str) -> None:
    with pytest.raises(ValueError):
        SearchSortField(payload)


# ── UserSortField ─────────────────────────────────────────────────────────────

VALID_USER_SORT_FIELDS = [e.value for e in UserSortField]


@pytest.mark.unit
@given(value=st.sampled_from(VALID_USER_SORT_FIELDS))
def test_user_sort_field_accepts_valid_values(value: str) -> None:
    assert UserSortField(value).value == value


@pytest.mark.unit
@given(value=non_member_text(UserSortField))
def test_user_sort_field_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError):
        UserSortField(value)


@pytest.mark.unit
@pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
def test_user_sort_field_rejects_sql_injection(payload: str) -> None:
    with pytest.raises(ValueError):
        UserSortField(payload)


# ── OrganizationSortField ─────────────────────────────────────────────────────

VALID_ORG_SORT_FIELDS = [e.value for e in OrganizationSortField]


@pytest.mark.unit
@given(value=st.sampled_from(VALID_ORG_SORT_FIELDS))
def test_organization_sort_field_accepts_valid_values(value: str) -> None:
    assert OrganizationSortField(value).value == value


@pytest.mark.unit
@given(value=non_member_text(OrganizationSortField))
def test_organization_sort_field_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError):
        OrganizationSortField(value)


@pytest.mark.unit
@pytest.mark.parametrize("payload", SQL_INJECTION_PAYLOADS)
def test_organization_sort_field_rejects_sql_injection(payload: str) -> None:
    with pytest.raises(ValueError):
        OrganizationSortField(payload)
