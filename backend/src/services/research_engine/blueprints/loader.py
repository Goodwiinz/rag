"""BlueprintLoader: loads and validates YAML blueprint templates."""

from pathlib import Path
from typing import Any, Dict, List

import yaml

from src.schemas.research_engine import StepType

TEMPLATES_DIR = Path(__file__).parent / "templates"

# Pre-compute valid step type values for validation.
_VALID_STEP_TYPES = {t.value for t in StepType}


class BlueprintLoader:
    """Loads, lists, and validates YAML blueprint templates."""

    def __init__(self, templates_dir: Path = TEMPLATES_DIR) -> None:
        self._templates_dir = templates_dir

    def list_templates(self) -> List[Dict[str, Any]]:
        """List all available YAML templates.

        Returns a list of dicts with slug, name, description, and step_count.
        """
        results: List[Dict[str, Any]] = []
        for path in sorted(self._templates_dir.glob("*.yaml")):
            with open(path, "r") as f:
                data = yaml.safe_load(f)
            results.append(
                {
                    "slug": path.stem,
                    "name": data.get("name", path.stem),
                    "description": data.get("description", ""),
                    "step_count": len(data.get("steps", [])),
                }
            )
        return results

    def load_template(self, slug: str) -> Dict[str, Any]:
        """Load and parse a YAML template by its slug (filename stem).

        Raises FileNotFoundError if the template does not exist.
        """
        path = self._templates_dir / f"{slug}.yaml"
        if not path.exists():
            raise FileNotFoundError(f"Blueprint template not found: {slug}")
        with open(path, "r") as f:
            data: Dict[str, Any] = yaml.safe_load(f)
        return data

    def validate_template(self, template: Dict[str, Any]) -> List[str]:
        """Validate a parsed template dict.

        Returns a list of error strings. An empty list means the template is valid.
        Checks:
          - steps is not empty
          - each step has a valid type (from StepType enum values)
          - each step has a name
        """
        errors: List[str] = []
        steps = template.get("steps", [])

        if not steps:
            errors.append("Steps must not be empty.")
            return errors

        for i, step in enumerate(steps):
            step_type = step.get("type")
            if step_type not in _VALID_STEP_TYPES:
                errors.append(
                    f"Step {i}: invalid type '{step_type}'. "
                    f"Must be one of {sorted(_VALID_STEP_TYPES)}."
                )

            if not step.get("name"):
                errors.append(f"Step {i}: missing required field 'name'.")

        return errors
