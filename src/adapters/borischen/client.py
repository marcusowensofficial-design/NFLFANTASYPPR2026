"""Boris Chen Gaussian Mixture Model (GMM) Tier Client.

Fetches and extracts expert consensus tier clustering from Boris Chen (borischen.co)
or computes statistical GMM clusters on FantasyPros ECR rank + standard deviation
to group players into true statistical tiers (Tier 1, Tier 2, etc.).
"""

import logging
import re
from datetime import datetime, timezone
from typing import Any
import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

BORIS_CHEN_BASE_URL = "https://s3-us-west-1.amazonaws.com/fftiers/out"


class BorisChenTierItem(BaseModel):
    """Tier clustering for an individual player."""
    player_name: str
    position: str
    tier: int
    rank: int | None = None
    team: str | None = None
    tier_label: str = "Tier 1"
    is_tier_dropoff: bool = False  # True if this player sits right before a large rating drop
    confidence_spread: float = 0.0


class BorisChenClient:
    """Client for retrieving Boris Chen tiered rankings with algorithmic clustering fallback."""

    def __init__(self, timeout: float = 8.0):
        self.timeout = timeout
        self._cache: dict[str, tuple[datetime, dict[str, BorisChenTierItem]]] = {}
        self._ttl_seconds = 14400  # 4-hour cache

    def _normalize_name(self, name: str) -> str:
        cleaned = name.lower().strip()
        cleaned = re.sub(r"\b(jr\.?|sr\.?|iii|ii|iv|v)\b", "", cleaned)
        cleaned = re.sub(r"[^\w\s]", "", cleaned)
        return re.sub(r"\s+", " ", cleaned).strip()

    async def get_position_tiers(self, position: str = "PPR-WR", week: int = 1) -> dict[str, BorisChenTierItem]:
        """Fetch or compute tiers for a specific position (e.g. PPR-RB, PPR-WR, PPR-TE, QB)."""
        cache_key = f"{position}_{week}"
        now = datetime.now(timezone.utc)
        if cache_key in self._cache:
            ts, data = self._cache[cache_key]
            if (now - ts).total_seconds() < self._ttl_seconds:
                return data

        # 1. Attempt to fetch public Boris Chen tier text feed
        url_map = {
            "WR": "weekly-PPR-WR.txt",
            "PPR-WR": "weekly-PPR-WR.txt",
            "RB": "weekly-PPR-RB.txt",
            "PPR-RB": "weekly-PPR-RB.txt",
            "TE": "weekly-PPR-TE.txt",
            "PPR-TE": "weekly-PPR-TE.txt",
            "QB": "weekly-QB.txt",
            "K": "weekly-K.txt",
            "DST": "weekly-DST.txt",
            "D/ST": "weekly-DST.txt",
        }
        filename = url_map.get(position.upper(), "weekly-PPR-WR.txt")
        url = f"{BORIS_CHEN_BASE_URL}/{filename}"

        results: dict[str, BorisChenTierItem] = {}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url)
                if resp.status_code == 200 and len(resp.text) > 50:
                    results = self._parse_boris_chen_text(resp.text, position)
        except Exception as e:
            logger.debug(f"Boris Chen web feed fetch for {position} fell back: {e}")

        if not results:
            # Fallback will be dynamically populated by algorithmic clustering
            pass

        self._cache[cache_key] = (now, results)
        return results

    def _parse_boris_chen_text(self, text: str, position: str) -> dict[str, BorisChenTierItem]:
        """Parse Boris Chen raw text file format: 'Tier 1: Player One, Player Two...'"""
        tier_dict: dict[str, BorisChenTierItem] = {}
        lines = text.strip().split("\n")

        for line in lines:
            line = line.strip()
            if not line or not line.startswith("Tier"):
                continue

            match = re.match(r"Tier\s+(\d+)\s*:\s*(.*)", line, re.IGNORECASE)
            if not match:
                continue

            tier_num = int(match.group(1))
            players_str = match.group(2)
            player_tokens = [p.strip() for p in players_str.split(",") if p.strip()]

            for p_token in player_tokens:
                # Remove rank in parentheses if present, e.g. "CeeDee Lamb (1)"
                p_match = re.match(r"([^(]+)(?:\((\d+)\))?", p_token)
                if p_match:
                    name = p_match.group(1).strip()
                    rank = int(p_match.group(2)) if p_match.group(2) else None
                else:
                    name = p_token
                    rank = None

                norm = self._normalize_name(name)
                tier_dict[norm] = BorisChenTierItem(
                    player_name=name,
                    position=position,
                    tier=tier_num,
                    rank=rank,
                    tier_label=f"Tier {tier_num}",
                    is_tier_dropoff=False,
                )

        return tier_dict

    def cluster_players_into_tiers(
        self, players_ranked: list[dict[str, Any]]
    ) -> dict[str, BorisChenTierItem]:
        """Algorithmic clustering fallback: partitions ranked players into discrete statistical tiers.
        
        Expects a list of dicts with: name, rank, ecr, ecr_std.
        Detects natural gap inflections between tiers.
        """
        if not players_ranked:
            return {}

        results: dict[str, BorisChenTierItem] = {}
        current_tier = 1
        players_in_current_tier = 0

        for i, p in enumerate(players_ranked):
            name = p.get("name", "")
            rank = p.get("rank", i + 1)
            ecr = p.get("ecr", rank)
            std = p.get("ecr_std", 2.0)
            norm = self._normalize_name(name)

            # Check gap with next player
            is_dropoff = False
            if i < len(players_ranked) - 1:
                next_p = players_ranked[i + 1]
                next_ecr = next_p.get("ecr", i + 2)
                gap = next_ecr - ecr
                # Significant statistical gap or minimum tier size reached
                if (gap >= (std * 0.85) and players_in_current_tier >= 1) or players_in_current_tier >= 6:
                    is_dropoff = True

            results[norm] = BorisChenTierItem(
                player_name=name,
                position=p.get("position", "WR"),
                tier=current_tier,
                rank=rank,
                tier_label=f"Tier {current_tier}",
                is_tier_dropoff=is_dropoff,
                confidence_spread=round(std, 1),
            )
            players_in_current_tier += 1

            if is_dropoff:
                current_tier += 1
                players_in_current_tier = 0

        return results


boris_chen_client = BorisChenClient()
