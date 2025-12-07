"""
Order Blocks Indicator - FIXED VERSION
Файл: indicators/order_blocks.py

ИСПРАВЛЕНО:
✅ #9: Добавлена проверка Order Block freshness
✅ #15: Time-based фильтр для OB (возраст OB учитывается в scoring)
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
    direction: str
    strength: float
    is_mitigated: bool
    distance_from_current: float
    age_in_candles: int  # ✅ НОВОЕ: Возраст OB


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
        lookback: int = None,
        min_impulse_pct: float = None,
        min_imbalance_bars: int = None,
        max_age_candles: int = None
) -> List[OrderBlockData]:
    """
    ✅ ИСПРАВЛЕНО: Найти Order Blocks с проверкой свежести

    Args:
        lookback: Период поиска (по умолчанию из config)
        min_impulse_pct: Минимальный импульс (по умолчанию из config)
        min_imbalance_bars: Минимум баров для импульса (по умолчанию из config)
        max_age_candles: Максимальный возраст OB в свечах (по умолчанию из config)
    """
    from config import config
    
    if lookback is None:
        lookback = config.OB_LOOKBACK
    if min_impulse_pct is None:
        min_impulse_pct = config.OB_MIN_IMPULSE_PCT
    if min_imbalance_bars is None:
        min_imbalance_bars = config.OB_MIN_IMBALANCE_BARS
    if max_age_candles is None:
        max_age_candles = config.OB_MAX_AGE_CANDLES
    
    if not candles or not candles.is_valid:
        return []

    if len(candles.closes) < lookback:
        return []

    try:
        order_blocks = []

        recent_highs = candles.highs[-lookback:]
        recent_lows = candles.lows[-lookback:]
        recent_closes = candles.closes[-lookback:]
        recent_opens = candles.opens[-lookback:]

        current_price = float(candles.closes[-1])
        current_candle_index = len(candles.closes) - 1

        # Swing points
        swing_highs = _find_swing_points(recent_highs, 'high', window=config.OB_SWING_WINDOW)
        swing_lows = _find_swing_points(recent_lows, 'low', window=config.OB_SWING_WINDOW)

        logger.debug(
            f"Found {len(swing_highs)} swing highs, {len(swing_lows)} swing lows"
        )

        # ============================================================
        # БЫЧЬИ Order Blocks
        # ============================================================
        for low_idx in swing_lows:
            impulse_detected, impulse_strength = _detect_impulse(
                recent_closes,
                recent_highs,
                low_idx,
                'BULLISH',
                min_impulse_pct,
                min_imbalance_bars
            )

            if impulse_detected:
                ob_idx = _find_ob_candle(
                    recent_opens,
                    recent_closes,
                    low_idx,
                    'BULLISH'
                )

                if ob_idx is not None and 0 <= ob_idx < len(recent_lows):
                    ob_low = float(recent_lows[ob_idx])
                    ob_high = float(recent_highs[ob_idx])

                    # ✅ НОВОЕ: Рассчитываем возраст OB
                    absolute_ob_index = len(candles.closes) - lookback + ob_idx
                    age_in_candles = current_candle_index - absolute_ob_index

                    # ✅ НОВОЕ: Пропускаем слишком старые OB
                    if age_in_candles > max_age_candles:
                        logger.debug(
                            f"Skipping old Bullish OB at index {ob_idx} "
                            f"(age: {age_in_candles} candles)"
                        )
                        continue

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
                        distance_from_current=round(distance, 2),
                        age_in_candles=age_in_candles  # ✅ НОВОЕ
                    ))

        # ============================================================
        # МЕДВЕЖЬИ Order Blocks
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

                    # ✅ НОВОЕ: Рассчитываем возраст OB
                    absolute_ob_index = len(candles.closes) - lookback + ob_idx
                    age_in_candles = current_candle_index - absolute_ob_index

                    # ✅ НОВОЕ: Пропускаем слишком старые OB
                    if age_in_candles > max_age_candles:
                        logger.debug(
                            f"Skipping old Bearish OB at index {ob_idx} "
                            f"(age: {age_in_candles} candles)"
                        )
                        continue

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
                        distance_from_current=round(distance, 2),
                        age_in_candles=age_in_candles  # ✅ НОВОЕ
                    ))

        # Сортируем по proximity к текущей цене
        order_blocks.sort(key=lambda x: x.distance_from_current)

        logger.debug(f"Found {len(order_blocks)} total order blocks (age <= {max_age_candles})")
        return order_blocks

    except Exception as e:
        logger.error(f"Order Blocks detection error: {e}")
        return []


def _find_swing_points(
        prices: np.ndarray,
        point_type: str,
        window: int = 3
) -> List[int]:
    """Найти swing highs или swing lows"""
    swings = []

    for i in range(window, len(prices) - window):
        if point_type == 'high':
            left_condition = all(
                prices[i] >= prices[i - j] for j in range(1, window + 1)
            )
            right_condition = all(
                prices[i] >= prices[i + j] for j in range(1, window + 1)
            )

            if left_condition and right_condition:
                swings.append(i)

        else:  # 'low'
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
        extremes: np.ndarray,
        start_idx: int,
        direction: str,
        min_pct: float,
        min_bars: int
) -> tuple[bool, float]:
    """Детекция импульсного движения"""
    if start_idx + min_bars >= len(closes):
        return False, 0.0

    try:
        start_price = float(closes[start_idx])
        window = extremes[start_idx:start_idx + min_bars + 1]

        if direction == 'BULLISH':
            max_price = float(np.max(window))
            move_pct = ((max_price - start_price) / start_price) * 100

            has_clean_move = _check_clean_impulse(
                closes[start_idx:start_idx + min_bars + 1],
                'BULLISH',
                config.OB_CLEAN_IMPULSE_RATIO
            )

        else:  # BEARISH
            min_price = float(np.min(window))
            move_pct = ((start_price - min_price) / start_price) * 100

            has_clean_move = _check_clean_impulse(
                closes[start_idx:start_idx + min_bars + 1],
                'BEARISH',
                config.OB_CLEAN_IMPULSE_RATIO
            )

        if move_pct >= min_pct and has_clean_move:
            strength = min(100, (move_pct / min_pct) * 50)
            return True, strength

        return False, 0.0

    except Exception as e:
        logger.debug(f"Impulse detection error: {e}")
        return False, 0.0


def _check_clean_impulse(closes: np.ndarray, direction: str, min_ratio: float = None) -> bool:
    """Проверка что импульс чистый (минимальные откаты)"""
    from config import config
    
    if min_ratio is None:
        min_ratio = config.OB_CLEAN_IMPULSE_RATIO
    
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

        return ratio >= min_ratio

    except Exception:
        return False


def _find_ob_candle(
        opens: np.ndarray,
        closes: np.ndarray,
        impulse_start: int,
        direction: str
) -> Optional[int]:
    """Найти последнюю свечу перед импульсом (Order Block свеча)"""
    if impulse_start < 1:
        return None

    try:
        for i in range(impulse_start, max(0, impulse_start - 5), -1):
            if direction == 'BULLISH':
                if closes[i] < opens[i]:
                    return i
            else:  # BEARISH
                if closes[i] > opens[i]:
                    return i

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
    """Проверка был ли Order Block протестирован (mitigated)"""
    if ob_idx >= len(lows) - 1:
        return False

    try:
        for i in range(ob_idx + 1, len(lows)):
            from config import config
            
            if direction == 'BULLISH':
                if lows[i] <= ob_high * (1 + config.OB_MITIGATION_TOLERANCE):
                    return True
            else:  # BEARISH
                if highs[i] >= ob_low * (1 - config.OB_MITIGATION_TOLERANCE):
                    return True

        return False

    except Exception:
        return False


def analyze_order_blocks(
        candles,
        current_price: float,
        signal_direction: str,
        lookback: int = None
) -> Optional[OrderBlockAnalysis]:
    """
    ✅ ИСПРАВЛЕНО: Анализ Order Blocks с учётом возраста
    """
    from config import config
    
    if lookback is None:
        lookback = config.OB_LOOKBACK
    
    if not candles or current_price == 0:
        return None

    try:
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
        elif signal_direction == 'SHORT':
            relevant_blocks = [
                ob for ob in all_blocks
                if ob.direction == 'BEARISH' and ob.price_low > current_price
            ]
        else:
            # UNKNOWN - берём все
            relevant_blocks = all_blocks

        # Находим ближайший (fresh приоритетнее)
        nearest_ob = None
        if relevant_blocks:
            unmitigated = [ob for ob in relevant_blocks if not ob.is_mitigated]

            if unmitigated:
                # Сортируем по distance, затем по age (свежие лучше)
                unmitigated.sort(key=lambda x: (x.distance_from_current, x.age_in_candles))
                nearest_ob = unmitigated[0]
            else:
                relevant_blocks.sort(key=lambda x: (x.distance_from_current, x.age_in_candles))
                nearest_ob = relevant_blocks[0]

        # ✅ ИСПРАВЛЕНО: Рассчитываем adjustment с учётом возраста
        adjustment = _calculate_ob_adjustment_with_age(nearest_ob, signal_direction)

        # Статистика
        bullish_count = sum(1 for ob in all_blocks if ob.direction == 'BULLISH')
        bearish_count = sum(1 for ob in all_blocks if ob.direction == 'BEARISH')

        # Детали
        if nearest_ob:
            mitigation_status = "mitigated" if nearest_ob.is_mitigated else "fresh"
            age_desc = f"{nearest_ob.age_in_candles} candles old"  # ✅ НОВОЕ

            details = (
                f"Nearest {nearest_ob.direction} OB at "
                f"${nearest_ob.price_low:.4f}-${nearest_ob.price_high:.4f} "
                f"({nearest_ob.distance_from_current:.1f}% away, {mitigation_status}, "
                f"strength: {nearest_ob.strength:.0f}, age: {age_desc})"  # ✅ НОВОЕ
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


def _calculate_ob_adjustment_with_age(
        nearest_ob: Optional[OrderBlockData],
        signal_direction: str
) -> int:
    """
    ✅ ИСПРАВЛЕНО: Рассчитать adjustment с учётом возраста OB
    """
    from config import config
    
    if not nearest_ob:
        return 0

    try:
        adjustment = 0

        # Базовый бонус за наличие OB
        adjustment += config.OB_BASE_ADJUSTMENT

        # Бонус за силу OB
        if nearest_ob.strength >= config.OB_STRENGTH_BONUS_THRESHOLD:
            adjustment += config.OB_STRENGTH_BONUS

        # Бонус за fresh (непротестированный) OB
        if not nearest_ob.is_mitigated:
            adjustment += config.OB_FRESH_BONUS

        # ✅ НОВОЕ: Штраф/бонус за возраст
        age = nearest_ob.age_in_candles

        if age <= config.OB_AGE_VERY_FRESH:
            # Очень свежий OB (до 5 свечей)
            adjustment += config.OB_AGE_VERY_FRESH_BONUS
        elif age <= config.OB_AGE_FRESH:
            # Свежий OB (до 10 свечей)
            adjustment += config.OB_AGE_FRESH_BONUS
        elif age <= config.OB_AGE_MEDIUM:
            # Средний возраст (до 20 свечей)
            adjustment += config.OB_AGE_MEDIUM_BONUS
        elif age <= config.OB_AGE_OLD:
            # Старый OB (до 30 свечей)
            adjustment += 0
        else:
            # Очень старый OB (>30 свечей) - не должен попасть сюда
            adjustment += config.OB_AGE_OLD_PENALTY

        # Penalty за большую дистанцию
        if nearest_ob.distance_from_current > config.OB_DISTANCE_FAR_PCT:
            adjustment += config.OB_DISTANCE_FAR_PENALTY
        elif nearest_ob.distance_from_current < config.OB_DISTANCE_CLOSE_PCT:
            # Очень близко - сильный уровень
            adjustment += config.OB_DISTANCE_CLOSE_BONUS

        return adjustment

    except Exception:
        return 0