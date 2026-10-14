"""Deterministic helpers for the Cohesive outbound prospecting agent.

The agent (Claude Code + ZoomInfo/HubSpot connectors) gathers raw account and
contact data; this package scores, dedupes and exports it so every run ranks
accounts the same way regardless of how the model phrased its research.
"""

__version__ = "0.1.0"
