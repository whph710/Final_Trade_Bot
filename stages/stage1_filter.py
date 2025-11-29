"""
Stage 1: Signal Filtering
Файл: stages/stage1_filter.py

Первичная фильтрация пар на базе Triple EMA и Volume
"""

import logging
from typing import List, Dict
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class SignalCandidate:
    """
    Кандидат сигнала после Stage 1

    Attributes:
        symbol: Торговая пара
        direction: 'LONG' | 'SHORT'
        confidence: Базовый confidence (0-100)
        ema_analysis: EMAAnalysis результат
        volume_analysis: VolumeAnalysis результат
    """
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

    Args:
        pairs: Список торговых пар
        min_confidence: Минимальный confidence для прохождения
        min_volume_ratio: Минимальный volume ratio

    Returns:
        Список SignalCandidate объектов
    """
    from data_providers import fetch_candles, normalize_candles
    from indicators import analyze_triple_ema, analyze_volume
    from config import config

    if not pairs:
        logger.warning("Stage 1: No pairs provided")
        return []

    logger.info(f"Stage 1: Analyzing {len(pairs)} pairs")

    candidates = []
    processed = 0

    # Загружаем свечи для всех пар (batch будет позже)
    for symbol in pairs:
        try:
            processed += 1

            # Загрузка свечей
            candles_raw = await fetch_candles(
                symbol,
                config.TIMEFRAME_LONG,
                config.QUICK_SCAN_CANDLES
            )

            if not candles_raw:
                continue

            # Нормализация
            candles = normalize_candles(
                candles_raw,
                symbol=symbol,
                interval=config.TIMEFRAME_LONG
            )

            if not candles or not candles.is_valid:
                continue

            # EMA анализ
            ema_analysis = analyze_triple_ema(
                candles,
                fast=config.EMA_FAST,
                medium=config.EMA_MEDIUM,
                slow=config.EMA_SLOW
            )

            if not ema_analysis:
                continue

            # Volume анализ
            volume_analysis = analyze_volume(
                candles,
                window=config.VOLUME_WINDOW
            )

            if not volume_analysis:
                continue

            # Проверка базовых условий
            if ema_analysis.confidence < min_confidence:
                continue

            if volume_analysis.volume_ratio_current < min_volume_ratio:
                continue

            # Определяем направление
            direction = _determine_direction(ema_analysis)

            if direction == 'NONE':
                continue

            # Создаём кандидата
            candidate = SignalCandidate(
                symbol=symbol,
                direction=direction,
                confidence=ema_analysis.confidence,
                ema_analysis=ema_analysis,
                volume_analysis=volume_analysis
            )

            candidates.append(candidate)

            logger.debug(
                f"Stage 1: {symbol} {direction} "
                f"(confidence: {ema_analysis.confidence}%)"
            )

        except Exception as e:
            logger.debug(f"Stage 1: Error processing {symbol}: {e}")
            continue

    # Сортируем по confidence
    candidates.sort(key=lambda x: x.confidence, reverse=True)

    logger.info(
        f"Stage 1 complete: {len(candidates)} signals found "
        f"from {processed} pairs"
    )

    return candidates


def _determine_direction(ema_analysis: 'EMAAnalysis') -> str:
    """
    Определить направление сигнала на основе EMA анализа

    Priority:
    1. Alignment (BULLISH/BEARISH)
    2. Crossover (GOLDEN/DEATH)
    3. Pullback (BULLISH_BOUNCE/BEARISH_BOUNCE)
    4. Compression (BREAKOUT_UP/BREAKOUT_DOWN)

    Args:
        ema_analysis: EMAAnalysis объект

    Returns:
        'LONG' | 'SHORT' | 'NONE'
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