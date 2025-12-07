"""
Stage 1: Signal Filtering - LEVELS + ATR Strategy (FIXED DISTANCE CHECK)
Файл: stages/stage1_filter.py

✅ ИСПРАВЛЕНО:
- Более строгий фильтр расстояния до уровня (< 1.5% вместо < 2%)
- Проверка наличия уровня ДО scoring
- Детальное логирование причин reject
"""

import logging
from typing import List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SignalCandidate:
    """Кандидат сигнала после Stage 1"""
    symbol: str
    direction: str
    confidence: int
    sr_analysis: 'SupportResistanceAnalysis'
    wave_analysis: 'WaveAnalysis'
    ema200_context: dict
    volume_analysis: 'VolumeAnalysis'
    rsi_value: float
    pattern_type: str


async def run_stage1(
        pairs: List[str],
        min_confidence: Optional[int] = None,
        min_volume_ratio: Optional[float] = None
) -> List[SignalCandidate]:
    """
    Stage 1: Фильтрация пар по стратегии Уровни + ATR

    ✅ ИСПРАВЛЕНО: Строгий фильтр расстояния до уровня
    """
    from data_providers import fetch_multiple_candles, normalize_candles
    from indicators import (
        analyze_support_resistance,
        analyze_waves_atr,
        analyze_ema200,
        analyze_volume,
        calculate_rsi
    )
    from config import config
    import time

    # ✅ Используем значения из config если не указаны
    if min_confidence is None:
        min_confidence = config.MIN_CONFIDENCE
    if min_volume_ratio is None:
        min_volume_ratio = config.MIN_VOLUME_RATIO

    if not pairs:
        logger.warning("Stage 1: No pairs provided")
        return []

    logger.info(f"Stage 1 (LEVELS+ATR): Analyzing {len(pairs)} pairs")
    start_time = time.time()

    # Batch loading 4H candles
    # ✅ Используем настройку из config
    candles_limit = config.QUICK_SCAN_CANDLES
    requests = [
        {'symbol': symbol, 'interval': config.TIMEFRAME_LONG, 'limit': candles_limit}
        for symbol in pairs
    ]
    batch_results = await fetch_multiple_candles(requests)

    load_time = time.time() - start_time
    logger.info(f"Stage 1: Loaded {len(batch_results)}/{len(pairs)} pairs in {load_time:.1f}s")

    if not batch_results:
        logger.warning("Stage 1: No valid candles loaded")
        return []

    candidates = []
    processed = 0
    stats = {
        'invalid': 0,
        'no_levels': 0,
        'level_too_far': 0,  # ✅ НОВАЯ КАТЕГОРИЯ
        'low_confidence': 0,
        'low_volume': 0,
        'rsi_extreme': 0,
        'overextension': 0
    }

    for result in batch_results:
        if not result.get('success'):
            continue

        symbol = result['symbol']
        candles_raw = result['klines']

        try:
            processed += 1
            candles = normalize_candles(candles_raw, symbol=symbol, interval=config.TIMEFRAME_LONG)

            if not candles or not candles.is_valid:
                stats['invalid'] += 1
                continue

            current_price = float(candles.closes[-1])

            # ============================================================
            # SUPPORT/RESISTANCE LEVELS (оптимизированные параметры)
            # ============================================================
            sr_analysis = analyze_support_resistance(
                candles,
                current_price,
                signal_direction='UNKNOWN'
            )

            if not sr_analysis or len(sr_analysis.all_levels) == 0:
                stats['no_levels'] += 1
                logger.debug(f"Stage 1: {symbol} - No S/R levels found")
                continue

            # ✅ КРИТИЧНО: Проверяем расстояние до ближайшего уровня ДО дальнейшего анализа
            nearest_support = sr_analysis.nearest_support
            nearest_resistance = sr_analysis.nearest_resistance

            # Проверка для LONG: есть ли поддержка рядом
            long_level_ok = (
                nearest_support is not None and
                nearest_support.distance_from_current_pct <= config.SR_LEVEL_MAX_DISTANCE_PCT
            )

            # Проверка для SHORT: есть ли сопротивление рядом
            short_level_ok = (
                nearest_resistance is not None and
                nearest_resistance.distance_from_current_pct <= config.SR_LEVEL_MAX_DISTANCE_PCT
            )

            # Если НИ ТО НИ ТО - пропускаем
            if not long_level_ok and not short_level_ok:
                stats['level_too_far'] += 1

                long_dist = nearest_support.distance_from_current_pct if nearest_support else 999
                short_dist = nearest_resistance.distance_from_current_pct if nearest_resistance else 999

                logger.debug(
                    f"Stage 1: {symbol} - Levels too far "
                    f"(support: {long_dist:.2f}%, resistance: {short_dist:.2f}%)"
                )
                continue

            # ============================================================
            # ATR WAVE ANALYSIS
            # ============================================================
            wave_analysis = analyze_waves_atr(candles, num_waves=config.WAVE_ANALYSIS_NUM_WAVES)

            # ============================================================
            # EMA200 CONTEXT
            # ============================================================
            ema200_context = analyze_ema200(candles)

            # ============================================================
            # VOLUME + RSI
            # ============================================================
            volume_analysis = analyze_volume(candles, window=config.VOLUME_WINDOW)
            if not volume_analysis:
                stats['invalid'] += 1
                continue

            if volume_analysis.volume_ratio_current < min_volume_ratio:
                stats['low_volume'] += 1
                continue

            rsi_values = calculate_rsi(candles.closes, config.RSI_PERIOD)
            current_rsi = float(rsi_values[-1])

            # RSI блокировка только при ЭКСТРЕМАЛЬНЫХ значениях
            if current_rsi > config.RSI_EXTREME_HIGH or current_rsi < config.RSI_EXTREME_LOW:
                stats['rsi_extreme'] += 1
                logger.debug(f"Stage 1: {symbol} skipped - RSI extreme ({current_rsi:.1f})")
                continue

            # ============================================================
            # ОПРЕДЕЛЯЕМ НАПРАВЛЕНИЕ + CONFIDENCE
            # ============================================================
            direction, confidence, pattern_type, rejection_reason = _determine_level_signal(
                sr_analysis, wave_analysis, ema200_context,
                current_rsi, volume_analysis,
                long_level_ok, short_level_ok  # ✅ Передаём флаги уровней
            )

            if direction == 'NONE':
                if 'overextension' in rejection_reason.lower():
                    stats['overextension'] += 1
                elif 'too far' in rejection_reason.lower():
                    stats['level_too_far'] += 1
                else:
                    stats['no_levels'] += 1

                logger.debug(f"Stage 1: {symbol} - {rejection_reason}")
                continue

            if confidence < min_confidence:
                stats['low_confidence'] += 1
                logger.debug(f"Stage 1: {symbol} skipped (confidence {confidence} < {min_confidence})")
                continue

            # ============================================================
            # СОЗДАЁМ КАНДИДАТА
            # ============================================================
            candidate = SignalCandidate(
                symbol=symbol,
                direction=direction,
                confidence=confidence,
                sr_analysis=sr_analysis,
                wave_analysis=wave_analysis,
                ema200_context=ema200_context,
                volume_analysis=volume_analysis,
                rsi_value=current_rsi,
                pattern_type=pattern_type
            )

            candidates.append(candidate)

            # Детальное логирование для отладки
            level_dist = (
                sr_analysis.nearest_support.distance_from_current_pct
                if direction == 'LONG' and sr_analysis.nearest_support
                else sr_analysis.nearest_resistance.distance_from_current_pct
                if direction == 'SHORT' and sr_analysis.nearest_resistance
                else 0
            )

            logger.info(
                f"Stage 1: ✓ {symbol} {direction} "
                f"(confidence: {confidence}%, pattern: {pattern_type}, "
                f"level_distance: {level_dist:.2f}%)"
            )

        except Exception as e:
            logger.debug(f"Stage 1: Error processing {symbol}: {e}")
            stats['invalid'] += 1
            continue

    # Сортируем по confidence
    candidates.sort(key=lambda x: x.confidence, reverse=True)
    total_time = time.time() - start_time

    # СТАТИСТИКА
    logger.info("=" * 70)
    logger.info("STAGE 1 (LEVELS+ATR) COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Total time: {total_time:.1f}s")
    logger.info(f"Processed: {processed} pairs")
    logger.info(f"✅ Signals found: {len(candidates)}")
    logger.info(f"❌ Skipped breakdown:")
    logger.info(f"   • Invalid data: {stats['invalid']}")
    logger.info(f"   • No S/R levels: {stats['no_levels']}")
    logger.info(f"   • Level too far (>{config.SR_LEVEL_MAX_DISTANCE_PCT}%): {stats['level_too_far']}")  # ✅ НОВОЕ
    logger.info(f"   • Low confidence: {stats['low_confidence']}")
    logger.info(f"   • Low volume: {stats['low_volume']}")
    logger.info(f"   • RSI extreme: {stats['rsi_extreme']}")
    logger.info(f"   • Overextension: {stats['overextension']}")

    if candidates:
        logger.info(f"\n📊 Pattern distribution:")
        pattern_counts = {}
        for c in candidates:
            pattern_counts[c.pattern_type] = pattern_counts.get(c.pattern_type, 0) + 1

        for pattern, count in sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"   • {pattern}: {count}")

        logger.info(f"\nTop 10 candidates:")
        for i, c in enumerate(candidates[:10], 1):
            level_dist = (
                c.sr_analysis.nearest_support.distance_from_current_pct
                if c.direction == 'LONG' and c.sr_analysis.nearest_support
                else c.sr_analysis.nearest_resistance.distance_from_current_pct
                if c.direction == 'SHORT' and c.sr_analysis.nearest_resistance
                else 0
            )
            logger.info(
                f"  {i}. {c.symbol} {c.direction} "
                f"(conf: {c.confidence}%, {c.pattern_type}, dist: {level_dist:.2f}%)"
            )

    logger.info("=" * 70)

    return candidates


def _determine_level_signal(
        sr_analysis: 'SupportResistanceAnalysis',
        wave_analysis: 'WaveAnalysis',
        ema200_context: dict,
        rsi: float,
        volume_analysis: 'VolumeAnalysis',
        long_level_ok: bool,  # ✅ НОВЫЙ ПАРАМЕТР
        short_level_ok: bool  # ✅ НОВЫЙ ПАРАМЕТР
) -> tuple[str, int, str, str]:
    """
    Определить сигнал на основе уровней + ATR

    ✅ ИСПРАВЛЕНО: Учитываем флаги long_level_ok/short_level_ok
    """
    from config import config

    MIN_SCORE = config.STAGE1_MIN_SCORE

    # ============================================================
    # БЫЧИЙ ПАТТЕРН (LONG)
    # ============================================================
    bullish_score = 0
    bullish_details = []

    if long_level_ok:  # ✅ Проверяем флаг ПЕРЕД скорингом
        nearest_support = sr_analysis.nearest_support

        # Качество уровня
        if nearest_support.touches >= config.SR_LEVEL_TOUCHES_PREMIUM:
            bullish_score += config.SR_TOUCHES_PREMIUM_SCORE
            bullish_details.append(f"Premium support ({nearest_support.touches} touches)")
        elif nearest_support.touches >= config.SR_LEVEL_TOUCHES_STRONG:
            bullish_score += config.SR_TOUCHES_STRONG_SCORE
            bullish_details.append(f"Strong support ({nearest_support.touches} touches)")
        elif nearest_support.touches >= config.SR_LEVEL_TOUCHES_VALID:
            bullish_score += config.SR_TOUCHES_VALID_SCORE
            bullish_details.append(f"Valid support ({nearest_support.touches} touches)")

        # Расстояние до уровня (ужесточено)
        distance = nearest_support.distance_from_current_pct
        if distance < config.SR_LEVEL_IDEAL_DISTANCE_PCT:
            bullish_score += config.SR_DISTANCE_IDEAL_SCORE
            bullish_details.append(f"Ideal entry (<{config.SR_LEVEL_IDEAL_DISTANCE_PCT}%)")
        elif distance < config.SR_LEVEL_NEAR_DISTANCE_PCT:
            bullish_score += config.SR_DISTANCE_GOOD_SCORE
            bullish_details.append(f"Good entry (<{config.SR_LEVEL_NEAR_DISTANCE_PCT}%)")
        elif distance < config.SR_LEVEL_MAX_DISTANCE_PCT:
            bullish_score += config.SR_DISTANCE_ACCEPTABLE_SCORE
            bullish_details.append(f"Acceptable entry (<{config.SR_LEVEL_MAX_DISTANCE_PCT}%)")
        else:
            bullish_details.append(f"Too far from support ({distance:.1f}%)")

    # ATR Wave Analysis
    if wave_analysis:
        if wave_analysis.wave_type == 'BULLISH':
            if wave_analysis.is_early_entry:
                bullish_score += config.WAVE_EARLY_ENTRY_SCORE
                bullish_details.append(f"Early entry ({wave_analysis.current_wave_progress:.0f}% of ATR)")
            elif wave_analysis.current_wave_progress < config.WAVE_GOOD_ENTRY_THRESHOLD:
                bullish_score += config.WAVE_GOOD_ENTRY_SCORE
                bullish_details.append(f"Good entry ({wave_analysis.current_wave_progress:.0f}% of ATR)")
            elif wave_analysis.current_wave_progress < config.WAVE_LATE_ENTRY_THRESHOLD:
                bullish_score += config.WAVE_LATE_ENTRY_SCORE
            else:
                bullish_score += config.WAVE_TOO_LATE_PENALTY
                bullish_details.append(f"Late entry ({wave_analysis.current_wave_progress:.0f}%)")

    # EMA200 alignment
    if ema200_context['price_above_ema200']:
        bullish_score += config.EMA200_ALIGNMENT_BONUS
        bullish_details.append("Above EMA200 (bullish trend)")

        # Проверка overextension
        distance_ema = ema200_context['distance_pct']
        if distance_ema > config.EMA200_OVEREXTENDED_PCT:
            bullish_score += config.EMA200_OVEREXTENDED_PENALTY
            bullish_details.append(f"OVEREXTENDED from EMA200 ({distance_ema:.1f}%)")
        elif distance_ema > config.EMA200_EXTENDED_PCT:
            bullish_score += config.EMA200_EXTENDED_PENALTY

    # RSI optimal
    if config.RSI_OPTIMAL_LONG_MIN <= rsi <= config.RSI_OPTIMAL_LONG_MAX:
        bullish_score += config.RSI_OPTIMAL_BONUS
    elif rsi > config.RSI_OVERBOUGHT:
        bullish_score += config.RSI_EXTREME_PENALTY

    # Volume
    vol_ratio = volume_analysis.volume_ratio_current
    if vol_ratio > config.VOLUME_SPIKE_THRESHOLD:
        bullish_score += config.VOLUME_SPIKE_SCORE
        bullish_details.append(f"Strong volume ({vol_ratio:.1f}x)")
    elif vol_ratio > config.VOLUME_STRONG_THRESHOLD:
        bullish_score += config.VOLUME_STRONG_SCORE
    elif vol_ratio > config.VOLUME_GOOD_THRESHOLD:
        bullish_score += config.VOLUME_GOOD_SCORE

    # ============================================================
    # МЕДВЕЖИЙ ПАТТЕРН (SHORT)
    # ============================================================
    bearish_score = 0
    bearish_details = []

    if short_level_ok:  # ✅ Проверяем флаг ПЕРЕД скорингом
        nearest_resistance = sr_analysis.nearest_resistance

        # Качество уровня
        if nearest_resistance.touches >= config.SR_LEVEL_TOUCHES_PREMIUM:
            bearish_score += config.SR_TOUCHES_PREMIUM_SCORE
            bearish_details.append(f"Premium resistance ({nearest_resistance.touches} touches)")
        elif nearest_resistance.touches >= config.SR_LEVEL_TOUCHES_STRONG:
            bearish_score += config.SR_TOUCHES_STRONG_SCORE
            bearish_details.append(f"Strong resistance ({nearest_resistance.touches} touches)")
        elif nearest_resistance.touches >= config.SR_LEVEL_TOUCHES_VALID:
            bearish_score += config.SR_TOUCHES_VALID_SCORE
            bearish_details.append(f"Valid resistance ({nearest_resistance.touches} touches)")

        # Расстояние до уровня (ужесточено)
        distance = nearest_resistance.distance_from_current_pct
        if distance < config.SR_LEVEL_IDEAL_DISTANCE_PCT:
            bearish_score += config.SR_DISTANCE_IDEAL_SCORE
            bearish_details.append(f"Ideal entry (<{config.SR_LEVEL_IDEAL_DISTANCE_PCT}%)")
        elif distance < config.SR_LEVEL_NEAR_DISTANCE_PCT:
            bearish_score += config.SR_DISTANCE_GOOD_SCORE
            bearish_details.append(f"Good entry (<{config.SR_LEVEL_NEAR_DISTANCE_PCT}%)")
        elif distance < config.SR_LEVEL_MAX_DISTANCE_PCT:
            bearish_score += config.SR_DISTANCE_ACCEPTABLE_SCORE
            bearish_details.append(f"Acceptable entry (<{config.SR_LEVEL_MAX_DISTANCE_PCT}%)")
        else:
            bearish_details.append(f"Too far from resistance ({distance:.1f}%)")

    # ATR Wave Analysis
    if wave_analysis:
        if wave_analysis.wave_type == 'BEARISH':
            if wave_analysis.is_early_entry:
                bearish_score += config.WAVE_EARLY_ENTRY_SCORE
                bearish_details.append(f"Early entry ({wave_analysis.current_wave_progress:.0f}% of ATR)")
            elif wave_analysis.current_wave_progress < config.WAVE_GOOD_ENTRY_THRESHOLD:
                bearish_score += config.WAVE_GOOD_ENTRY_SCORE
                bearish_details.append(f"Good entry ({wave_analysis.current_wave_progress:.0f}% of ATR)")
            elif wave_analysis.current_wave_progress < config.WAVE_LATE_ENTRY_THRESHOLD:
                bearish_score += config.WAVE_LATE_ENTRY_SCORE
            else:
                bearish_score += config.WAVE_TOO_LATE_PENALTY
                bearish_details.append(f"Late entry ({wave_analysis.current_wave_progress:.0f}%)")

    # EMA200 alignment
    if not ema200_context['price_above_ema200']:
        bearish_score += config.EMA200_ALIGNMENT_BONUS
        bearish_details.append("Below EMA200 (bearish trend)")

        # Проверка overextension
        distance_ema = ema200_context['distance_pct']
        if distance_ema > config.EMA200_OVEREXTENDED_PCT:
            bearish_score += config.EMA200_OVEREXTENDED_PENALTY
            bearish_details.append(f"OVEREXTENDED from EMA200 ({distance_ema:.1f}%)")
        elif distance_ema > config.EMA200_EXTENDED_PCT:
            bearish_score += config.EMA200_EXTENDED_PENALTY

    # RSI optimal
    if config.RSI_OPTIMAL_SHORT_MIN <= rsi <= config.RSI_OPTIMAL_SHORT_MAX:
        bearish_score += config.RSI_OPTIMAL_BONUS
    elif rsi < config.RSI_OVERSOLD:
        bearish_score += config.RSI_EXTREME_PENALTY

    # Volume
    if vol_ratio > config.VOLUME_SPIKE_THRESHOLD:
        bearish_score += config.VOLUME_SPIKE_SCORE
        bearish_details.append(f"Strong volume ({vol_ratio:.1f}x)")
    elif vol_ratio > config.VOLUME_STRONG_THRESHOLD:
        bearish_score += config.VOLUME_STRONG_SCORE
    elif vol_ratio > config.VOLUME_GOOD_THRESHOLD:
        bearish_score += config.VOLUME_GOOD_SCORE

    # ============================================================
    # РЕШЕНИЕ
    # ============================================================

    if bullish_score < MIN_SCORE and bearish_score < MIN_SCORE:
        return 'NONE', 0, 'NO_PATTERN', f'Both scores below minimum: L={bullish_score}, S={bearish_score}'

    if bullish_score >= MIN_SCORE and bearish_score >= MIN_SCORE:
        score_diff = abs(bullish_score - bearish_score)
        if score_diff < config.STAGE1_CONFLICTING_SCORE_DIFF:
            return 'NONE', 0, 'CONFLICTING', f'Both strong (L:{bullish_score}, S:{bearish_score})'

    if bullish_score > bearish_score:
        direction = 'LONG'
        confidence = min(config.STAGE1_MAX_CONFIDENCE, config.STAGE1_BASE_CONFIDENCE + bullish_score)

        if bullish_score >= config.STAGE1_PERFECT_PATTERN_SCORE:
            pattern_type = 'PERFECT_LEVEL'
        elif bullish_score >= config.STAGE1_STRONG_PATTERN_SCORE:
            pattern_type = 'STRONG_LEVEL'
        else:
            pattern_type = 'MODERATE_LEVEL'

        logger.debug(f"LONG signal: score={bullish_score}, details={bullish_details}")

    else:
        direction = 'SHORT'
        confidence = min(config.STAGE1_MAX_CONFIDENCE, config.STAGE1_BASE_CONFIDENCE + bearish_score)

        if bearish_score >= config.STAGE1_PERFECT_PATTERN_SCORE:
            pattern_type = 'PERFECT_LEVEL'
        elif bearish_score >= config.STAGE1_STRONG_PATTERN_SCORE:
            pattern_type = 'STRONG_LEVEL'
        else:
            pattern_type = 'MODERATE_LEVEL'

        logger.debug(f"SHORT signal: score={bearish_score}, details={bearish_details}")

    return direction, confidence, pattern_type, ''