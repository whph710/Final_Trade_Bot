"""
Utils Package
Файл: utils/__init__.py

ОБНОВЛЕНО:
- Добавлены signal_storage и backtesting
"""

from .logger import setup_logger, get_logger
from .validators import (
    validate_candles,
    safe_float,
    safe_int,
    validate_rr_ratio,
    validate_prices_in_range
)
from .signal_storage import SignalStorage, get_signal_storage
from .backtesting import Backtester, get_backtester, format_backtest_report

__all__ = [
    # Logger
    'setup_logger',
    'get_logger',

    # Validators
    'validate_candles',
    'safe_float',
    'safe_int',
    'validate_rr_ratio',
    'validate_prices_in_range',

    # Signal Storage
    'SignalStorage',
    'get_signal_storage',

    # Backtesting
    'Backtester',
    'get_backtester',
    'format_backtest_report',
]