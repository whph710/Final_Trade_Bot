"""
BTC Correlation Indicator
Файл: indicators/correlation.py

Анализ корреляции с BTC и детекция аномалий (decoupling)
"""

import numpy as np
import logging
from typing import Dict, Optional, List, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class BTCCorrelationAnalysis:
    """
    Результат анализа корреляции с BTC

    Attributes:
        correlation: Коэффициент корреляции Пирсона (-1 до 1)
        correlation_strength: 'STRONG' | 'MODERATE' | 'WEAK'
        is_correlated: Значимая корреляция (>0.5)
        should_block: Блокировать ли сигнал (только при >0.85)
        confidence_adjustment: Корректировка confidence
        reasoning: Текстовое описание
    """
    correlation: float
    correlation_strength: str
    is_correlated: bool
    should_block: bool
    confidence_adjustment: int
    reasoning: str


@dataclass
class CorrelationAnomalyAnalysis:
    """Результат анализа корреляционных аномалий"""
    anomaly_detected: bool
    anomaly_type: str  # 'DECOUPLING_STRENGTH' | 'DECOUPLING_WEAKNESS' | 'NONE'
    expected_direction: str
    confidence_adjustment: int
    reasoning: str


def calculate_correlation(
        prices1: np.ndarray,
        prices2: np.ndarray,
        window: int = None
) -> float:
    """
    Рассчитать корреляцию Пирсона между двумя рядами цен

    Args:
        prices1: Первый ряд цен
        prices2: Второй ряд цен (обычно BTC)
        window: Окно для расчета (по умолчанию из config)

    Returns:
        Коэффициент корреляции (-1 до 1)
    """
    from config import config
    
    if window is None:
        window = config.CORR_WINDOW
    
    if len(prices1) < window or len(prices2) < window:
        return 0.0

    try:
        recent_p1 = prices1[-window:]
        recent_p2 = prices2[-window:]

        # Конвертируем в numpy arrays
        arr1 = np.array(recent_p1, dtype=np.float64)
        arr2 = np.array(recent_p2, dtype=np.float64)

        # Фильтруем NaN/Inf
        mask = np.isfinite(arr1) & np.isfinite(arr2)
        arr1 = arr1[mask]
        arr2 = arr2[mask]

        if len(arr1) < 10:
            return 0.0

        # Рассчитываем корреляцию
        corr_matrix = np.corrcoef(arr1, arr2)
        correlation = corr_matrix[0, 1]

        if np.isnan(correlation) or np.isinf(correlation):
            return 0.0

        return float(correlation)

    except Exception as e:
        logger.debug(f"Correlation calculation error: {e}")
        return 0.0


def analyze_btc_correlation(
        symbol: str,
        symbol_candles,  # NormalizedCandles
        btc_candles,     # NormalizedCandles
        signal_direction: str,
        window: int = None
) -> BTCCorrelationAnalysis:
    """
    Анализ корреляции с BTC

    Args:
        symbol: Символ актива
        symbol_candles: NormalizedCandles актива
        btc_candles: NormalizedCandles BTC
        signal_direction: 'LONG' | 'SHORT'
        window: Окно корреляции

    Returns:
        BTCCorrelationAnalysis
    """
    if not symbol_candles or not btc_candles:
        return BTCCorrelationAnalysis(
            correlation=0.0,
            correlation_strength='UNKNOWN',
            is_correlated=False,
            should_block=False,
            confidence_adjustment=0,
            reasoning='Missing candles data'
        )

    from config import config
    
    if window is None:
        window = config.CORR_WINDOW
    
    if len(symbol_candles.closes) < window or len(btc_candles.closes) < window:
        return BTCCorrelationAnalysis(
            correlation=0.0,
            correlation_strength='UNKNOWN',
            is_correlated=False,
            should_block=False,
            confidence_adjustment=0,
            reasoning='Insufficient data for correlation'
        )

    # Рассчитываем корреляцию
    corr = calculate_correlation(
        symbol_candles.closes,
        btc_candles.closes,
        window
    )

    abs_corr = abs(corr)

    # Определяем силу корреляции
    if abs_corr > config.CORR_STRONG_THRESHOLD:
        strength = 'STRONG'
        is_correlated = True
    elif abs_corr > config.CORR_MODERATE_THRESHOLD:
        strength = 'MODERATE'
        is_correlated = True
    else:
        strength = 'WEAK'
        is_correlated = False

    # Определяем BTC тренд
    btc_trend = _determine_btc_trend(btc_candles.closes)

    # Проверяем alignment
    should_block = False
    adjustment = 0

    # Блокируем ТОЛЬКО при очень сильной корреляции >threshold
    if abs_corr > config.CORR_BLOCK_THRESHOLD:
        if corr > config.CORR_BLOCK_THRESHOLD:  # Положительная корреляция
            if signal_direction == 'LONG' and btc_trend == 'UP':
                adjustment = config.CORR_ALIGNED_BONUS
                reasoning = f'LONG aligned with BTC uptrend (strong correlation {corr:.2f})'
            elif signal_direction == 'SHORT' and btc_trend == 'DOWN':
                adjustment = config.CORR_ALIGNED_BONUS
                reasoning = f'SHORT aligned with BTC downtrend (strong correlation {corr:.2f})'
            else:
                adjustment = config.CORR_MISALIGNED_PENALTY
                should_block = False  # Не блокируем, только штрафуем
                reasoning = f'{signal_direction} misaligned with BTC {btc_trend}, correlation {corr:.2f} WARNING'

        elif corr < -config.CORR_BLOCK_THRESHOLD:  # Отрицательная корреляция
            if signal_direction == 'LONG' and btc_trend == 'DOWN':
                adjustment = config.CORR_ALIGNED_BONUS
                reasoning = f'LONG with strong negative BTC correlation during BTC down'
            elif signal_direction == 'SHORT' and btc_trend == 'UP':
                adjustment = config.CORR_ALIGNED_BONUS
                reasoning = f'SHORT with strong negative BTC correlation during BTC up'
            else:
                adjustment = config.CORR_MISALIGNED_PENALTY
                reasoning = f'{signal_direction} misaligned with negative BTC correlation WARNING'
    else:
        # Умеренная/слабая корреляция
        reasoning = f'{strength} BTC correlation {corr:.2f}'

    return BTCCorrelationAnalysis(
        correlation=round(corr, 3),
        correlation_strength=strength,
        is_correlated=is_correlated,
        should_block=should_block,
        confidence_adjustment=adjustment,
        reasoning=reasoning
    )


def detect_correlation_anomaly(
        symbol: str,
        symbol_change_pct: float,
        btc_change_pct: float,
        correlation: float
) -> CorrelationAnomalyAnalysis:
    """
    Детекция корреляционных аномалий (decoupling)

    Returns:
        CorrelationAnomalyAnalysis
    """
    from config import config
    
    # Слабая корреляция - нет смысла искать аномалии
    if abs(correlation) < config.CORR_SIGNIFICANT_THRESHOLD:
        return CorrelationAnomalyAnalysis(
            anomaly_detected=False,
            anomaly_type='NONE',
            expected_direction='NEUTRAL',
            confidence_adjustment=0,
            reasoning=f'Weak correlation {correlation:.2f}'
        )

    # Определяем ожидаемое направление движения
    if correlation > config.CORR_SIGNIFICANT_THRESHOLD:
        expected_move_sign = np.sign(btc_change_pct)
    elif correlation < -config.CORR_SIGNIFICANT_THRESHOLD:
        expected_move_sign = -np.sign(btc_change_pct)
    else:
        expected_move_sign = 0

    actual_move_sign = np.sign(symbol_change_pct)

    # Проверяем наличие аномалии
    if expected_move_sign != 0 and actual_move_sign != 0:
        if expected_move_sign == actual_move_sign:
            # Движение в ожидаемом направлении
            expected_magnitude = abs(btc_change_pct) * abs(correlation)
            actual_magnitude = abs(symbol_change_pct)

            # Decoupling strength: актив движется сильнее ожидаемого
            if actual_magnitude > expected_magnitude * config.CORR_ANOMALY_DECOUPLING_MULTIPLIER:
                return CorrelationAnomalyAnalysis(
                    anomaly_detected=True,
                    anomaly_type='DECOUPLING_STRENGTH',
                    expected_direction='UP' if actual_move_sign > 0 else 'DOWN',
                    confidence_adjustment=config.CORR_ANOMALY_STRENGTH_BONUS,
                    reasoning=f'{symbol} moving {actual_magnitude:.1f}% vs expected {expected_magnitude:.1f}%'
                )
            else:
                return CorrelationAnomalyAnalysis(
                    anomaly_detected=False,
                    anomaly_type='NONE',
                    expected_direction='NEUTRAL',
                    confidence_adjustment=0,
                    reasoning=f'{symbol} following BTC normally'
                )
        else:
            # Decoupling weakness: актив движется против корреляции
            return CorrelationAnomalyAnalysis(
                anomaly_detected=True,
                anomaly_type='DECOUPLING_WEAKNESS',
                expected_direction='NEUTRAL',
                confidence_adjustment=config.CORR_ANOMALY_WEAKNESS_PENALTY,
                reasoning=f'{symbol} {symbol_change_pct:+.1f}% vs BTC {btc_change_pct:+.1f}% divergence'
            )

    return CorrelationAnomalyAnalysis(
        anomaly_detected=False,
        anomaly_type='NONE',
        expected_direction='NEUTRAL',
        confidence_adjustment=0,
        reasoning='No significant movement'
    )


def calculate_price_change(prices: np.ndarray, window: int = 24) -> float:
    """Рассчитать изменение цены в процентах"""
    if len(prices) < window:
        window = len(prices)

    if window < 2:
        return 0.0

    try:
        old_price = prices[-window]
        new_price = prices[-1]

        if old_price == 0:
            return 0.0

        change = ((new_price - old_price) / old_price) * 100
        return round(change, 2)
    except (IndexError, ZeroDivisionError):
        return 0.0


def _determine_btc_trend(btc_prices: np.ndarray, window: int = None) -> str:
    """
    Определить тренд BTC

    Returns:
        'UP' | 'DOWN' | 'FLAT'
    """
    from config import config
    
    if window is None:
        window = config.CORR_BTC_TREND_WINDOW
    
    if len(btc_prices) < window:
        window = len(btc_prices)

    if window < 5:
        return 'FLAT'

    try:
        recent_prices = btc_prices[-window:]

        first_third = np.mean(recent_prices[:window // 3])
        last_third = np.mean(recent_prices[-window // 3:])

        change_pct = ((last_third - first_third) / first_third) * 100

        if change_pct > config.CORR_BTC_TREND_THRESHOLD_PCT:
            return 'UP'
        elif change_pct < -config.CORR_BTC_TREND_THRESHOLD_PCT:
            return 'DOWN'
        else:
            return 'FLAT'
    except Exception:
        return 'FLAT'


def get_comprehensive_correlation_analysis(
        symbol: str,
        symbol_candles,
        btc_candles,
        signal_direction: str
) -> Dict:
    """
    Comprehensive correlation analysis

    Args:
        symbol: Торговая пара
        symbol_candles: NormalizedCandles актива
        btc_candles: NormalizedCandles BTC
        signal_direction: 'LONG' | 'SHORT'

    Returns:
        {
            'btc_correlation': BTCCorrelationAnalysis,
            'correlation_anomaly': CorrelationAnomalyAnalysis,
            'total_confidence_adjustment': int,
            'should_block_signal': bool
        }
    """
    if not symbol_candles or not btc_candles:
        return {
            'btc_correlation': BTCCorrelationAnalysis(
                correlation=0.0,
                correlation_strength='UNKNOWN',
                is_correlated=False,
                should_block=False,
                confidence_adjustment=0,
                reasoning='Missing data'
            ),
            'correlation_anomaly': CorrelationAnomalyAnalysis(
                anomaly_detected=False,
                anomaly_type='NONE',
                expected_direction='NEUTRAL',
                confidence_adjustment=0,
                reasoning='Missing data'
            ),
            'total_confidence_adjustment': 0,
            'should_block_signal': False
        }

    # 1. BTC Correlation Analysis
    btc_corr_analysis = analyze_btc_correlation(
        symbol,
        symbol_candles,
        btc_candles,
        signal_direction
    )

    # 2. Price Changes
    symbol_change_1h = calculate_price_change(symbol_candles.closes, window=1)
    btc_change_1h = calculate_price_change(btc_candles.closes, window=1)

    # 3. Anomaly Detection
    anomaly_analysis = detect_correlation_anomaly(
        symbol,
        symbol_change_1h,
        btc_change_1h,
        btc_corr_analysis.correlation
    )

    # 4. Total Adjustment
    total_adjustment = (
        btc_corr_analysis.confidence_adjustment +
        anomaly_analysis.confidence_adjustment
    )

    return {
        'btc_correlation': btc_corr_analysis,
        'correlation_anomaly': anomaly_analysis,
        'total_confidence_adjustment': total_adjustment,
        'should_block_signal': btc_corr_analysis.should_block,
        'price_changes': {
            'symbol_1h': symbol_change_1h,
            'btc_1h': btc_change_1h
        },
        'btc_trend': _determine_btc_trend(btc_candles.closes)
    }