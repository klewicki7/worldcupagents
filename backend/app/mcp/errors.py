"""MCP tool error codes.

We raise `McpToolError` from tool implementations; the FastMCP middleware turns
them into the documented `{error, message, details}` envelope (per
`docs/04-mcp-spec.md` § 6).
"""

from __future__ import annotations

from fastmcp.exceptions import ToolError


class McpToolError(ToolError):
    """Tool-level error with a stable machine code."""

    def __init__(self, code: str, message: str, details: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}

    def as_payload(self) -> dict[str, object]:
        return {"error": self.code, "message": self.message, "details": self.details}


# Authentication / authorization
class InvalidTokenError(McpToolError):
    def __init__(self, message: str = "invalid bearer token") -> None:
        super().__init__("INVALID_TOKEN", message)


class AgentRetiredError(McpToolError):
    def __init__(self) -> None:
        super().__init__("AGENT_RETIRED", "agent is retired")


# Resource lookup
class MatchNotFoundError(McpToolError):
    def __init__(self, match_id: int) -> None:
        super().__init__("MATCH_NOT_FOUND", f"no match with id={match_id}", {"match_id": match_id})


class AgentNotFoundError(McpToolError):
    def __init__(self, key: str) -> None:
        super().__init__("AGENT_NOT_FOUND", f"no agent: {key}", {"key": key})


# Validation
class InvalidParamError(McpToolError):
    def __init__(self, message: str, details: dict[str, object] | None = None) -> None:
        super().__init__("INVALID_PARAM", message, details)


class InvalidProbabilitiesError(McpToolError):
    def __init__(self, message: str, details: dict[str, object] | None = None) -> None:
        super().__init__("INVALID_PROBABILITIES", message, details)


class InvalidScoreError(McpToolError):
    def __init__(self, message: str, details: dict[str, object] | None = None) -> None:
        super().__init__("INVALID_SCORE", message, details)


class ReasoningTooLongError(McpToolError):
    def __init__(self, length: int) -> None:
        super().__init__(
            "REASONING_TOO_LONG", "reasoning must be ≤500 characters", {"length": length}
        )


# Prediction lifecycle
class PredictionLockedError(McpToolError):
    def __init__(self, lock_at: str) -> None:
        super().__init__(
            "PREDICTION_LOCKED",
            "predictions for this match are locked",
            {"lock_at": lock_at},
        )


class MatchTeamsTbdError(McpToolError):
    def __init__(self, match_id: int) -> None:
        super().__init__(
            "MATCH_TEAMS_TBD",
            "knockout match has unfilled team slots — try after the previous round",
            {"match_id": match_id},
        )


class MatchCancelledError(McpToolError):
    def __init__(self, match_id: int) -> None:
        super().__init__("MATCH_CANCELLED", "match is cancelled", {"match_id": match_id})


# Rate limiting
class RateLimitedError(McpToolError):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__(
            "RATE_LIMITED",
            "agent is rate-limited",
            {"retry_after_seconds": retry_after_seconds},
        )
