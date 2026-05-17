"""Agent token generation and argon2id hashing.

Plain tokens are 32 random bytes encoded as URL-safe base64, prefixed with `wca_`.
We never store the plain token: only an argon2id hash plus the first 12 characters
(prefix incl. `wca_`) for display.
"""

from __future__ import annotations

import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

TOKEN_BYTES = 32
TOKEN_BRAND_PREFIX = "wca_"
TOKEN_PREFIX_LEN = 12  # "wca_" + 8 chars, matches docs/03-data-model.md note

_hasher = PasswordHasher()


def generate_token() -> tuple[str, str, str]:
    """Generate a new agent token.

    Returns:
        (plain_token, token_hash, token_prefix) — caller stores hash+prefix in DB,
        returns plain_token to the user ONCE.
    """
    raw = secrets.token_urlsafe(TOKEN_BYTES)
    plain = f"{TOKEN_BRAND_PREFIX}{raw}"
    token_hash = _hasher.hash(plain)
    token_prefix = plain[:TOKEN_PREFIX_LEN]
    return plain, token_hash, token_prefix


def verify_token(plain: str, token_hash: str) -> bool:
    """Constant-time verify; returns True on match, False on mismatch."""
    try:
        _hasher.verify(token_hash, plain)
    except VerifyMismatchError:
        return False
    return True
