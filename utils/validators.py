"""
Data Validators
Файл: utils/validators.py

Валидация данных и базовые проверки
"""

import numpy as np
import logging
from typing import List

logger = logging.getLogger(__name__)


def validate_candles(
        candles: List[List],
        min_length: int = 10
) -> bool:
    """
    Валидация свечных данных

    Args:
        candles: Список свечей [[timestamp, open, high, low, close, volume], ...]
        min_length: Минимальное количество свечей

    Returns:
        True если данные корректны
    """
    if not candles or len(candles) < min_length:
        return False

    try:
        # Проверяем первые 3 свечи
        for candle in candles[:3]:
            if not isinstance(candle, list) or len(candle) < 6:
                return False

            try:
                open_p = float(candle[1])
                high = float(candle[2])
                low = float(candle[3])
                close = float(candle[4])
                volume = float(candle[5])

                # Проверка 1: Цены положительные
                if any(p <= 0 for p in [open_p, high, low, close]):
                    return False

                # Проверка 2: High >= max(Open, Close), Low <= min(Open, Close)
                if high < max(open_p, close) or low > min(open_p, close):
                    return False

                # Проверка 3: Объём неотрицательный
                if volume < 0:
                    return False

            except (ValueError, IndexError):
                return False

        return True

    except Exception as e:
        logger.debug(f"Candle validation error: {e}")
        return False


def safe_float(value, default: float = 0.0) -> float:
    """
    Безопасное преобразование в float

    Args:
        value: Значение для конвертации
        default: Значение по умолчанию

    Returns:
        Float значение или default при ошибке
    """
    try:
        if isinstance(value, np.ndarray):
            value = value[-1] if len(value) > 0 else default

        if value is None:
            return default

        result = float(value)

        if np.isnan(result) or np.isinf(result):
            return default

        return result

    except (ValueError, TypeError):
        return default


def safe_int(value, default: int = 0) -> int:
    """
    Безопасное преобразование в int

    Args:
        value: Значение для конвертации
        default: Значение по умолчанию

    Returns:
        Int значение или default при ошибке
    """
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


def validate_rr_ratio(
        entry_price: float,
        stop_loss: float,
        take_profit: float,
        min_rr: float = 1.5
) -> bool:
    """
    Валидация R/R ratio

    Args:
        entry_price: Цена входа
        stop_loss: Stop loss
        take_profit: Take profit
        min_rr: Минимальный R/R ratio

    Returns:
        True если R/R >= min_rr
    """
    if entry_price == 0 or stop_loss == 0 or take_profit == 0:
        return False

    try:
        risk = abs(entry_price - stop_loss)
        reward = abs(take_profit - entry_price)

        if risk > 0:
            rr_ratio = reward / risk
            return rr_ratio >= min_rr

        return False

    except Exception as e:
        logger.debug(f"R/R validation error: {e}")
        return False


def validate_prices_in_range(
        price: float,
        low: float,
        high: float,
        tolerance_pct: float = 0.1
) -> bool:
    """
    Проверка что цена находится в разумном диапазоне

    Args:
        price: Проверяемая цена
        low: Нижняя граница
        high: Верхняя граница
        tolerance_pct: Допустимое отклонение в процентах

    Returns:
        True если цена в допустимом диапазоне
    """
    if price <= 0 or low <= 0 or high <= 0:
        return False

    try:
        min_price = low * (1 - tolerance_pct / 100)
        max_price = high * (1 + tolerance_pct / 100)

        return min_price <= price <= max_price

    except Exception:
        return False