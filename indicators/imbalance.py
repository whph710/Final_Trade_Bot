"""
Imbalance (Fair Value Gap) Indicator - FIXED VERSION
Файл: indicators/imbalance.py

ИСПРАВЛЕНО:
✅ #11: Улучшена логика проверки заполнения FVG (учитывается частичное заполнение с обеих сторон)
"""

import numpy as np
import logging
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ImbalanceData:
    """Fair Value Gap (имбаланс)"""
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
        candles,
        lookback: int = 50,
        min_gap_size_pct: float = 0.1
) -> List[ImbalanceData]:
    """Найти Fair Value Gaps (имбалансы)"""
    if not candles or not candles.is_valid:
        return []

    if len(candles.closes) < lookback + 2:
        return []

    try:
        imbalances = []

        start_idx = max(0, len(candles.closes) - lookback)

        highs = candles.highs[start_idx:]
        lows = candles.lows[start_idx:]
        current_price = float(candles.closes[-1])

        # Ищем gap паттерны (нужно минимум 3 свечи)
        for i in range(1, len(highs) - 1):
            # ============================================================
            # Bullish FVG: gap между prev.high и next.low
            # ============================================================
            prev_high = float(highs[i - 1])
            next_low = float(lows[i + 1])

            if prev_high < next_low:
                gap_size_pct = ((next_low - prev_high) / prev_high) * 100

                if gap_size_pct >= min_gap_size_pct:
                    # ✅ ИСПРАВЛЕНО: Улучшенная проверка заполнения
                    fill_pct, is_filled = _check_gap_fill_improved(
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

            # ============================================================
            # Bearish FVG: gap между prev.low и next.high
            # ============================================================
            prev_low = float(lows[i - 1])
            next_high = float(highs[i + 1])

            if prev_low > next_high:
                gap_size_pct = ((prev_low - next_high) / next_high) * 100

                if gap_size_pct >= min_gap_size_pct:
                    # ✅ ИСПРАВЛЕНО: Улучшенная проверка заполнения
                    fill_pct, is_filled = _check_gap_fill_improved(
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


def _check_gap_fill_improved(
        lows: np.ndarray,
        highs: np.ndarray,
        gap_low: float,
        gap_high: float,
        direction: str
) -> tuple[float, bool]:
    """
    ✅ ИСПРАВЛЕНО: Улучшенная проверка заполнения FVG

    Учитывается:
    - Частичное заполнение с обеих сторон
    - Многократные касания зоны
    - Агрессивное проникновение в зону

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
        total_penetration = 0.0
        touch_count = 0

        for i in range(len(lows)):
            low = float(lows[i])
            high = float(highs[i])

            # ============================================================
            # BULLISH FVG: цена возвращается вниз в зону gap
            # ============================================================
            if direction == 'BULLISH':
                # Проверяем проникла ли цена в зону FVG
                if low < gap_high and high > gap_low:
                    # Цена в зоне FVG
                    touch_count += 1

                    # Рассчитываем насколько глубоко проникла
                    penetration_low = max(gap_low, low)
                    penetration_high = min(gap_high, high)

                    penetration_size = penetration_high - penetration_low

                    if penetration_size > 0:
                        fill_ratio = (penetration_size / gap_size) * 100
                        total_penetration += fill_ratio
                        max_fill = max(max_fill, fill_ratio)

                # Полное заполнение: цена прошла через всю зону
                if low <= gap_low:
                    max_fill = 100.0
                    is_filled = True
                    return round(max_fill, 1), is_filled

            # ============================================================
            # BEARISH FVG: цена возвращается вверх в зону gap
            # ============================================================
            else:
                if high > gap_low and low < gap_high:
                    touch_count += 1

                    penetration_low = max(gap_low, low)
                    penetration_high = min(gap_high, high)

                    penetration_size = penetration_high - penetration_low

                    if penetration_size > 0:
                        fill_ratio = (penetration_size / gap_size) * 100
                        total_penetration += fill_ratio
                        max_fill = max(max_fill, fill_ratio)

                # Полное заполнение
                if high >= gap_high:
                    max_fill = 100.0
                    is_filled = True
                    return round(max_fill, 1), is_filled

        # ============================================================
        # КРИТЕРИЙ ЗАПОЛНЕНИЯ
        # ============================================================
        # Считается заполненным если:
        # 1. Максимальное проникновение > 50%, ИЛИ
        # 2. Суммарное проникновение > 100% (многократные касания), ИЛИ
        # 3. Более 3 касаний зоны

        is_filled = (
            max_fill > 50 or
            total_penetration > 100 or
            touch_count > 3
        )

        # Возвращаем максимальное проникновение как fill_percentage
        return round(max_fill, 1), is_filled

    except Exception as e:
        logger.error(f"Gap fill check error: {e}")
        return 0.0, False


def analyze_imbalances(
        candles,
        current_price: float,
        signal_direction: str,
        lookback: int = 50
) -> Optional[ImbalanceAnalysis]:
    """Анализ Imbalances относительно текущей цены"""
    if not candles or current_price == 0:
        return None

    try:
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
            relevant = [
                imb for imb in all_imbalances
                if imb.direction == 'BULLISH' and imb.gap_high < current_price
            ]
        elif signal_direction == 'SHORT':
            relevant = [
                imb for imb in all_imbalances
                if imb.direction == 'BEARISH' and imb.gap_low > current_price
            ]
        else:
            relevant = all_imbalances

        # Находим ближайший незаполненный или частично заполненный
        nearest = None
        if relevant:
            unfilled = [imb for imb in relevant if not imb.is_filled]

            if unfilled:
                nearest = unfilled[0]
            else:
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
            # Частично заполнен (<30%)
            adjustment += 5
        elif nearest.fill_percentage < 50:
            # Частично заполнен (30-50%)
            adjustment += 3

        # Penalty за большую дистанцию
        if nearest.distance_from_current > 5.0:
            adjustment -= 5
        elif nearest.distance_from_current < 1.0:
            # Очень близко
            adjustment += 5

        return adjustment

    except Exception:
        return 0