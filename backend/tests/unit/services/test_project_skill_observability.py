"""Safety contracts for project-skill rollout telemetry."""

from unittest.mock import Mock, patch


def test_project_skill_telemetry_emits_only_safe_dimensions(caplog):
    from src.services.agent.observability import record_project_skill_event

    caplog.set_level("INFO")
    counter = Mock()
    loaded_skills = Mock()
    loaded_tokens = Mock()

    with (
        patch("src.services.agent.observability._METRICS_AVAILABLE", True),
        patch("src.services.agent.observability.PROJECT_SKILL_EVENTS", counter),
        patch(
            "src.services.agent.observability.PROJECT_SKILL_LOADED_SKILLS",
            loaded_skills,
        ),
        patch(
            "src.services.agent.observability.PROJECT_SKILL_LOADED_TOKENS",
            loaded_tokens,
        ),
    ):
        record_project_skill_event(
            "loader",
            "success",
            loaded_skill_count=1,
            loaded_skill_tokens=123,
            unsafe_detail="instructions: SECRET_TOKEN",
        )

    counter.labels.assert_called_once_with(event="loader", outcome="success")
    counter.labels.return_value.inc.assert_called_once_with()
    loaded_skills.inc.assert_called_once_with(1)
    loaded_tokens.inc.assert_called_once_with(123)
    assert "SECRET_TOKEN" not in caplog.text


def test_project_skill_telemetry_bounds_metric_dimensions():
    from src.services.agent.observability import record_project_skill_event

    counter = Mock()
    with (
        patch("src.services.agent.observability._METRICS_AVAILABLE", True),
        patch("src.services.agent.observability.PROJECT_SKILL_EVENTS", counter),
    ):
        record_project_skill_event("unsafe-project-name", "unsafe-skill-name")

    counter.labels.assert_called_once_with(event="unknown", outcome="unknown")
