"""Unit tests for FeatureFlagService.

Covers:
- Initialization with and without LaunchDarkly SDK
- _load_mock_flags: JSON config and hardcoded defaults
- is_enabled, get_variation, get_all_flags in mock and LD modes
- identify_user, track_event, flush, close
- _create_ld_user with optional fields
- Module-level feature_flag_service singleton
- All convenience functions

Note: the module is imported directly (bypassing the package __init__.py) so
that this test has no transitive dependencies on SQLAlchemy, cryptography, etc.
"""

import importlib.util
import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, mock_open, patch

import pytest

# ---------------------------------------------------------------------------
# Isolated module import — bypasses src/services/infrastructure/__init__.py
# ---------------------------------------------------------------------------
_MODULE_PATH = (
    Path(__file__).parent.parent.parent.parent
    / "src"
    / "services"
    / "infrastructure"
    / "feature_flags.py"
)
_spec = importlib.util.spec_from_file_location("_ff_isolated", str(_MODULE_PATH))
ff_module = importlib.util.module_from_spec(_spec)
sys.modules["_ff_isolated"] = ff_module
_spec.loader.exec_module(ff_module)  # type: ignore[union-attr]

FeatureFlag = ff_module.FeatureFlag
FeatureFlagService = ff_module.FeatureFlagService
UserContext = ff_module.UserContext
get_ai_model_type = ff_module.get_ai_model_type
get_file_upload_limit = ff_module.get_file_upload_limit
get_search_result_count = ff_module.get_search_result_count
is_advanced_analytics_enabled = ff_module.is_advanced_analytics_enabled
is_evaluation_metrics_enabled = ff_module.is_evaluation_metrics_enabled
is_multimodal_processing_enabled = ff_module.is_multimodal_processing_enabled
is_real_time_processing_enabled = ff_module.is_real_time_processing_enabled

# ── Constants ─────────────────────────────────────────────────────────────────

_HARDCODED_DEFAULTS = {
    "multimodal-processing": False,
    "advanced-analytics": True,
    "evaluation-metrics": True,
    "real-time-processing": False,
    "experimental-ui": False,
    "ai-model-optimization": "standard",
    "file-upload-limits": 100,
    "search-result-count": 10,
}

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def user_ctx() -> UserContext:
    return UserContext(user_id="user-123", email="user@example.com", name="Test User")


@pytest.fixture
def ld_service():
    """
    FeatureFlagService backed by a mocked LaunchDarkly client.

    Patches remain active for the full duration of the test (via yield).
    Returns (service, mock_ld_client).
    """
    mock_ld = MagicMock()
    mock_client = MagicMock()
    mock_user = MagicMock()
    mock_config = MagicMock()

    mock_ld.LDClient.return_value = mock_client
    mock_ld.Config.return_value = mock_config
    mock_ld.User.return_value = mock_user

    with (
        patch.dict(os.environ, {"LAUNCHDARKLY_SDK_KEY": "sdk-test-key"}),
        patch.object(ff_module, "LAUNCHDARKLY_AVAILABLE", True),
        patch.object(ff_module, "ld", mock_ld, create=True),
    ):
        service = FeatureFlagService()
        yield service, mock_client


# ── Initialization ────────────────────────────────────────────────────────────


@pytest.mark.unit
def test_init_without_sdk_key_uses_mock_flags():
    """Without LAUNCHDARKLY_SDK_KEY the service starts in mock mode."""
    env = {k: v for k, v in os.environ.items() if k != "LAUNCHDARKLY_SDK_KEY"}
    with patch.dict(os.environ, env, clear=True):
        service = FeatureFlagService()

    assert service._initialized is False
    assert service._client is None
    assert len(service._mock_flags) > 0


@pytest.mark.unit
def test_init_with_sdk_key_initializes_launchdarkly_client():
    """When SDK key is present and SDK available, the LD client is initialised."""
    mock_ld = MagicMock()
    mock_client = MagicMock()
    mock_ld.LDClient.return_value = mock_client
    mock_ld.Config.return_value = MagicMock()

    with (
        patch.dict(os.environ, {"LAUNCHDARKLY_SDK_KEY": "sdk-test-key"}),
        patch.object(ff_module, "LAUNCHDARKLY_AVAILABLE", True),
        patch.object(ff_module, "ld", mock_ld, create=True),
    ):
        service = FeatureFlagService()

    assert service._initialized is True
    assert service._client is mock_client


@pytest.mark.unit
def test_init_launchdarkly_failure_falls_back_to_mock_flags():
    """When LD initialisation raises, the service falls back to mock flags."""
    mock_ld = MagicMock()
    mock_ld.Config.side_effect = RuntimeError("SDK unreachable")

    with (
        patch.dict(os.environ, {"LAUNCHDARKLY_SDK_KEY": "sdk-test-key"}),
        patch.object(ff_module, "LAUNCHDARKLY_AVAILABLE", True),
        patch.object(ff_module, "ld", mock_ld, create=True),
    ):
        service = FeatureFlagService()

    assert service._initialized is False
    assert service._client is None
    assert len(service._mock_flags) > 0


# ── _load_mock_flags ───────────────────────────────────────────────────────────


@pytest.mark.unit
def test_load_mock_flags_hardcoded_defaults_when_file_missing():
    """When the JSON config file does not exist, hardcoded defaults are applied."""
    with patch("os.path.exists", return_value=False):
        service = FeatureFlagService()

    for key, expected in _HARDCODED_DEFAULTS.items():
        assert service._mock_flags[key] == expected, (
            f"Expected {key!r} = {expected!r}, got {service._mock_flags[key]!r}"
        )


@pytest.mark.unit
def test_load_mock_flags_from_valid_json_stores_under_outer_key():
    """Values from JSON config are stored under their outer (underscore) keys."""
    mock_config = {
        "flags": {
            "custom_flag": {
                "variations": [{"value": "alpha"}, {"value": "beta"}],
                "defaultRule": {"variation": 0},
            }
        }
    }
    m = mock_open(read_data=json.dumps(mock_config))
    with (
        patch("os.path.exists", return_value=True),
        patch("builtins.open", m),
    ):
        service = FeatureFlagService()

    assert service._mock_flags.get("custom_flag") == "alpha"


@pytest.mark.unit
def test_load_mock_flags_out_of_range_variation_index_skips_entry():
    """If the variation index exceeds the variations list, the flag is skipped."""
    mock_config = {
        "flags": {
            "bad_flag": {
                "variations": [{"value": True}],
                "defaultRule": {"variation": 5},
            }
        }
    }
    m = mock_open(read_data=json.dumps(mock_config))
    with (
        patch("os.path.exists", return_value=True),
        patch("builtins.open", m),
    ):
        service = FeatureFlagService()

    assert "bad_flag" not in service._mock_flags


@pytest.mark.unit
def test_load_mock_flags_malformed_json_falls_back_to_hardcoded_defaults():
    """A JSON parse error does not raise; hardcoded defaults are still applied."""
    m = mock_open(read_data="not valid json {{{{")
    with (
        patch("os.path.exists", return_value=True),
        patch("builtins.open", m),
    ):
        service = FeatureFlagService()

    assert service._mock_flags["advanced-analytics"] is True
    assert service._mock_flags["multimodal-processing"] is False


@pytest.mark.unit
def test_load_mock_flags_json_underscore_keys_never_shadow_dash_defaults():
    """
    JSON stores flags under underscore keys (e.g. "multimodal_processing"),
    but is_enabled lookups use dash keys (e.g. "multimodal-processing").
    The hardcoded defaults for dash keys are therefore always applied.
    """
    mock_config = {
        "flags": {
            "multimodal_processing": {
                "variations": [{"value": True}, {"value": False}],
                "defaultRule": {"variation": 0},
            }
        }
    }
    m = mock_open(read_data=json.dumps(mock_config))
    with (
        patch("os.path.exists", return_value=True),
        patch("builtins.open", m),
    ):
        service = FeatureFlagService()

    # Dash key gets hardcoded default (False), not the JSON value.
    assert service._mock_flags["multimodal-processing"] is False
    # Underscore key holds the JSON-loaded value.
    assert service._mock_flags["multimodal_processing"] is True


# ── is_enabled (mock mode) ────────────────────────────────────────────────────


@pytest.mark.unit
def test_is_enabled_multimodal_processing_disabled_by_default():
    assert FeatureFlagService().is_enabled(FeatureFlag.MULTIMODAL_PROCESSING) is False


@pytest.mark.unit
def test_is_enabled_advanced_analytics_enabled_by_default():
    assert FeatureFlagService().is_enabled(FeatureFlag.ADVANCED_ANALYTICS) is True


@pytest.mark.unit
def test_is_enabled_evaluation_metrics_enabled_by_default():
    assert FeatureFlagService().is_enabled(FeatureFlag.EVALUATION_METRICS) is True


@pytest.mark.unit
def test_is_enabled_real_time_processing_disabled_by_default():
    assert FeatureFlagService().is_enabled(FeatureFlag.REAL_TIME_PROCESSING) is False


@pytest.mark.unit
def test_is_enabled_experimental_ui_disabled_by_default():
    assert FeatureFlagService().is_enabled(FeatureFlag.EXPERIMENTAL_UI) is False


@pytest.mark.unit
def test_is_enabled_casts_truthy_numeric_to_true():
    """FILE_UPLOAD_LIMITS default is 100 (truthy); is_enabled must return True."""
    assert FeatureFlagService().is_enabled(FeatureFlag.FILE_UPLOAD_LIMITS) is True


@pytest.mark.unit
def test_is_enabled_returns_supplied_default_when_flag_absent():
    service = FeatureFlagService()
    service._mock_flags.clear()

    assert service.is_enabled(FeatureFlag.MULTIMODAL_PROCESSING, default_value=True) is True
    assert service.is_enabled(FeatureFlag.MULTIMODAL_PROCESSING, default_value=False) is False


@pytest.mark.unit
def test_is_enabled_user_context_ignored_in_mock_mode(user_ctx):
    """In mock mode, the user context has no effect on the returned value."""
    service = FeatureFlagService()
    assert service.is_enabled(FeatureFlag.ADVANCED_ANALYTICS, user_context=user_ctx) is True


# ── get_variation (mock mode) ─────────────────────────────────────────────────


@pytest.mark.unit
def test_get_variation_ai_model_optimization_returns_standard():
    assert FeatureFlagService().get_variation(FeatureFlag.AI_MODEL_OPTIMIZATION) == "standard"


@pytest.mark.unit
def test_get_variation_file_upload_limits_returns_100():
    assert FeatureFlagService().get_variation(FeatureFlag.FILE_UPLOAD_LIMITS) == 100


@pytest.mark.unit
def test_get_variation_search_result_count_returns_10():
    assert FeatureFlagService().get_variation(FeatureFlag.SEARCH_RESULT_COUNT) == 10


@pytest.mark.unit
def test_get_variation_returns_custom_default_when_flag_absent():
    service = FeatureFlagService()
    service._mock_flags.clear()

    assert service.get_variation(FeatureFlag.AI_MODEL_OPTIMIZATION, default_value="fallback") == "fallback"


@pytest.mark.unit
def test_get_variation_user_context_ignored_in_mock_mode(user_ctx):
    service = FeatureFlagService()
    assert service.get_variation(FeatureFlag.FILE_UPLOAD_LIMITS, user_context=user_ctx) == 100


# ── get_all_flags (mock mode) ─────────────────────────────────────────────────


@pytest.mark.unit
def test_get_all_flags_contains_all_expected_keys():
    flags = FeatureFlagService().get_all_flags()
    for key in _HARDCODED_DEFAULTS:
        assert key in flags, f"Expected key {key!r} missing from get_all_flags()"


@pytest.mark.unit
def test_get_all_flags_values_match_hardcoded_defaults():
    flags = FeatureFlagService().get_all_flags()
    for key, expected in _HARDCODED_DEFAULTS.items():
        assert flags[key] == expected


@pytest.mark.unit
def test_get_all_flags_returns_independent_copy():
    """Mutating the returned dict must not affect the service's internal state."""
    service = FeatureFlagService()
    flags = service.get_all_flags()
    original = flags["multimodal-processing"]

    flags["multimodal-processing"] = not original

    assert service._mock_flags["multimodal-processing"] == original


# ── LaunchDarkly mode — is_enabled ────────────────────────────────────────────


@pytest.mark.unit
def test_is_enabled_ld_mode_delegates_to_client_variation(ld_service):
    service, mock_client = ld_service
    mock_client.variation.return_value = True

    result = service.is_enabled(FeatureFlag.MULTIMODAL_PROCESSING)

    assert result is True
    mock_client.variation.assert_called_once()
    assert mock_client.variation.call_args[0][0] == FeatureFlag.MULTIMODAL_PROCESSING.value


@pytest.mark.unit
def test_is_enabled_ld_mode_uses_user_context_when_provided(ld_service, user_ctx):
    service, mock_client = ld_service
    mock_client.variation.return_value = False

    service.is_enabled(FeatureFlag.ADVANCED_ANALYTICS, user_context=user_ctx)

    mock_client.variation.assert_called_once()


@pytest.mark.unit
def test_is_enabled_ld_mode_falls_back_to_mock_on_exception(ld_service):
    service, mock_client = ld_service
    mock_client.variation.side_effect = RuntimeError("LD unavailable")

    # Seed the mock flags so fallback returns a known value.
    service._mock_flags["advanced-analytics"] = True

    result = service.is_enabled(FeatureFlag.ADVANCED_ANALYTICS)

    assert result is True


# ── LaunchDarkly mode — get_variation ─────────────────────────────────────────


@pytest.mark.unit
def test_get_variation_ld_mode_delegates_to_client(ld_service):
    service, mock_client = ld_service
    mock_client.variation.return_value = "optimized"

    assert service.get_variation(FeatureFlag.AI_MODEL_OPTIMIZATION) == "optimized"
    mock_client.variation.assert_called_once()


@pytest.mark.unit
def test_get_variation_ld_mode_falls_back_to_mock_on_exception(ld_service):
    service, mock_client = ld_service
    mock_client.variation.side_effect = RuntimeError("network error")

    # Seed the mock flags so fallback returns a known value.
    service._mock_flags["ai-model-optimization"] = "standard"

    assert service.get_variation(FeatureFlag.AI_MODEL_OPTIMIZATION) == "standard"


# ── LaunchDarkly mode — get_all_flags ─────────────────────────────────────────


@pytest.mark.unit
def test_get_all_flags_ld_mode_delegates_to_all_flags_state(ld_service):
    service, mock_client = ld_service
    flag_val = MagicMock()
    flag_val.value = True
    mock_client.all_flags_state.return_value.to_values_map.return_value = {
        "multimodal-processing": flag_val
    }

    result = service.get_all_flags()

    assert result == {"multimodal-processing": True}
    mock_client.all_flags_state.assert_called_once()


@pytest.mark.unit
def test_get_all_flags_ld_mode_falls_back_to_mock_on_exception(ld_service):
    service, mock_client = ld_service
    mock_client.all_flags_state.side_effect = RuntimeError("error")

    # Seed the mock flags so the fallback dict is non-empty.
    service._mock_flags.update(_HARDCODED_DEFAULTS)

    result = service.get_all_flags()

    for key in _HARDCODED_DEFAULTS:
        assert key in result


# ── LaunchDarkly mode — side-effect methods ────────────────────────────────────


@pytest.mark.unit
def test_identify_user_ld_mode_calls_client_identify(ld_service, user_ctx):
    service, mock_client = ld_service
    service.identify_user(user_ctx)
    mock_client.identify.assert_called_once()


@pytest.mark.unit
def test_track_event_ld_mode_calls_client_track_with_event_name(ld_service, user_ctx):
    service, mock_client = ld_service
    service.track_event("purchase", user_ctx, {"amount": 42})

    mock_client.track.assert_called_once()
    assert mock_client.track.call_args[0][0] == "purchase"


@pytest.mark.unit
def test_track_event_ld_mode_passes_empty_dict_when_data_is_none(ld_service):
    service, mock_client = ld_service
    service.track_event("no-data-event")

    mock_client.track.assert_called_once()
    assert mock_client.track.call_args[0][2] == {}


@pytest.mark.unit
def test_flush_ld_mode_calls_client_flush(ld_service):
    service, mock_client = ld_service
    service.flush()
    mock_client.flush.assert_called_once()


@pytest.mark.unit
def test_close_ld_mode_calls_client_close(ld_service):
    service, mock_client = ld_service
    service.close()
    mock_client.close.assert_called_once()


# ── mock-mode no-ops for side-effect methods ──────────────────────────────────


@pytest.mark.unit
def test_identify_user_noop_in_mock_mode(user_ctx):
    FeatureFlagService().identify_user(user_ctx)  # must not raise


@pytest.mark.unit
def test_track_event_noop_in_mock_mode():
    FeatureFlagService().track_event("event", data={"k": "v"})  # must not raise


@pytest.mark.unit
def test_flush_noop_in_mock_mode():
    FeatureFlagService().flush()  # must not raise


@pytest.mark.unit
def test_close_noop_in_mock_mode():
    FeatureFlagService().close()  # must not raise


# ── _create_ld_user ───────────────────────────────────────────────────────────


@pytest.mark.unit
def test_create_ld_user_sets_user_id_email_and_name():
    """`ld.User` is constructed with the user_id; email and name are set."""
    mock_ld = MagicMock()
    mock_user = MagicMock()
    mock_user.custom = {}
    mock_ld.User.return_value = mock_user

    service = FeatureFlagService()
    ctx = UserContext(user_id="u1", email="u1@test.com", name="Alice")

    with patch.object(ff_module, "ld", mock_ld, create=True):
        service._create_ld_user(ctx)

    mock_ld.User.assert_called_once_with("u1")
    assert mock_user.email == "u1@test.com"
    assert mock_user.name == "Alice"


@pytest.mark.unit
def test_create_ld_user_sets_custom_attributes():
    mock_ld = MagicMock()
    mock_user = MagicMock()
    mock_user.custom = {}
    mock_ld.User.return_value = mock_user

    service = FeatureFlagService()
    ctx = UserContext(
        user_id="u1",
        email="u1@test.com",
        custom_attributes={"role": "admin", "tier": "premium"},
    )

    with patch.object(ff_module, "ld", mock_ld, create=True):
        service._create_ld_user(ctx)

    assert mock_user.custom["role"] == "admin"
    assert mock_user.custom["tier"] == "premium"


@pytest.mark.unit
def test_create_ld_user_skips_name_assignment_when_none():
    mock_ld = MagicMock()
    mock_user = MagicMock(spec=["email", "custom"])
    mock_user.custom = {}
    mock_ld.User.return_value = mock_user

    service = FeatureFlagService()
    ctx = UserContext(user_id="u1", email="u1@test.com")  # name=None

    with patch.object(ff_module, "ld", mock_ld, create=True):
        service._create_ld_user(ctx)

    assert not hasattr(mock_user, "name") or mock_user.name != "u1"


@pytest.mark.unit
def test_create_ld_user_skips_custom_attrs_when_none():
    mock_ld = MagicMock()
    mock_user = MagicMock()
    custom_dict: dict = {}
    mock_user.custom = custom_dict
    mock_ld.User.return_value = mock_user

    service = FeatureFlagService()
    ctx = UserContext(user_id="u1", email="u1@test.com")  # custom_attributes=None

    with patch.object(ff_module, "ld", mock_ld, create=True):
        service._create_ld_user(ctx)

    assert custom_dict == {}


# ── UserContext dataclass ──────────────────────────────────────────────────────


@pytest.mark.unit
def test_user_context_stores_all_fields():
    ctx = UserContext(
        user_id="u42",
        email="u42@example.com",
        name="Bob",
        custom_attributes={"plan": "pro"},
    )
    assert ctx.user_id == "u42"
    assert ctx.email == "u42@example.com"
    assert ctx.name == "Bob"
    assert ctx.custom_attributes == {"plan": "pro"}


@pytest.mark.unit
def test_user_context_optional_fields_default_to_none():
    ctx = UserContext(user_id="u1", email="u1@example.com")
    assert ctx.name is None
    assert ctx.custom_attributes is None


# ── Module-level singleton ────────────────────────────────────────────────────


@pytest.mark.unit
def test_module_level_feature_flag_service_is_instance_of_service():
    assert isinstance(ff_module.feature_flag_service, FeatureFlagService)


@pytest.mark.unit
def test_module_level_feature_flag_service_is_same_object_each_access():
    """The module-level instance must be stable (not re-created on each access)."""
    svc1 = ff_module.feature_flag_service
    svc2 = ff_module.feature_flag_service
    assert svc1 is svc2


# ── Convenience functions ──────────────────────────────────────────────────────


@pytest.mark.unit
def test_is_multimodal_processing_enabled_returns_false():
    assert is_multimodal_processing_enabled() is False


@pytest.mark.unit
def test_is_advanced_analytics_enabled_returns_true():
    assert is_advanced_analytics_enabled() is True


@pytest.mark.unit
def test_is_evaluation_metrics_enabled_returns_true():
    assert is_evaluation_metrics_enabled() is True


@pytest.mark.unit
def test_is_real_time_processing_enabled_returns_false():
    assert is_real_time_processing_enabled() is False


@pytest.mark.unit
def test_get_file_upload_limit_returns_100():
    assert get_file_upload_limit() == 100


@pytest.mark.unit
def test_get_search_result_count_returns_10():
    assert get_search_result_count() == 10


@pytest.mark.unit
def test_get_ai_model_type_returns_standard():
    assert get_ai_model_type() == "standard"


@pytest.mark.unit
def test_convenience_functions_accept_user_context_without_raising(user_ctx):
    assert isinstance(is_multimodal_processing_enabled(user_ctx), bool)
    assert isinstance(is_advanced_analytics_enabled(user_ctx), bool)
    assert isinstance(is_evaluation_metrics_enabled(user_ctx), bool)
    assert isinstance(is_real_time_processing_enabled(user_ctx), bool)
    assert isinstance(get_file_upload_limit(user_ctx), int)
    assert isinstance(get_search_result_count(user_ctx), int)
    assert isinstance(get_ai_model_type(user_ctx), str)


@pytest.mark.unit
def test_convenience_functions_delegate_to_module_singleton():
    """Convenience functions must use the module-level feature_flag_service."""
    mock_service = MagicMock()
    mock_service.is_enabled.return_value = True
    mock_service.get_variation.return_value = 999

    with patch.object(ff_module, "feature_flag_service", mock_service):
        assert is_multimodal_processing_enabled() is True
        assert get_file_upload_limit() == 999

    mock_service.is_enabled.assert_called()
    mock_service.get_variation.assert_called()
