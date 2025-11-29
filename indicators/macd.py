"""
MACD Indicator
Файл: indicators/macd.py

Moving Average Convergence Divergence calculation and analysis
"""

import numpy as np
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class MACDData:
    """
    Raw MACD calculation data

    Attributes:
        line: MACD line (EMA12 - EMA26)
        signal: Signal line (EMA9 of MACD line)
        histogram: MACD histogram (line - signal)
    """
    line: np.ndarray
    signal: np.ndarray
    histogram: np.ndarray


@dataclass
class MACDAnalysis:
    """
    Результат анализа MACD

    Attributes:
        histogram_current: Текущее значение histogram
        trend: 'BULLISH' | 'BEARISH' | 'NEUTRAL'
        crossover_recent: Был ли недавний crossover
        divergence_detected: Обнаружена ли дивергенция
        confidence_adjustment: Корректировка confidence (-12 до +10)
        details: Текстовое описание
    """
    histogram_current: float
    trend: str
    crossover_recent: bool
    divergence_detected: bool
    confidence_adjustment: int
    details: str


def calculate_macd(
        prices: np.ndarray,
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
) -> MACDData:
    """
    Рассчитать MACD (Moving Average Convergence Divergence)

    Args:
        prices: Массив цен закрытия
        fast: Период быстрой EMA (default 12)
        slow: Период медленной EMA (default 26)
        signal: Период signal line (default 9)

    Returns:
        MACDData с line, signal, histogram
    """
    zero_array = np.zeros_like(prices)

    if len(prices) < max(fast, slow):
        return MACDData(
            line=zero_array,
            signal=zero_array,
            histogram=zero_array
        )

    try:
        from .ema import calculate_ema

        ema_fast = calculate_ema(prices, fast)
        ema_slow = calculate_ema(prices, slow)

        macd_line = ema_fast - ema_slow
        signal_line = calculate_ema(macd_line, signal)
        histogram = macd_line - signal_line

        return MACDData(
            line=macd_line,
            signal=signal_line,
            histogram=histogram
        )

    except Exception as e:
        logger.error(f"MACD calculation error: {e}")
        return MACDData(
            line=zero_array,
            signal=zero_array,
            histogram=zero_array
        )


def analyze_macd(
        candles,  # NormalizedCandles
        fast: int = 12,
        slow: int = 26,
        signal: int = 9
) -> Optional[MACDAnalysis]:
    """
    Анализ MACD для определения трендов и crossovers

    Args:
        candles: NormalizedCandles объект
        fast: Период быстрой EMA
        slow: Период медленной EMA
        signal: Период signal line

    Returns:
        MACDAnalysis объект или None при ошибке
    """
    if not candles or not candles.is_valid:
        return None

    if len(candles.closes) < max(fast, slow) + 10:
        return None

    try:
        macd_data = calculate_macd(candles.closes, fast, slow, signal)

        current_histogram = float(macd_data.histogram[-1])

        # Определяем тренд
        trend = _determine_macd_trend(macd_data.histogram)

        # Проверка недавнего crossover
        crossover_recent = _check_macd_crossover(macd_data.line, macd_data.signal)

        # Проверка дивергенции (упрощённая)
        divergence = _check_macd_divergence(candles.closes, macd_data.histogram)

        # Корректировка confidence
        adjustment = _calculate_macd_adjustment(
            current_histogram, trend, crossover_recent, divergence
        )

        # Детали
        details = _build_macd_details(
            current_histogram, trend, crossover_recent, divergence, adjustment
        )

        return MACDAnalysis(
            histogram_current=round(current_histogram, 4),
            trend=trend,
            crossover_recent=crossover_recent,
            divergence_detected=divergence,
            confidence_adjustment=adjustment,
            details=details
        )

    except Exception as e:
        logger.error(f"MACD analysis error: {e}")
        return None


def _determine_macd_trend(histogram: np.ndarray, lookback: int = 5) -> str:
    """Определить тренд по MACD histogram"""
    if len(histogram) < lookback:
        return 'NEUTRAL'

    try:
        recent = histogram[-lookback:]

        # Все положительные и растут
        if np.all(recent > 0) and recent[-1] > recent[0]:
            return 'BULLISH'

        # Все отрицательные и падают
        if np.all(recent < 0) and recent[-1] < recent[0]:
            return 'BEARISH'

        return 'NEUTRAL'

    except:
        return 'NEUTRAL'


def _check_macd_crossover(line: np.ndarray, signal: np.ndarray, lookback: int = 5) -> bool:
    """Проверка недавнего MACD crossover"""
    if len(line) < lookback or len(signal) < lookback:
        return False

    try:
        for i in range(1, lookback + 1):
            idx = -i

            # Bullish crossover: line пересекает signal вверх
            if line[idx] > signal[idx] and line[idx - 1] <= signal[idx - 1]:
                return True

            # Bearish crossover: line пересекает signal вниз
            if line[idx] < signal[idx] and line[idx - 1] >= signal[idx - 1]:
                return True

        return False

    except:
        return False


def _check_macd_divergence(prices: np.ndarray, histogram: np.ndarray, lookback: int = 10) -> bool:
    """
    Упрощённая проверка MACD дивергенции
    Bullish: цена падает, histogram растёт
    Bearish: цена растёт, histogram падает
    """
    if len(prices) < lookback or len(histogram) < lookback:
        return False

    try:
        price_trend = prices[-1] - prices[-lookback]
        histogram_trend = histogram[-1] - histogram[-lookback]

        # Bullish divergence
        if price_trend < 0 and histogram_trend > 0:
            return True

        # Bearish divergence
        if price_trend > 0 and histogram_trend < 0:
            return True

        return False

    except:
        return False


def _calculate_macd_adjustment(
        histogram: float,
        trend: str,
        crossover: bool,
        divergence: bool
) -> int:
    """Рассчитать корректировку confidence"""
    adjustment = 0

    # Сильный тренд
    if trend == 'BULLISH':
        adjustment += 8
    elif trend == 'BEARISH':
        adjustment += 8

    # Недавний crossover
    if crossover:
        adjustment += 10

    # Дивергенция (предупреждающий сигнал)
    if divergence:
        adjustment -= 12

    # Слабый histogram
    if abs(histogram) < 0.001:
        adjustment -= 8

    return adjustment


def _build_macd_details(
        histogram: float,
        trend: str,
        crossover: bool,
        divergence: bool,
        adjustment: int
) -> str:
    """Построить текстовое описание"""
    parts = [f"Histogram: {histogram:.4f}", f"Trend: {trend}"]

    if crossover:
        parts.append("Recent crossover")

    if divergence:
        parts.append("Divergence detected")

    if adjustment != 0:
        parts.append(f"Adjustment: {adjustment:+d}")

    return '; '.join(parts)