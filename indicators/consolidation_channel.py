"""
Consolidation Channel Detection
Файл: indicators/consolidation_channel.py

Определение каналов консолидации для стратегии "ложного пробоя"
"""

import numpy as np
import logging
from dataclasses import dataclass
from typing import Optional, List, Tuple
from data_providers.data_normalizer import NormalizedCandles

logger = logging.getLogger(__name__)


@dataclass
class ConsolidationChannel:
    """
    Канал консолидации (накопления энергии)
    
    Attributes:
        upper_bound: Верхняя граница канала
        lower_bound: Нижняя граница канала
        start_index: Индекс начала канала в массиве свечей
        end_index: Индекс конца канала (текущая свеча)
        duration_candles: Длительность канала в свечах
        duration_days: Длительность канала в днях (приблизительно)
        avg_price: Средняя цена в канале
        touches_upper: Количество касаний верхней границы
        touches_lower: Количество касаний нижней границы
        is_valid: Валидность канала (длительность > месяца)
    """
    upper_bound: float
    lower_bound: float
    start_index: int
    end_index: int
    duration_candles: int
    duration_days: float
    avg_price: float
    touches_upper: int
    touches_lower: int
    is_valid: bool


def find_consolidation_channel(
        candles: NormalizedCandles,
        min_duration_candles: int = 30,
        lookback_candles: Optional[int] = None,
        tolerance_pct: float = 1.0
) -> Optional[ConsolidationChannel]:
    """
    Найти канал консолидации в исторических данных
    
    Args:
        candles: Нормализованные свечи
        min_duration_candles: Минимальная длительность канала в свечах (по умолчанию 30)
        lookback_candles: Максимальное количество свечей для анализа (None = все)
        tolerance_pct: Допустимое отклонение от границ канала в процентах
    
    Returns:
        ConsolidationChannel или None если канал не найден
    """
    if not candles or not candles.is_valid:
        return None
    
    if len(candles.closes) < min_duration_candles:
        logger.debug(f"find_consolidation_channel: {candles.symbol} - Insufficient candles")
        return None
    
    # Определяем диапазон анализа
    if lookback_candles is None:
        lookback_candles = len(candles.closes)
    
    lookback_candles = min(lookback_candles, len(candles.closes))
    start_idx = max(0, len(candles.closes) - lookback_candles)
    end_idx = len(candles.closes)
    
    # Анализируем окна разной длины
    best_channel = None
    best_score = 0
    
    # Минимум свечей после канала для анализа пробоя
    from config import config
    min_bars_after_channel = config.CONSOLIDATION_MIN_BARS_AFTER
    
    # Пробуем разные начальные точки
    # Ограничиваем поиск: канал должен заканчиваться минимум за min_bars_after_channel свечей до конца
    max_end_idx = end_idx - min_bars_after_channel
    
    # ✅ ОПТИМИЗАЦИЯ: Используем шаги из config для ускорения поиска
    step_start = config.CONSOLIDATION_SEARCH_STEP_START
    step_size = config.CONSOLIDATION_SEARCH_STEP_SIZE
    
    for window_start in range(start_idx, max_end_idx - min_duration_candles + 1, step_start):
        # Пробуем разные длины окна, но не до самого конца
        max_window_size = min(max_end_idx - window_start, end_idx - window_start)
        # ✅ ОПТИМИЗАЦИЯ: Увеличиваем шаг для window_size
        for window_size in range(min_duration_candles, max_window_size + 1, step_size):
            window_end = window_start + window_size
            
            # Извлекаем данные окна
            window_highs = candles.highs[window_start:window_end]
            window_lows = candles.lows[window_start:window_end]
            window_closes = candles.closes[window_start:window_end]
            
            if len(window_highs) < min_duration_candles:
                continue
            
            # Определяем границы канала
            upper_bound = np.max(window_highs)
            lower_bound = np.min(window_lows)
            
            # Проверяем, что канал не слишком широкий (консолидация, а не тренд)
            from config import config
            channel_width_pct = ((upper_bound - lower_bound) / lower_bound) * 100
            if channel_width_pct > config.CONSOLIDATION_MAX_WIDTH_PCT:
                continue
            
            # Проверяем, что большинство свечей находится внутри канала
            tolerance_upper = upper_bound * (1 + tolerance_pct / 100)
            tolerance_lower = lower_bound * (1 - tolerance_pct / 100)
            
            inside_count = 0
            touches_upper = 0
            touches_lower = 0
            
            for i in range(len(window_closes)):
                high = window_highs[i]
                low = window_lows[i]
                close = window_closes[i]
                
                # Проверка касаний границ
                if abs(high - upper_bound) / upper_bound * 100 <= tolerance_pct:
                    touches_upper += 1
                if abs(low - lower_bound) / lower_bound * 100 <= tolerance_pct:
                    touches_lower += 1
                
                # Проверка нахождения внутри канала
                if tolerance_lower <= close <= tolerance_upper:
                    inside_count += 1
            
            # Минимум X% свечей должны быть внутри канала
            inside_ratio = inside_count / len(window_closes)
            if inside_ratio < config.CONSOLIDATION_MIN_INSIDE_RATIO:
                continue
            
            # Минимум N касаний каждой границы
            if touches_upper < config.CONSOLIDATION_MIN_TOUCHES or touches_lower < config.CONSOLIDATION_MIN_TOUCHES:
                continue
            
            # Вычисляем среднюю цену
            avg_price = np.mean(window_closes)
            
            # Оценка качества канала
            score = (
                window_size * 0.4 +  # Длительность
                (touches_upper + touches_lower) * 10 +  # Касания
                (1.0 / max(channel_width_pct, 0.1)) * 5  # Узость канала
            )
            
            if score > best_score:
                best_score = score
                
                # Вычисляем длительность в днях (приблизительно)
                if candles.interval == "60":  # 1H
                    duration_days = window_size / 24.0
                elif candles.interval == "240":  # 4H
                    duration_days = window_size / 6.0
                else:
                    duration_days = window_size  # Для других ТФ считаем как дни
                
                # Используем параметр из config для проверки валидности
                from config import config
                min_duration_days = config.CONSOLIDATION_MIN_DURATION_DAYS
                
                best_channel = ConsolidationChannel(
                    upper_bound=float(upper_bound),
                    lower_bound=float(lower_bound),
                    start_index=window_start,
                    end_index=window_end - 1,  # Последняя свеча в канале
                    duration_candles=window_size,
                    duration_days=duration_days,
                    avg_price=float(avg_price),
                    touches_upper=touches_upper,
                    touches_lower=touches_lower,
                    is_valid=window_size >= min_duration_candles and duration_days >= min_duration_days
                )
    
    if best_channel:
        logger.debug(
            f"find_consolidation_channel: {candles.symbol} - "
            f"Channel found: {best_channel.lower_bound:.4f}-{best_channel.upper_bound:.4f}, "
            f"duration: {best_channel.duration_days:.1f} days, "
            f"touches: U={best_channel.touches_upper}, L={best_channel.touches_lower}"
        )
    
    return best_channel


def is_price_in_channel(
        price: float,
        channel: ConsolidationChannel,
        tolerance_pct: float = 1.0
) -> bool:
    """
    Проверить, находится ли цена внутри канала
    
    Args:
        price: Текущая цена
        channel: Канал консолидации
        tolerance_pct: Допустимое отклонение в процентах
    
    Returns:
        True если цена внутри канала
    """
    tolerance_upper = channel.upper_bound * (1 + tolerance_pct / 100)
    tolerance_lower = channel.lower_bound * (1 - tolerance_pct / 100)
    
    return tolerance_lower <= price <= tolerance_upper


def get_channel_distance_pct(
        price: float,
        channel: ConsolidationChannel
) -> Tuple[float, float]:
    """
    Вычислить расстояние от цены до границ канала в процентах
    
    Args:
        price: Текущая цена
        channel: Канал консолидации
    
    Returns:
        Tuple (distance_to_lower_pct, distance_to_upper_pct)
    """
    distance_to_lower = ((price - channel.lower_bound) / channel.lower_bound) * 100
    distance_to_upper = ((channel.upper_bound - price) / channel.upper_bound) * 100
    
    return distance_to_lower, distance_to_upper

