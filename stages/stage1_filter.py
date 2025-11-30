"""
Stage 1: Signal Filtering - OPTIMIZED BATCH LOADING
Файл: stages/stage1_filter.py

ИЗМЕНЕНИЯ:
- Batch загрузка всех пар ОДНОВРЕМЕННО (431 пара за ~5-10 секунд)
- Параллельная обработка индикаторов
- Более детальное логирование
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
    ema_analysis: 'EMAAnalysis'
    volume_analysis: 'VolumeAnalysis'


async def run_stage1(
        pairs: List[str],
        min_confidence: int = 60,
        min_volume_ratio: float = 1.0
) -> List[SignalCandidate]:
    """
    Stage 1: Фильтрация пар по базовым сигналам Triple EMA

    ОПТИМИЗАЦИЯ: Batch загрузка всех пар одновременно
    """
    from data_providers import fetch_multiple_candles, normalize_candles
    from indicators import analyze_triple_ema, analyze_volume
    from config import config
    import time

    if not pairs:
        logger.warning("Stage 1: No pairs provided")
        return []

    logger.info(f"Stage 1: Analyzing {len(pairs)} pairs (batch loading)")

    start_time = time.time()

    # ===================================================================
    # BATCH LOADING - ВСЕ ПАРЫ СРАЗУ
    # ===================================================================
    logger.debug(f"Stage 1: Preparing {len(pairs)} batch requests...")

    requests = [
        {
            'symbol': symbol,
            'interval': config.TIMEFRAME_LONG,
            'limit': config.QUICK_SCAN_CANDLES
        }
        for symbol in pairs
    ]

    # Загрузка ВСЕХ пар одновременно
    logger.debug(f"Stage 1: Fetching candles for {len(requests)} pairs...")
    batch_results = await fetch_multiple_candles(requests)

    load_time = time.time() - start_time
    logger.info(
        f"Stage 1: Loaded {len(batch_results)}/{len(pairs)} pairs "
        f"in {load_time:.1f}s ({len(pairs)/load_time:.1f} pairs/sec)"
    )

    if not batch_results:
        logger.warning("Stage 1: No valid candles loaded")
        return []

    # ===================================================================
    # АНАЛИЗ КАЖДОЙ ПАРЫ
    # ===================================================================
    candidates = []
    processed = 0
    skipped_invalid = 0
    skipped_confidence = 0
    skipped_volume = 0
    skipped_direction = 0

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
                skipped_invalid += 1
                continue

            # EMA анализ
            ema_analysis = analyze_triple_ema(
                candles,
                fast=config.EMA_FAST,
                medium=config.EMA_MEDIUM,
                slow=config.EMA_SLOW
            )

            if not ema_analysis:
                skipped_invalid += 1
                continue

            # Volume анализ
            volume_analysis = analyze_volume(
                candles,
                window=config.VOLUME_WINDOW
            )

            if not volume_analysis:
                skipped_invalid += 1
                continue

            # Проверка базовых условий
            if ema_analysis.confidence_score < min_confidence:
                skipped_confidence += 1
                logger.debug(
                    f"Stage 1: {symbol} skipped (confidence {ema_analysis.confidence_score} < {min_confidence})"
                )
                continue

            if volume_analysis.volume_ratio_current < min_volume_ratio:
                skipped_volume += 1
                logger.debug(
                    f"Stage 1: {symbol} skipped (volume {volume_analysis.volume_ratio_current:.2f} < {min_volume_ratio})"
                )
                continue

            # Определяем направление
            direction = _determine_direction(ema_analysis)

            if direction == 'NONE':
                skipped_direction += 1
                logger.debug(
                    f"Stage 1: {symbol} skipped (no clear direction, alignment={ema_analysis.alignment})"
                )
                continue

            # Создаём кандидата
            candidate = SignalCandidate(
                symbol=symbol,
                direction=direction,
                confidence=ema_analysis.confidence_score,
                ema_analysis=ema_analysis,
                volume_analysis=volume_analysis
            )

            candidates.append(candidate)

            logger.info(
                f"Stage 1: ✓ {symbol} {direction} "
                f"(confidence: {ema_analysis.confidence_score}%, "
                f"volume: {volume_analysis.volume_ratio_current:.2f}x, "
                f"pattern: {ema_analysis.alignment}/{ema_analysis.crossover})"
            )

        except Exception as e:
            logger.debug(f"Stage 1: Error processing {symbol}: {e}")
            continue

    # Сортируем по confidence
    candidates.sort(key=lambda x: x.confidence, reverse=True)

    total_time = time.time() - start_time

    # ===================================================================
    # ИТОГОВАЯ СТАТИСТИКА
    # ===================================================================
    logger.info("=" * 70)
    logger.info("STAGE 1 COMPLETE")
    logger.info("=" * 70)
    logger.info(f"Total time: {total_time:.1f}s")
    logger.info(f"Processed: {processed} pairs")
    logger.info(f"✅ Signals found: {len(candidates)}")
    logger.info(f"❌ Skipped breakdown:")
    logger.info(f"   • Invalid data: {skipped_invalid}")
    logger.info(f"   • Low confidence: {skipped_confidence}")
    logger.info(f"   • Low volume: {skipped_volume}")
    logger.info(f"   • No direction: {skipped_direction}")

    if candidates:
        logger.info(f"\nTop 5 candidates:")
        for i, c in enumerate(candidates[:5], 1):
            logger.info(
                f"  {i}. {c.symbol} {c.direction} "
                f"(conf: {c.confidence}%, vol: {c.volume_analysis.volume_ratio_current:.2f}x)"
            )

    logger.info("=" * 70)

    return candidates


def _determine_direction(ema_analysis: 'EMAAnalysis') -> str:
    """
    Определить направление сигнала на основе EMA анализа

    Priority:
    1. Alignment (BULLISH/BEARISH)
    2. Crossover (GOLDEN/DEATH)
    3. Pullback (BULLISH_BOUNCE/BEARISH_BOUNCE)
    4. Compression (BREAKOUT_UP/BREAKOUT_DOWN)
    """
    alignment = ema_analysis.alignment
    crossover = ema_analysis.crossover
    pullback = ema_analysis.pullback
    compression = ema_analysis.compression

    # Priority 1: Alignment
    if alignment == 'BULLISH':
        return 'LONG'
    elif alignment == 'BEARISH':
        return 'SHORT'

    # Priority 2: Crossovers
    if crossover == 'GOLDEN':
        return 'LONG'
    elif crossover == 'DEATH':
        return 'SHORT'

    # Priority 3: Pullback
    if pullback == 'BULLISH_BOUNCE':
        return 'LONG'
    elif pullback == 'BEARISH_BOUNCE':
        return 'SHORT'

    # Priority 4: Compression breakout
    if compression == 'BREAKOUT_UP':
        return 'LONG'
    elif compression == 'BREAKOUT_DOWN':
        return 'SHORT'

    return 'NONE'