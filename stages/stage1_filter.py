"""
Stage 1: SMC-Based Signal Filtering - FIXED LOGIC
Файл: stages/stage1_filter.py

ИСПРАВЛЕНО:
✅ Строгая проверка позиции OB (блокировка неправильных)
✅ Минимальный порог 40 баллов для каждого направления
✅ Конфликтующие сигналы отсекаются раньше
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
    ob_analysis: 'OrderBlockAnalysis'
    imbalance_analysis: 'ImbalanceAnalysis'
    sweep_analysis: dict
    ema_context: dict
    volume_analysis: 'VolumeAnalysis'
    rsi_value: float
    pattern_type: str


async def run_stage1(
        pairs: List[str],
        min_confidence: int = 60,
        min_volume_ratio: float = 1.0
) -> List[SignalCandidate]:
    """Stage 1: Фильтрация пар по Smart Money Concept паттернам"""
    from data_providers import fetch_multiple_candles, normalize_candles
    from indicators import (
        analyze_order_blocks,
        analyze_imbalances,
        analyze_liquidity_sweep,
        calculate_ema,
        analyze_volume,
        calculate_rsi
    )
    from config import config
    import time

    if not pairs:
        logger.warning("Stage 1: No pairs provided")
        return []

    logger.info(f"Stage 1 (SMC-FIXED): Analyzing {len(pairs)} pairs")
    start_time = time.time()

    # Batch loading
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
        'no_smc_patterns': 0,
        'low_confidence': 0,
        'low_volume': 0,
        'rsi_exhaustion': 0,
        'conflicting_signals': 0,
        'wrong_ob_position': 0  # ✅ НОВОЕ
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

            # SMC ANALYSIS
            ob_analysis = analyze_order_blocks(
                candles, current_price, signal_direction='UNKNOWN', lookback=50
            )

            if not ob_analysis or ob_analysis.total_blocks_found == 0:
                stats['no_smc_patterns'] += 1
                continue

            imbalance_analysis = analyze_imbalances(
                candles, current_price, signal_direction='UNKNOWN', lookback=50
            )
            sweep_analysis = analyze_liquidity_sweep(candles, signal_direction='UNKNOWN')

            # EMA CONTEXT
            ema50 = calculate_ema(candles.closes, config.EMA_SLOW)
            current_ema50 = float(ema50[-1])
            price_above_ema50 = current_price > current_ema50
            distance_from_ema50 = abs((current_price - current_ema50) / current_ema50 * 100)

            ema_context = {
                'ema50': current_ema50,
                'price_above_ema50': price_above_ema50,
                'distance_pct': distance_from_ema50
            }

            # VOLUME + RSI
            volume_analysis = analyze_volume(candles, window=config.VOLUME_WINDOW)
            if not volume_analysis:
                stats['invalid'] += 1
                continue

            if volume_analysis.volume_ratio_current < min_volume_ratio:
                stats['low_volume'] += 1
                continue

            rsi_values = calculate_rsi(candles.closes, config.RSI_PERIOD)
            current_rsi = float(rsi_values[-1])

            # RSI exhaustion check
            if current_rsi > 70:
                rsi_penalty = -15
            elif current_rsi < 30:
                rsi_penalty = -15
            else:
                rsi_penalty = 0

            # ✅ ИСПРАВЛЕНО: ОПРЕДЕЛЯЕМ НАПРАВЛЕНИЕ + CONFIDENCE
            direction, confidence, pattern_type, rejection_reason = _determine_smc_signal_fixed(
                ob_analysis, imbalance_analysis, sweep_analysis,
                ema_context, current_rsi, volume_analysis, current_price, rsi_penalty
            )

            if direction == 'NONE':
                if 'WRONG_OB_POSITION' in rejection_reason:
                    stats['wrong_ob_position'] += 1
                elif 'CONFLICTING' in rejection_reason:
                    stats['conflicting_signals'] += 1
                else:
                    stats['no_smc_patterns'] += 1

                logger.debug(f"Stage 1: {symbol} - {rejection_reason}")
                continue

            if confidence < min_confidence:
                stats['low_confidence'] += 1
                logger.debug(f"Stage 1: {symbol} skipped (confidence {confidence} < {min_confidence})")
                continue

            # СОЗДАЁМ КАНДИДАТА
            candidate = SignalCandidate(
                symbol=symbol,
                direction=direction,
                confidence=confidence,
                ob_analysis=ob_analysis,
                imbalance_analysis=imbalance_analysis,
                sweep_analysis=sweep_analysis,
                ema_context=ema_context,
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
    logger.info("STAGE 1 (SMC-FIXED) COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Total time: {total_time:.1f}s")
    logger.info(f"Processed: {processed} pairs")
    logger.info(f"✅ SMC Signals found: {len(candidates)}")
    logger.info(f"❌ Skipped breakdown:")
    logger.info(f"   • Invalid data: {stats['invalid']}")
    logger.info(f"   • No SMC patterns: {stats['no_smc_patterns']}")
    logger.info(f"   • Low confidence: {stats['low_confidence']}")
    logger.info(f"   • Low volume: {stats['low_volume']}")
    logger.info(f"   • RSI exhaustion: {stats['rsi_exhaustion']}")
    logger.info(f"   • Conflicting signals: {stats['conflicting_signals']}")
    logger.info(f"   • Wrong OB position: {stats['wrong_ob_position']}")

    if candidates:
        logger.info(f"\n📊 Pattern distribution:")
        pattern_counts = {}
        for c in candidates:
            pattern_counts[c.pattern_type] = pattern_counts.get(c.pattern_type, 0) + 1

        for pattern, count in sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"   • {pattern}: {count}")

        logger.info(f"\nTop 5 candidates:")
        for i, c in enumerate(candidates[:5], 1):
            logger.info(f"  {i}. {c.symbol} {c.direction} (conf: {c.confidence}%, {c.pattern_type})")

    logger.info("=" * 70)

    return candidates


def _determine_smc_signal_fixed(
        ob_analysis: 'OrderBlockAnalysis',
        imbalance_analysis: 'ImbalanceAnalysis',
        sweep_analysis: dict,
        ema_context: dict,
        rsi: float,
        volume_analysis: 'VolumeAnalysis',
        current_price: float,
        rsi_penalty: int
) -> tuple[str, int, str, str]:
    """
    ✅ ИСПРАВЛЕНО: Строгая проверка позиции OB

    Returns:
        (direction, confidence, pattern_type, rejection_reason)
    """

    MIN_SCORE = 40  # Минимум для каждого направления
    MIN_DIFF = 20   # Минимальная разница между направлениями

    # ============================================================
    # БЫЧЬИ ПАТТЕРНЫ
    # ============================================================
    bullish_score = 0
    bullish_details = []

    # ✅ Order Blocks - СТРОГАЯ ПРОВЕРКА ПОЗИЦИИ
    if ob_analysis.bullish_blocks > 0:
        nearest_ob = ob_analysis.nearest_ob

        if nearest_ob and nearest_ob.direction == 'BULLISH':
            # ✅ КРИТИЧНО: Для LONG нужен OB НИЖЕ текущей цены
            if nearest_ob.price_high < current_price:
                # OB в правильной позиции
                if not nearest_ob.is_mitigated:
                    bullish_score += 35
                    bullish_details.append("Fresh Bullish OB BELOW")

                    if nearest_ob.distance_from_current < 2.0:
                        bullish_score += 10
                        bullish_details.append("OB very close")
                    elif nearest_ob.distance_from_current < 5.0:
                        bullish_score += 5
                else:
                    bullish_score += 18
                    bullish_details.append("Mitigated Bullish OB BELOW")
            else:
                # ❌ OB ВЫШЕ цены = СОПРОТИВЛЕНИЕ
                logger.debug(f"LONG: Bullish OB wrongly positioned ABOVE price: {nearest_ob.price_high} > {current_price}")
                return 'NONE', 0, 'WRONG_OB_POSITION', f'Bullish OB at {nearest_ob.price_high:.2f} is ABOVE price {current_price:.2f} (acts as resistance)'

    # Imbalances
    if imbalance_analysis and imbalance_analysis.bullish_count > 0:
        nearest_imb = imbalance_analysis.nearest_imbalance
        if nearest_imb and nearest_imb.direction == 'BULLISH':
            if not nearest_imb.is_filled:
                bullish_score += 15
                bullish_details.append("Unfilled Bullish FVG")
            elif nearest_imb.fill_percentage < 50:
                bullish_score += 8

    # Liquidity Sweep
    if sweep_analysis.get('sweep_detected'):
        sweep_data = sweep_analysis.get('sweep_data')
        if sweep_data and sweep_data.direction == 'SWEEP_LOW':
            if sweep_data.reversal_confirmed:
                bullish_score += 20
                bullish_details.append("Sweep Low + Reversal")
                if sweep_data.volume_confirmation:
                    bullish_score += 5

    # EMA Context
    if ema_context['price_above_ema50']:
        bullish_score += 8
        bullish_details.append("Above EMA50")

    # RSI optimal
    if 40 <= rsi <= 70:
        bullish_score += 5

    # Volume
    if volume_analysis.volume_ratio_current > 1.5:
        bullish_score += 8
        bullish_details.append(f"Volume {volume_analysis.volume_ratio_current:.1f}x")

    bullish_score += rsi_penalty

    # ============================================================
    # МЕДВЕЖЬИ ПАТТЕРНЫ
    # ============================================================
    bearish_score = 0
    bearish_details = []

    # ✅ Order Blocks - СТРОГАЯ ПРОВЕРКА ПОЗИЦИИ
    if ob_analysis.bearish_blocks > 0:
        nearest_ob = ob_analysis.nearest_ob

        if nearest_ob and nearest_ob.direction == 'BEARISH':
            # ✅ КРИТИЧНО: Для SHORT нужен OB ВЫШЕ текущей цены
            if nearest_ob.price_low > current_price:
                # OB в правильной позиции
                if not nearest_ob.is_mitigated:
                    bearish_score += 35
                    bearish_details.append("Fresh Bearish OB ABOVE")

                    if nearest_ob.distance_from_current < 2.0:
                        bearish_score += 10
                        bearish_details.append("OB very close")
                    elif nearest_ob.distance_from_current < 5.0:
                        bearish_score += 5
                else:
                    bearish_score += 18
                    bearish_details.append("Mitigated Bearish OB ABOVE")
            else:
                # ❌ OB НИЖЕ цены = ПОДДЕРЖКА
                logger.debug(f"SHORT: Bearish OB wrongly positioned BELOW price: {nearest_ob.price_low} < {current_price}")
                return 'NONE', 0, 'WRONG_OB_POSITION', f'Bearish OB at {nearest_ob.price_low:.2f} is BELOW price {current_price:.2f} (acts as support)'

    # Imbalances
    if imbalance_analysis and imbalance_analysis.bearish_count > 0:
        nearest_imb = imbalance_analysis.nearest_imbalance
        if nearest_imb and nearest_imb.direction == 'BEARISH':
            if not nearest_imb.is_filled:
                bearish_score += 15
                bearish_details.append("Unfilled Bearish FVG")
            elif nearest_imb.fill_percentage < 50:
                bearish_score += 8

    # Liquidity Sweep
    if sweep_analysis.get('sweep_detected'):
        sweep_data = sweep_analysis.get('sweep_data')
        if sweep_data and sweep_data.direction == 'SWEEP_HIGH':
            if sweep_data.reversal_confirmed:
                bearish_score += 20
                bearish_details.append("Sweep High + Reversal")
                if sweep_data.volume_confirmation:
                    bearish_score += 5

    # EMA Context
    if not ema_context['price_above_ema50']:
        bearish_score += 8
        bearish_details.append("Below EMA50")

    # RSI optimal
    if 30 <= rsi <= 60:
        bearish_score += 5

    # Volume
    if volume_analysis.volume_ratio_current > 1.5:
        bearish_score += 8
        bearish_details.append(f"Volume {volume_analysis.volume_ratio_current:.1f}x")

    bearish_score += rsi_penalty

    # ============================================================
    # ✅ РЕШАЮЩАЯ ЛОГИКА
    # ============================================================

    # Оба направления слабые
    if bullish_score < MIN_SCORE and bearish_score < MIN_SCORE:
        return 'NONE', 0, 'NO_PATTERN', f'Both scores below minimum: L={bullish_score}, S={bearish_score}'

    # Оба направления сильные (конфликт)
    if bullish_score >= MIN_SCORE and bearish_score >= MIN_SCORE:
        score_diff = abs(bullish_score - bearish_score)
        if score_diff < MIN_DIFF:
            logger.warning(f"Conflicting SMC signals: LONG={bullish_score}, SHORT={bearish_score}, diff={score_diff}")
            return 'NONE', 0, 'CONFLICTING_SIGNALS', f'Both directions strong (L:{bullish_score}, S:{bearish_score}, diff:{score_diff})'

    # Одно направление явно сильнее
    if bullish_score > bearish_score:
        direction = 'LONG'
        confidence = min(95, 50 + bullish_score)

        if bullish_score >= 65:
            pattern_type = 'PERFECT_SMC'
        elif bullish_score >= 55:
            pattern_type = 'STRONG_SMC'
        elif bullish_score >= 45:
            pattern_type = 'MODERATE_SMC'
        else:
            pattern_type = 'WEAK_SMC'

        logger.debug(f"LONG signal: score={bullish_score}, details={bullish_details}")
    else:
        direction = 'SHORT'
        confidence = min(95, 50 + bearish_score)

        if bearish_score >= 65:
            pattern_type = 'PERFECT_SMC'
        elif bearish_score >= 55:
            pattern_type = 'STRONG_SMC'
        elif bearish_score >= 45:
            pattern_type = 'MODERATE_SMC'
        else:
            pattern_type = 'WEAK_SMC'

        logger.debug(f"SHORT signal: score={bearish_score}, details={bearish_details}")

    return direction, confidence, pattern_type, ''