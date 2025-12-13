"""
Utils Package
Файл: utils/__init__.py

Утилиты для работы бота
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
from .asset_detector import AssetTypeDetector

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
    
    # Asset Detector
    'AssetTypeDetector',
]