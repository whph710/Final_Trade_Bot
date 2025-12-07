"""
Support/Resistance Levels Indicator
Файл: indicators/support_resistance.py

Определение уровней поддержки/сопротивления методом "3 удара"
"""

import numpy as np
import logging
from dataclasses import dataclass
from typing import List, Optional

logger = logging.getLogger(__name__)


@dataclass
class SupportResistanceLevel:
    """Уровень поддержки/сопротивления"""
    price: float
    level_type: str  # 'SUPPORT' | 'RESISTANCE'
    touches: int
    strength: float  # 0-100
    distance_from_current_pct: float
    candle_indices: List[int]


@dataclass
class SupportResistanceAnalysis:
    """Результат анализа уровней"""
    nearest_support: Optional[SupportResistanceLevel]
    nearest_resistance: Optional[SupportResistanceLevel]
    all_levels: List[SupportResistanceLevel]
    current_price_zone: str  # 'NEAR_SUPPORT' | 'NEAR_RESISTANCE' | 'MIDDLE'
    confidence_adjustment: int
    details: str


def find_support_resistance_levels(
        candles: 'NormalizedCandles',
        lookback: int = None,
        min_touches: int = None,
        touch_tolerance_pct: float = None
) -> List[SupportResistanceLevel]:
    """
    Найти уровни поддержки/сопротивления методом "3 удара"

    Args:
        candles: NormalizedCandles объект
        lookback: Период анализа (по умолчанию из config)
        min_touches: Минимум касаний для уровня (по умолчанию из config)
        touch_tolerance_pct: Допуск касания (по умолчанию из config)

    Returns:
        Список найденных уровней
    """
    from config import config
    
    if lookback is None:
        lookback = config.SR_LOOKBACK
    if min_touches is None:
        min_touches = config.SR_MIN_TOUCHES
    if touch_tolerance_pct is None:
        touch_tolerance_pct = config.SR_TOUCH_TOLERANCE_PCT
    
    if not candles or not candles.is_valid:
        return []

    if len(candles.closes) < lookback:
        lookback = len(candles.closes)

    if lookback < 20:
        return []

    try:
        highs = candles.highs[-lookback:]
        lows = candles.lows[-lookback:]
        current_price = float(candles.closes[-1])

        # Находим потенциальные уровни (локальные экстремумы)
        potential_levels = []

        # Ищем swing highs (потенциальные сопротивления)
        for i in range(2, len(highs) - 2):
            if (highs[i] >= highs[i - 1] and highs[i] >= highs[i - 2] and
                    highs[i] >= highs[i + 1] and highs[i] >= highs[i + 2]):
                potential_levels.append({
                    'price': float(highs[i]),
                    'type': 'RESISTANCE',
                    'index': i
                })

        # Ищем swing lows (потенциальные поддержки)
        for i in range(2, len(lows) - 2):
            if (lows[i] <= lows[i - 1] and lows[i] <= lows[i - 2] and
                    lows[i] <= lows[i + 1] and lows[i] <= lows[i + 2]):
                potential_levels.append({
                    'price': float(lows[i]),
                    'type': 'SUPPORT',
                    'index': i
                })

        if not potential_levels:
            return []

        # Группируем близкие уровни
        grouped_levels = _group_similar_levels(
            potential_levels,
            touch_tolerance_pct
        )

        # Фильтруем по минимальному количеству касаний
        valid_levels = []

        for level_group in grouped_levels:
            touches = len(level_group['indices'])

            if touches >= min_touches:
                avg_price = np.mean([pl['price'] for pl in level_group['levels']])
                level_type = level_group['type']

                # Рассчитываем силу уровня
                strength = min(100, (touches / min_touches) * 50)

                # Бонус за большое количество касаний
                if touches >= 5:
                    strength += 20
                elif touches >= 4:
                    strength += 10

                distance_pct = abs((current_price - avg_price) / current_price * 100)

                valid_levels.append(SupportResistanceLevel(
                    price=avg_price,
                    level_type=level_type,
                    touches=touches,
                    strength=strength,
                    distance_from_current_pct=round(distance_pct, 2),
                    candle_indices=level_group['indices']
                ))

        # Сортируем по расстоянию от текущей цены
        valid_levels.sort(key=lambda x: x.distance_from_current_pct)

        logger.debug(f"Found {len(valid_levels)} valid S/R levels")
        return valid_levels

    except Exception as e:
        logger.error(f"S/R levels detection error: {e}")
        return []


def _group_similar_levels(
        potential_levels: List[dict],
        tolerance_pct: float
) -> List[dict]:
    """Группировать близкие уровни в кластеры"""
    if not potential_levels:
        return []

    # Сортируем по цене
    sorted_levels = sorted(potential_levels, key=lambda x: x['price'])

    groups = []
    current_group = {
        'levels': [sorted_levels[0]],
        'type': sorted_levels[0]['type'],
        'indices': [sorted_levels[0]['index']]
    }

    for level in sorted_levels[1:]:
        last_price = current_group['levels'][-1]['price']
        current_price = level['price']

        # Проверяем близость
        diff_pct = abs((current_price - last_price) / last_price * 100)

        if diff_pct <= tolerance_pct and level['type'] == current_group['type']:
            # Добавляем в текущую группу
            current_group['levels'].append(level)
            current_group['indices'].append(level['index'])
        else:
            # Начинаем новую группу
            groups.append(current_group)
            current_group = {
                'levels': [level],
                'type': level['type'],
                'indices': [level['index']]
            }

    # Добавляем последнюю группу
    groups.append(current_group)

    return groups


def analyze_support_resistance(
        candles: 'NormalizedCandles',
        current_price: float,
        signal_direction: str
) -> Optional[SupportResistanceAnalysis]:
    """
    Анализ уровней относительно текущей цены

    Args:
        candles: NormalizedCandles объект
        current_price: Текущая цена
        signal_direction: 'LONG' | 'SHORT' | 'UNKNOWN'

    Returns:
        SupportResistanceAnalysis или None
    """
    if not candles or current_price == 0:
        return None

    try:
        all_levels = find_support_resistance_levels(candles)

        if not all_levels:
            return SupportResistanceAnalysis(
                nearest_support=None,
                nearest_resistance=None,
                all_levels=[],
                current_price_zone='MIDDLE',
                confidence_adjustment=0,
                details='No S/R levels found'
            )

        # Разделяем на поддержки и сопротивления
        supports = [lvl for lvl in all_levels
                    if lvl.level_type == 'SUPPORT' and lvl.price < current_price]
        resistances = [lvl for lvl in all_levels
                       if lvl.level_type == 'RESISTANCE' and lvl.price > current_price]

        # Находим ближайшие
        nearest_support = supports[0] if supports else None
        nearest_resistance = resistances[0] if resistances else None

        # Определяем зону цены
        zone = _determine_price_zone(
            current_price,
            nearest_support,
            nearest_resistance
        )

        # Рассчитываем adjustment
        adjustment = _calculate_sr_adjustment(
            nearest_support,
            nearest_resistance,
            signal_direction,
            zone
        )

        # Детали
        details = _build_sr_details(
            nearest_support,
            nearest_resistance,
            zone,
            len(all_levels)
        )

        return SupportResistanceAnalysis(
            nearest_support=nearest_support,
            nearest_resistance=nearest_resistance,
            all_levels=all_levels,
            current_price_zone=zone,
            confidence_adjustment=adjustment,
            details=details
        )

    except Exception as e:
        logger.error(f"S/R analysis error: {e}")
        return None


def _determine_price_zone(
        current_price: float,
        nearest_support: Optional[SupportResistanceLevel],
        nearest_resistance: Optional[SupportResistanceLevel]
) -> str:
    """Определить зону текущей цены"""
    from config import config
    
    if nearest_support and nearest_support.distance_from_current_pct < config.SR_LEVEL_NEAR_DISTANCE_PCT:
        return 'NEAR_SUPPORT'

    if nearest_resistance and nearest_resistance.distance_from_current_pct < config.SR_LEVEL_NEAR_DISTANCE_PCT:
        return 'NEAR_RESISTANCE'

    return 'MIDDLE'


def _calculate_sr_adjustment(
        nearest_support: Optional[SupportResistanceLevel],
        nearest_resistance: Optional[SupportResistanceLevel],
        signal_direction: str,
        zone: str
) -> int:
    """Рассчитать корректировку confidence"""
    adjustment = 0

    from config import config
    
    # LONG сигнал
    if signal_direction == 'LONG':
        if nearest_support:
            # Близко к поддержке - хорошо для LONG
            if nearest_support.distance_from_current_pct < config.SR_LEVEL_NEAR_DISTANCE_PCT:
                adjustment += config.SR_ADJUSTMENT_NEAR

                # Бонус за сильный уровень
                if nearest_support.touches >= config.SR_LEVEL_TOUCHES_STRONG:
                    adjustment += config.SR_ADJUSTMENT_BONUS_TOUCHES

            elif nearest_support.distance_from_current_pct < 2.5:
                adjustment += config.SR_ADJUSTMENT_MODERATE

    # SHORT сигнал
    elif signal_direction == 'SHORT':
        if nearest_resistance:
            # Близко к сопротивлению - хорошо для SHORT
            if nearest_resistance.distance_from_current_pct < config.SR_LEVEL_NEAR_DISTANCE_PCT:
                adjustment += config.SR_ADJUSTMENT_NEAR

                # Бонус за сильный уровень
                if nearest_resistance.touches >= config.SR_LEVEL_TOUCHES_STRONG:
                    adjustment += config.SR_ADJUSTMENT_BONUS_TOUCHES

            elif nearest_resistance.distance_from_current_pct < 2.5:
                adjustment += config.SR_ADJUSTMENT_MODERATE

    return adjustment


def _build_sr_details(
        nearest_support: Optional[SupportResistanceLevel],
        nearest_resistance: Optional[SupportResistanceLevel],
        zone: str,
        total_levels: int
) -> str:
    """Построить текстовое описание"""
    parts = [f"Total levels: {total_levels}"]

    if nearest_support:
        parts.append(
            f"Nearest support: ${nearest_support.price:.4f} "
            f"({nearest_support.distance_from_current_pct:.1f}% away, "
            f"{nearest_support.touches} touches)"
        )

    if nearest_resistance:
        parts.append(
            f"Nearest resistance: ${nearest_resistance.price:.4f} "
            f"({nearest_resistance.distance_from_current_pct:.1f}% away, "
            f"{nearest_resistance.touches} touches)"
        )

    parts.append(f"Price zone: {zone}")

    return '; '.join(parts)

