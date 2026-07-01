"""Unit tests for S3StorageHelper.object_exists / StorageHelper.object_exists.

The download endpoint now checks existence before issuing a presign+302 for
remote backends (a blind redirect for a missing object served the provider's
raw XML error instead of an app 404). These tests pin the semantics:
- definitive 404/NoSuchKey -> False
- object present -> True
- any other error propagates (an outage must not read as "missing")

Pure-mock tests: no network, no app wiring.
"""

from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

from src.core.s3_client import S3StorageHelper
from src.core.supabase_client import StorageHelper


def _client_error(code, http_status):
    return ClientError(
        error_response={
            "Error": {"Code": code},
            "ResponseMetadata": {"HTTPStatusCode": http_status},
        },
        operation_name="HeadObject",
    )


class TestS3ObjectExists:
    def _helper(self, client):
        return S3StorageHelper(client=client)

    def test_present(self):
        client = MagicMock()
        client.head_object.return_value = {"ContentLength": 1}
        assert self._helper(client).object_exists("k") is True
        client.head_object.assert_called_once()

    @pytest.mark.parametrize(
        "code,http", [("404", 404), ("NoSuchKey", 404), ("NotFound", 404)]
    )
    def test_missing_variants(self, code, http):
        client = MagicMock()
        client.head_object.side_effect = _client_error(code, http)
        assert self._helper(client).object_exists("k") is False

    def test_non_404_propagates(self):
        client = MagicMock()
        client.head_object.side_effect = _client_error("AccessDenied", 403)
        with pytest.raises(ClientError):
            self._helper(client).object_exists("k")


class TestSupabaseObjectExists:
    def _helper(self, entries=None, error=None):
        client = MagicMock()
        bucket_api = client.storage.from_.return_value
        if error is not None:
            bucket_api.list.side_effect = error
        else:
            bucket_api.list.return_value = entries
        return StorageHelper(client=client), bucket_api

    def test_present_exact_name(self):
        helper, api = self._helper(entries=[{"name": "doc.pdf"}])
        assert helper.object_exists("bucket", "org/123/doc.pdf") is True
        api.list.assert_called_once_with(path="org/123", options={"search": "doc.pdf"})

    def test_search_partial_match_is_not_existence(self):
        # search is a substring match server-side; only an exact name counts
        helper, _ = self._helper(entries=[{"name": "doc.pdf.bak"}])
        assert helper.object_exists("bucket", "org/123/doc.pdf") is False

    def test_missing(self):
        helper, _ = self._helper(entries=[])
        assert helper.object_exists("bucket", "org/123/doc.pdf") is False

    def test_none_entries(self):
        helper, _ = self._helper(entries=None)
        assert helper.object_exists("bucket", "org/123/doc.pdf") is False

    def test_key_without_prefix(self):
        helper, api = self._helper(entries=[{"name": "doc.pdf"}])
        assert helper.object_exists("bucket", "doc.pdf") is True
        api.list.assert_called_once_with(path="", options={"search": "doc.pdf"})

    def test_error_propagates(self):
        helper, _ = self._helper(error=RuntimeError("storage down"))
        with pytest.raises(RuntimeError):
            helper.object_exists("bucket", "org/doc.pdf")
