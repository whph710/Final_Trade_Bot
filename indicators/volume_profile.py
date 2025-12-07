"""
Volume Profile Indicator
Файл: indicators/volume_profile.py

Расчёт Volume Profile: POC, Value Area, HVN/LVN зоны
"""

import numpy as np
import logging
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class VolumeProfileData:
    """
    Данные Volume Profile

    Attributes:
        poc: Point of Control (цена с максимальным объёмом)
        poc_volume: Объём на POC
        value_area_high: Верхняя граница Value Area (70% объёма)
        value_area_low: Нижняя граница Value Area
        hvn_zones: High Volume Node zones [(low, high), ...]
        lvn_zones: Low Volume Node zones [(low, high), ...]
        total_volume: Общий объём
        profile: Полный профиль {price: volume}
    """
    poc: float
    poc_volume: float
    value_area_high: float
    value_area_low: float
    hvn_zones: List[Tuple[float, float]]
    lvn_zones: List[Tuple[float, float]]
    total_volume: float
    profile: Dict[float, float]


@dataclass
class VolumeProfileAnalysis:
    """Результат анализа Volume Profile"""
    poc_proximity: Dict
    value_area_position: Dict
    volume_nodes: Dict
    total_confidence_adjustment: int


def calculate_volume_profile(
        candles,  # NormalizedCandles
        num_bins: int = None
) -> Optional[VolumeProfileData]:
    """
    Рассчитать Volume Profile

    Args:
        candles: NormalizedCandles объект
        num_bins: Количество ценовых уровней (по умолчанию из config)

    Returns:
        VolumeProfileData или None при ошибке
    """
    from config import config
    
    if num_bins is None:
        num_bins = config.VP_NUM_BINS
    
    if not candles or not candles.is_valid:
        return None

    if len(candles.closes) < 20:
        return None

    try:
        highs = candles.highs
        lows = candles.lows
        volumes = candles.volumes

        min_price = float(np.min(lows))
        max_price = float(np.max(highs))

        if min_price == max_price or max_price == 0:
            return None

        # Рассчитываем размер бина
        price_range = max_price - min_price
        bin_size = price_range / num_bins

        # Создаём ценовые уровни
        price_levels = np.arange(min_price, max_price + bin_size, bin_size)
        volume_at_price = defaultdict(float)

        # Распределяем объём по уровням
        for i in range(len(candles.closes)):
            high = float(highs[i])
            low = float(lows[i])
            volume = float(volumes[i])

            # Находим уровни внутри свечи
            candle_levels = [p for p in price_levels if low <= p <= high]

            if candle_levels:
                volume_per_level = volume / len(candle_levels)
                for level in candle_levels:
                    rounded_level = round(level / bin_size) * bin_size
                    volume_at_price[rounded_level] += volume_per_level

        if not volume_at_price:
            return None

        # Сортируем по объёму (max -> min)
        sorted_levels = sorted(
            volume_at_price.items(),
            key=lambda x: x[1],
            reverse=True
        )

        # POC - уровень с максимальным объёмом
        poc_price, poc_volume = sorted_levels[0]

        # Рассчитываем Value Area (% из config)
        from config import config
        total_volume = sum(volume_at_price.values())
        value_area_target = total_volume * config.VP_VALUE_AREA_PCT

        value_area_prices = []
        accumulated_volume = 0

        for price, volume in sorted_levels:
            value_area_prices.append(price)
            accumulated_volume += volume
            if accumulated_volume >= value_area_target:
                break

        value_area_high = max(value_area_prices)
        value_area_low = min(value_area_prices)

        # Определяем HVN и LVN зоны
        hvn_zones, lvn_zones = _identify_volume_nodes(
            volume_at_price,
            poc_volume,
            bin_size
        )

        return VolumeProfileData(
            poc=float(poc_price),
            poc_volume=float(poc_volume),
            value_area_high=float(value_area_high),
            value_area_low=float(value_area_low),
            hvn_zones=hvn_zones,
            lvn_zones=lvn_zones,
            total_volume=float(total_volume),
            profile={float(k): float(v) for k, v in volume_at_price.items()}
        )

    except Exception as e:
        logger.error(f"Volume Profile calculation error: {e}")
        return None


def _identify_volume_nodes(
        volume_at_price: Dict[float, float],
        poc_volume: float,
        bin_size: float
) -> Tuple[List[Tuple], List[Tuple]]:
    """Определить HVN и LVN зоны"""
    if not volume_at_price:
        return [], []

    try:
        from config import config
        avg_volume = np.mean(list(volume_at_price.values()))
        hvn_threshold = avg_volume * config.VP_HVN_MULTIPLIER
        lvn_threshold = avg_volume * config.VP_LVN_MULTIPLIER

        sorted_by_price = sorted(volume_at_price.items())

        hvn_zones = []
        lvn_zones = []

        current_hvn = None
        current_lvn = None

        for price, volume in sorted_by_price:
            # HVN detection
            if volume >= hvn_threshold:
                if current_hvn is None:
                    current_hvn = [price, price]
                else:
                    current_hvn[1] = price
            else:
                if current_hvn is not None:
                    hvn_zones.append(tuple(current_hvn))
                    current_hvn = None

            # LVN detection
            if volume <= lvn_threshold:
                if current_lvn is None:
                    current_lvn = [price, price]
                else:
                    current_lvn[1] = price
            else:
                if current_lvn is not None:
                    lvn_zones.append(tuple(current_lvn))
                    current_lvn = None

        # Добавляем последние зоны если есть
        if current_hvn:
            hvn_zones.append(tuple(current_hvn))
        if current_lvn:
            lvn_zones.append(tuple(current_lvn))

        return hvn_zones, lvn_zones

    except Exception as e:
        logger.error(f"Volume nodes identification error: {e}")
        return [], []


def analyze_volume_profile(
        vp_data: VolumeProfileData,
        current_price: float
) -> Optional[VolumeProfileAnalysis]:
    """
    Анализ Volume Profile относительно текущей цены

    Returns:
        VolumeProfileAnalysis или None
    """
    if not vp_data or vp_data.poc == 0:
        return None

    try:
        # 1. POC Proximity Analysis
        poc_analysis = _analyze_poc_proximity(
            current_price,
            vp_data.poc,
            (vp_data.value_area_low, vp_data.value_area_high)
        )

        # 2. Value Area Position Analysis
        va_analysis = _analyze_value_area_position(
            current_price,
            vp_data.value_area_low,
            vp_data.value_area_high
        )

        # 3. Volume Nodes Analysis
        vn_analysis = _analyze_volume_nodes(
            current_price,
            vp_data.hvn_zones,
            vp_data.lvn_zones
        )

        # Total confidence adjustment
        total_adjustment = (
                poc_analysis['confidence_adjustment'] +
                va_analysis['confidence_adjustment'] +
                vn_analysis['confidence_adjustment']
        )

        return VolumeProfileAnalysis(
            poc_proximity=poc_analysis,
            value_area_position=va_analysis,
            volume_nodes=vn_analysis,
            total_confidence_adjustment=total_adjustment
        )

    except Exception as e:
        logger.error(f"Volume Profile analysis error: {e}")
        return None


def _analyze_poc_proximity(
        current_price: float,
        poc: float,
        value_area: Tuple[float, float]
) -> Dict:
    """Анализ близости к POC"""
    if poc == 0 or current_price == 0:
        return {
            'distance_to_poc_pct': 0,
            'poc_relevance': 'UNKNOWN',
            'expected_behavior': 'NEUTRAL',
            'confidence_adjustment': 0
        }

    from config import config
    distance_pct = abs((current_price - poc) / current_price * 100)

    if distance_pct < config.VP_POC_STRONG_DISTANCE_PCT:
        relevance = 'STRONG'
        behavior = 'ATTRACTION'
        adjustment = config.VP_POC_STRONG_ADJUSTMENT
    elif distance_pct < config.VP_POC_MODERATE_DISTANCE_PCT:
        relevance = 'MODERATE'
        behavior = 'ATTRACTION'
        adjustment = config.VP_POC_MODERATE_ADJUSTMENT
    elif distance_pct < config.VP_POC_WEAK_DISTANCE_PCT:
        relevance = 'WEAK'
        behavior = 'NEUTRAL'
        adjustment = 0
    else:
        relevance = 'EXPIRED'
        behavior = 'NEUTRAL'
        adjustment = 0

    return {
        'distance_to_poc_pct': round(distance_pct, 2),
        'poc_relevance': relevance,
        'expected_behavior': behavior,
        'confidence_adjustment': adjustment
    }


def _analyze_value_area_position(
        current_price: float,
        va_low: float,
        va_high: float
) -> Dict:
    """Анализ позиции относительно Value Area"""
    if va_low == 0 or va_high == 0:
        return {
            'position': 'UNKNOWN',
            'market_condition': 'UNKNOWN',
            'expected_move': 'RANGE',
            'confidence_adjustment': 0
        }

    from config import config
    
    if current_price > va_high:
        position = 'ABOVE'
        distance_pct = ((current_price - va_high) / va_high) * 100

        if distance_pct > config.VP_VA_OVEREXTENDED_PCT:
            condition = 'OVEREXTENDED'
            move = 'REVERT_TO_VA'
            adjustment = config.VP_VA_OVEREXTENDED_PENALTY
        else:
            condition = 'STRONG'
            move = 'CONTINUE'
            adjustment = config.VP_VA_STRONG_BONUS

    elif current_price < va_low:
        position = 'BELOW'
        distance_pct = ((va_low - current_price) / va_low) * 100

        if distance_pct > config.VP_VA_OVEREXTENDED_PCT:
            condition = 'UNDEREXTENDED'
            move = 'REVERT_TO_VA'
            adjustment = config.VP_VA_OVEREXTENDED_PENALTY
        else:
            condition = 'WEAK'
            move = 'CONTINUE'
            adjustment = config.VP_VA_STRONG_BONUS

    else:
        position = 'INSIDE'
        condition = 'NORMAL'
        move = 'RANGE'
        adjustment = 0

    return {
        'position': position,
        'market_condition': condition,
        'expected_move': move,
        'confidence_adjustment': adjustment
    }


def _analyze_volume_nodes(
        current_price: float,
        hvn_zones: List[Tuple[float, float]],
        lvn_zones: List[Tuple[float, float]]
) -> Dict:
    """Анализ volume nodes"""
    in_hvn = any(low <= current_price <= high for low, high in hvn_zones)
    in_lvn = any(low <= current_price <= high for low, high in lvn_zones)

    # Найти ближайшую HVN зону
    nearest_hvn = None
    min_distance = float('inf')

    for low, high in hvn_zones:
        zone_center = (low + high) / 2
        distance = abs(current_price - zone_center)

        if distance < min_distance:
            min_distance = distance
            nearest_hvn = (low, high)

    from config import config
    
    if in_hvn:
        behavior = 'SUPPORT'
        adjustment = config.VP_HVN_BONUS
    elif in_lvn:
        behavior = 'FAST_MOVE'
        adjustment = config.VP_LVN_PENALTY
    else:
        behavior = 'NORMAL'
        adjustment = 0

    return {
        'in_hvn': in_hvn,
        'in_lvn': in_lvn,
        'nearest_hvn': nearest_hvn,
        'price_behavior': behavior,
        'confidence_adjustment': adjustment
    }