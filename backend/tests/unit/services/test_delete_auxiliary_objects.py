"""delete_physical_file must remove ALL THREE object classes a document owns,
not just the original upload (audit finding D6).

A single document accumulates three Spaces objects:
  1. the original upload (``storage_path``, honoring ``storage_backend``);
  2. the canonical DO-KB text mirror ``documents/{org}/{doc}.txt``;
  3. figure PNG crops under ``figures/{org}/{doc}/``.

Classes 2 and 3 were never deleted, so they lingered as retained user content
after delete. These tests assert all three are attempted with keys derived
strictly from the document row, that the auxiliary cleanup is best-effort
(storage errors never fail the request), and that the original-delete
raise-on-failure contract is preserved.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.services.documents.file_service import FileService

pytestmark = pytest.mark.unit


def _svc():
    svc = object.__new__(FileService)  # skip heavy __init__
    # Isolate the original-upload delete (class 1) so tests can assert its args
    # without touching real storage.
    svc._delete_stored_object = MagicMock()
    return svc


def _doc(org_id="org-1", doc_id="doc-1"):
    doc = MagicMock()
    doc.organization_id = org_id
    doc.id = doc_id
    doc.storage_backend = "s3"
    doc.storage_path = f"documents/{org_id}/{doc_id}/1700000000_abcd.pdf"
    doc.file_path = f"s3://bucket/{doc.storage_path}"
    return doc


def _helper(figure_keys):
    helper = MagicMock()
    helper.list_objects = MagicMock(return_value=list(figure_keys))
    helper.delete_file = MagicMock(return_value=True)
    return helper


def test_deletes_all_three_object_classes_with_correct_keys():
    svc = _svc()
    doc = _doc()
    figure_keys = [
        "figures/org-1/doc-1/figure-p1-x5.png",
        "figures/org-1/doc-1/figure-p3-x9.png",
    ]
    helper = _helper(figure_keys)
    svc._s3_helper_or_none = MagicMock(return_value=helper)

    svc.delete_physical_file(doc)

    # (1) original upload — honors storage_backend / key / file_path.
    svc._delete_stored_object.assert_called_once_with(
        "s3", doc.storage_path, doc.file_path
    )
    # (3) figures listed under the doc-scoped prefix (embeds the doc UUID).
    helper.list_objects.assert_called_once_with("figures/org-1/doc-1/")
    # (2) canonical KB text mirror + (3) each figure crop are deleted.
    deleted = {c.args[0] for c in helper.delete_file.call_args_list}
    assert deleted == {"documents/org-1/doc-1.txt", *figure_keys}


def test_auxiliary_keys_are_scoped_to_the_document_being_deleted():
    # The derived keys must contain THIS document's ids only — the safety
    # invariant that stops the sweep from ever touching another doc's objects.
    svc = _svc()
    doc = _doc(org_id="org-XYZ", doc_id="doc-ABC")
    helper = _helper([])
    svc._s3_helper_or_none = MagicMock(return_value=helper)

    svc.delete_physical_file(doc)

    helper.delete_file.assert_called_once_with("documents/org-XYZ/doc-ABC.txt")
    helper.list_objects.assert_called_once_with("figures/org-XYZ/doc-ABC/")


def test_no_s3_configured_is_a_noop_for_auxiliary_objects():
    svc = _svc()
    doc = _doc()
    svc._s3_helper_or_none = MagicMock(return_value=None)  # e.g. local dev

    svc.delete_physical_file(doc)

    # Original still attempted; no auxiliary work when S3 is unavailable.
    svc._delete_stored_object.assert_called_once()


def test_canonical_text_delete_failure_does_not_stop_figure_cleanup():
    svc = _svc()
    doc = _doc()
    figure_keys = ["figures/org-1/doc-1/figure-p1-x5.png"]
    helper = _helper(figure_keys)

    def _delete(key):
        if key.endswith(".txt"):
            raise RuntimeError("spaces 500 on the txt object")
        return True

    helper.delete_file = MagicMock(side_effect=_delete)
    svc._s3_helper_or_none = MagicMock(return_value=helper)

    # A failure deleting the canonical .txt must NOT abort figure cleanup, and
    # must never raise out of the best-effort path.
    svc.delete_physical_file(doc)

    helper.list_objects.assert_called_once_with("figures/org-1/doc-1/")
    assert helper.delete_file.call_args_list[-1].args[0] == figure_keys[0]


def test_figure_listing_failure_is_swallowed():
    svc = _svc()
    doc = _doc()
    helper = MagicMock()
    helper.delete_file = MagicMock(return_value=True)
    helper.list_objects = MagicMock(side_effect=RuntimeError("list_objects blew up"))
    svc._s3_helper_or_none = MagicMock(return_value=helper)

    # A listing failure leaves figures as sweepable orphans; it must not raise.
    svc.delete_physical_file(doc)

    # Canonical .txt was still attempted before the (failing) figure step.
    helper.delete_file.assert_called_once_with("documents/org-1/doc-1.txt")


def test_original_delete_error_reraised_after_aux_still_runs():
    # The original-file delete keeps its raise-on-failure contract (callers log
    # it as a recoverable orphan), but auxiliary cleanup must still be attempted
    # and must not mask/replace the original error.
    svc = _svc()
    doc = _doc()
    boom = RuntimeError("original object delete failed")
    svc._delete_stored_object = MagicMock(side_effect=boom)
    helper = _helper(["figures/org-1/doc-1/figure-p1-x5.png"])
    svc._s3_helper_or_none = MagicMock(return_value=helper)

    with pytest.raises(RuntimeError) as exc:
        svc.delete_physical_file(doc)

    assert exc.value is boom  # original error, not an aux error
    # Auxiliary cleanup still ran despite the original failure.
    helper.list_objects.assert_called_once_with("figures/org-1/doc-1/")
    assert helper.delete_file.call_count >= 1
