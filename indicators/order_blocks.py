"""
Order Blocks Indicator - FULL IMPLEMENTATION
Файл: indicators/order_blocks.py

✅ ПОЛНАЯ РЕАЛИЗАЦИЯ алгоритма Smart Money Order Blocks
"""

import numpy as np
import logging
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class OrderBlockData:
    """Данные Order Block"""
    price_low: float
    price_high: float
    candle_index: int
    direction: str  # 'BULLISH' | 'BEARISH'
    strength: float  # 0-100
    is_mitigated: bool
    distance_from_current: float


@dataclass
class OrderBlockAnalysis:
    """Результат анализа Order Blocks"""
    nearest_ob: Optional[OrderBlockData]
    total_blocks_found: int
    bullish_blocks: int
    bearish_blocks: int
    confidence_adjustment: int
    details: str


def find_order_blocks(
        candles,
        lookback: int = 50,
        min_impulse_pct: float = 2.0,
        min_imbalance_bars: int = 2
) -> List[OrderBlockData]:
    """
    ✅ ПОЛНАЯ РЕАЛИЗАЦИЯ: Найти Order Blocks на графике

    Алгоритм:
    1. Найти Swing Highs/Lows (локальные экстремумы)
    2. Детектировать импульсные движения от swing points
    3. Определить последнюю противоположную свечу перед импульсом = OB
    """
    if not candles or not candles.is_valid:
        return []

    if len(candles.closes) < lookback:
        return []

    try:
        order_blocks = []

        # Берём последние lookback свечей
        recent_highs = candles.highs[-lookback:]
        recent_lows = candles.lows[-lookback:]
        recent_closes = candles.closes[-lookback:]
        recent_opens = candles.opens[-lookback:]

        current_price = float(candles.closes[-1])

        # ============================================================
        # ШАГ 1: Найти Swing Highs и Swing Lows
        # ============================================================
        swing_highs = _find_swing_points(recent_highs, 'high', window=3)
        swing_lows = _find_swing_points(recent_lows, 'low', window=3)

        logger.debug(
            f"Found {len(swing_highs)} swing highs, "
            f"{len(swing_lows)} swing lows"
        )

        # ============================================================
        # ШАГ 2: Поиск БЫЧЬИХ Order Blocks (перед движением вверх)
        # ============================================================
        for low_idx in swing_lows:
            # Проверяем есть ли импульс ВВЕРХ после этого swing low
            impulse_detected, impulse_strength = _detect_impulse(
                recent_closes,
                recent_highs,
                low_idx,
                'BULLISH',
                min_impulse_pct,
                min_imbalance_bars
            )

            if impulse_detected:
                # Order Block = последняя DOWN-свеча перед импульсом
                ob_idx = _find_ob_candle(
                    recent_opens,
                    recent_closes,
                    low_idx,
                    'BULLISH'
                )

                if ob_idx is not None and 0 <= ob_idx < len(recent_lows):
                    ob_low = float(recent_lows[ob_idx])
                    ob_high = float(recent_highs[ob_idx])

                    # Проверяем не был ли уже протестирован ценой
                    is_mitigated = _check_mitigation(
                        recent_lows,
                        recent_highs,
                        ob_idx,
                        ob_low,
                        ob_high,
                        'BULLISH'
                    )

                    distance = abs((current_price - ob_high) / current_price * 100)

                    order_blocks.append(OrderBlockData(
                        price_low=ob_low,
                        price_high=ob_high,
                        candle_index=ob_idx,
                        direction='BULLISH',
                        strength=impulse_strength,
                        is_mitigated=is_mitigated,
                        distance_from_current=round(distance, 2)
                    ))

        # ============================================================
        # ШАГ 3: Поиск МЕДВЕЖЬИХ Order Blocks (перед движением вниз)
        # ============================================================
        for high_idx in swing_highs:
            impulse_detected, impulse_strength = _detect_impulse(
                recent_closes,
                recent_lows,
                high_idx,
                'BEARISH',
                min_impulse_pct,
                min_imbalance_bars
            )

            if impulse_detected:
                ob_idx = _find_ob_candle(
                    recent_opens,
                    recent_closes,
                    high_idx,
                    'BEARISH'
                )

                if ob_idx is not None and 0 <= ob_idx < len(recent_lows):
                    ob_low = float(recent_lows[ob_idx])
                    ob_high = float(recent_highs[ob_idx])

                    is_mitigated = _check_mitigation(
                        recent_lows,
                        recent_highs,
                        ob_idx,
                        ob_low,
                        ob_high,
                        'BEARISH'
                    )

                    distance = abs((current_price - ob_low) / current_price * 100)

                    order_blocks.append(OrderBlockData(
                        price_low=ob_low,
                        price_high=ob_high,
                        candle_index=ob_idx,
                        direction='BEARISH',
                        strength=impulse_strength,
                        is_mitigated=is_mitigated,
                        distance_from_current=round(distance, 2)
                    ))

        # Сортируем по proximity к текущей цене
        order_blocks.sort(key=lambda x: x.distance_from_current)

        logger.debug(f"Found {len(order_blocks)} total order blocks")
        return order_blocks

    except Exception as e:
        logger.error(f"Order Blocks detection error: {e}")
        return []


def _find_swing_points(
        prices: np.ndarray,
        point_type: str,
        window: int = 3
) -> List[int]:
    """
    Найти swing highs или swing lows

    Swing High = локальный максимум (выше всех соседей в окне)
    Swing Low = локальный минимум (ниже всех соседей в окне)
    """
    swings = []

    for i in range(window, len(prices) - window):
        if point_type == 'high':
            # Swing High: выше всех слева и справа
            left_condition = all(
                prices[i] >= prices[i - j] for j in range(1, window + 1)
            )
            right_condition = all(
                prices[i] >= prices[i + j] for j in range(1, window + 1)
            )

            if left_condition and right_condition:
                swings.append(i)

        else:  # 'low'
            # Swing Low: ниже всех слева и справа
            left_condition = all(
                prices[i] <= prices[i - j] for j in range(1, window + 1)
            )
            right_condition = all(
                prices[i] <= prices[i + j] for j in range(1, window + 1)
            )

            if left_condition and right_condition:
                swings.append(i)

    return swings


def _detect_impulse(
        closes: np.ndarray,
        extremes: np.ndarray,  # highs для BULLISH, lows для BEARISH
        start_idx: int,
        direction: str,
        min_pct: float,
        min_bars: int
) -> tuple[bool, float]:
    """
    Детекция импульсного движения

    Критерии импульса:
    - Движение >= min_pct за min_bars свечей
    - Минимум 70% свечей движутся в направлении тренда
    """
    if start_idx + min_bars >= len(closes):
        return False, 0.0

    try:
        start_price = float(closes[start_idx])

        # Проверяем следующие min_bars свечей
        window = extremes[start_idx:start_idx + min_bars + 1]

        if direction == 'BULLISH':
            max_price = float(np.max(window))
            move_pct = ((max_price - start_price) / start_price) * 100

            # Проверка чистоты движения
            has_clean_move = _check_clean_impulse(
                closes[start_idx:start_idx + min_bars + 1],
                'BULLISH'
            )

        else:  # BEARISH
            min_price = float(np.min(window))
            move_pct = ((start_price - min_price) / start_price) * 100

            has_clean_move = _check_clean_impulse(
                closes[start_idx:start_idx + min_bars + 1],
                'BEARISH'
            )

        # Импульс подтверждён если движение >= min_pct и чистое
        if move_pct >= min_pct and has_clean_move:
            # Strength зависит от размера движения
            strength = min(100, (move_pct / min_pct) * 50)
            return True, strength

        return False, 0.0

    except Exception as e:
        logger.debug(f"Impulse detection error: {e}")
        return False, 0.0


def _check_clean_impulse(closes: np.ndarray, direction: str) -> bool:
    """
    Проверка что импульс чистый (минимальные откаты)

    Требование: минимум 70% свечей движутся в направлении тренда
    """
    if len(closes) < 3:
        return False

    try:
        if direction == 'BULLISH':
            bullish_candles = sum(
                1 for i in range(1, len(closes)) if closes[i] > closes[i - 1]
            )
            ratio = bullish_candles / (len(closes) - 1)
        else:  # BEARISH
            bearish_candles = sum(
                1 for i in range(1, len(closes)) if closes[i] < closes[i - 1]
            )
            ratio = bearish_candles / (len(closes) - 1)

        return ratio >= 0.7

    except Exception:
        return False


def _find_ob_candle(
        opens: np.ndarray,
        closes: np.ndarray,
        impulse_start: int,
        direction: str
) -> Optional[int]:
    """
    Найти последнюю свечу перед импульсом (Order Block свеча)

    Для BULLISH: последняя DOWN-свеча (close < open)
    Для BEARISH: последняя UP-свеча (close > open)
    """
    if impulse_start < 1:
        return None

    try:
        # Ищем назад от точки импульса (максимум 5 свечей)
        for i in range(impulse_start, max(0, impulse_start - 5), -1):
            if direction == 'BULLISH':
                # Последняя down-свеча
                if closes[i] < opens[i]:
                    return i
            else:  # BEARISH
                # Последняя up-свеча
                if closes[i] > opens[i]:
                    return i

        # Если не нашли, возвращаем свечу перед импульсом
        return impulse_start - 1

    except Exception:
        return None


def _check_mitigation(
        lows: np.ndarray,
        highs: np.ndarray,
        ob_idx: int,
        ob_low: float,
        ob_high: float,
        direction: str
) -> bool:
    """
    Проверка был ли Order Block протестирован (mitigated)

    Mitigation = цена вернулась в зону OB
    """
    if ob_idx >= len(lows) - 1:
        return False

    try:
        # Проверяем свечи ПОСЛЕ Order Block
        for i in range(ob_idx + 1, len(lows)):
            if direction == 'BULLISH':
                # Цена вернулась в зону OB? (1% tolerance)
                if lows[i] <= ob_high * 1.01:
                    return True
            else:  # BEARISH
                # Цена вернулась в зону OB?
                if highs[i] >= ob_low * 0.99:
                    return True

        return False

    except Exception:
        return False


def analyze_order_blocks(
        candles,
        current_price: float,
        signal_direction: str,
        lookback: int = 50
) -> Optional[OrderBlockAnalysis]:
    """
    Анализ Order Blocks относительно текущей цены и направления сигнала
    """
    if not candles or current_price == 0:
        return None

    try:
        # Находим все Order Blocks
        all_blocks = find_order_blocks(candles, lookback)

        if not all_blocks:
            return OrderBlockAnalysis(
                nearest_ob=None,
                total_blocks_found=0,
                bullish_blocks=0,
                bearish_blocks=0,
                confidence_adjustment=0,
                details='No order blocks found'
            )

        # Фильтруем по направлению
        if signal_direction == 'LONG':
            relevant_blocks = [
                ob for ob in all_blocks
                if ob.direction == 'BULLISH' and ob.price_high < current_price
            ]
        else:  # SHORT
            relevant_blocks = [
                ob for ob in all_blocks
                if ob.direction == 'BEARISH' and ob.price_low > current_price
            ]

        # Находим ближайший релевантный блок (fresh приоритетнее)
        nearest_ob = None
        if relevant_blocks:
            unmitigated = [ob for ob in relevant_blocks if not ob.is_mitigated]

            if unmitigated:
                nearest_ob = unmitigated[0]
            else:
                nearest_ob = relevant_blocks[0]

        # Рассчитываем confidence adjustment
        adjustment = _calculate_ob_adjustment(nearest_ob, signal_direction)

        # Статистика
        bullish_count = sum(1 for ob in all_blocks if ob.direction == 'BULLISH')
        bearish_count = sum(1 for ob in all_blocks if ob.direction == 'BEARISH')

        # Детали
        if nearest_ob:
            distance_pct = nearest_ob.distance_from_current
            mitigation_status = "mitigated" if nearest_ob.is_mitigated else "fresh"

            details = (
                f"Nearest {nearest_ob.direction} OB at "
                f"${nearest_ob.price_low:.4f}-${nearest_ob.price_high:.4f} "
                f"({distance_pct:.1f}% away, {mitigation_status}, "
                f"strength: {nearest_ob.strength:.0f})"
            )
        else:
            details = f"No relevant {signal_direction} order blocks nearby"

        return OrderBlockAnalysis(
            nearest_ob=nearest_ob,
            total_blocks_found=len(all_blocks),
            bullish_blocks=bullish_count,
            bearish_blocks=bearish_count,
            confidence_adjustment=adjustment,
            details=details
        )

    except Exception as e:
        logger.error(f"Order Blocks analysis error: {e}")
        return None


def _calculate_ob_adjustment(
        nearest_ob: Optional[OrderBlockData],
        signal_direction: str
) -> int:
    """Рассчитать корректировку confidence на основе Order Block"""
    if not nearest_ob:
        return 0

    try:
        adjustment = 0

        # Базовый бонус за наличие OB
        adjustment += 8

        # Бонус за силу OB
        if nearest_ob.strength >= 70:
            adjustment += 5

        # Бонус за fresh (непротестированный) OB
        if not nearest_ob.is_mitigated:
            adjustment += 10

        # Penalty за большую дистанцию
        if nearest_ob.distance_from_current > 5.0:
            adjustment -= 8
        elif nearest_ob.distance_from_current < 1.0:
            # Очень близко - сильный уровень
            adjustment += 5

        return adjustment

    except Exception:
        return 0