"""Unit tests for the lib/ helpers. No DB, no I/O."""

from __future__ import annotations

import pytest

from app.lib.disposable_domains import is_disposable
from app.lib.reserved_names import is_reserved
from app.lib.slugify import slugify
from app.lib.tokens import (
    TOKEN_BRAND_PREFIX,
    TOKEN_PREFIX_LEN,
    generate_token,
    verify_token,
)


class TestSlugify:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("Kevin's Predictor", "kevin-s-predictor"),
            ("Tomás-Río", "tomas-rio"),
            ("  spaces   collapse  ", "spaces-collapse"),
            ("AAA-bbb", "aaa-bbb"),
            ("a!b@c", "a-b-c"),
        ],
    )
    def test_slugify(self, raw: str, expected: str) -> None:
        assert slugify(raw) == expected


class TestReservedNames:
    @pytest.mark.parametrize(
        "name",
        ["claude-bot", "Anthropic-Predictor", "my-gpt", "official-agent", "fifa-fan"],
    )
    def test_blocked_substrings(self, name: str) -> None:
        assert is_reserved(name) is True

    @pytest.mark.parametrize("name", ["null", "UNDEFINED", "test"])
    def test_blocked_exact(self, name: str) -> None:
        assert is_reserved(name) is True

    @pytest.mark.parametrize("name", ["kevcode", "predictor-2026", "river-fan"])
    def test_allowed(self, name: str) -> None:
        assert is_reserved(name) is False


class TestDisposable:
    def test_mailinator_blocked(self) -> None:
        assert is_disposable("foo@mailinator.com") is True

    def test_gmail_allowed(self) -> None:
        assert is_disposable("kevin@gmail.com") is False

    def test_missing_at_returns_false(self) -> None:
        assert is_disposable("no-at-sign") is False

    def test_case_insensitive(self) -> None:
        assert is_disposable("X@MAILINATOR.COM") is True


class TestTokens:
    def test_generate_format(self) -> None:
        plain, token_hash, token_prefix = generate_token()
        assert plain.startswith(TOKEN_BRAND_PREFIX)
        assert len(token_prefix) == TOKEN_PREFIX_LEN
        assert token_prefix == plain[:TOKEN_PREFIX_LEN]
        # argon2id hashes start with $argon2id$
        assert token_hash.startswith("$argon2id$")

    def test_verify_round_trip(self) -> None:
        plain, token_hash, _ = generate_token()
        assert verify_token(plain, token_hash) is True
        assert verify_token(plain + "x", token_hash) is False

    def test_each_token_unique(self) -> None:
        seen = {generate_token()[0] for _ in range(20)}
        assert len(seen) == 20
