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

# ✅ ДОБАВЛЕНО: Correlation module
from .correlation import (
    calculate_correlation,
    analyze_btc_correlation,
    detect_correlation_anomaly,
    get_comprehensive_correlation_analysis,
    BTCCorrelationAnalysis,
    CorrelationAnomalyAnalysis
)

# ✅ ДОБАВЛЕНО: Volume Profile module
from .volume_profile import (
    calculate_volume_profile,
    analyze_volume_profile,
    VolumeProfileData,
    VolumeProfileAnalysis
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

    # ✅ ДОБАВЛЕНО: Correlation
    'calculate_correlation',
    'analyze_btc_correlation',
    'detect_correlation_anomaly',
    'get_comprehensive_correlation_analysis',
    'BTCCorrelationAnalysis',
    'CorrelationAnomalyAnalysis',

    # ✅ ДОБАВЛЕНО: Volume Profile
    'calculate_volume_profile',
    'analyze_volume_profile',
    'VolumeProfileData',
    'VolumeProfileAnalysis',
]