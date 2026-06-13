"""Prompt-field sanitization utilities.

Neutralises user-controlled text before it is interpolated into LLM system
prompts, providing a minimum defence against prompt-injection attacks.

Public API
----------
_PROMPT_FIELD_MAX_CHARS : int
    Maximum character length for any sanitised field.
_sanitize_prompt_field(value: str) -> str
    Truncate, escape braces, and collapse newlines in *value*.
"""

# Maximum length (chars) for any user-supplied string interpolated into a
# classifier system prompt.  Truncating + neutralising braces/newlines is the
# minimum defence against prompt-injection via previous_turn / prior_tool /
# page_context.  Longer values are clipped with an ellipsis.
_PROMPT_FIELD_MAX_CHARS = 400


def _sanitize_prompt_field(value: str) -> str:
    """Neutralise user-controlled text before interpolating into a prompt.

    Strips characters that could either break the ``str.format()`` call
    (``{`` / ``}``) or attempt to escape the surrounding section header in
    the system prompt (newlines, markdown headings). Truncates to
    ``_PROMPT_FIELD_MAX_CHARS`` so an attacker cannot drown the actual
    classification prompt by stuffing thousands of tokens through one of
    the dynamic context fields.
    """
    if not value:
        return ""
    text = str(value)
    if len(text) > _PROMPT_FIELD_MAX_CHARS:
        text = text[:_PROMPT_FIELD_MAX_CHARS] + "..."
    # ``str.format`` interprets ``{`` / ``}`` as field delimiters — escape
    # them to literal braces.
    text = text.replace("{", "{{").replace("}", "}}")
    # Collapse newlines so dynamic content cannot start a new markdown
    # heading and visually impersonate prompt sections.
    text = text.replace("\r", " ").replace("\n", " ")
    return text
