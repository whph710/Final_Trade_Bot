"""
ATR Indicator (Average True Range)
Файл: indicators/atr.py

ATR calculation and stop-loss suggestions
"""

import numpy as np
import logging

logger = logging.getLogger(__name__)


def calculate_atr(candles, period: int = 14) -> float:
    """
    Рассчитать Average True Range

    Args:
        candles: NormalizedCandles объект
        period: Период ATR (default 14)

    Returns:
        ATR значение (float)
    """
    if not candles or not candles.is_valid:
        return 0.0

    if len(candles.closes) < period + 1:
        return 0.0

    try:
        highs = candles.highs
        lows = candles.lows
        closes = candles.closes

        # Проверка на нулевые значения
        if np.any(highs <= 0) or np.any(lows <= 0) or np.any(closes <= 0):
            return 0.0

        # True Range calculation
        tr = np.zeros(len(candles.closes))

        for i in range(1, len(candles.closes)):
            tr[i] = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1])
            )

        if len(tr) <= period:
            return float(np.mean(tr[1:]))

        # Экспоненциальное сглаживание
        atr = np.mean(tr[1:period + 1])

        for i in range(period + 1, len(candles.closes)):
            atr = (atr * (period - 1) + tr[i]) / period

        return float(atr)

    except Exception as e:
        logger.error(f"ATR calculation error: {e}")
        return 0.0


def suggest_stop_loss(
        entry_price: float,
        atr: float,
        signal_type: str,
        multiplier: float = 2.0
) -> float:
    """
    Предложить stop-loss на основе ATR

    Args:
        entry_price: Цена входа
        atr: ATR значение
        signal_type: 'LONG' или 'SHORT'
        multiplier: Множитель ATR (default 2.0)

    Returns:
        Предложенная цена stop-loss
    """
    if entry_price == 0 or atr == 0:
        return 0.0

    try:
        stop_distance = atr * multiplier

        if signal_type == 'LONG':
            stop_loss = entry_price - stop_distance
        elif signal_type == 'SHORT':
            stop_loss = entry_price + stop_distance
        else:
            return 0.0

        return float(stop_loss)

    except Exception as e:
        logger.error(f"Stop-loss calculation error: {e}")
        return 0.0