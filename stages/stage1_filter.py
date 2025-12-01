"""
Stage 1: SMC-Based Signal Filtering - FIXED VERSION
Файл: stages/stage1_filter.py

✅ ИСПРАВЛЕНО:
- Проблема #6: EMA distance используется в scoring (штрафуется overextension)
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
        min_confidence: int = 55,
        min_volume_ratio: float = 0.8
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

    logger.info(f"Stage 1 (SMC-ADAPTED): Analyzing {len(pairs)} pairs")
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
        'rsi_extreme': 0,
        'conflicting_signals': 0
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

            # RSI блокировка только при ЭКСТРЕМАЛЬНЫХ значениях
            if current_rsi > 85 or current_rsi < 15:
                stats['rsi_extreme'] += 1
                logger.debug(f"Stage 1: {symbol} skipped - RSI extreme ({current_rsi:.1f})")
                continue

            # RSI penalty
            if current_rsi > 75:
                rsi_penalty = -10
            elif current_rsi < 25:
                rsi_penalty = -10
            else:
                rsi_penalty = 0

            # ✅ ОПРЕДЕЛЯЕМ НАПРАВЛЕНИЕ + CONFIDENCE (с EMA distance penalty)
            direction, confidence, pattern_type, rejection_reason = _determine_smc_signal_adapted(
                ob_analysis, imbalance_analysis, sweep_analysis,
                ema_context, current_rsi, volume_analysis, current_price, rsi_penalty
            )

            if direction == 'NONE':
                if 'CONFLICTING' in rejection_reason:
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
    logger.info("STAGE 1 (SMC-ADAPTED) COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Total time: {total_time:.1f}s")
    logger.info(f"Processed: {processed} pairs")
    logger.info(f"✅ SMC Signals found: {len(candidates)}")
    logger.info(f"❌ Skipped breakdown:")
    logger.info(f"   • Invalid data: {stats['invalid']}")
    logger.info(f"   • No SMC patterns: {stats['no_smc_patterns']}")
    logger.info(f"   • Low confidence: {stats['low_confidence']}")
    logger.info(f"   • Low volume: {stats['low_volume']}")
    logger.info(f"   • RSI extreme: {stats['rsi_extreme']}")
    logger.info(f"   • Conflicting signals: {stats['conflicting_signals']}")

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


def _determine_smc_signal_adapted(
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
    ✅ ИСПРАВЛЕНО: EMA distance теперь используется в scoring
    """

    MIN_SCORE = 25
    MIN_DIFF = 15

    # ============================================================
    # БЫЧЬИ ПАТТЕРНЫ
    # ============================================================
    bullish_score = 0
    bullish_details = []

    # Order Blocks
    if ob_analysis.bullish_blocks > 0:
        nearest_ob = ob_analysis.nearest_ob

        if nearest_ob and nearest_ob.direction == 'BULLISH':
            distance = nearest_ob.distance_from_current

            if not nearest_ob.is_mitigated:
                base_score = 35
                bullish_details.append("Fresh Bullish OB")
            else:
                base_score = 18
                bullish_details.append("Mitigated Bullish OB")

            if distance < 1.0:
                bullish_score += base_score + 10
                bullish_details.append("OB very close (<1%)")
            elif distance < 2.5:
                bullish_score += base_score + 5
                bullish_details.append("OB close (<2.5%)")
            elif distance < 5.0:
                bullish_score += base_score
                bullish_details.append(f"OB medium distance ({distance:.1f}%)")
            elif distance < 8.0:
                bullish_score += base_score - 10
                bullish_details.append(f"OB far ({distance:.1f}%)")
            else:
                bullish_score += 5
                bullish_details.append(f"OB too far ({distance:.1f}%)")

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

    # ✅ ИСПРАВЛЕНО #6: EMA distance penalty (overextension)
    if ema_context['price_above_ema50']:
        bullish_score += 3
        bullish_details.append("Above EMA50")

        # ✅ НОВОЕ: Штрафуем overextension
        distance_pct = ema_context['distance_pct']
        if distance_pct > 10.0:
            bullish_score -= 15
            bullish_details.append(f"OVEREXTENDED from EMA50 ({distance_pct:.1f}%)")
        elif distance_pct > 5.0:
            bullish_score -= 8
            bullish_details.append(f"Extended from EMA50 ({distance_pct:.1f}%)")
        elif distance_pct < 3.0:
            bullish_score += 5
            bullish_details.append(f"Near EMA50 ({distance_pct:.1f}%)")

    # RSI optimal
    if 40 <= rsi <= 70:
        bullish_score += 5

    # Volume
    if volume_analysis.volume_ratio_current > 1.5:
        bullish_score += 8
        bullish_details.append(f"Volume {volume_analysis.volume_ratio_current:.1f}x")
    elif volume_analysis.volume_ratio_current > 1.2:
        bullish_score += 5

    bullish_score += rsi_penalty

    # ============================================================
    # МЕДВЕЖЬИ ПАТТЕРНЫ (аналогично)
    # ============================================================
    bearish_score = 0
    bearish_details = []

    if ob_analysis.bearish_blocks > 0:
        nearest_ob = ob_analysis.nearest_ob

        if nearest_ob and nearest_ob.direction == 'BEARISH':
            distance = nearest_ob.distance_from_current

            if not nearest_ob.is_mitigated:
                base_score = 35
                bearish_details.append("Fresh Bearish OB")
            else:
                base_score = 18
                bearish_details.append("Mitigated Bearish OB")

            if distance < 1.0:
                bearish_score += base_score + 10
                bearish_details.append("OB very close (<1%)")
            elif distance < 2.5:
                bearish_score += base_score + 5
                bearish_details.append("OB close (<2.5%)")
            elif distance < 5.0:
                bearish_score += base_score
                bearish_details.append(f"OB medium distance ({distance:.1f}%)")
            elif distance < 8.0:
                bearish_score += base_score - 10
                bearish_details.append(f"OB far ({distance:.1f}%)")
            else:
                bearish_score += 5
                bearish_details.append(f"OB too far ({distance:.1f}%)")

    if imbalance_analysis and imbalance_analysis.bearish_count > 0:
        nearest_imb = imbalance_analysis.nearest_imbalance
        if nearest_imb and nearest_imb.direction == 'BEARISH':
            if not nearest_imb.is_filled:
                bearish_score += 15
                bearish_details.append("Unfilled Bearish FVG")
            elif nearest_imb.fill_percentage < 50:
                bearish_score += 8

    if sweep_analysis.get('sweep_detected'):
        sweep_data = sweep_analysis.get('sweep_data')
        if sweep_data and sweep_data.direction == 'SWEEP_HIGH':
            if sweep_data.reversal_confirmed:
                bearish_score += 20
                bearish_details.append("Sweep High + Reversal")
                if sweep_data.volume_confirmation:
                    bearish_score += 5

    # ✅ ИСПРАВЛЕНО #6: EMA distance penalty
    if not ema_context['price_above_ema50']:
        bearish_score += 3
        bearish_details.append("Below EMA50")

        # ✅ НОВОЕ: Штрафуем overextension
        distance_pct = ema_context['distance_pct']
        if distance_pct > 10.0:
            bearish_score -= 15
            bearish_details.append(f"OVEREXTENDED from EMA50 ({distance_pct:.1f}%)")
        elif distance_pct > 5.0:
            bearish_score -= 8
            bearish_details.append(f"Extended from EMA50 ({distance_pct:.1f}%)")
        elif distance_pct < 3.0:
            bearish_score += 5
            bearish_details.append(f"Near EMA50 ({distance_pct:.1f}%)")

    if 30 <= rsi <= 60:
        bearish_score += 5

    if volume_analysis.volume_ratio_current > 1.5:
        bearish_score += 8
        bearish_details.append(f"Volume {volume_analysis.volume_ratio_current:.1f}x")
    elif volume_analysis.volume_ratio_current > 1.2:
        bearish_score += 5

    bearish_score += rsi_penalty

    # ============================================================
    # РЕШАЮЩАЯ ЛОГИКА
    # ============================================================

    if bullish_score < MIN_SCORE and bearish_score < MIN_SCORE:
        return 'NONE', 0, 'NO_PATTERN', f'Both scores below minimum: L={bullish_score}, S={bearish_score}'

    if bullish_score >= MIN_SCORE and bearish_score >= MIN_SCORE:
        score_diff = abs(bullish_score - bearish_score)
        if score_diff < MIN_DIFF:
            logger.warning(f"Conflicting SMC signals: LONG={bullish_score}, SHORT={bearish_score}, diff={score_diff}")
            return 'NONE', 0, 'CONFLICTING_SIGNALS', f'Both directions strong (L:{bullish_score}, S:{bearish_score}, diff:{score_diff})'

    if bullish_score > bearish_score:
        direction = 'LONG'
        confidence = min(95, 50 + bullish_score)

        if bullish_score >= 60:
            pattern_type = 'PERFECT_SMC'
        elif bullish_score >= 45:
            pattern_type = 'STRONG_SMC'
        elif bullish_score >= 30:
            pattern_type = 'MODERATE_SMC'
        else:
            pattern_type = 'WEAK_SMC'

        logger.debug(f"LONG signal: score={bullish_score}, details={bullish_details}")
    else:
        direction = 'SHORT'
        confidence = min(95, 50 + bearish_score)

        if bearish_score >= 60:
            pattern_type = 'PERFECT_SMC'
        elif bearish_score >= 45:
            pattern_type = 'STRONG_SMC'
        elif bearish_score >= 30:
            pattern_type = 'MODERATE_SMC'
        else:
            pattern_type = 'WEAK_SMC'

        logger.debug(f"SHORT signal: score={bearish_score}, details={bearish_details}")

    return direction, confidence, pattern_type, ''