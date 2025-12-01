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

# ✅ ДОБАВЛЕНО: Smart Money Concept - Order Blocks
from .order_blocks import (
    find_order_blocks,
    analyze_order_blocks,
    OrderBlockData,
    OrderBlockAnalysis
)

# ✅ ДОБАВЛЕНО: Smart Money Concept - Imbalances (FVG)
from .imbalance import (
    find_imbalances,
    analyze_imbalances,
    ImbalanceData,
    ImbalanceAnalysis
)

# ✅ ДОБАВЛЕНО: Smart Money Concept - Liquidity Sweeps
from .liquidity_sweep import (
    detect_liquidity_sweep,
    analyze_liquidity_sweep,
    LiquiditySweepData
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

    # ✅ ДОБАВЛЕНО: Order Blocks
    'find_order_blocks',
    'analyze_order_blocks',
    'OrderBlockData',
    'OrderBlockAnalysis',

    # ✅ ДОБАВЛЕНО: Imbalances (FVG)
    'find_imbalances',
    'analyze_imbalances',
    'ImbalanceData',
    'ImbalanceAnalysis',

    # ✅ ДОБАВЛЕНО: Liquidity Sweeps
    'detect_liquidity_sweep',
    'analyze_liquidity_sweep',
    'LiquiditySweepData',
]