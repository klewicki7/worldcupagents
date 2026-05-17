"""Domain exceptions. API layer maps these to HTTP responses via a single handler."""

from __future__ import annotations


class WCAError(Exception):
    """Base for all expected business errors. Carries an HTTP status + machine code."""

    status_code: int = 500
    code: str = "INTERNAL_ERROR"

    def __init__(self, message: str = "", details: dict[str, object] | None = None) -> None:
        super().__init__(message or self.code)
        self.message = message or self.code
        self.details = details or {}


# 400
class ValidationError(WCAError):
    status_code = 400
    code = "VALIDATION_ERROR"


class InvalidTokenError(WCAError):
    status_code = 400
    code = "INVALID_TOKEN"


class BlockedDomainError(WCAError):
    status_code = 400
    code = "BLOCKED_DOMAIN"


class InvalidNameError(WCAError):
    status_code = 400
    code = "INVALID_NAME"


class NameReservedError(WCAError):
    status_code = 400
    code = "NAME_RESERVED"


# 401
class UnauthenticatedError(WCAError):
    status_code = 401
    code = "UNAUTHENTICATED"


# 403
class ForbiddenError(WCAError):
    status_code = 403
    code = "FORBIDDEN"


# 404
class NotFoundError(WCAError):
    status_code = 404
    code = "NOT_FOUND"


# 409
class AgentAlreadyExistsError(WCAError):
    status_code = 409
    code = "AGENT_ALREADY_EXISTS"


class NameTakenError(WCAError):
    status_code = 409
    code = "NAME_TAKEN"


class MatchAlreadyResolvedError(WCAError):
    status_code = 409
    code = "ALREADY_RESOLVED"


# Admin-side resolution validation
class AdminInvalidScoreError(WCAError):
    status_code = 400
    code = "INVALID_SCORE"


class MatchTeamsTbdAdminError(WCAError):
    status_code = 400
    code = "MATCH_TEAMS_TBD"


class MatchCancelledAdminError(WCAError):
    status_code = 400
    code = "MATCH_CANCELLED"


class MatchNotResolvedError(WCAError):
    status_code = 409
    code = "NOT_RESOLVED"
