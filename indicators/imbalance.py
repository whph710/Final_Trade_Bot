"""
Imbalance (Fair Value Gap) Indicator
Файл: indicators/imbalance.py

Детекция Fair Value Gaps (имбалансы) - зоны где не было торговли
"""

import numpy as np
import logging
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ImbalanceData:
    """
    Fair Value Gap (имбаланс)

    Attributes:
        gap_low: Нижняя граница gap
        gap_high: Верхняя граница gap
        candle_index: Индекс центральной свечи
        direction: 'BULLISH' | 'BEARISH'
        is_filled: Был ли заполнен ценой
        fill_percentage: Процент заполнения (0-100)
        distance_from_current: Расстояние от текущей цены в %
    """
    gap_low: float
    gap_high: float
    candle_index: int
    direction: str
    is_filled: bool
    fill_percentage: float
    distance_from_current: float


@dataclass
class ImbalanceAnalysis:
    """Результат анализа Imbalances"""
    nearest_imbalance: Optional[ImbalanceData]
    total_imbalances: int
    unfilled_count: int
    bullish_count: int
    bearish_count: int
    confidence_adjustment: int
    details: str


def find_imbalances(
        candles,  # NormalizedCandles
        lookback: int = 50,
        min_gap_size_pct: float = 0.1
) -> List[ImbalanceData]:
    """
    Найти Fair Value Gaps (имбалансы)

    Логика:
    Имбаланс = зона, где НЕ было торговли (gap между свечами)

    Bullish FVG:
    - Candle[i-1].high < Candle[i+1].low
    - Цена прыгнула вверх, оставив gap

    Bearish FVG:
    - Candle[i-1].low > Candle[i+1].high
    - Цена прыгнула вниз, оставив gap

    Args:
        candles: NormalizedCandles объект
        lookback: Количество свечей для анализа
        min_gap_size_pct: Минимальный размер gap в %

    Returns:
        Список незаполненных и частично заполненных имбалансов
    """
    if not candles or not candles.is_valid:
        return []

    if len(candles.closes) < lookback + 2:
        return []

    try:
        imbalances = []

        # Анализируем последние lookback свечей
        start_idx = max(0, len(candles.closes) - lookback)

        highs = candles.highs[start_idx:]
        lows = candles.lows[start_idx:]
        current_price = float(candles.closes[-1])

        # Ищем gap паттерны (нужно минимум 3 свечи)
        for i in range(1, len(highs) - 1):
            # Bullish FVG: gap между prev.high и next.low
            prev_high = float(highs[i - 1])
            next_low = float(lows[i + 1])

            if prev_high < next_low:
                gap_size_pct = ((next_low - prev_high) / prev_high) * 100

                if gap_size_pct >= min_gap_size_pct:
                    # Проверяем был ли заполнен
                    fill_pct, is_filled = _check_gap_fill(
                        lows[i + 1:],
                        highs[i + 1:],
                        prev_high,
                        next_low,
                        'BULLISH'
                    )

                    distance = abs((current_price - next_low) / current_price * 100)

                    imbalances.append(ImbalanceData(
                        gap_low=prev_high,
                        gap_high=next_low,
                        candle_index=start_idx + i,
                        direction='BULLISH',
                        is_filled=is_filled,
                        fill_percentage=fill_pct,
                        distance_from_current=round(distance, 2)
                    ))

            # Bearish FVG: gap между prev.low и next.high
            prev_low = float(lows[i - 1])
            next_high = float(highs[i + 1])

            if prev_low > next_high:
                gap_size_pct = ((prev_low - next_high) / next_high) * 100

                if gap_size_pct >= min_gap_size_pct:
                    fill_pct, is_filled = _check_gap_fill(
                        lows[i + 1:],
                        highs[i + 1:],
                        next_high,
                        prev_low,
                        'BEARISH'
                    )

                    distance = abs((current_price - prev_low) / current_price * 100)

                    imbalances.append(ImbalanceData(
                        gap_low=next_high,
                        gap_high=prev_low,
                        candle_index=start_idx + i,
                        direction='BEARISH',
                        is_filled=is_filled,
                        fill_percentage=fill_pct,
                        distance_from_current=round(distance, 2)
                    ))

        # Сортируем по proximity
        imbalances.sort(key=lambda x: x.distance_from_current)

        logger.debug(f"Found {len(imbalances)} imbalances")
        return imbalances

    except Exception as e:
        logger.error(f"Imbalance detection error: {e}")
        return []


def analyze_imbalances(
        candles,  # NormalizedCandles
        current_price: float,
        signal_direction: str,
        lookback: int = 50
) -> Optional[ImbalanceAnalysis]:
    """
    Анализ Imbalances относительно текущей цены

    Args:
        candles: NormalizedCandles объект
        current_price: Текущая цена
        signal_direction: 'LONG' | 'SHORT'
        lookback: Период анализа

    Returns:
        ImbalanceAnalysis или None
    """
    if not candles or current_price == 0:
        return None

    try:
        # Находим все имбалансы
        all_imbalances = find_imbalances(candles, lookback)

        if not all_imbalances:
            return ImbalanceAnalysis(
                nearest_imbalance=None,
                total_imbalances=0,
                unfilled_count=0,
                bullish_count=0,
                bearish_count=0,
                confidence_adjustment=0,
                details='No imbalances found'
            )

        # Фильтруем релевантные для направления сигнала
        if signal_direction == 'LONG':
            # Для LONG интересны бычьи имбалансы ниже текущей цены
            relevant = [
                imb for imb in all_imbalances
                if imb.direction == 'BULLISH' and imb.gap_high < current_price
            ]
        else:  # SHORT
            # Для SHORT интересны медвежьи имбалансы выше текущей цены
            relevant = [
                imb for imb in all_imbalances
                if imb.direction == 'BEARISH' and imb.gap_low > current_price
            ]

        # Находим ближайший незаполненный или частично заполненный
        nearest = None
        if relevant:
            # Приоритет незаполненным
            unfilled = [imb for imb in relevant if not imb.is_filled]

            if unfilled:
                nearest = unfilled[0]
            else:
                # Если все заполнены, берём ближайший
                nearest = relevant[0]

        # Рассчитываем adjustment
        adjustment = _calculate_imbalance_adjustment(
            nearest,
            signal_direction
        )

        # Статистика
        unfilled_count = sum(1 for imb in all_imbalances if not imb.is_filled)
        bullish_count = sum(1 for imb in all_imbalances if imb.direction == 'BULLISH')
        bearish_count = sum(1 for imb in all_imbalances if imb.direction == 'BEARISH')

        # Детали
        if nearest:
            fill_status = f"{nearest.fill_percentage:.0f}% filled" if nearest.is_filled else "unfilled"

            details = (
                f"Nearest {nearest.direction} FVG at "
                f"${nearest.gap_low:.4f}-${nearest.gap_high:.4f} "
                f"({nearest.distance_from_current:.1f}% away, {fill_status})"
            )
        else:
            details = f"No relevant {signal_direction} imbalances nearby"

        return ImbalanceAnalysis(
            nearest_imbalance=nearest,
            total_imbalances=len(all_imbalances),
            unfilled_count=unfilled_count,
            bullish_count=bullish_count,
            bearish_count=bearish_count,
            confidence_adjustment=adjustment,
            details=details
        )

    except Exception as e:
        logger.error(f"Imbalance analysis error: {e}")
        return None


def _check_gap_fill(
        lows: np.ndarray,
        highs: np.ndarray,
        gap_low: float,
        gap_high: float,
        direction: str
) -> tuple[float, bool]:
    """
    Проверить был ли gap заполнен

    Returns:
        (fill_percentage, is_filled)
    """
    if len(lows) == 0:
        return 0.0, False

    try:
        gap_size = gap_high - gap_low
        if gap_size <= 0:
            return 0.0, False

        max_fill = 0.0

        for i in range(len(lows)):
            low = float(lows[i])
            high = float(highs[i])

            if direction == 'BULLISH':
                # Для бычьего gap проверяем вернулась ли цена вниз
                if low <= gap_high:
                    # Рассчитываем сколько заполнено
                    fill_level = min(gap_high, low)
                    filled = ((gap_high - fill_level) / gap_size) * 100
                    max_fill = max(max_fill, filled)

                    # Считается заполненным если >50%
                    if filled > 50:
                        return round(filled, 1), True

            else:  # BEARISH
                # Для медвежьего gap проверяем вернулась ли цена вверх
                if high >= gap_low:
                    fill_level = max(gap_low, high)
                    filled = ((fill_level - gap_low) / gap_size) * 100
                    max_fill = max(max_fill, filled)

                    if filled > 50:
                        return round(filled, 1), True

        return round(max_fill, 1), False

    except Exception:
        return 0.0, False


def _calculate_imbalance_adjustment(
        nearest: Optional[ImbalanceData],
        signal_direction: str
) -> int:
    """Рассчитать корректировку confidence на основе imbalance"""
    if not nearest:
        return 0

    try:
        adjustment = 0

        # Базовый бонус за наличие imbalance
        adjustment += 5

        # Бонус за незаполненный imbalance
        if not nearest.is_filled:
            adjustment += 8
        elif nearest.fill_percentage < 30:
            # Частично заполнен
            adjustment += 5

        # Penalty за большую дистанцию
        if nearest.distance_from_current > 5.0:
            adjustment -= 5
        elif nearest.distance_from_current < 1.0:
            # Очень близко
            adjustment += 5

        return adjustment

    except Exception:
        return 0