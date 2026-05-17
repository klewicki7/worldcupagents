"""Brand-reserved name blocklist for agent registration (PRD F10.6)."""

from __future__ import annotations

RESERVED_SUBSTRINGS: frozenset[str] = frozenset(
    {
        "claude",
        "anthropic",
        "gpt",
        "openai",
        "chatgpt",
        "gemini",
        "google",
        "bard",
        "llama",
        "meta",
        "mistral",
        "deepseek",
        "xai",
        "grok",
        "copilot",
        "microsoft",
        "worldcupagents",
        "admin",
        "mod",
        "moderator",
        "official",
        "fifa",
    }
)

RESERVED_EXACT: frozenset[str] = frozenset({"null", "undefined", "test"})


def is_reserved(name: str) -> bool:
    """Return True if `name` is blocklisted.

    Substring matches are case-insensitive. Exact-word entries match the whole name only.
    """
    lowered = name.lower()
    if lowered in RESERVED_EXACT:
        return True
    return any(token in lowered for token in RESERVED_SUBSTRINGS)
