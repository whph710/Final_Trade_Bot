"""
Correlation Analysis Indicator
Файл: indicators/correlation.py

Модуль для анализа корреляции с BTC и определения аномалий
"""

import numpy as np
import logging
from typing import Dict, Optional, List
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
        should_block: Блокировать ли сигнал
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
        window: int = 24
) -> float:
    """
    Рассчитать корреляцию Пирсона между двумя рядами цен

    Args:
        prices1: Первый ряд цен
        prices2: Второй ряд цен (обычно BTC)
        window: Окно для расчета

    Returns:
        Коэффициент корреляции (-1 до 1)
    """
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
        symbol_prices: List[float],
        btc_prices: List[float],
        signal_direction: str,
        btc_trend: str,
        window: int = 24
) -> BTCCorrelationAnalysis:
    """
    Анализ корреляции с BTC

    Args:
        symbol: Символ актива
        symbol_prices: Цены актива
        btc_prices: Цены BTC
        signal_direction: 'LONG' | 'SHORT'
        btc_trend: 'UP' | 'DOWN' | 'FLAT'
        window: Окно корреляции

    Returns:
        BTCCorrelationAnalysis
    """
    if len(symbol_prices) < window or len(btc_prices) < window:
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
        np.array(symbol_prices),
        np.array(btc_prices),
        window
    )

    abs_corr = abs(corr)

    # Определяем силу корреляции
    if abs_corr > 0.7:
        strength = 'STRONG'
        is_correlated = True
    elif abs_corr > 0.4:
        strength = 'MODERATE'
        is_correlated = True
    else:
        strength = 'WEAK'
        is_correlated = False

    # Проверяем alignment с BTC трендом
    should_block = False
    adjustment = 0

    # Блокируем ТОЛЬКО при очень сильной корреляции >0.85
    if abs_corr > 0.85:
        if corr > 0.85:  # Положительная корреляция
            if signal_direction == 'LONG' and btc_trend == 'UP':
                adjustment = +8
                reasoning = f'LONG aligned with BTC uptrend (strong correlation {corr:.2f})'
            elif signal_direction == 'SHORT' and btc_trend == 'DOWN':
                adjustment = +8
                reasoning = f'SHORT aligned with BTC downtrend (strong correlation {corr:.2f})'
            else:
                adjustment = -12
                should_block = False  # Не блокируем, только штрафуем
                reasoning = f'{signal_direction} misaligned with BTC {btc_trend}, correlation {corr:.2f} WARNING'

        elif corr < -0.85:  # Отрицательная корреляция
            if signal_direction == 'LONG' and btc_trend == 'DOWN':
                adjustment = +8
                reasoning = f'LONG with strong negative BTC correlation during BTC down'
            elif signal_direction == 'SHORT' and btc_trend == 'UP':
                adjustment = +8
                reasoning = f'SHORT with strong negative BTC correlation during BTC up'
            else:
                adjustment = -12
                reasoning = f'{signal_direction} misaligned with negative BTC correlation WARNING'

    elif abs_corr > 0.5:  # Умеренная корреляция
        reasoning = f'Moderate correlation {corr:.2f}, monitoring'

    else:  # Слабая корреляция
        reasoning = f'Weak BTC correlation {corr:.2f}'

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
    # Слабая корреляция - нет смысла искать аномалии
    if abs(correlation) < 0.5:
        return CorrelationAnomalyAnalysis(
            anomaly_detected=False,
            anomaly_type='NONE',
            expected_direction='NEUTRAL',
            confidence_adjustment=0,
            reasoning=f'Weak correlation {correlation:.2f}'
        )

    # Определяем ожидаемое направление движения
    if correlation > 0.5:
        expected_move_sign = np.sign(btc_change_pct)
    elif correlation < -0.5:
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
            if actual_magnitude > expected_magnitude * 1.5:
                return CorrelationAnomalyAnalysis(
                    anomaly_detected=True,
                    anomaly_type='DECOUPLING_STRENGTH',
                    expected_direction='UP' if actual_move_sign > 0 else 'DOWN',
                    confidence_adjustment=+10,
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
                confidence_adjustment=-15,
                reasoning=f'{symbol} {symbol_change_pct:+.1f}% vs BTC {btc_change_pct:+.1f}% divergence'
            )

    return CorrelationAnomalyAnalysis(
        anomaly_detected=False,
        anomaly_type='NONE',
        expected_direction='NEUTRAL',
        confidence_adjustment=0,
        reasoning='No significant movement'
    )


def calculate_price_change(prices: List[float], window: int = 24) -> float:
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


def determine_btc_trend(btc_prices: List[float], window: int = 20) -> str:
    """
    Определить тренд BTC

    Returns:
        'UP' | 'DOWN' | 'FLAT'
    """
    if len(btc_prices) < window:
        window = len(btc_prices)

    if window < 5:
        return 'FLAT'

    try:
        recent_prices = btc_prices[-window:]

        first_third = np.mean(recent_prices[:window // 3])
        last_third = np.mean(recent_prices[-window // 3:])

        change_pct = ((last_third - first_third) / first_third) * 100

        if change_pct > 1.0:
            return 'UP'
        elif change_pct < -1.0:
            return 'DOWN'
        else:
            return 'FLAT'
    except Exception:
        return 'FLAT'


def extract_closes_from_candles(candles: List[List]) -> List[float]:
    """Извлечь closes из raw candles"""
    try:
        return [float(candle[4]) for candle in candles]
    except (IndexError, ValueError, TypeError):
        return []