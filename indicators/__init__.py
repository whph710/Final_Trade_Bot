"""
Technical Indicators Package
Модульные индикаторы с единым форматом данных (NormalizedCandles)

ОБНОВЛЕНО: Добавлены Support/Resistance и Wave Analysis
"""

from .ema import (
    calculate_ema,
    analyze_ema200,  # ✅ НОВОЕ
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
    analyze_waves_atr,  # ✅ НОВОЕ
    WaveAnalysis
)

from .correlation import (
    calculate_correlation,
    analyze_market_correlation,  # Универсальная функция для crypto/stocks
    detect_correlation_anomaly,
    get_comprehensive_correlation_analysis,
    BTCCorrelationAnalysis,
    CorrelationAnomalyAnalysis
)

from .volume_profile import (
    calculate_volume_profile,
    analyze_volume_profile,
    VolumeProfileData,
    VolumeProfileAnalysis
)

# ✅ НОВОЕ: News Analysis
from .news_analysis import (
    analyze_news
)

# ✅ НОВОЕ: False Breakout Strategy
from .consolidation_channel import (
    find_consolidation_channel,
    is_price_in_channel,
    get_channel_distance_pct,
    ConsolidationChannel
)

from .false_breakout import (
    detect_false_breakout,
    FalseBreakoutSignal
)

from .candle_patterns import (
    detect_buyout_bar,
    detect_sellout_bar,
    BuyoutBar,
    SelloutBar
)

# ✅ НОВОЕ: Support/Resistance Levels
from .support_resistance import (
    find_support_resistance_levels,
    analyze_support_resistance,
    SupportResistanceLevel,
    SupportResistanceAnalysis
)

__all__ = [
    # EMA
    'calculate_ema',
    'analyze_ema200',  # ✅ НОВОЕ
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
    'analyze_waves_atr',  # ✅ НОВОЕ
    'WaveAnalysis',

    # Correlation
    'calculate_correlation',
    'analyze_market_correlation',  # Универсальная для crypto/stocks
    'detect_correlation_anomaly',
    'get_comprehensive_correlation_analysis',
    'BTCCorrelationAnalysis',
    'CorrelationAnomalyAnalysis',

    # Volume Profile
    'calculate_volume_profile',
    'analyze_volume_profile',
    'VolumeProfileData',
    'VolumeProfileAnalysis',

    # ✅ НОВОЕ: Support/Resistance
    'find_support_resistance_levels',
    'analyze_support_resistance',
    'SupportResistanceLevel',
    'SupportResistanceAnalysis',
    
    # ✅ НОВОЕ: News Analysis
    'analyze_news',
    
    # ✅ НОВОЕ: False Breakout Strategy
    'find_consolidation_channel',
    'is_price_in_channel',
    'get_channel_distance_pct',
    'ConsolidationChannel',
    'detect_false_breakout',
    'FalseBreakoutSignal',
    'detect_buyout_bar',
    'detect_sellout_bar',
    'BuyoutBar',
    'SelloutBar',
]