"""Dedicated Daily Fantasy Sports (DFS) Subsystem for FanDuel & DraftKings.

Completely isolated from the season-long fantasy league web application.
Provides slate ingestion, DvP & Vegas enrichment, MILP mathematical optimization,
and game theory analysis.
"""

from src.dfs.engine import dfs_engine

__all__ = ["dfs_engine"]
