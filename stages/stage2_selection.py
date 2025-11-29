"""
Stage 2: AI Pair Selection
Файл: stages/stage2_selection.py

AI отбор лучших пар на базе compact multi-timeframe данных
"""

import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


async def run_stage2(
        candidates: List['SignalCandidate'],
        max_pairs: int = 3
) -> List[str]:
    """
    Stage 2: AI выбор лучших пар из кандидатов

    Args:
        candidates: Список SignalCandidate из Stage 1
        max_pairs: Максимальное количество пар для выбора

    Returns:
        Список выбранных символов (например ['BTCUSDT', 'ETHUSDT'])
    """
    from data_providers import fetch_candles, normalize_candles
    from indicators import analyze_triple_ema, analyze_rsi, analyze_volume
    from ai.ai_router import AIRouter
    from config import config

    if not candidates:
        logger.warning("Stage 2: No candidates provided")
        return []

    logger.info(
        f"Stage 2: Selecting from {len(candidates)} candidates "
        f"(max: {max_pairs})"
    )

    # Подготовка compact данных для AI
    ai_input_data = []

    for candidate in candidates:
        symbol = candidate.symbol

        try:
            # Загрузка 1H и 4H свечей
            candles_1h_raw = await fetch_candles(
                symbol,
                config.TIMEFRAME_SHORT,
                config.STAGE2_CANDLES_1H
            )

            candles_4h_raw = await fetch_candles(
                symbol,
                config.TIMEFRAME_LONG,
                config.STAGE2_CANDLES_4H
            )

            if not candles_1h_raw or not candles_4h_raw:
                logger.debug(f"Stage 2: Missing candles for {symbol}")
                continue

            # Нормализация
            candles_1h = normalize_candles(
                candles_1h_raw,
                symbol=symbol,
                interval=config.TIMEFRAME_SHORT
            )

            candles_4h = normalize_candles(
                candles_4h_raw,
                symbol=symbol,
                interval=config.TIMEFRAME_LONG
            )

            if not candles_1h or not candles_4h:
                continue

            # Рассчитываем compact indicators
            indicators_1h = _calculate_compact_indicators(candles_1h)
            indicators_4h = _calculate_compact_indicators(candles_4h)

            if not indicators_1h or not indicators_4h:
                continue

            # Формируем данные для AI
            ai_input_data.append({
                'symbol': symbol,
                'confidence': candidate.confidence,
                'direction': candidate.direction,
                'candles_1h': _extract_last_candles(candles_1h_raw, 30),
                'candles_4h': _extract_last_candles(candles_4h_raw, 30),
                'indicators_1h': indicators_1h,
                'indicators_4h': indicators_4h
            })

        except Exception as e:
            logger.debug(f"Stage 2: Error preparing {symbol}: {e}")
            continue

    if not ai_input_data:
        logger.warning("Stage 2: No valid AI input data")
        return []

    logger.info(
        f"Stage 2: Sending {len(ai_input_data)} pairs to AI "
        f"(provider: {config.STAGE2_PROVIDER})"
    )

    # Вызов AI для отбора
    ai_router = AIRouter()

    selected_pairs = await ai_router.select_pairs(
        pairs_data=ai_input_data,
        max_pairs=max_pairs
    )

    logger.info(f"Stage 2 complete: AI selected {len(selected_pairs)} pairs")

    if selected_pairs:
        logger.info(f"Selected: {selected_pairs}")

    return selected_pairs


def _calculate_compact_indicators(candles) -> Dict:
    """
    Рассчитать compact indicators для Stage 2

    Returns:
        {
            'current': {...},
            'ema9': [...],
            'ema21': [...],
            'ema50': [...],
            'rsi': [...],
            'volume_ratio': [...]
        }
    """
    from indicators import analyze_triple_ema, analyze_rsi, analyze_volume

    try:
        # EMA
        ema_analysis = analyze_triple_ema(candles)

        # RSI
        rsi_analysis = analyze_rsi(candles)

        # Volume
        volume_analysis = analyze_volume(candles)

        if not ema_analysis or not rsi_analysis or not volume_analysis:
            return {}

        # Извлекаем историю (последние 30 значений)
        from indicators.ema import calculate_ema
        from indicators.rsi import calculate_rsi
        from indicators.volume import calculate_volume_ratio

        ema9 = calculate_ema(candles.closes, 9)
        ema21 = calculate_ema(candles.closes, 21)
        ema50 = calculate_ema(candles.closes, 50)
        rsi = calculate_rsi(candles.closes, 14)
        volume_ratios = calculate_volume_ratio(candles.volumes, 20)

        return {
            'current': {
                'price': float(candles.closes[-1]),
                'ema9': ema_analysis.ema9_current,
                'ema21': ema_analysis.ema21_current,
                'ema50': ema_analysis.ema50_current,
                'rsi': rsi_analysis.rsi_current,
                'volume_ratio': volume_analysis.volume_ratio_current
            },
            'ema9': [float(x) for x in ema9[-30:]],
            'ema21': [float(x) for x in ema21[-30:]],
            'ema50': [float(x) for x in ema50[-30:]],
            'rsi': [float(x) for x in rsi[-30:]],
            'volume_ratio': [float(x) for x in volume_ratios[-30:]]
        }

    except Exception as e:
        logger.error(f"Compact indicators calculation error: {e}")
        return {}


def _extract_last_candles(candles_raw: List, count: int) -> List:
    """Извлечь последние N свечей"""
    if not candles_raw:
        return []

    return candles_raw[-count:] if len(candles_raw) > count else candles_raw