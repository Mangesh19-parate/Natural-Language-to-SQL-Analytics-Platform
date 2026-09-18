"""
Compatibility re-export for app.services.optimizer module.
"""

from app.services.optimizer.query_optimizer import QueryOptimizerService
from app.services.optimizer.facade import CostBasedJoinOptimizer

__all__ = [
    "QueryOptimizerService",
    "CostBasedJoinOptimizer",
]
