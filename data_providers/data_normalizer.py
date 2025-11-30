"""
Data Normalizer - IMPROVED LOGGING
Файл: data_providers/data_normalizer.py

ИСПРАВЛЕНИЯ:
- Добавлено детальное логирование причин невалидности
"""

import numpy as np
import logging
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class NormalizedCandles:
    """
    Единый формат свечей для всех индикаторов

    Attributes:
        timestamps: Unix timestamps в миллисекундах
        opens: Цены открытия
        highs: Максимумы
        lows: Минимумы
        closes: Цены закрытия
        volumes: Объёмы торгов
        is_valid: Прошла ли валидация
        symbol: Торговая пара
        interval: Таймфрейм
    """
    timestamps: np.ndarray
    opens: np.ndarray
    highs: np.ndarray
    lows: np.ndarray
    closes: np.ndarray
    volumes: np.ndarray
    is_valid: bool
    symbol: str
    interval: str


def normalize_candles(
        raw_candles: List[List],
        symbol: str = "UNKNOWN",
        interval: str = "UNKNOWN",
        min_length: int = 10
) -> Optional[NormalizedCandles]:
    """
    Нормализовать raw свечи Bybit в единый формат

    Args:
        raw_candles: Raw данные от Bybit [timestamp, open, high, low, close, volume, turnover]
        symbol: Название пары
        interval: Таймфрейм
        min_length: Минимальное количество свечей

    Returns:
        NormalizedCandles объект или None при ошибке
    """
    if not raw_candles:
        logger.debug(f"normalize_candles: {symbol} {interval} - No raw candles provided")
        return None

    if len(raw_candles) < min_length:
        logger.debug(
            f"normalize_candles: {symbol} {interval} - "
            f"Insufficient candles: {len(raw_candles)} < {min_length}"
        )
        return None

    try:
        # Извлекаем данные
        timestamps = np.array([int(candle[0]) for candle in raw_candles], dtype=np.int64)
        opens = np.array([float(candle[1]) for candle in raw_candles], dtype=np.float64)
        highs = np.array([float(candle[2]) for candle in raw_candles], dtype=np.float64)
        lows = np.array([float(candle[3]) for candle in raw_candles], dtype=np.float64)
        closes = np.array([float(candle[4]) for candle in raw_candles], dtype=np.float64)
        volumes = np.array([float(candle[5]) for candle in raw_candles], dtype=np.float64)

        # Валидация
        is_valid = _validate_candles_data(
            timestamps, opens, highs, lows, closes, volumes, symbol, interval
        )

        return NormalizedCandles(
            timestamps=timestamps,
            opens=opens,
            highs=highs,
            lows=lows,
            closes=closes,
            volumes=volumes,
            is_valid=is_valid,
            symbol=symbol,
            interval=interval
        )

    except (ValueError, IndexError, TypeError) as e:
        logger.warning(f"normalize_candles: {symbol} {interval} - Error: {e}")
        return None


def _validate_candles_data(
        timestamps: np.ndarray,
        opens: np.ndarray,
        highs: np.ndarray,
        lows: np.ndarray,
        closes: np.ndarray,
        volumes: np.ndarray,
        symbol: str,
        interval: str
) -> bool:
    """
    Валидация нормализованных данных

    ИСПРАВЛЕНО: Детальное логирование причин невалидности

    Returns:
        True если данные корректны, False иначе
    """
    try:
        # Проверка 1: Все массивы одинаковой длины
        lengths = [len(timestamps), len(opens), len(highs), len(lows), len(closes), len(volumes)]
        if len(set(lengths)) != 1:
            logger.warning(
                f"validate: {symbol} {interval} - "
                f"Mismatched array lengths: {lengths}"
            )
            return False

        # Проверка 2: Нет NaN или Inf
        arrays = [opens, highs, lows, closes, volumes]
        for idx, arr in enumerate(arrays):
            if np.any(np.isnan(arr)):
                logger.warning(
                    f"validate: {symbol} {interval} - "
                    f"NaN detected in array {idx}"
                )
                return False
            if np.any(np.isinf(arr)):
                logger.warning(
                    f"validate: {symbol} {interval} - "
                    f"Inf detected in array {idx}"
                )
                return False

        # Проверка 3: Все цены положительные
        if np.any(opens <= 0):
            logger.warning(f"validate: {symbol} {interval} - Non-positive opens")
            return False
        if np.any(highs <= 0):
            logger.warning(f"validate: {symbol} {interval} - Non-positive highs")
            return False
        if np.any(lows <= 0):
            logger.warning(f"validate: {symbol} {interval} - Non-positive lows")
            return False
        if np.any(closes <= 0):
            logger.warning(f"validate: {symbol} {interval} - Non-positive closes")
            return False

        # Проверка 4: High >= max(Open, Close), Low <= min(Open, Close)
        for i in range(len(opens)):
            max_price = max(opens[i], closes[i])
            min_price = min(opens[i], closes[i])

            if highs[i] < max_price:
                logger.warning(
                    f"validate: {symbol} {interval} - "
                    f"Invalid OHLC at index {i}: high < max(open,close)"
                )
                return False

            if lows[i] > min_price:
                logger.warning(
                    f"validate: {symbol} {interval} - "
                    f"Invalid OHLC at index {i}: low > min(open,close)"
                )
                return False

        # Проверка 5: Объёмы неотрицательные
        if np.any(volumes < 0):
            logger.warning(f"validate: {symbol} {interval} - Negative volumes")
            return False

        # Проверка 6: Timestamps растут (свечи в правильном порядке)
        if not np.all(np.diff(timestamps) > 0):
            logger.warning(f"validate: {symbol} {interval} - Non-increasing timestamps")
            return False

        # Всё ОК
        logger.debug(f"validate: {symbol} {interval} - ✓ VALID ({len(timestamps)} candles)")
        return True

    except Exception as e:
        logger.warning(f"validate: {symbol} {interval} - Validation error: {e}")
        return False


def safe_float(value) -> float:
    """
    Безопасное преобразование в float

    Args:
        value: Значение для конвертации

    Returns:
        Float значение или 0.0 при ошибке
    """
    try:
        if isinstance(value, np.ndarray):
            value = value[-1] if len(value) > 0 else 0.0

        if value is None:
            return 0.0

        result = float(value)

        if np.isnan(result) or np.isinf(result):
            return 0.0

        return result

    except (ValueError, TypeError):
        return 0.0