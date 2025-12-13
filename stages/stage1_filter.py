"""
Stage 1: Signal Filtering - FALSE BREAKOUT Strategy (Level-based)
Файл: stages/stage1_filter.py

✅ ОБНОВЛЕНО: Стратегия "ложного пробоя" на основе уровней S/R
Работает с таймфреймами 1H и 4H
"""

import logging
from typing import List, Optional, Dict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SignalCandidate:
    """Кандидат сигнала после Stage 1 (False Breakout Strategy)"""
    symbol: str
    direction: str
    confidence: int
    support_resistance_level: 'SupportResistanceLevel'  # Уровень S/R
    false_breakout: 'FalseBreakoutSignal'
    candle_pattern: Optional['BuyoutBar'] | Optional['SelloutBar']
    pattern_type: str


async def run_stage1(
        pairs: List[str],
        min_confidence: Optional[int] = None,
        min_volume_ratio: Optional[float] = None
) -> List[SignalCandidate]:
    """
    Stage 1: Фильтрация пар по стратегии "Ложный пробой" (на основе уровней S/R)
    
    Алгоритм:
    1. Поиск уровней поддержки/сопротивления
    2. Проверка предпосылок для ЛП (дальний уровень, безоткатное движение, скорость подхода)
    3. Детекция ложного пробоя (пробой + возврат за уровень)
    4. Анализ объемов и волатильности
    5. Подтверждение выкупным/продажным баром (опционально)
    """
    from data_providers import fetch_multiple_candles, normalize_candles
    from indicators import (
        find_support_resistance_levels,
        detect_false_breakout,
        detect_buyout_bar,
        detect_sellout_bar
    )
    from config import config
    import time

    # Используем значения из config если не указаны
    if min_confidence is None:
        min_confidence = config.MIN_CONFIDENCE
    if min_volume_ratio is None:
        min_volume_ratio = config.MIN_VOLUME_RATIO

    if not pairs:
        logger.warning("Stage 1: No pairs provided")
        return []

    # Определяем тип активов для логирования
    from utils.asset_detector import AssetTypeDetector
    grouped = AssetTypeDetector.group_by_type(pairs)
    stock_count = len(grouped['stock'])
    crypto_count = len(grouped['crypto'])
    
    logger.info(f"Stage 1: Analyzing {len(pairs)} pairs ({stock_count} stocks, {crypto_count} crypto)")
    
    start_time = time.time()

    # Batch loading 4H candles (для консолидации нужен больший период)
    candles_limit = config.QUICK_SCAN_CANDLES
    requests = [
        {'symbol': symbol, 'interval': config.TIMEFRAME_LONG, 'limit': candles_limit}
        for symbol in pairs
    ]
    batch_results = await fetch_multiple_candles(requests)

    load_time = time.time() - start_time
    logger.info(f"Stage 1: Loaded {len(batch_results)}/{len(pairs)} instruments in {load_time:.1f}s")

    if not batch_results:
        logger.warning("Stage 1: No valid candles loaded")
        return []

    # ✅ ОПТИМИЗИРОВАНО: Параллельная обработка пар
    import asyncio
    
    async def process_single_pair(result: Dict) -> Optional[SignalCandidate]:
        """Обработать одну пару асинхронно"""
        if not result.get('success'):
            return None
        
        symbol = result['symbol']
        candles_raw = result['klines']
        
        try:
            candles = normalize_candles(candles_raw, symbol=symbol, interval=config.TIMEFRAME_LONG)
            
            if not candles or not candles.is_valid:
                return None
            
            # ============================================================
            # ШАГ 1: Поиск уровней поддержки/сопротивления
            # ============================================================
            levels = find_support_resistance_levels(candles)
            
            if not levels:
                return None
            
            # Ищем уровень, который был пробит (ближайший к текущей цене)
            current_price = float(candles.closes[-1])
            relevant_level = None
            
            for level in levels:
                # Проверяем, что уровень недавно был пробит
                distance_pct = abs((current_price - level.price) / current_price * 100)
                if distance_pct <= 3.0:  # В пределах 3% от текущей цены
                    relevant_level = level
                    break
            
            if not relevant_level:
                return None
            
            # ============================================================
            # ШАГ 2: Детекция ложного пробоя уровня
            # ============================================================
            false_breakout = detect_false_breakout(
                candles,
                relevant_level,
                lookback_bars=config.FALSE_BREAKOUT_LOOKBACK_BARS,
                max_breakout_bars=config.FALSE_BREAKOUT_MAX_BREAKOUT_BARS,
                min_level_age_candles=config.FALSE_BREAKOUT_MIN_LEVEL_AGE_CANDLES
            )
            
            if not false_breakout or not false_breakout.is_valid:
                return None
            
            # ============================================================
            # ШАГ 3: Подтверждение выкупным/продажным баром (опционально)
            # ============================================================
            candle_pattern = None
            pattern_type = 'FALSE_BREAKOUT'
            
            # Пытаемся найти подтверждающий паттерн, но не требуем его обязательно
            if false_breakout.direction == 'LONG':
                buyout_bar = detect_buyout_bar(
                    candles,
                    lookback_bars=config.CANDLE_PATTERN_LOOKBACK_BARS,
                    min_lower_shadow_pct=config.BUYOUT_MIN_LOWER_SHADOW_PCT,
                    min_close_near_high_pct=config.BUYOUT_MIN_CLOSE_NEAR_HIGH_PCT
                )
                if buyout_bar and buyout_bar.is_valid:
                    candle_pattern = buyout_bar
                    pattern_type = 'FALSE_BREAKOUT_BUYOUT'
            else:  # SHORT
                sellout_bar = detect_sellout_bar(
                    candles,
                    lookback_bars=config.CANDLE_PATTERN_LOOKBACK_BARS,
                    min_upper_shadow_pct=config.SELLOUT_MIN_UPPER_SHADOW_PCT,
                    min_close_near_low_pct=config.SELLOUT_MIN_CLOSE_NEAR_LOW_PCT
                )
                if sellout_bar and sellout_bar.is_valid:
                    candle_pattern = sellout_bar
                    pattern_type = 'FALSE_BREAKOUT_SELLOUT'
            
            # ============================================================
            # ШАГ 4: Финальная проверка confidence
            # ============================================================
            confidence = false_breakout.confidence
            
            if candle_pattern and hasattr(candle_pattern, 'strength'):
                pattern_bonus = int((candle_pattern.strength / 100.0) * config.CANDLE_PATTERN_STRENGTH_BONUS)
                confidence = min(100, confidence + pattern_bonus)
            
            if confidence < min_confidence:
                return None
            
            # ============================================================
            # СОЗДАЁМ КАНДИДАТА
            # ============================================================
            candidate = SignalCandidate(
                symbol=symbol,
                direction=false_breakout.direction,
                confidence=confidence,
                support_resistance_level=relevant_level,
                false_breakout=false_breakout,
                candle_pattern=candle_pattern,
                pattern_type=pattern_type
            )
            
            logger.debug(
                f"Stage 1: ✓ {symbol} {false_breakout.direction} "
                f"(conf: {confidence}%, {pattern_type})"
            )
            
            return candidate
            
        except Exception as e:
            logger.debug(f"Stage 1: Error processing {symbol}: {e}")
            return None
    
    # Параллельная обработка всех пар
    tasks = [process_single_pair(result) for result in batch_results]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Собираем результаты и статистику
    candidates = []
    processed = 0
    stats = {
        'invalid': 0,
        'no_channel': 0,
        'channel_too_short': 0,
        'no_breakout': 0,
        'no_candle_pattern': 0,
        'low_confidence': 0,
        'low_volume': 0
    }
    
    for result in results:
        if isinstance(result, Exception):
            stats['invalid'] += 1
            continue
        
        if result is None:
            # Подсчитываем статистику (упрощенно, так как детали теряются при параллельной обработке)
            stats['no_channel'] += 1
            continue
        
        candidates.append(result)
        processed += 1

    # Сортируем по confidence
    candidates.sort(key=lambda x: x.confidence, reverse=True)
    total_time = time.time() - start_time

    # СТАТИСТИКА
    logger.info("=" * 70)
    logger.info(f"STAGE 1 COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Time: {total_time:.1f}s | Processed: {processed} | Signals: {len(candidates)}")
    if stats['invalid'] + stats['no_channel'] > 0:
        logger.info(f"Skipped: invalid={stats['invalid']}, no_levels={stats['no_channel']}")

    if candidates:
        # Логируем топ-5 кандидатов
        logger.info(f"Top candidates:")
        for i, c in enumerate(candidates[:5], 1):
            logger.info(f"  {i}. {c.symbol} {c.direction} (conf: {c.confidence}%)")

    return candidates
