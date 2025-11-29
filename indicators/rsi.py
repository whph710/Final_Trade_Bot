"""
RSI Indicator
Файл: indicators/rsi.py

Relative Strength Index calculation and analysis
"""

import numpy as np
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class RSIAnalysis:
    """
    Результат анализа RSI

    Attributes:
        rsi_current: Текущее значение RSI
        rsi_zone: 'OVERBOUGHT' | 'OVERSOLD' | 'OPTIMAL' | 'NEUTRAL'
        divergence_detected: Обнаружена ли дивергенция
        multi_tf_exhaustion: Multi-timeframe exhaustion (опционально)
        confidence_adjustment: Корректировка confidence (-15 до +8)
        details: Текстовое описание
    """
    rsi_current: float
    rsi_zone: str
    divergence_detected: bool
    multi_tf_exhaustion: bool
    confidence_adjustment: int
    details: str


def calculate_rsi(prices: np.ndarray, period: int = 14) -> np.ndarray:
    """
    Рассчитать Relative Strength Index

    Args:
        prices: Массив цен закрытия
        period: Период RSI (обычно 14)

    Returns:
        Массив значений RSI (0-100)
    """
    if len(prices) < period + 1:
        return np.full_like(prices, 50.0)

    try:
        prices = np.array(prices, dtype=np.float64)

        if np.all(prices == 0) or len(prices) < 2:
            return np.full_like(prices, 50.0)

        # Рассчитываем изменения цен
        deltas = np.diff(prices)

        # Разделяем на gains и losses
        gains = np.where(deltas > 0, deltas, 0)
        losses = np.where(deltas < 0, -deltas, 0)

        # Добавляем 0 в начало для выравнивания длины
        gains = np.concatenate([[0], gains])
        losses = np.concatenate([[0], losses])

        avg_gains = np.zeros_like(prices)
        avg_losses = np.zeros_like(prices)

        # Инициализация первого среднего
        if len(gains) >= period:
            avg_gains[period] = np.mean(gains[1:period + 1])
            avg_losses[period] = np.mean(losses[1:period + 1])

        # Экспоненциальное сглаживание
        alpha = 1.0 / period
        for i in range(period + 1, len(prices)):
            avg_gains[i] = alpha * gains[i] + (1 - alpha) * avg_gains[i - 1]
            avg_losses[i] = alpha * losses[i] + (1 - alpha) * avg_losses[i - 1]

        # Рассчитываем RSI
        rsi = np.full_like(prices, 50.0)
        for i in range(period, len(prices)):
            if avg_losses[i] != 0:
                rs = avg_gains[i] / avg_losses[i]
                rsi[i] = 100 - (100 / (1 + rs))
            else:
                rsi[i] = 100 if avg_gains[i] > 0 else 50

        return np.clip(rsi, 0, 100)

    except Exception as e:
        logger.error(f"RSI calculation error: {e}")
        return np.full_like(prices, 50.0)


def analyze_rsi(
        candles,  # NormalizedCandles
        period: int = 14,
        overbought: float = 70,
        oversold: float = 30,
        optimal_long: tuple = (50, 70),
        optimal_short: tuple = (30, 50)
) -> Optional[RSIAnalysis]:
    """
    Анализ RSI для определения зон перекупленности/перепроданности

    Args:
        candles: NormalizedCandles объект
        period: Период RSI
        overbought: Порог перекупленности
        oversold: Порог перепроданности
        optimal_long: Оптимальная зона для LONG
        optimal_short: Оптимальная зона для SHORT

    Returns:
        RSIAnalysis объект или None при ошибке
    """
    if not candles or not candles.is_valid:
        return None

    if len(candles.closes) < period + 10:
        return None

    try:
        rsi = calculate_rsi(candles.closes, period)
        current_rsi = float(rsi[-1])

        # Определяем зону
        zone = _determine_zone(
            current_rsi, overbought, oversold,
            optimal_long, optimal_short
        )

        # Проверка дивергенции (опционально, упрощённая версия)
        divergence = _check_divergence(candles.closes, rsi)

        # Multi-TF exhaustion (для будущего использования)
        multi_tf_exhaustion = False

        # Корректировка confidence
        adjustment = _calculate_adjustment(
            current_rsi, zone, divergence, overbought, oversold
        )

        # Детали
        details = _build_rsi_details(current_rsi, zone, divergence, adjustment)

        return RSIAnalysis(
            rsi_current=round(current_rsi, 1),
            rsi_zone=zone,
            divergence_detected=divergence,
            multi_tf_exhaustion=multi_tf_exhaustion,
            confidence_adjustment=adjustment,
            details=details
        )

    except Exception as e:
        logger.error(f"RSI analysis error: {e}")
        return None


def _determine_zone(rsi, overbought, oversold, optimal_long, optimal_short):
    """Определить RSI зону"""
    if rsi > overbought:
        return 'OVERBOUGHT'
    elif rsi < oversold:
        return 'OVERSOLD'
    elif optimal_long[0] <= rsi <= optimal_long[1]:
        return 'OPTIMAL_LONG'
    elif optimal_short[0] <= rsi <= optimal_short[1]:
        return 'OPTIMAL_SHORT'
    else:
        return 'NEUTRAL'


def _check_divergence(prices, rsi, lookback=10):
    """
    Упрощённая проверка дивергенции
    Bullish divergence: цена падает, RSI растёт
    Bearish divergence: цена растёт, RSI падает
    """
    if len(prices) < lookback or len(rsi) < lookback:
        return False

    try:
        price_trend = prices[-1] - prices[-lookback]
        rsi_trend = rsi[-1] - rsi[-lookback]

        # Bullish divergence
        if price_trend < 0 and rsi_trend > 0:
            return True

        # Bearish divergence
        if price_trend > 0 and rsi_trend < 0:
            return True

        return False

    except:
        return False


def _calculate_adjustment(rsi, zone, divergence, overbought, oversold):
    """Рассчитать корректировку confidence"""
    adjustment = 0

    # Optimal zones
    if zone == 'OPTIMAL_LONG':
        adjustment += 8
    elif zone == 'OPTIMAL_SHORT':
        adjustment += 8

    # Extreme zones
    if rsi > overbought + 10:  # >80
        adjustment -= 15
    elif rsi < oversold - 10:  # <20
        adjustment -= 15
    elif rsi > overbought:  # 70-80
        adjustment -= 8
    elif rsi < oversold:  # 20-30
        adjustment -= 8

    # Divergence bonus
    if divergence:
        adjustment += 10

    return adjustment


def _build_rsi_details(rsi, zone, divergence, adjustment):
    """Построить текстовое описание"""
    parts = [f"RSI: {rsi:.1f}", f"Zone: {zone}"]

    if divergence:
        parts.append("Divergence detected")

    if adjustment != 0:
        parts.append(f"Adjustment: {adjustment:+d}")

    return '; '.join(parts)