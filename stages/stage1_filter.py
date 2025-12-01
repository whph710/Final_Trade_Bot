"""
Stage 1: SMC-Based Signal Filtering
Файл: stages/stage1_filter.py

НОВАЯ СТРАТЕГИЯ:
- Фильтрация по Smart Money Concept паттернам
- Order Blocks + Liquidity Sweeps + Imbalances как основа
- EMA только как контекст тренда
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

    # SMC Components
    ob_analysis: 'OrderBlockAnalysis'
    imbalance_analysis: 'ImbalanceAnalysis'
    sweep_analysis: dict

    # Context indicators
    ema_context: dict
    volume_analysis: 'VolumeAnalysis'
    rsi_value: float

    # Details
    pattern_type: str  # 'PERFECT_SMC', 'STRONG_SMC', 'MODERATE_SMC', 'WEAK_SMC'


async def run_stage1(
        pairs: List[str],
        min_confidence: int = 60,
        min_volume_ratio: float = 1.0
) -> List[SignalCandidate]:
    """
    Stage 1: Фильтрация пар по Smart Money Concept паттернам

    НОВАЯ ЛОГИКА:
    1. Order Blocks detection (primary)
    2. Liquidity Sweeps detection (confirmation)
    3. Imbalances detection (targets)
    4. EMA50 для trend context
    5. Volume + RSI базовая фильтрация
    """
    from data_providers import fetch_multiple_candles, normalize_candles
    from indicators import (
        analyze_order_blocks,
        analyze_imbalances,
        analyze_liquidity_sweep,
        calculate_ema,
        analyze_volume,
        calculate_rsi
    )
    from indicators.order_blocks import analyze_order_blocks
    from indicators.imbalance import analyze_imbalances
    from indicators.liquidity_sweep import analyze_liquidity_sweep
    from config import config
    import time

    if not pairs:
        logger.warning("Stage 1: No pairs provided")
        return []

    logger.info(f"Stage 1 (SMC): Analyzing {len(pairs)} pairs (batch loading)")

    start_time = time.time()

    # ===================================================================
    # BATCH LOADING - ВСЕ ПАРЫ СРАЗУ (4H для SMC анализа)
    # ===================================================================
    logger.debug(f"Stage 1 (SMC): Preparing {len(pairs)} batch requests...")

    requests = [
        {
            'symbol': symbol,
            'interval': config.TIMEFRAME_LONG,  # 4H для SMC
            'limit': 100  # Достаточно для OB/FVG detection
        }
        for symbol in pairs
    ]

    logger.debug(f"Stage 1 (SMC): Fetching candles for {len(requests)} pairs...")
    batch_results = await fetch_multiple_candles(requests)

    load_time = time.time() - start_time
    logger.info(
        f"Stage 1 (SMC): Loaded {len(batch_results)}/{len(pairs)} pairs "
        f"in {load_time:.1f}s"
    )

    if not batch_results:
        logger.warning("Stage 1 (SMC): No valid candles loaded")
        return []

    # ===================================================================
    # SMC АНАЛИЗ КАЖДОЙ ПАРЫ
    # ===================================================================
    candidates = []
    processed = 0

    # Статистика отклонений
    stats = {
        'invalid': 0,
        'no_smc_patterns': 0,
        'low_confidence': 0,
        'low_volume': 0,
        'rsi_exhaustion': 0
    }

    for result in batch_results:
        if not result.get('success'):
            continue

        symbol = result['symbol']
        candles_raw = result['klines']

        try:
            processed += 1

            # Нормализация
            candles = normalize_candles(
                candles_raw,
                symbol=symbol,
                interval=config.TIMEFRAME_LONG
            )

            if not candles or not candles.is_valid:
                stats['invalid'] += 1
                continue

            current_price = float(candles.closes[-1])

            # ============================================================
            # 1. ORDER BLOCKS ANALYSIS (PRIMARY)
            # ============================================================
            ob_analysis = analyze_order_blocks(
                candles,
                current_price,
                signal_direction='UNKNOWN',  # Ищем оба направления
                lookback=50
            )

            if not ob_analysis or ob_analysis.total_blocks_found == 0:
                stats['no_smc_patterns'] += 1
                logger.debug(f"Stage 1 (SMC): {symbol} - No Order Blocks found")
                continue

            # ============================================================
            # 2. IMBALANCES ANALYSIS
            # ============================================================
            imbalance_analysis = analyze_imbalances(
                candles,
                current_price,
                signal_direction='UNKNOWN',
                lookback=50
            )

            # ============================================================
            # 3. LIQUIDITY SWEEPS ANALYSIS
            # ============================================================
            sweep_analysis = analyze_liquidity_sweep(
                candles,
                signal_direction='UNKNOWN'
            )

            # ============================================================
            # 4. EMA CONTEXT (trend anchor)
            # ============================================================
            ema50 = calculate_ema(candles.closes, config.EMA_SLOW)
            current_ema50 = float(ema50[-1])

            price_above_ema50 = current_price > current_ema50
            distance_from_ema50 = abs((current_price - current_ema50) / current_ema50 * 100)

            ema_context = {
                'ema50': current_ema50,
                'price_above_ema50': price_above_ema50,
                'distance_pct': distance_from_ema50
            }

            # ============================================================
            # 5. VOLUME + RSI (базовая фильтрация)
            # ============================================================
            volume_analysis = analyze_volume(candles, window=config.VOLUME_WINDOW)

            if not volume_analysis:
                stats['invalid'] += 1
                continue

            if volume_analysis.volume_ratio_current < min_volume_ratio:
                stats['low_volume'] += 1
                logger.debug(
                    f"Stage 1 (SMC): {symbol} skipped "
                    f"(volume {volume_analysis.volume_ratio_current:.2f} < {min_volume_ratio})"
                )
                continue

            rsi_values = calculate_rsi(candles.closes, config.RSI_PERIOD)
            current_rsi = float(rsi_values[-1])

            # RSI exhaustion check
            if current_rsi > 85 or current_rsi < 15:
                stats['rsi_exhaustion'] += 1
                logger.debug(
                    f"Stage 1 (SMC): {symbol} skipped "
                    f"(RSI exhaustion: {current_rsi:.1f})"
                )
                continue

            # ============================================================
            # 6. ОПРЕДЕЛЯЕМ НАПРАВЛЕНИЕ + CONFIDENCE
            # ============================================================
            direction, confidence, pattern_type = _determine_smc_signal(
                ob_analysis,
                imbalance_analysis,
                sweep_analysis,
                ema_context,
                current_rsi,
                volume_analysis,
                current_price
            )

            if direction == 'NONE':
                stats['no_smc_patterns'] += 1
                logger.debug(
                    f"Stage 1 (SMC): {symbol} - No clear SMC direction"
                )
                continue

            if confidence < min_confidence:
                stats['low_confidence'] += 1
                logger.debug(
                    f"Stage 1 (SMC): {symbol} skipped "
                    f"(confidence {confidence} < {min_confidence})"
                )
                continue

            # ============================================================
            # 7. СОЗДАЁМ КАНДИДАТА
            # ============================================================
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

            logger.info(
                f"Stage 1 (SMC): ✓ {symbol} {direction} "
                f"(confidence: {confidence}%, pattern: {pattern_type}, "
                f"OB: {ob_analysis.total_blocks_found}, "
                f"FVG: {imbalance_analysis.total_imbalances if imbalance_analysis else 0}, "
                f"Sweep: {'YES' if sweep_analysis.get('sweep_detected') else 'NO'})"
            )

        except Exception as e:
            logger.debug(f"Stage 1 (SMC): Error processing {symbol}: {e}")
            stats['invalid'] += 1
            continue

    # Сортируем по confidence
    candidates.sort(key=lambda x: x.confidence, reverse=True)

    total_time = time.time() - start_time

    # ===================================================================
    # ИТОГОВАЯ СТАТИСТИКА
    # ===================================================================
    logger.info("=" * 70)
    logger.info("STAGE 1 (SMC) COMPLETE")
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

    if candidates:
        logger.info(f"\n📊 Pattern distribution:")
        pattern_counts = {}
        for c in candidates:
            pattern_counts[c.pattern_type] = pattern_counts.get(c.pattern_type, 0) + 1

        for pattern, count in sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True):
            logger.info(f"   • {pattern}: {count}")

        logger.info(f"\nTop 5 candidates:")
        for i, c in enumerate(candidates[:5], 1):
            ob_count = c.ob_analysis.total_blocks_found
            fvg_count = c.imbalance_analysis.total_imbalances if c.imbalance_analysis else 0
            sweep = '✓' if c.sweep_analysis.get('sweep_detected') else '✗'

            logger.info(
                f"  {i}. {c.symbol} {c.direction} "
                f"(conf: {c.confidence}%, {c.pattern_type}, "
                f"OB: {ob_count}, FVG: {fvg_count}, Sweep: {sweep})"
            )

    logger.info("=" * 70)

    return candidates


def _determine_smc_signal(
        ob_analysis: 'OrderBlockAnalysis',
        imbalance_analysis: 'ImbalanceAnalysis',
        sweep_analysis: dict,
        ema_context: dict,
        rsi: float,
        volume_analysis: 'VolumeAnalysis',
        current_price: float
) -> tuple[str, int, str]:
    """
    Определить направление сигнала на основе SMC компонентов

    Returns:
        (direction, confidence, pattern_type)
    """

    # ============================================================
    # АНАЛИЗИРУЕМ БЫЧЬИ ПАТТЕРНЫ
    # ============================================================
    bullish_score = 0
    bullish_details = []

    # Order Blocks (BULLISH)
    if ob_analysis.bullish_blocks > 0:
        nearest_ob = ob_analysis.nearest_ob

        if nearest_ob and nearest_ob.direction == 'BULLISH':
            if not nearest_ob.is_mitigated:
                # Fresh OB
                bullish_score += 30
                bullish_details.append("Fresh Bullish OB")

                if nearest_ob.distance_from_current < 2.0:
                    bullish_score += 10  # Очень близко
                    bullish_details.append("OB nearby (<2%)")
                elif nearest_ob.distance_from_current < 5.0:
                    bullish_score += 5
            else:
                # Mitigated OB (слабее)
                bullish_score += 15
                bullish_details.append("Mitigated Bullish OB")

    # Imbalances (BULLISH)
    if imbalance_analysis and imbalance_analysis.bullish_count > 0:
        nearest_imb = imbalance_analysis.nearest_imbalance

        if nearest_imb and nearest_imb.direction == 'BULLISH':
            if not nearest_imb.is_filled:
                bullish_score += 15
                bullish_details.append("Unfilled Bullish FVG")
            elif nearest_imb.fill_percentage < 50:
                bullish_score += 8
                bullish_details.append("Partial Bullish FVG")

    # Liquidity Sweep (BULLISH reversal)
    if sweep_analysis.get('sweep_detected'):
        sweep_data = sweep_analysis.get('sweep_data')

        if sweep_data and sweep_data.direction == 'SWEEP_LOW':
            if sweep_data.reversal_confirmed:
                bullish_score += 20
                bullish_details.append("Sweep Low + Reversal")

                if sweep_data.volume_confirmation:
                    bullish_score += 5

    # EMA Context (вспомогательный фильтр)
    if ema_context['price_above_ema50']:
        bullish_score += 8
        bullish_details.append("Above EMA50")

    # RSI optimal zone
    if 40 <= rsi <= 70:
        bullish_score += 5

    # Volume
    if volume_analysis.volume_ratio_current > 1.5:
        bullish_score += 8
        bullish_details.append(f"Volume {volume_analysis.volume_ratio_current:.1f}x")

    # ============================================================
    # АНАЛИЗИРУЕМ МЕДВЕЖЬИ ПАТТЕРНЫ
    # ============================================================
    bearish_score = 0
    bearish_details = []

    # Order Blocks (BEARISH)
    if ob_analysis.bearish_blocks > 0:
        nearest_ob = ob_analysis.nearest_ob

        if nearest_ob and nearest_ob.direction == 'BEARISH':
            if not nearest_ob.is_mitigated:
                bearish_score += 30
                bearish_details.append("Fresh Bearish OB")

                if nearest_ob.distance_from_current < 2.0:
                    bearish_score += 10
                    bearish_details.append("OB nearby (<2%)")
                elif nearest_ob.distance_from_current < 5.0:
                    bearish_score += 5
            else:
                bearish_score += 15
                bearish_details.append("Mitigated Bearish OB")

    # Imbalances (BEARISH)
    if imbalance_analysis and imbalance_analysis.bearish_count > 0:
        nearest_imb = imbalance_analysis.nearest_imbalance

        if nearest_imb and nearest_imb.direction == 'BEARISH':
            if not nearest_imb.is_filled:
                bearish_score += 15
                bearish_details.append("Unfilled Bearish FVG")
            elif nearest_imb.fill_percentage < 50:
                bearish_score += 8
                bearish_details.append("Partial Bearish FVG")

    # Liquidity Sweep (BEARISH reversal)
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

    # RSI optimal zone
    if 30 <= rsi <= 60:
        bearish_score += 5

    # Volume
    if volume_analysis.volume_ratio_current > 1.5:
        bearish_score += 8
        bearish_details.append(f"Volume {volume_analysis.volume_ratio_current:.1f}x")

    # ============================================================
    # ОПРЕДЕЛЯЕМ НАПРАВЛЕНИЕ
    # ============================================================

    # Минимальный порог для сигнала
    MIN_SCORE = 35

    if bullish_score < MIN_SCORE and bearish_score < MIN_SCORE:
        return 'NONE', 0, 'NO_PATTERN'

    # Выбираем сильнейшее направление
    if bullish_score > bearish_score:
        direction = 'LONG'
        confidence = min(95, 50 + bullish_score)

        # Определяем тип паттерна
        if bullish_score >= 65:
            pattern_type = 'PERFECT_SMC'
        elif bullish_score >= 50:
            pattern_type = 'STRONG_SMC'
        elif bullish_score >= 40:
            pattern_type = 'MODERATE_SMC'
        else:
            pattern_type = 'WEAK_SMC'

        logger.debug(f"LONG signal: score={bullish_score}, details={bullish_details}")

    else:
        direction = 'SHORT'
        confidence = min(95, 50 + bearish_score)

        if bearish_score >= 65:
            pattern_type = 'PERFECT_SMC'
        elif bearish_score >= 50:
            pattern_type = 'STRONG_SMC'
        elif bearish_score >= 40:
            pattern_type = 'MODERATE_SMC'
        else:
            pattern_type = 'WEAK_SMC'

        logger.debug(f"SHORT signal: score={bearish_score}, details={bearish_details}")

    return direction, confidence, pattern_type