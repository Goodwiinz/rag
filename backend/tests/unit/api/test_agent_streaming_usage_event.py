"""Unit tests for the per-turn `usage` SSE event emitted by streaming.py.

Covers _extract_usage_tokens helper which pulls token counts from the
LangChain `on_chat_model_end` event payload. Both the normalized
`usage_metadata` shape and the raw provider `response_metadata.token_usage`
shape are exercised.
"""

from types import SimpleNamespace

from src.api.agent.streaming import _extract_usage_tokens


def _event_with_output(output) -> dict:
    return {"event": "on_chat_model_end", "data": {"output": output}}


class TestExtractUsageTokens:
    def test_uses_normalized_usage_metadata_when_present(self):
        msg = SimpleNamespace(
            usage_metadata={"input_tokens": 312, "output_tokens": 540}
        )
        assert _extract_usage_tokens(_event_with_output(msg)) == (312, 540)

    def test_falls_back_to_provider_token_usage_keys(self):
        msg = SimpleNamespace(
            usage_metadata=None,
            response_metadata={
                "token_usage": {"prompt_tokens": 11, "completion_tokens": 22}
            },
        )
        assert _extract_usage_tokens(_event_with_output(msg)) == (11, 22)

    def test_falls_back_to_input_output_alias_in_token_usage(self):
        msg = SimpleNamespace(
            usage_metadata=None,
            response_metadata={
                "token_usage": {"input_tokens": 5, "output_tokens": 7}
            },
        )
        assert _extract_usage_tokens(_event_with_output(msg)) == (5, 7)

    def test_returns_zero_when_output_missing(self):
        assert _extract_usage_tokens({"event": "on_chat_model_end", "data": {}}) == (0, 0)

    def test_returns_zero_when_usage_metadata_absent(self):
        msg = SimpleNamespace()
        assert _extract_usage_tokens(_event_with_output(msg)) == (0, 0)

    def test_returns_zero_when_token_usage_is_not_a_dict(self):
        msg = SimpleNamespace(
            usage_metadata=None,
            response_metadata={"token_usage": None},
        )
        assert _extract_usage_tokens(_event_with_output(msg)) == (0, 0)

    def test_handles_none_values_in_usage_metadata(self):
        msg = SimpleNamespace(
            usage_metadata={"input_tokens": None, "output_tokens": 10}
        )
        assert _extract_usage_tokens(_event_with_output(msg)) == (0, 10)
