"""QATRA multi-agent decision system.

This package is deliberately deterministic until a production model provider,
database and authenticated device bus are connected.
"""

from .orchestrator import QatraOrchestrator

__all__ = ["QatraOrchestrator"]
