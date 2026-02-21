"""System prompts for the Scholarly Tone Engine."""

CITATION_INSTRUCTION = (
    "CRITICAL: Preserve ALL citation markers (e.g. [1], [2], [3]) in their "
    "semantically equivalent positions. Do NOT remove, add, or renumber citations."
)

TONE_PROMPTS = {
    "academic": (
        "Rewrite the following text in a formal academic tone. Use precise vocabulary, "
        "hedging language (e.g., 'suggests', 'appears to'), passive voice where appropriate, "
        "and discipline-specific terminology. Maintain the original meaning and all factual claims.\n\n"
        f"{CITATION_INSTRUCTION}"
    ),
    "simplified": (
        "Rewrite the following text for a general audience at an 8th-grade reading level. "
        "Use active voice, short sentences, concrete examples, and avoid jargon. "
        "Replace technical terms with plain-language equivalents.\n\n"
        f"{CITATION_INSTRUCTION}"
    ),
    "concise": (
        "Rewrite the following text to be as concise as possible without losing meaning. "
        "Remove redundancy, tighten sentences, eliminate filler words, and merge related ideas. "
        "The result should be significantly shorter than the original.\n\n"
        f"{CITATION_INSTRUCTION}"
    ),
    "expanded": (
        "Expand the following text by adding context, examples, transitions, and elaboration. "
        "Flesh out implicit assumptions, provide supporting details, and improve flow between ideas. "
        "The result should be more thorough and accessible.\n\n"
        f"{CITATION_INSTRUCTION}"
    ),
}
