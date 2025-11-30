"""
Stage 2: AI Pair Selection - FIXED
Файл: stages/stage2_selection.py

ИСПРАВЛЕНИЯ:
- Добавлено детальное логирование каждого этапа
- Исправлена проверка на None в normalize_candles
- Улучшена обработка ошибок
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
    failed_symbols = []

    for idx, candidate in enumerate(candidates, 1):
        symbol = candidate.symbol

        try:
            logger.debug(f"Stage 2: [{idx}/{len(candidates)}] Processing {symbol}...")

            # Загрузка 1H и 4H свечей
            logger.debug(f"Stage 2: {symbol} fetching candles...")

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

            # ИСПРАВЛЕНО: Детальное логирование
            logger.debug(
                f"Stage 2: {symbol} loaded - "
                f"1H: {len(candles_1h_raw) if candles_1h_raw else 0} candles, "
                f"4H: {len(candles_4h_raw) if candles_4h_raw else 0} candles"
            )

            if not candles_1h_raw or not candles_4h_raw:
                logger.debug(f"Stage 2: {symbol} SKIP - Missing raw candles")
                failed_symbols.append((symbol, "Missing raw candles"))
                continue

            # Нормализация
            logger.debug(f"Stage 2: {symbol} normalizing candles...")

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

            # ✅ КРИТИЧНО: Проверка на None (не на truthy/falsy!)
            if candles_1h is None:
                logger.warning(f"Stage 2: {symbol} SKIP - 1H normalization returned None")
                failed_symbols.append((symbol, "1H normalization failed"))
                continue

            if candles_4h is None:
                logger.warning(f"Stage 2: {symbol} SKIP - 4H normalization returned None")
                failed_symbols.append((symbol, "4H normalization failed"))
                continue

            # Проверка валидности
            if not candles_1h.is_valid:
                logger.warning(f"Stage 2: {symbol} SKIP - 1H candles invalid")
                failed_symbols.append((symbol, "1H candles invalid"))
                continue

            if not candles_4h.is_valid:
                logger.warning(f"Stage 2: {symbol} SKIP - 4H candles invalid")
                failed_symbols.append((symbol, "4H candles invalid"))
                continue

            # Рассчитываем compact indicators
            logger.debug(f"Stage 2: {symbol} calculating indicators...")

            indicators_1h = _calculate_compact_indicators(candles_1h, symbol, "1H")
            indicators_4h = _calculate_compact_indicators(candles_4h, symbol, "4H")

            # ✅ КРИТИЧНО: Проверка на None + наличие 'current'
            if indicators_1h is None:
                logger.warning(f"Stage 2: {symbol} SKIP - 1H indicators calculation returned None")
                failed_symbols.append((symbol, "1H indicators failed"))
                continue

            if indicators_4h is None:
                logger.warning(f"Stage 2: {symbol} SKIP - 4H indicators calculation returned None")
                failed_symbols.append((symbol, "4H indicators failed"))
                continue

            if not indicators_1h.get('current'):
                logger.warning(f"Stage 2: {symbol} SKIP - Missing 'current' in 1H indicators")
                failed_symbols.append((symbol, "Missing 1H current data"))
                continue

            if not indicators_4h.get('current'):
                logger.warning(f"Stage 2: {symbol} SKIP - Missing 'current' in 4H indicators")
                failed_symbols.append((symbol, "Missing 4H current data"))
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

            logger.info(f"Stage 2: ✓ {symbol} prepared successfully")

        except Exception as e:
            logger.error(f"Stage 2: {symbol} ERROR - {e}", exc_info=True)
            failed_symbols.append((symbol, f"Exception: {str(e)[:50]}"))
            continue

    # Логирование результатов подготовки
    logger.info("=" * 70)
    logger.info(f"Stage 2: Data preparation complete")
    logger.info(f"  • Successfully prepared: {len(ai_input_data)}/{len(candidates)}")
    logger.info(f"  • Failed: {len(failed_symbols)}/{len(candidates)}")

    if failed_symbols and len(failed_symbols) <= 10:
        logger.info(f"\nFailed symbols:")
        for sym, reason in failed_symbols:
            logger.info(f"  • {sym}: {reason}")
    elif failed_symbols:
        logger.info(f"\nShowing first 10 failed symbols:")
        for sym, reason in failed_symbols[:10]:
            logger.info(f"  • {sym}: {reason}")
        logger.info(f"  ... and {len(failed_symbols) - 10} more")

    logger.info("=" * 70)

    if not ai_input_data:
        logger.error("Stage 2: No valid AI input data prepared - CRITICAL FAILURE")
        logger.error("All candidates failed validation. Check:")
        logger.error("  1. Bybit API connectivity")
        logger.error("  2. Candle data validity")
        logger.error("  3. Indicator calculation parameters")
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
    else:
        logger.warning("Stage 2: AI selected 0 pairs")

    return selected_pairs


def _calculate_compact_indicators(candles, symbol: str = "UNKNOWN", tf: str = "UNKNOWN") -> Dict:
    """
    Рассчитать compact indicators для Stage 2

    ИСПРАВЛЕНО: Возвращает None при ошибках (не пустой dict!)

    Args:
        candles: NormalizedCandles объект
        symbol: Символ (для логирования)
        tf: Timeframe (для логирования)

    Returns:
        Dict с indicators ИЛИ None при ошибке
    """
    from indicators import analyze_triple_ema, analyze_rsi, analyze_volume

    try:
        # EMA
        ema_analysis = analyze_triple_ema(candles)

        if not ema_analysis:
            logger.debug(f"Stage 2: {symbol} {tf} - EMA analysis returned None")
            return None

        # RSI
        rsi_analysis = analyze_rsi(candles)

        if not rsi_analysis:
            logger.debug(f"Stage 2: {symbol} {tf} - RSI analysis returned None")
            return None

        # Volume
        volume_analysis = analyze_volume(candles)

        if not volume_analysis:
            logger.debug(f"Stage 2: {symbol} {tf} - Volume analysis returned None")
            return None

        # Извлекаем историю (последние 30 значений)
        from indicators.ema import calculate_ema
        from indicators.rsi import calculate_rsi
        from indicators.volume import calculate_volume_ratio

        ema9 = calculate_ema(candles.closes, 9)
        ema21 = calculate_ema(candles.closes, 21)
        ema50 = calculate_ema(candles.closes, 50)
        rsi = calculate_rsi(candles.closes, 14)
        volume_ratios = calculate_volume_ratio(candles.volumes, 20)

        result = {
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

        # ✅ ФИНАЛЬНАЯ ПРОВЕРКА
        if not result.get('current'):
            logger.debug(f"Stage 2: {symbol} {tf} - Failed to build 'current' dict")
            return None

        if not all(k in result['current'] for k in ['price', 'ema9', 'ema21', 'ema50', 'rsi', 'volume_ratio']):
            logger.debug(f"Stage 2: {symbol} {tf} - Missing keys in 'current' dict")
            return None

        logger.debug(f"Stage 2: {symbol} {tf} - Indicators calculated successfully")
        return result

    except Exception as e:
        logger.error(f"Stage 2: {symbol} {tf} - Indicators calculation error: {e}")
        return None


def _extract_last_candles(candles_raw: List, count: int) -> List:
    """Извлечь последние N свечей"""
    if not candles_raw:
        return []

    return candles_raw[-count:] if len(candles_raw) > count else candles_raw