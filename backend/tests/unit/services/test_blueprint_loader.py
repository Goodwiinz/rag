"""Tests for the BlueprintLoader service."""

import pytest

from src.schemas.research_engine import BlueprintStepDefinition
from src.services.research_engine.blueprints.loader import BlueprintLoader


@pytest.fixture
def loader() -> BlueprintLoader:
    """Create a BlueprintLoader with the default templates directory."""
    return BlueprintLoader()


class TestListTemplates:
    """Tests for BlueprintLoader.list_templates."""

    def test_list_templates(self, loader: BlueprintLoader) -> None:
        """Returns at least 3 templates with correct fields."""
        templates = loader.list_templates()
        assert len(templates) >= 3

        slugs = {t["slug"] for t in templates}
        assert "systematic_literature_review" in slugs
        assert "evidence_synthesis" in slugs
        assert "data_extraction" in slugs

        for t in templates:
            assert "slug" in t
            assert "name" in t
            assert "description" in t
            assert "step_count" in t
            assert isinstance(t["step_count"], int)
            assert t["step_count"] > 0


class TestLoadTemplate:
    """Tests for BlueprintLoader.load_template."""

    def test_load_template(self, loader: BlueprintLoader) -> None:
        """Loads systematic_literature_review successfully with valid steps."""
        template = loader.load_template("systematic_literature_review")
        assert template["name"] is not None
        assert "steps" in template
        assert len(template["steps"]) == 6

    def test_load_template_returns_valid_steps(self, loader: BlueprintLoader) -> None:
        """Each step can be parsed as a BlueprintStepDefinition."""
        template = loader.load_template("systematic_literature_review")
        for step_data in template["steps"]:
            step = BlueprintStepDefinition(**step_data)
            assert step.name
            assert step.type

    def test_load_template_not_found(self, loader: BlueprintLoader) -> None:
        """Raises FileNotFoundError for missing templates."""
        with pytest.raises(FileNotFoundError):
            loader.load_template("nonexistent_template")


class TestValidateTemplate:
    """Tests for BlueprintLoader.validate_template."""

    def test_validate_template(self, loader: BlueprintLoader) -> None:
        """No errors for a valid template."""
        template = loader.load_template("systematic_literature_review")
        errors = loader.validate_template(template)
        assert errors == []

    def test_validate_template_rejects_empty_steps(self, loader: BlueprintLoader) -> None:
        """Returns errors when steps list is empty."""
        template = {"name": "Test", "description": "Test", "steps": []}
        errors = loader.validate_template(template)
        assert len(errors) > 0
        assert any("empty" in e.lower() or "steps" in e.lower() for e in errors)

    def test_validate_template_rejects_invalid_step_type(self, loader: BlueprintLoader) -> None:
        """Returns errors when a step has an invalid type."""
        template = {
            "name": "Test",
            "description": "Test",
            "steps": [{"type": "invalid_type", "name": "Bad Step"}],
        }
        errors = loader.validate_template(template)
        assert len(errors) > 0

    def test_validate_template_rejects_missing_name(self, loader: BlueprintLoader) -> None:
        """Returns errors when a step is missing a name."""
        template = {
            "name": "Test",
            "description": "Test",
            "steps": [{"type": "search"}],
        }
        errors = loader.validate_template(template)
        assert len(errors) > 0
