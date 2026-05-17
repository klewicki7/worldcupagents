"""Single slowapi limiter shared across routers.

Per-IP routes use the default key_func (remote address). Per-human routes pass an
endpoint-specific `key_func` to `@limiter.limit(..., key_func=human_key)`, which reads
the authenticated human off `request.state`.
"""

from __future__ import annotations

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def human_key(request: Request) -> str:
    """Key the limiter by the authenticated human's UUID; fall back to IP."""
    human = getattr(request.state, "human", None)
    if human is not None:
        return f"human:{human.id}"
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=get_remote_address)
