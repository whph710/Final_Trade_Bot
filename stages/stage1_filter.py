"""
Stage 1: Signal Filtering - LEVELS + ATR Strategy
Файл: stages/stage1_filter.py

✅ НОВАЯ СТРАТЕГИЯ:
- Уровни поддержки/сопротивления (метод "3 удара")
- ATR для расчёта волн
- EMA200 для контекста тренда
- Объёмы как ключевой фильтр
"""

import logging
from typing import List
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
        min_confidence: int = 60,
        min_volume_ratio: float = 1.0
) -> List[SignalCandidate]:
    """
    Stage 1: Фильтрация пар по стратегии Уровни + ATR

    Args:
        pairs: Список торговых пар
        min_confidence: Минимальный confidence (default 60)
        min_volume_ratio: Минимальный volume ratio (default 1.0)

    Returns:
        Список SignalCandidate с confidence >= min_confidence
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

    if not pairs:
        logger.warning("Stage 1: No pairs provided")
        return []

    logger.info(f"Stage 1 (LEVELS+ATR): Analyzing {len(pairs)} pairs")
    start_time = time.time()

    # Batch loading 4H candles
    requests = [
        {'symbol': symbol, 'interval': config.TIMEFRAME_LONG, 'limit': 100}
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
            # SUPPORT/RESISTANCE LEVELS
            # ============================================================
            sr_analysis = analyze_support_resistance(
                candles, current_price, signal_direction='UNKNOWN'
            )

            if not sr_analysis or len(sr_analysis.all_levels) == 0:
                stats['no_levels'] += 1
                logger.debug(f"Stage 1: {symbol} - No S/R levels found")
                continue

            # ============================================================
            # ATR WAVE ANALYSIS
            # ============================================================
            wave_analysis = analyze_waves_atr(candles, num_waves=5)

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
            if current_rsi > 85 or current_rsi < 15:
                stats['rsi_extreme'] += 1
                logger.debug(f"Stage 1: {symbol} skipped - RSI extreme ({current_rsi:.1f})")
                continue

            # ============================================================
            # ОПРЕДЕЛЯЕМ НАПРАВЛЕНИЕ + CONFIDENCE
            # ============================================================
            direction, confidence, pattern_type, rejection_reason = _determine_level_signal(
                sr_analysis, wave_analysis, ema200_context,
                current_rsi, volume_analysis
            )

            if direction == 'NONE':
                if 'overextension' in rejection_reason.lower():
                    stats['overextension'] += 1
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
            logger.info(f"Stage 1: ✓ {symbol} {direction} (confidence: {confidence}%, pattern: {pattern_type})")

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
            logger.info(f"  {i}. {c.symbol} {c.direction} (conf: {c.confidence}%, {c.pattern_type})")

    logger.info("=" * 70)

    return candidates


def _determine_level_signal(
        sr_analysis: 'SupportResistanceAnalysis',
        wave_analysis: 'WaveAnalysis',
        ema200_context: dict,
        rsi: float,
        volume_analysis: 'VolumeAnalysis'
) -> tuple[str, int, str, str]:
    """
    Определить сигнал на основе уровней + ATR

    БЫЧИЙ СИГНАЛ (LONG):
    ✅ Цена около уровня SUPPORT (< 1%)
    ✅ Уровень сильный (3+ касания)
    ✅ Объём растёт
    ✅ ATR: ранний вход (< 30% от средней волны)
    ✅ EMA200: цена выше EMA200 (бычий тренд)
    ✅ RSI: 40-70

    МЕДВЕЖИЙ СИГНАЛ (SHORT):
    ✅ Цена около уровня RESISTANCE (< 1%)
    ✅ Уровень сильный (3+ касания)
    ✅ Объём растёт
    ✅ ATR: ранний вход
    ✅ EMA200: цена ниже EMA200 (медвежий тренд)
    ✅ RSI: 30-60

    SCORING:
    - Качество уровня (3+ касания): 35 баллов
    - Расстояние до уровня (< 1%): 25 баллов
    - ATR ранний вход: 20 баллов
    - EMA200 alignment: 10 баллов
    - Объём > 1.5x: 10 баллов

    MIN_SCORE = 60 баллов
    """

    MIN_SCORE = 60

    # ============================================================
    # БЫЧИЙ ПАТТЕРН (LONG)
    # ============================================================
    bullish_score = 0
    bullish_details = []

    nearest_support = sr_analysis.nearest_support

    if nearest_support:
        # Качество уровня
        if nearest_support.touches >= 5:
            bullish_score += 40
            bullish_details.append(f"Premium support ({nearest_support.touches} touches)")
        elif nearest_support.touches >= 4:
            bullish_score += 35
            bullish_details.append(f"Strong support ({nearest_support.touches} touches)")
        elif nearest_support.touches >= 3:
            bullish_score += 25
            bullish_details.append(f"Valid support ({nearest_support.touches} touches)")

        # Расстояние до уровня
        distance = nearest_support.distance_from_current_pct
        if distance < 0.5:
            bullish_score += 30
            bullish_details.append(f"Ideal entry (<0.5%)")
        elif distance < 1.0:
            bullish_score += 25
            bullish_details.append(f"Good entry (<1%)")
        elif distance < 2.0:
            bullish_score += 15
            bullish_details.append(f"Acceptable entry (<2%)")
        else:
            bullish_details.append(f"Too far from support ({distance:.1f}%)")

    # ATR Wave Analysis
    if wave_analysis:
        if wave_analysis.wave_type == 'BULLISH':
            if wave_analysis.is_early_entry:
                bullish_score += 20
                bullish_details.append(f"Early entry ({wave_analysis.current_wave_progress:.0f}% of ATR)")
            elif wave_analysis.current_wave_progress < 50:
                bullish_score += 15
                bullish_details.append(f"Good entry ({wave_analysis.current_wave_progress:.0f}% of ATR)")
            elif wave_analysis.current_wave_progress < 70:
                bullish_score += 5
            else:
                bullish_score -= 10
                bullish_details.append(f"Late entry ({wave_analysis.current_wave_progress:.0f}%)")

    # EMA200 alignment
    if ema200_context['price_above_ema200']:
        bullish_score += 10
        bullish_details.append("Above EMA200 (bullish trend)")

        # Проверка overextension
        distance_ema = ema200_context['distance_pct']
        if distance_ema > 10:
            bullish_score -= 15
            bullish_details.append(f"OVEREXTENDED from EMA200 ({distance_ema:.1f}%)")
        elif distance_ema > 5:
            bullish_score -= 8

    # RSI optimal
    if 40 <= rsi <= 70:
        bullish_score += 5
    elif rsi > 75:
        bullish_score -= 10

    # Volume
    vol_ratio = volume_analysis.volume_ratio_current
    if vol_ratio > 2.0:
        bullish_score += 10
        bullish_details.append(f"Strong volume ({vol_ratio:.1f}x)")
    elif vol_ratio > 1.5:
        bullish_score += 8
    elif vol_ratio > 1.2:
        bullish_score += 5

    # ============================================================
    # МЕДВЕЖИЙ ПАТТЕРН (SHORT)
    # ============================================================
    bearish_score = 0
    bearish_details = []

    nearest_resistance = sr_analysis.nearest_resistance

    if nearest_resistance:
        # Качество уровня
        if nearest_resistance.touches >= 5:
            bearish_score += 40
            bearish_details.append(f"Premium resistance ({nearest_resistance.touches} touches)")
        elif nearest_resistance.touches >= 4:
            bearish_score += 35
            bearish_details.append(f"Strong resistance ({nearest_resistance.touches} touches)")
        elif nearest_resistance.touches >= 3:
            bearish_score += 25
            bearish_details.append(f"Valid resistance ({nearest_resistance.touches} touches)")

        # Расстояние до уровня
        distance = nearest_resistance.distance_from_current_pct
        if distance < 0.5:
            bearish_score += 30
            bearish_details.append(f"Ideal entry (<0.5%)")
        elif distance < 1.0:
            bearish_score += 25
            bearish_details.append(f"Good entry (<1%)")
        elif distance < 2.0:
            bearish_score += 15
            bearish_details.append(f"Acceptable entry (<2%)")
        else:
            bearish_details.append(f"Too far from resistance ({distance:.1f}%)")

    # ATR Wave Analysis
    if wave_analysis:
        if wave_analysis.wave_type == 'BEARISH':
            if wave_analysis.is_early_entry:
                bearish_score += 20
                bearish_details.append(f"Early entry ({wave_analysis.current_wave_progress:.0f}% of ATR)")
            elif wave_analysis.current_wave_progress < 50:
                bearish_score += 15
                bearish_details.append(f"Good entry ({wave_analysis.current_wave_progress:.0f}% of ATR)")
            elif wave_analysis.current_wave_progress < 70:
                bearish_score += 5
            else:
                bearish_score -= 10
                bearish_details.append(f"Late entry ({wave_analysis.current_wave_progress:.0f}%)")

    # EMA200 alignment
    if not ema200_context['price_above_ema200']:
        bearish_score += 10
        bearish_details.append("Below EMA200 (bearish trend)")

        # Проверка overextension
        distance_ema = ema200_context['distance_pct']
        if distance_ema > 10:
            bearish_score -= 15
            bearish_details.append(f"OVEREXTENDED from EMA200 ({distance_ema:.1f}%)")
        elif distance_ema > 5:
            bearish_score -= 8

    # RSI optimal
    if 30 <= rsi <= 60:
        bearish_score += 5
    elif rsi < 25:
        bearish_score -= 10

    # Volume
    if vol_ratio > 2.0:
        bearish_score += 10
        bearish_details.append(f"Strong volume ({vol_ratio:.1f}x)")
    elif vol_ratio > 1.5:
        bearish_score += 8
    elif vol_ratio > 1.2:
        bearish_score += 5

    # ============================================================
    # РЕШЕНИЕ
    # ============================================================

    if bullish_score < MIN_SCORE and bearish_score < MIN_SCORE:
        return 'NONE', 0, 'NO_PATTERN', f'Both scores below minimum: L={bullish_score}, S={bearish_score}'

    if bullish_score >= MIN_SCORE and bearish_score >= MIN_SCORE:
        score_diff = abs(bullish_score - bearish_score)
        if score_diff < 15:
            return 'NONE', 0, 'CONFLICTING', f'Both strong (L:{bullish_score}, S:{bearish_score})'

    if bullish_score > bearish_score:
        direction = 'LONG'
        confidence = min(95, 50 + bullish_score)

        if bullish_score >= 85:
            pattern_type = 'PERFECT_LEVEL'
        elif bullish_score >= 70:
            pattern_type = 'STRONG_LEVEL'
        else:
            pattern_type = 'MODERATE_LEVEL'

        logger.debug(f"LONG signal: score={bullish_score}, details={bullish_details}")

    else:
        direction = 'SHORT'
        confidence = min(95, 50 + bearish_score)

        if bearish_score >= 85:
            pattern_type = 'PERFECT_LEVEL'
        elif bearish_score >= 70:
            pattern_type = 'STRONG_LEVEL'
        else:
            pattern_type = 'MODERATE_LEVEL'

        logger.debug(f"SHORT signal: score={bearish_score}, details={bearish_details}")

    return direction, confidence, pattern_type, ''