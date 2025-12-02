"""
Stage 2: AI Pair Selection - LEVELS + ATR Strategy
Файл: stages/stage2_selection.py

ОБНОВЛЕНО:
- Передаём данные о уровнях + ATR волнах
- Убраны SMC данные (OB, FVG, Sweeps)
"""

import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


async def run_stage2(
        candidates: List['SignalCandidate'],
        max_pairs: int = 3
) -> List[str]:
    """Stage 2: AI выбор лучших пар из кандидатов с уровнями + ATR"""
    from data_providers import fetch_multiple_candles, normalize_candles
    from ai.ai_router import AIRouter
    from config import config
    import time

    if not candidates:
        logger.warning("Stage 2 (LEVELS+ATR): No candidates provided")
        return []

    logger.info(
        f"Stage 2 (LEVELS+ATR): Selecting from {len(candidates)} candidates "
        f"(max: {max_pairs})"
    )

    start_time = time.time()

    # Загрузка 1H + 4H свечей
    logger.info(f"Stage 2: Loading 1H + 4H candles for {len(candidates)} pairs...")

    requests = []
    for candidate in candidates:
        symbol = candidate.symbol
        requests.append({
            'symbol': symbol,
            'interval': config.TIMEFRAME_SHORT,
            'limit': config.STAGE2_CANDLES_1H,
            'timeframe': '1H'
        })
        requests.append({
            'symbol': symbol,
            'interval': config.TIMEFRAME_LONG,
            'limit': config.STAGE2_CANDLES_4H,
            'timeframe': '4H'
        })

    batch_results = await fetch_multiple_candles(requests)

    load_time = time.time() - start_time
    logger.info(
        f"Stage 2: Loaded {len(batch_results)}/{len(requests)} requests "
        f"in {load_time:.1f}s"
    )

    # Группируем по символам
    candles_by_symbol = _group_candles_by_symbol(batch_results)

    # Формируем AI input data
    ai_input_data = []
    failed_symbols = []

    for idx, candidate in enumerate(candidates, 1):
        symbol = candidate.symbol

        try:
            logger.debug(f"Stage 2: [{idx}/{len(candidates)}] Processing {symbol}...")

            # Получаем свечи
            symbol_data = candles_by_symbol.get(symbol, {})

            candles_1h_raw = symbol_data.get('1H')
            candles_4h_raw = symbol_data.get('4H')

            if not candles_1h_raw or not candles_4h_raw:
                logger.debug(f"Stage 2: {symbol} SKIP - Missing candles")
                failed_symbols.append((symbol, "Missing candles"))
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

            if not candles_1h or not candles_1h.is_valid:
                failed_symbols.append((symbol, "1H candles invalid"))
                continue

            if not candles_4h or not candles_4h.is_valid:
                failed_symbols.append((symbol, "4H candles invalid"))
                continue

            # Рассчитываем compact indicators
            indicators_1h = _calculate_compact_indicators(candles_1h, symbol, "1H")
            indicators_4h = _calculate_compact_indicators(candles_4h, symbol, "4H")

            if not indicators_1h or not indicators_4h:
                failed_symbols.append((symbol, "Indicators failed"))
                continue

            # ✅ ФОРМИРУЕМ LEVELS DATA (вместо SMC)
            levels_data = _prepare_levels_data(candidate)

            # Формируем данные для AI
            ai_input_data.append({
                'symbol': symbol,
                'direction': candidate.direction,
                'confidence': candidate.confidence,
                'pattern_type': candidate.pattern_type,

                # ✅ LEVELS + ATR (вместо SMC)
                'sr_analysis': levels_data['sr_analysis'],
                'wave_analysis': levels_data['wave_analysis'],
                'ema200_context': levels_data['ema200_context'],

                # Context
                'volume_ratio': candidate.volume_analysis.volume_ratio_current,
                'rsi_value': candidate.rsi_value,

                # Multi-TF data
                'candles_1h': _extract_last_candles(candles_1h_raw, 30),
                'candles_4h': _extract_last_candles(candles_4h_raw, 30),
                'indicators_1h': indicators_1h,
                'indicators_4h': indicators_4h
            })

            logger.info(f"Stage 2: ✓ {symbol} prepared successfully")

        except Exception as e:
            logger.error(f"Stage 2: {symbol} ERROR - {e}", exc_info=False)
            failed_symbols.append((symbol, f"Exception: {str(e)[:50]}"))
            continue

    prep_time = time.time() - start_time

    # Логирование результатов
    logger.info("=" * 70)
    logger.info(f"Stage 2: Data preparation complete")
    logger.info(f"  • Successfully prepared: {len(ai_input_data)}/{len(candidates)}")
    logger.info(f"  • Failed: {len(failed_symbols)}/{len(candidates)}")
    logger.info(f"  • Preparation time: {prep_time:.1f}s")

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
        logger.error("Stage 2: No valid AI input data - CRITICAL FAILURE")
        return []

    logger.info(
        f"Stage 2: Sending {len(ai_input_data)} pairs to AI "
        f"(provider: {config.STAGE2_PROVIDER})"
    )

    # Вызов AI
    ai_router = AIRouter()

    selected_pairs = await ai_router.select_pairs(
        pairs_data=ai_input_data,
        max_pairs=max_pairs
    )

    total_time = time.time() - start_time

    logger.info(
        f"Stage 2 complete: AI selected {len(selected_pairs)} pairs "
        f"(total time: {total_time:.1f}s)"
    )

    if selected_pairs:
        logger.info(f"Selected: {selected_pairs}")
    else:
        logger.warning("Stage 2: AI selected 0 pairs")

    return selected_pairs


def _prepare_levels_data(candidate: 'SignalCandidate') -> Dict:
    """
    ✅ НОВОЕ: Подготовить данные уровней + ATR для AI
    """
    # Support/Resistance (упрощённо)
    sr_data = {
        'total_levels': len(candidate.sr_analysis.all_levels),
        'current_zone': candidate.sr_analysis.current_price_zone
    }

    nearest_support = candidate.sr_analysis.nearest_support
    if nearest_support:
        sr_data['nearest_support'] = {
            'price': nearest_support.price,
            'touches': nearest_support.touches,
            'strength': nearest_support.strength,
            'distance_pct': nearest_support.distance_from_current_pct
        }

    nearest_resistance = candidate.sr_analysis.nearest_resistance
    if nearest_resistance:
        sr_data['nearest_resistance'] = {
            'price': nearest_resistance.price,
            'touches': nearest_resistance.touches,
            'strength': nearest_resistance.strength,
            'distance_pct': nearest_resistance.distance_from_current_pct
        }

    # Wave Analysis (упрощённо)
    wave_data = {}
    if candidate.wave_analysis:
        wave_data = {
            'wave_type': candidate.wave_analysis.wave_type,
            'average_wave_length': candidate.wave_analysis.average_wave_length,
            'current_progress': candidate.wave_analysis.current_wave_progress,
            'is_early_entry': candidate.wave_analysis.is_early_entry
        }

    # EMA200 Context
    ema200_data = candidate.ema200_context

    return {
        'sr_analysis': sr_data,
        'wave_analysis': wave_data,
        'ema200_context': ema200_data
    }


def _group_candles_by_symbol(batch_results: List[Dict]) -> Dict[str, Dict]:
    """Группировать результаты batch загрузки по символам"""
    grouped = {}

    for result in batch_results:
        if not result.get('success'):
            continue

        symbol = result['symbol']
        klines = result.get('klines', [])
        timeframe = result.get('timeframe', 'UNKNOWN')

        if symbol not in grouped:
            grouped[symbol] = {}

        grouped[symbol][timeframe] = klines

    return grouped


def _calculate_compact_indicators(candles, symbol: str = "UNKNOWN", tf: str = "UNKNOWN") -> Dict:
    """Рассчитать compact indicators"""
    try:
        if candles is None or not candles.is_valid:
            return None

        if len(candles.closes) < 50:
            return None

        from indicators.ema import calculate_ema
        from indicators.rsi import calculate_rsi
        from indicators.macd import calculate_macd
        from indicators.volume import calculate_volume_ratio
        from config import config

        ema9 = calculate_ema(candles.closes, config.EMA_FAST)
        ema21 = calculate_ema(candles.closes, config.EMA_MEDIUM)
        ema50 = calculate_ema(candles.closes, config.EMA_SLOW)
        rsi = calculate_rsi(candles.closes, config.RSI_PERIOD)
        volume_ratios = calculate_volume_ratio(candles.volumes, config.VOLUME_WINDOW)
        macd_data = calculate_macd(candles.closes)

        current = {
            'price': float(candles.closes[-1]),
            'ema9': float(ema9[-1]),
            'ema21': float(ema21[-1]),
            'ema50': float(ema50[-1]),
            'rsi': float(rsi[-1]),
            'volume_ratio': float(volume_ratios[-1]),
            'macd_line': float(macd_data.line[-1]),
            'macd_histogram': float(macd_data.histogram[-1])
        }

        return {
            'current': current,
            'ema9': [float(x) for x in ema9[-30:]],
            'ema21': [float(x) for x in ema21[-30:]],
            'ema50': [float(x) for x in ema50[-30:]],
            'rsi': [float(x) for x in rsi[-30:]],
            'volume_ratio': [float(x) for x in volume_ratios[-30:]],
            'macd_line': [float(x) for x in macd_data.line[-30:]],
            'macd_histogram': [float(x) for x in macd_data.histogram[-30:]]
        }

    except Exception as e:
        logger.error(f"Stage 2: {symbol} {tf} - Indicators error: {e}")
        return None


def _extract_last_candles(candles_raw: List, count: int) -> List:
    """Извлечь последние N свечей"""
    if not candles_raw:
        return []
    return candles_raw[-count:] if len(candles_raw) > count else candles_raw