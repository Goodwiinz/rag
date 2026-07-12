"""Unit tests for the public ``ApiDocumentStatus`` vocabulary (audit C6).

``ApiDocumentStatus`` is the single source of truth for translating between the
raw ``ProcessingStatus`` stored in the DB and the stable, client-facing status
vocabulary the API emits. It replaced several per-router inline dicts that had
drifted apart and caused two production incidents (a filter 500 and a false
``queued`` upload state).

These tests pull in only ``src.shared.enums`` + ``src.models.document`` and
therefore run without libpq/spacy/redis.
"""

from __future__ import annotations

import pytest

from src.models.document import ProcessingStatus
from src.shared.enums import ApiDocumentStatus

pytestmark = pytest.mark.unit


# --- from_db: db -> public API vocabulary -----------------------------------


@pytest.mark.parametrize(
    "db_status, expected",
    [
        (ProcessingStatus.PENDING, ApiDocumentStatus.QUEUED),
        (ProcessingStatus.PROCESSING, ApiDocumentStatus.PROCESSING),
        (ProcessingStatus.COMPLETED, ApiDocumentStatus.INDEXED),
        (ProcessingStatus.FAILED, ApiDocumentStatus.FAILED),
        # Quirk: retrying collapses to processing; it is never surfaced raw.
        (ProcessingStatus.RETRYING, ApiDocumentStatus.PROCESSING),
    ],
)
def test_from_db_maps_enum(db_status, expected):
    assert ApiDocumentStatus.from_db(db_status) is expected


def test_from_db_accepts_raw_value_strings():
    assert ApiDocumentStatus.from_db("pending") is ApiDocumentStatus.QUEUED
    assert ApiDocumentStatus.from_db("completed") is ApiDocumentStatus.INDEXED
    assert ApiDocumentStatus.from_db("RETRYING") is ApiDocumentStatus.PROCESSING


def test_from_db_unknown_and_none_default_to_queued():
    assert ApiDocumentStatus.from_db(None) is ApiDocumentStatus.QUEUED
    assert ApiDocumentStatus.from_db("") is ApiDocumentStatus.QUEUED
    assert ApiDocumentStatus.from_db("not-a-status") is ApiDocumentStatus.QUEUED


# --- to_db: public/raw filter input -> db enum ------------------------------


@pytest.mark.parametrize(
    "api_status, expected",
    [
        ("queued", ProcessingStatus.PENDING),
        ("processing", ProcessingStatus.PROCESSING),
        ("indexed", ProcessingStatus.COMPLETED),
        ("failed", ProcessingStatus.FAILED),
        # Raw backend spellings accepted for back-compat filtering.
        ("pending", ProcessingStatus.PENDING),
        ("completed", ProcessingStatus.COMPLETED),
        ("retrying", ProcessingStatus.RETRYING),
    ],
)
def test_to_db_maps_status(api_status, expected):
    assert ApiDocumentStatus.to_db(api_status) is expected


def test_to_db_is_case_insensitive():
    assert ApiDocumentStatus.to_db("INDEXED") is ProcessingStatus.COMPLETED
    assert ApiDocumentStatus.to_db(ApiDocumentStatus.QUEUED) is ProcessingStatus.PENDING


def test_to_db_rejects_unknown():
    with pytest.raises(ValueError):
        ApiDocumentStatus.to_db("bogus")
    with pytest.raises(ValueError):
        ApiDocumentStatus.to_db(None)


def test_try_to_db_returns_none_on_unknown():
    assert ApiDocumentStatus.try_to_db("bogus") is None
    assert ApiDocumentStatus.try_to_db("indexed") is ProcessingStatus.COMPLETED


# --- bijection over the canonical public vocabulary -------------------------


def test_round_trip_bijection_on_public_members():
    # queued/processing/indexed/failed round-trip through the db and back.
    for member in ApiDocumentStatus:
        assert ApiDocumentStatus.from_db(ApiDocumentStatus.to_db(member)) is member


def test_retrying_is_the_only_many_to_one_collapse():
    # retrying -> processing is intentionally NOT reversible: to_db("processing")
    # yields PROCESSING (not RETRYING). This documents the one non-bijective edge.
    assert (
        ApiDocumentStatus.from_db(ProcessingStatus.RETRYING)
        is ApiDocumentStatus.PROCESSING
    )
    assert (
        ApiDocumentStatus.to_db(ApiDocumentStatus.PROCESSING)
        is ProcessingStatus.PROCESSING
    )


# --- serialization: StrEnum carries the wire value --------------------------


def test_str_enum_serializes_to_lowercase_wire_value():
    assert str(ApiDocumentStatus.INDEXED) == "indexed"
    assert ApiDocumentStatus.INDEXED.value == "indexed"
    # The 4 public values are exactly the frontend union / OpenAPI vocabulary.
    assert {m.value for m in ApiDocumentStatus} == {
        "queued",
        "processing",
        "indexed",
        "failed",
    }
