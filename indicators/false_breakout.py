"""
False Breakout Strategy - "Ложный Пробой"
Файл: indicators/false_breakout.py

Стратегия торговли ложными пробоями уровней поддержки/сопротивления
Адаптирована для таймфреймов 1H и 4H

Основная философия: Торговля в направлении, противоположном пробою уровня,
после того как рынок продемонстрировал неспособность закрепиться выше/ниже уровня.
"""

import numpy as np
import logging
from dataclasses import dataclass
from typing import Optional, Literal, List, Tuple
from data_providers.data_normalizer import NormalizedCandles
from indicators.support_resistance import SupportResistanceLevel
from indicators.volume import calculate_volume_ratio
from indicators.atr import calculate_atr

logger = logging.getLogger(__name__)


@dataclass
class FalseBreakoutSignal:
    """
    Сигнал ложного пробоя уровня
    
    Attributes:
        direction: Направление сигнала ('LONG' или 'SHORT')
        breakout_direction: Направление пробоя ('UP' или 'DOWN')
        level_price: Цена уровня, который был пробит
        level_type: Тип уровня ('SUPPORT' или 'RESISTANCE')
        breakout_type: Тип ложного пробоя ('SIMPLE', 'TWO_BARS', 'MULTI_BAR')
        breakout_index: Индекс свечи, где произошел пробой
        return_index: Индекс свечи, где произошел возврат за уровень
        entry_index: Индекс свечи для входа (после возврата)
        breakout_depth_pct: Глубина пробоя в процентах
        tail_size_pct: Размер хвоста в % от ATR
        stop_loss: Рекомендуемый стоп-лосс
        volume_spike_ratio: Соотношение объема на пробое к среднему
        volatility_spike: Увеличение волатильности на пробое
        is_valid: Валидность сигнала
        confidence: Уверенность в сигнале (0-100)
        details: Детали сигнала
    """
    direction: Literal['LONG', 'SHORT']
    breakout_direction: Literal['UP', 'DOWN']
    level_price: float
    level_type: Literal['SUPPORT', 'RESISTANCE']
    breakout_type: Literal['SIMPLE', 'TWO_BARS', 'MULTI_BAR']
    breakout_index: int
    return_index: int
    entry_index: int
    breakout_depth_pct: float
    tail_size_pct: float
    stop_loss: float
    volume_spike_ratio: float
    volatility_spike: float
    is_valid: bool
    confidence: int
    details: str


def detect_false_breakout(
        candles: NormalizedCandles,
        level: SupportResistanceLevel,
        lookback_bars: int = 50,
        max_breakout_bars: int = 10,
        min_level_age_candles: int = 20
) -> Optional[FalseBreakoutSignal]:
    """
    Обнаружить ложный пробой уровня поддержки/сопротивления
    
    Стратегия основана на следующих принципах:
    1. Ложный пробой - это невозможность инструмента закрепиться выше/ниже уровня
    2. Признаки ЛП: резкое увеличение волатильности, огромные объемы, отсутствие ретеста
    3. Вход осуществляется после возврата цены за уровень
    
    Args:
        candles: Нормализованные свечи
        level: Уровень поддержки/сопротивления
        lookback_bars: Количество свечей для анализа перед уровнем
        max_breakout_bars: Максимальное количество баров для определения ЛП
        min_level_age_candles: Минимальный возраст уровня в свечах (для дальнего ретеста)
    
    Returns:
        FalseBreakoutSignal или None если пробой не обнаружен
    """
    if not candles or not candles.is_valid:
        return None
    
    if not level or level.price <= 0:
        return None
    
    if len(candles.closes) < lookback_bars + max_breakout_bars + 10:
        return None
    
    try:
        # Находим индекс уровня в истории
        level_index = _find_level_index(candles, level)
        if level_index is None:
            return None
        
        # Проверяем предпосылки для ЛП
        prerequisites = _check_prerequisites(
            candles, level, level_index, lookback_bars, min_level_age_candles
        )
        if not prerequisites['valid']:
            logger.debug(
                f"detect_false_breakout: {candles.symbol} - "
                f"Prerequisites not met: {prerequisites['reason']}"
            )
            return None
        
        # Ищем пробой уровня
        breakout_info = _detect_breakout_attempt(
            candles, level, level_index, max_breakout_bars
        )
        if not breakout_info:
            return None
        
        # Проверяем, что это ложный пробой (возврат за уровень)
        return_info = _check_false_breakout_return(
            candles, level, breakout_info, max_breakout_bars
        )
        if not return_info:
            return None
        
        # Проверяем на прилипание (исключаем реальный пробой)
        if _check_sticking_to_level(candles, level, breakout_info, return_info['index']):
            logger.debug(
                f"detect_false_breakout: {candles.symbol} - "
                f"Sticking to level detected (real breakout likely)"
            )
            return None
        
        # Анализируем объемы и волатильность
        volume_analysis = _analyze_breakout_volume(
            candles, breakout_info['index'], lookback_bars
        )
        volatility_analysis = _analyze_breakout_volatility(
            candles, breakout_info['index'], lookback_bars
        )
        
        # Определяем тип ЛП
        breakout_type = _determine_breakout_type(
            candles, level, breakout_info, return_info
        )
        
        # Рассчитываем стоп-лосс
        atr = calculate_atr(candles)
        tail_size_pct = _calculate_tail_size(candles, level, breakout_info, atr)
        stop_loss = _calculate_stop_loss(
            candles, level, breakout_info, return_info, tail_size_pct, atr
        )
        
        # Определяем направление сигнала (противоположно пробою)
        if breakout_info['direction'] == 'UP':
            signal_direction = 'SHORT'
        else:
            signal_direction = 'LONG'
        
        # Вычисляем уверенность
        confidence = _calculate_confidence(
            prerequisites, breakout_info, return_info, volume_analysis,
            volatility_analysis, breakout_type, tail_size_pct, level, atr
        )
        
        # Точка входа - после возврата за уровень
        entry_index = return_info['index']
        
        signal = FalseBreakoutSignal(
            direction=signal_direction,
            breakout_direction=breakout_info['direction'],
            level_price=level.price,
            level_type=level.level_type,
            breakout_type=breakout_type,
            breakout_index=breakout_info['index'],
            return_index=return_info['index'],
            entry_index=entry_index,
            breakout_depth_pct=breakout_info['depth_pct'],
            tail_size_pct=tail_size_pct,
            stop_loss=stop_loss,
            volume_spike_ratio=volume_analysis['ratio'],
            volatility_spike=volatility_analysis['spike'],
            is_valid=True,
            confidence=confidence,
            details=_build_signal_details(
                prerequisites, breakout_info, return_info, volume_analysis,
                volatility_analysis, breakout_type, level
            )
        )
        
        logger.info(
            f"detect_false_breakout: {candles.symbol} - "
            f"False breakout {breakout_type} detected: {breakout_info['direction']} -> {signal_direction}, "
            f"depth: {breakout_info['depth_pct']:.2f}%, confidence: {confidence}%"
        )
        
        return signal
        
    except Exception as e:
        logger.error(f"detect_false_breakout error for {candles.symbol}: {e}", exc_info=True)
        return None


def _find_level_index(candles: NormalizedCandles, level: SupportResistanceLevel) -> Optional[int]:
    """Найти индекс свечи, где был сформирован уровень"""
    if not level.candle_indices:
        return None
    
    # Берем последний индекс касания уровня
    last_touch = max(level.candle_indices)
    
    # Проверяем, что индекс в пределах данных
    if last_touch < len(candles.closes):
        return last_touch
    
    return None


def _check_prerequisites(
        candles: NormalizedCandles,
        level: SupportResistanceLevel,
        level_index: int,
        lookback_bars: int,
        min_level_age_candles: int
) -> dict:
    """
    Проверка предпосылок для ложного пробоя
    
    Предпосылки:
    1. Дальний ретест уровня (месяц+ назад)
    2. Длинное безоткатное движение к уровню
    3. Высокая скорость подхода (большие паранормальные бары)
    4. Отсутствие консолидации у уровня
    """
    from config import config
    
    current_index = len(candles.closes) - 1
    level_age = current_index - level_index
    
    result = {
        'valid': False,
        'reason': '',
        'level_age_candles': level_age,
        'has_trending_move': False,
        'has_fast_approach': False,
        'has_no_consolidation': False,
        'score': 0
    }
    
    # 1. Проверка дальности уровня
    # Для 1H: месяц = ~720 свечей, для 4H: месяц = ~180 свечей
    # Используем минимум 20 свечей как базовый порог
    if level_age < min_level_age_candles:
        result['reason'] = f"Level too recent ({level_age} < {min_level_age_candles} candles)"
        return result
    
    # Бонус за дальний уровень
    if level_age >= 180:  # ~1 месяц на 4H или ~1 неделя на 1H
        result['score'] += 20
    elif level_age >= 60:  # ~1 неделя на 4H
        result['score'] += 10
    
    # 2. Проверка безоткатного движения к уровню
    approach_start = max(0, current_index - lookback_bars)
    approach_candles = candles.closes[approach_start:current_index + 1]
    
    if len(approach_candles) < 10:
        result['reason'] = "Not enough candles for approach analysis"
        return result
    
    # Анализ тренда к уровню
    if level.level_type == 'RESISTANCE':
        # Движение вверх к сопротивлению
        price_change = (approach_candles[-1] - approach_candles[0]) / approach_candles[0] * 100
        # Проверяем, что движение преимущественно вверх с минимальными откатами
        pullbacks = _count_pullbacks(approach_candles, 'UP')
        if price_change > 2.0 and pullbacks <= 2:  # Минимум откатов
            result['has_trending_move'] = True
            result['score'] += 15
    else:  # SUPPORT
        # Движение вниз к поддержке
        price_change = (approach_candles[0] - approach_candles[-1]) / approach_candles[0] * 100
        pullbacks = _count_pullbacks(approach_candles, 'DOWN')
        if price_change > 2.0 and pullbacks <= 2:
            result['has_trending_move'] = True
            result['score'] += 15
    
    # 3. Проверка скорости подхода (большие бары)
    large_bars = _count_large_bars(candles, approach_start, current_index)
    if large_bars >= 3:  # 3-5 больших баров
        result['has_fast_approach'] = True
        result['score'] += 15
    
    # 4. Проверка отсутствия консолидации у уровня
    consolidation_near_level = _check_consolidation_near_level(
        candles, level, current_index, lookback_bars // 2
    )
    if not consolidation_near_level:
        result['has_no_consolidation'] = True
        result['score'] += 10
    
    # Минимальный score для валидности
    if result['score'] >= 20:
        result['valid'] = True
    else:
        result['reason'] = f"Prerequisites score too low: {result['score']}"
    
    return result


def _count_pullbacks(prices: np.ndarray, direction: str) -> int:
    """Подсчитать количество откатов в движении"""
    if len(prices) < 3:
        return 0
    
    pullbacks = 0
    for i in range(1, len(prices) - 1):
        if direction == 'UP':
            # Откат вниз
            if prices[i] < prices[i-1] and prices[i] < prices[i+1]:
                pullbacks += 1
        else:  # DOWN
            # Откат вверх
            if prices[i] > prices[i-1] and prices[i] > prices[i+1]:
                pullbacks += 1
    
    return pullbacks


def _count_large_bars(candles: NormalizedCandles, start: int, end: int) -> int:
    """Подсчитать количество больших (паранормальных) баров"""
    if end <= start:
        return 0
    
    atr = calculate_atr(candles)
    if atr == 0:
        return 0
    
    large_bars = 0
    for i in range(start, min(end, len(candles.closes))):
        bar_range = candles.highs[i] - candles.lows[i]
        if bar_range > atr * 1.5:  # Бар больше 1.5 ATR
            large_bars += 1
    
    return large_bars


def _check_consolidation_near_level(
        candles: NormalizedCandles,
        level: SupportResistanceLevel,
        current_index: int,
        lookback: int
) -> bool:
    """Проверить наличие консолидации у уровня (прилипание)"""
    from config import config
    
    start = max(0, current_index - lookback)
    tolerance_pct = config.SR_TOUCH_TOLERANCE_PCT
    
    # Проверяем, сколько свечей торговались близко к уровню
    near_level_count = 0
    for i in range(start, current_index + 1):
        high = float(candles.highs[i])
        low = float(candles.lows[i])
        close = float(candles.closes[i])
        
        # Проверяем близость к уровню
        if abs(high - level.price) / level.price * 100 <= tolerance_pct or \
           abs(low - level.price) / level.price * 100 <= tolerance_pct or \
           abs(close - level.price) / level.price * 100 <= tolerance_pct:
            near_level_count += 1
    
    # Если много свечей близко к уровню - это консолидация (прилипание)
    # Это признак реального пробоя, а не ложного
    consolidation_threshold = lookback * 0.3  # 30% свечей
    return near_level_count >= consolidation_threshold


def _detect_breakout_attempt(
        candles: NormalizedCandles,
        level: SupportResistanceLevel,
        level_index: int,
        max_bars: int
) -> Optional[dict]:
    """Обнаружить попытку пробоя уровня"""
    from config import config
    
    current_index = len(candles.closes) - 1
    tolerance_pct = config.SR_TOUCH_TOLERANCE_PCT
    
    # Ищем пробой в последних max_bars свечах
    for i in range(max(level_index, current_index - max_bars), current_index + 1):
        high = float(candles.highs[i])
        low = float(candles.lows[i])
        close = float(candles.closes[i])
        
        # Пробой сопротивления вверх
        if level.level_type == 'RESISTANCE' and high > level.price * (1 + tolerance_pct / 100):
            depth_pct = ((high - level.price) / level.price) * 100
            return {
                'index': i,
                'direction': 'UP',
                'depth_pct': depth_pct,
                'high': high,
                'close': close
            }
        
        # Пробой поддержки вниз
        elif level.level_type == 'SUPPORT' and low < level.price * (1 - tolerance_pct / 100):
            depth_pct = ((level.price - low) / level.price) * 100
            return {
                'index': i,
                'direction': 'DOWN',
                'depth_pct': depth_pct,
                'low': low,
                'close': close
            }
    
    return None


def _check_false_breakout_return(
        candles: NormalizedCandles,
        level: SupportResistanceLevel,
        breakout_info: dict,
        max_bars: int
) -> Optional[dict]:
    """Проверить возврат цены за уровень (подтверждение ложного пробоя)"""
    from config import config
    
    tolerance_pct = config.SR_TOUCH_TOLERANCE_PCT
    breakout_index = breakout_info['index']
    
    # Ищем возврат в следующих max_bars свечах
    for i in range(breakout_index + 1, min(breakout_index + max_bars + 1, len(candles.closes))):
        close = float(candles.closes[i])
        high = float(candles.highs[i])
        low = float(candles.lows[i])
        
        # Возврат за сопротивление (цена закрылась ниже уровня)
        if breakout_info['direction'] == 'UP' and level.level_type == 'RESISTANCE':
            if close < level.price * (1 - tolerance_pct / 100):
                return {
                    'index': i,
                    'close': close
                }
        
        # Возврат за поддержку (цена закрылась выше уровня)
        elif breakout_info['direction'] == 'DOWN' and level.level_type == 'SUPPORT':
            if close > level.price * (1 + tolerance_pct / 100):
                return {
                    'index': i,
                    'close': close
                }
    
    return None


def _check_sticking_to_level(
        candles: NormalizedCandles,
        level: SupportResistanceLevel,
        breakout_info: dict,
        return_index: int
) -> bool:
    """Проверить прилипание к уровню (признак реального пробоя)"""
    from config import config
    
    tolerance_pct = config.SR_TOUCH_TOLERANCE_PCT
    breakout_index = breakout_info['index']
    
    # Проверяем свечи между пробоем и возвратом
    for i in range(breakout_index, min(return_index + 1, len(candles.closes))):
        high = float(candles.highs[i])
        low = float(candles.lows[i])
        close = float(candles.closes[i])
        
        # Если цена консолидируется выше/ниже уровня - это прилипание
        if breakout_info['direction'] == 'UP':
            # Прилипание выше уровня
            if close > level.price * (1 + tolerance_pct / 100):
                # Проверяем, что цена не возвращается
                if i < return_index:
                    return True
        else:  # DOWN
            # Прилипание ниже уровня
            if close < level.price * (1 - tolerance_pct / 100):
                if i < return_index:
                    return True
    
    return False


def _analyze_breakout_volume(
        candles: NormalizedCandles,
        breakout_index: int,
        lookback: int
) -> dict:
    """Анализ объемов на пробое (всплески в 5-10 ближайших свечах)"""
    if breakout_index >= len(candles.volumes):
        return {'ratio': 1.0, 'spike_detected': False}
    
    # Анализируем объемы в ближайших 10 свечах
    volume_window = 10
    start = max(0, breakout_index - volume_window)
    end = min(len(candles.volumes), breakout_index + volume_window + 1)
    
    breakout_volumes = candles.volumes[start:end]
    if len(breakout_volumes) == 0:
        return {'ratio': 1.0, 'spike_detected': False}
    
    # Средний объем до пробоя
    before_volumes = candles.volumes[max(0, breakout_index - lookback):breakout_index]
    avg_before = np.mean(before_volumes) if len(before_volumes) > 0 else 1.0
    
    # Максимальный объем в окне пробоя
    max_volume = float(np.max(breakout_volumes))
    
    if avg_before > 0:
        ratio = max_volume / avg_before
        spike_detected = ratio >= 1.5  # Порог всплеска
    else:
        ratio = 1.0
        spike_detected = False
    
    return {
        'ratio': ratio,
        'spike_detected': spike_detected,
        'max_volume': max_volume,
        'avg_before': avg_before
    }


def _analyze_breakout_volatility(
        candles: NormalizedCandles,
        breakout_index: int,
        lookback: int
) -> dict:
    """Анализ волатильности на пробое"""
    if breakout_index >= len(candles.closes):
        return {'spike': 0.0, 'detected': False}
    
    # ATR до пробоя
    atr_before = calculate_atr(candles)
    
    # Волатильность на пробое (диапазон свечи)
    if breakout_index < len(candles.highs):
        bar_range = float(candles.highs[breakout_index] - candles.lows[breakout_index])
        
        if atr_before > 0:
            spike_ratio = bar_range / atr_before
            detected = spike_ratio >= 1.5  # Резкое увеличение
        else:
            spike_ratio = 0.0
            detected = False
    else:
        spike_ratio = 0.0
        detected = False
    
    return {
        'spike': spike_ratio,
        'detected': detected
    }


def _determine_breakout_type(
        candles: NormalizedCandles,
        level: SupportResistanceLevel,
        breakout_info: dict,
        return_info: dict
) -> Literal['SIMPLE', 'TWO_BARS', 'MULTI_BAR']:
    """Определить тип ложного пробоя"""
    breakout_idx = breakout_info['index']
    return_idx = return_info['index']
    
    bars_count = return_idx - breakout_idx + 1
    
    if bars_count == 1:
        # Простой ЛП (одним баром) - шпилька
        return 'SIMPLE'
    elif bars_count == 2:
        # ЛП двумя барами
        return 'TWO_BARS'
    else:
        # ЛП N барами (консолидация выше/ниже уровня)
        return 'MULTI_BAR'


def _calculate_tail_size(
        candles: NormalizedCandles,
        level: SupportResistanceLevel,
        breakout_info: dict,
        atr: float
) -> float:
    """Рассчитать размер хвоста пробойной свечи в % от ATR"""
    if atr == 0:
        return 0.0
    
    idx = breakout_info['index']
    if idx >= len(candles.highs):
        return 0.0
    
    high = float(candles.highs[idx])
    low = float(candles.lows[idx])
    close = float(candles.closes[idx])
    open_price = float(candles.opens[idx])
    
    if breakout_info['direction'] == 'UP':
        # Хвост вверх (high - max(open, close))
        tail = high - max(open_price, close)
    else:  # DOWN
        # Хвост вниз (min(open, close) - low)
        tail = min(open_price, close) - low
    
    if atr > 0:
        tail_pct = (tail / atr) * 100
    else:
        tail_pct = 0.0
    
    return tail_pct


def _calculate_stop_loss(
        candles: NormalizedCandles,
        level: SupportResistanceLevel,
        breakout_info: dict,
        return_info: dict,
        tail_size_pct: float,
        atr: float
) -> float:
    """Рассчитать стоп-лосс"""
    from config import config
    
    entry_idx = return_info['index']
    if entry_idx >= len(candles.closes):
        entry_price = float(candles.closes[-1])
    else:
        entry_price = float(candles.closes[entry_idx])
    
    # Если хвост короткий (10-15% ATR), стоп за хвостом
    if tail_size_pct <= 15.0 and tail_size_pct > 0:
        breakout_idx = breakout_info['index']
        if breakout_info['direction'] == 'UP':
            # Стоп за максимумом пробойной свечи
            stop_loss = float(candles.highs[breakout_idx]) * 1.001  # Небольшой буфер
        else:  # DOWN
            # Стоп за минимумом пробойной свечи
            stop_loss = float(candles.lows[breakout_idx]) * 0.999
    else:
        # Стоп за уровнем
        if breakout_info['direction'] == 'UP':
            # Для шорта стоп выше уровня
            stop_loss = level.price * 1.002  # Небольшой буфер
        else:  # DOWN
            # Для лонга стоп ниже уровня
            stop_loss = level.price * 0.998
    
    return stop_loss


def _calculate_confidence(
        prerequisites: dict,
        breakout_info: dict,
        return_info: dict,
        volume_analysis: dict,
        volatility_analysis: dict,
        breakout_type: str,
        tail_size_pct: float,
        level: SupportResistanceLevel,
        atr: float
) -> int:
    """Вычислить уверенность в сигнале"""
    from config import config
    
    confidence = config.FALSE_BREAKOUT_BASE_CONFIDENCE
    
    # Бонус за предпосылки
    confidence += prerequisites['score']
    
    # Бонус за всплеск объема
    if volume_analysis['spike_detected']:
        if volume_analysis['ratio'] >= 2.0:
            confidence += config.FALSE_BREAKOUT_VOLUME_RATIO_BONUS_2_0
        elif volume_analysis['ratio'] >= 1.5:
            confidence += config.FALSE_BREAKOUT_VOLUME_RATIO_BONUS_1_5
    
    # Бонус за всплеск волатильности
    if volatility_analysis['detected']:
        confidence += 10
    
    # Бонус за тип ЛП
    if breakout_type == 'SIMPLE':
        confidence += 10  # Простой ЛП - самый надежный
    elif breakout_type == 'TWO_BARS':
        confidence += 5
    
    # Бонус за короткий хвост (10-15% ATR)
    if 10.0 <= tail_size_pct <= 15.0:
        confidence += 15
    elif tail_size_pct < 10.0:
        confidence += 10
    
    # Бонус за силу уровня
    if level.touches >= 5:
        confidence += 10
    elif level.touches >= 3:
        confidence += 5
    
    # Бонус за быстрый возврат
    return_speed = return_info['index'] - breakout_info['index']
    if return_speed <= 2:
        confidence += 15
    elif return_speed <= 3:
        confidence += 10
    elif return_speed <= 5:
        confidence += 5
    
    # Ограничиваем уверенность
    confidence = min(100, max(0, confidence))
    
    return confidence


def _build_signal_details(
        prerequisites: dict,
        breakout_info: dict,
        return_info: dict,
        volume_analysis: dict,
        volatility_analysis: dict,
        breakout_type: str,
        level: SupportResistanceLevel
) -> str:
    """Построить детальное описание сигнала"""
    parts = [
        f"Type: {breakout_type}",
        f"Level: {level.level_type} @ {level.price:.4f} ({level.touches} touches)",
        f"Breakout depth: {breakout_info['depth_pct']:.2f}%",
        f"Return speed: {return_info['index'] - breakout_info['index']} bars"
    ]
    
    if volume_analysis['spike_detected']:
        parts.append(f"Volume spike: {volume_analysis['ratio']:.2f}x")
    
    if volatility_analysis['detected']:
        parts.append(f"Volatility spike: {volatility_analysis['spike']:.2f}x")
    
    parts.append(f"Prerequisites score: {prerequisites['score']}")
    
    return "; ".join(parts)
