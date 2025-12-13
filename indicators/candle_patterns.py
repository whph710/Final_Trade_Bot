"""
Candle Patterns Detection
Файл: indicators/candle_patterns.py

Определение выкупного/продажного бара для подтверждения разворота
"""

import numpy as np
import logging
from dataclasses import dataclass
from typing import Optional, Literal
from data_providers.data_normalizer import NormalizedCandles

logger = logging.getLogger(__name__)


@dataclass
class BuyoutBar:
    """
    Выкупной бар (для разворота вверх)
    
    Attributes:
        index: Индекс свечи
        body_size_pct: Размер тела свечи в процентах от диапазона
        lower_shadow_pct: Размер нижней тени в процентах от диапазона
        upper_shadow_pct: Размер верхней тени в процентах от диапазона
        close_near_high_pct: Близость закрытия к максимуму в процентах
        is_valid: Валидность паттерна
        strength: Сила паттерна (0-100)
    """
    index: int
    body_size_pct: float
    lower_shadow_pct: float
    upper_shadow_pct: float
    close_near_high_pct: float
    is_valid: bool
    strength: int


@dataclass
class SelloutBar:
    """
    Продажный бар (для разворота вниз)
    
    Attributes:
        index: Индекс свечи
        body_size_pct: Размер тела свечи в процентах от диапазона
        lower_shadow_pct: Размер нижней тени в процентах от диапазона
        upper_shadow_pct: Размер верхней тени в процентах от диапазона
        close_near_low_pct: Близость закрытия к минимуму в процентах
        is_valid: Валидность паттерна
        strength: Сила паттерна (0-100)
    """
    index: int
    body_size_pct: float
    lower_shadow_pct: float
    upper_shadow_pct: float
    close_near_low_pct: float
    is_valid: bool
    strength: int


def detect_buyout_bar(
        candles: NormalizedCandles,
        lookback_bars: int = 5,
        min_lower_shadow_pct: float = 30.0,
        min_close_near_high_pct: float = 80.0
) -> Optional[BuyoutBar]:
    """
    Обнаружить выкупной бар (для разворота вверх)
    
    Выкупной бар - это свеча, которая:
    1. Сильно падает вниз (длинная нижняя тень)
    2. Полностью выкупает падение и закрывается близко к максимуму
    
    Args:
        candles: Нормализованные свечи
        lookback_bars: Количество свечей для анализа
        min_lower_shadow_pct: Минимальный размер нижней тени в процентах от диапазона
        min_close_near_high_pct: Минимальная близость закрытия к максимуму в процентах
    
    Returns:
        BuyoutBar или None если паттерн не найден
    """
    if not candles or not candles.is_valid:
        return None
    
    if len(candles.closes) < lookback_bars:
        return None
    
    # Анализируем последние свечи
    start_idx = max(0, len(candles.closes) - lookback_bars)
    
    best_bar = None
    best_strength = 0
    
    for i in range(start_idx, len(candles.closes)):
        open_price = float(candles.opens[i])
        high = float(candles.highs[i])
        low = float(candles.lows[i])
        close = float(candles.closes[i])
        
        # Вычисляем размеры компонентов свечи
        candle_range = high - low
        if candle_range == 0:
            continue
        
        body_size = abs(close - open_price)
        lower_shadow = min(open_price, close) - low
        upper_shadow = high - max(open_price, close)
        
        body_size_pct = (body_size / candle_range) * 100
        lower_shadow_pct = (lower_shadow / candle_range) * 100
        upper_shadow_pct = (upper_shadow / candle_range) * 100
        
        # Близость закрытия к максимуму
        close_near_high_pct = ((close - low) / candle_range) * 100
        
        # Проверяем условия выкупного бара
        is_buyout = (
            lower_shadow_pct >= min_lower_shadow_pct and  # Длинная нижняя тень
            close_near_high_pct >= min_close_near_high_pct  # Закрытие близко к максимуму
        )
        
        if is_buyout:
            # Вычисляем силу паттерна
            strength = _calculate_buyout_strength(
                lower_shadow_pct, close_near_high_pct, body_size_pct, upper_shadow_pct
            )
            
            if strength > best_strength:
                best_strength = strength
                best_bar = BuyoutBar(
                    index=i,
                    body_size_pct=body_size_pct,
                    lower_shadow_pct=lower_shadow_pct,
                    upper_shadow_pct=upper_shadow_pct,
                    close_near_high_pct=close_near_high_pct,
                    is_valid=True,
                    strength=strength
                )
    
    if best_bar:
        logger.debug(
            f"detect_buyout_bar: {candles.symbol} - "
            f"Buyout bar found at index {best_bar.index}, strength: {best_bar.strength}%"
        )
    
    return best_bar


def detect_sellout_bar(
        candles: NormalizedCandles,
        lookback_bars: int = 5,
        min_upper_shadow_pct: float = 30.0,
        min_close_near_low_pct: float = 80.0
) -> Optional[SelloutBar]:
    """
    Обнаружить продажный бар (для разворота вниз)
    
    Продажный бар - это свеча, которая:
    1. Сильно растет вверх (длинная верхняя тень)
    2. Полностью продает рост и закрывается близко к минимуму
    
    Args:
        candles: Нормализованные свечи
        lookback_bars: Количество свечей для анализа
        min_upper_shadow_pct: Минимальный размер верхней тени в процентах от диапазона
        min_close_near_low_pct: Минимальная близость закрытия к минимуму в процентах
    
    Returns:
        SelloutBar или None если паттерн не найден
    """
    if not candles or not candles.is_valid:
        return None
    
    if len(candles.closes) < lookback_bars:
        return None
    
    # Анализируем последние свечи
    start_idx = max(0, len(candles.closes) - lookback_bars)
    
    best_bar = None
    best_strength = 0
    
    for i in range(start_idx, len(candles.closes)):
        open_price = float(candles.opens[i])
        high = float(candles.highs[i])
        low = float(candles.lows[i])
        close = float(candles.closes[i])
        
        # Вычисляем размеры компонентов свечи
        candle_range = high - low
        if candle_range == 0:
            continue
        
        body_size = abs(close - open_price)
        lower_shadow = min(open_price, close) - low
        upper_shadow = high - max(open_price, close)
        
        body_size_pct = (body_size / candle_range) * 100
        lower_shadow_pct = (lower_shadow / candle_range) * 100
        upper_shadow_pct = (upper_shadow / candle_range) * 100
        
        # Близость закрытия к минимуму
        close_near_low_pct = ((high - close) / candle_range) * 100
        
        # Проверяем условия продажного бара
        is_sellout = (
            upper_shadow_pct >= min_upper_shadow_pct and  # Длинная верхняя тень
            close_near_low_pct >= min_close_near_low_pct  # Закрытие близко к минимуму
        )
        
        if is_sellout:
            # Вычисляем силу паттерна
            strength = _calculate_sellout_strength(
                upper_shadow_pct, close_near_low_pct, body_size_pct, lower_shadow_pct
            )
            
            if strength > best_strength:
                best_strength = strength
                best_bar = SelloutBar(
                    index=i,
                    body_size_pct=body_size_pct,
                    lower_shadow_pct=lower_shadow_pct,
                    upper_shadow_pct=upper_shadow_pct,
                    close_near_low_pct=close_near_low_pct,
                    is_valid=True,
                    strength=strength
                )
    
    if best_bar:
        logger.debug(
            f"detect_sellout_bar: {candles.symbol} - "
            f"Sellout bar found at index {best_bar.index}, strength: {best_bar.strength}%"
        )
    
    return best_bar


def _calculate_buyout_strength(
        lower_shadow_pct: float,
        close_near_high_pct: float,
        body_size_pct: float,
        upper_shadow_pct: float
) -> int:
    """
    Вычислить силу выкупного бара
    
    Args:
        lower_shadow_pct: Размер нижней тени в процентах
        close_near_high_pct: Близость закрытия к максимуму в процентах
        body_size_pct: Размер тела в процентах
        upper_shadow_pct: Размер верхней тени в процентах
    
    Returns:
        Сила паттерна (0-100)
    """
    strength = 50  # Базовая сила
    
    # Бонус за длинную нижнюю тень
    if lower_shadow_pct >= 50:
        strength += 20
    elif lower_shadow_pct >= 40:
        strength += 15
    elif lower_shadow_pct >= 30:
        strength += 10
    
    # Бонус за закрытие близко к максимуму
    if close_near_high_pct >= 95:
        strength += 20
    elif close_near_high_pct >= 90:
        strength += 15
    elif close_near_high_pct >= 80:
        strength += 10
    
    # Бонус за маленькую верхнюю тень (сильный выкуп)
    if upper_shadow_pct <= 5:
        strength += 10
    elif upper_shadow_pct <= 10:
        strength += 5
    
    # Штраф за маленькое тело (неопределенность)
    if body_size_pct < 20:
        strength -= 10
    
    return min(100, max(0, strength))


def _calculate_sellout_strength(
        upper_shadow_pct: float,
        close_near_low_pct: float,
        body_size_pct: float,
        lower_shadow_pct: float
) -> int:
    """
    Вычислить силу продажного бара
    
    Args:
        upper_shadow_pct: Размер верхней тени в процентах
        close_near_low_pct: Близость закрытия к минимуму в процентах
        body_size_pct: Размер тела в процентах
        lower_shadow_pct: Размер нижней тени в процентах
    
    Returns:
        Сила паттерна (0-100)
    """
    strength = 50  # Базовая сила
    
    # Бонус за длинную верхнюю тень
    if upper_shadow_pct >= 50:
        strength += 20
    elif upper_shadow_pct >= 40:
        strength += 15
    elif upper_shadow_pct >= 30:
        strength += 10
    
    # Бонус за закрытие близко к минимуму
    if close_near_low_pct >= 95:
        strength += 20
    elif close_near_low_pct >= 90:
        strength += 15
    elif close_near_low_pct >= 80:
        strength += 10
    
    # Бонус за маленькую нижнюю тень (сильная продажа)
    if lower_shadow_pct <= 5:
        strength += 10
    elif lower_shadow_pct <= 10:
        strength += 5
    
    # Штраф за маленькое тело (неопределенность)
    if body_size_pct < 20:
        strength -= 10
    
    return min(100, max(0, strength))

