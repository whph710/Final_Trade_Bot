"""
Stages Package
Модули для этапов pipeline (Stage 1, 2, 3)
"""

from .stage1_filter import run_stage1, SignalCandidate
from .stage2_selection import run_stage2
from .stage3_analysis import run_stage3, TradingSignal

__all__ = [
    # Stage 1
    'run_stage1',
    'SignalCandidate',

    # Stage 2
    'run_stage2',

    # Stage 3
    'run_stage3',
    'TradingSignal',
]