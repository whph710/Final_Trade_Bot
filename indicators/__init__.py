"""
Technical Indicators Package
Модульные индикаторы с единым форматом данных (NormalizedCandles)
"""

from .ema import (
    calculate_ema,
    analyze_triple_ema,
    EMAAnalysis
)

from .rsi import (
    calculate_rsi,
    analyze_rsi,
    RSIAnalysis
)

from .macd import (
    calculate_macd,
    analyze_macd,
    MACDData,
    MACDAnalysis
)

from .volume import (
    calculate_volume_ratio,
    analyze_volume,
    VolumeAnalysis
)

from .atr import (
    calculate_atr,
    suggest_stop_loss
)

__all__ = [
    # EMA
    'calculate_ema',
    'analyze_triple_ema',
    'EMAAnalysis',

    # RSI
    'calculate_rsi',
    'analyze_rsi',
    'RSIAnalysis',

    # MACD
    'calculate_macd',
    'analyze_macd',
    'MACDData',
    'MACDAnalysis',

    # Volume
    'calculate_volume_ratio',
    'analyze_volume',
    'VolumeAnalysis',

    # ATR
    'calculate_atr',
    'suggest_stop_loss',
]