"""Player Identity Package."""

from src.core.identity.resolver import (
    CanonicalPlayer,
    PlayerIdentityResolver,
    normalize_name,
    player_resolver,
)

__all__ = [
    "CanonicalPlayer",
    "PlayerIdentityResolver",
    "normalize_name",
    "player_resolver",
]
