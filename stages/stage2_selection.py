"""
Stage 2: AI Pair Selection - ENHANCED WITH FULL HISTORY
Файл: stages/stage2_selection.py

✅ УЛУЧШЕНО:
- Добавлены исторические данные для всех индикаторов (50 баров)
- Добавлена история уровней S/R
- Добавлена история волн ATR
- Добавлена история EMA200
- AI видит полную картину рынка на 1H и 4H
"""

import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


async def run_stage2(
        candidates: List['SignalCandidate'],
        max_pairs: int = 3
) -> List[str]:
    """Stage 2: AI выбор лучших пар с ПОЛНОЙ историей данных"""
    from data_providers import fetch_multiple_candles, normalize_candles
    from ai.ai_router import AIRouter
    from config import config
    import time

    if not candidates:
        logger.warning("Stage 2 (ENHANCED): No candidates provided")
        return []

    logger.info(
        f"Stage 2 (ENHANCED): Selecting from {len(candidates)} candidates "
        f"(max: {max_pairs}) with full historical data"
    )

    start_time = time.time()

    # Загрузка 1H + 4H свечей (увеличено для истории)
    logger.info(f"Stage 2: Loading 1H + 4H candles for {len(candidates)} pairs...")

    requests = []
    for candidate in candidates:
        symbol = candidate.symbol
        requests.append({
            'symbol': symbol,
            'interval': config.TIMEFRAME_SHORT,
            'limit': 100,  # Увеличено с 60 до 100 для истории
            'timeframe': '1H'
        })
        requests.append({
            'symbol': symbol,
            'interval': config.TIMEFRAME_LONG,
            'limit': 100,  # Увеличено с 60 до 100 для истории
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

            # ✅ НОВОЕ: Рассчитываем indicators с ПОЛНОЙ историей (50 баров)
            indicators_1h = _calculate_full_indicators_stage2(candles_1h, symbol, "1H")
            indicators_4h = _calculate_full_indicators_stage2(candles_4h, symbol, "4H")

            if not indicators_1h or not indicators_4h:
                failed_symbols.append((symbol, "Indicators failed"))
                continue

            # ✅ НОВОЕ: Подготовка levels data с ИСТОРИЕЙ
            levels_data = _prepare_levels_data_with_history(candidate, candles_4h)

            # Формируем данные для AI
            ai_input_data.append({
                'symbol': symbol,
                'direction': candidate.direction,
                'confidence': candidate.confidence,
                'pattern_type': candidate.pattern_type,

                # ✅ LEVELS + ATR + EMA200 с ИСТОРИЕЙ
                'sr_analysis': levels_data['sr_analysis'],
                'wave_analysis': levels_data['wave_analysis'],
                'ema200_context': levels_data['ema200_context'],
                'sr_history': levels_data['sr_history'],
                'ema200_history': levels_data['ema200_history'],

                # Context
                'volume_ratio': candidate.volume_analysis.volume_ratio_current,
                'rsi_value': candidate.rsi_value,

                # Multi-TF data (последние 30 свечей для компактности)
                'candles_1h': _extract_last_candles(candles_1h_raw, 30),
                'candles_4h': _extract_last_candles(candles_4h_raw, 30),

                # ✅ ПОЛНЫЕ ИНДИКАТОРЫ С ИСТОРИЕЙ 50 БАРОВ
                'indicators_1h': indicators_1h,
                'indicators_4h': indicators_4h
            })

            logger.info(f"Stage 2: ✓ {symbol} prepared with full history")

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
        f"(provider: {config.STAGE2_PROVIDER}) with FULL HISTORY"
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


def _prepare_levels_data_with_history(
        candidate: 'SignalCandidate',
        candles_4h: 'NormalizedCandles'
) -> Dict:
    """
    ✅ НОВОЕ: Подготовить данные уровней + ATR + EMA200 с ИСТОРИЕЙ
    """
    from indicators import analyze_ema200

    # Support/Resistance (текущие + история уровней)
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
    else:
        sr_data['nearest_support'] = None

    nearest_resistance = candidate.sr_analysis.nearest_resistance
    if nearest_resistance:
        sr_data['nearest_resistance'] = {
            'price': nearest_resistance.price,
            'touches': nearest_resistance.touches,
            'strength': nearest_resistance.strength,
            'distance_pct': nearest_resistance.distance_from_current_pct
        }
    else:
        sr_data['nearest_resistance'] = None

    # ✅ НОВОЕ: История уровней S/R (последние 50 свечей)
    sr_history = _extract_sr_levels_history(candidate.sr_analysis, candles_4h)

    # Wave Analysis (текущая + история волн)
    wave_data = {}
    if candidate.wave_analysis:
        wave_data = {
            'wave_type': candidate.wave_analysis.wave_type,
            'average_wave_length': candidate.wave_analysis.average_wave_length,
            'current_progress': candidate.wave_analysis.current_wave_progress,
            'is_early_entry': candidate.wave_analysis.is_early_entry,
            'wave_lengths': candidate.wave_analysis.wave_lengths  # ✅ История волн
        }
    else:
        wave_data = {
            'wave_type': 'NEUTRAL',
            'average_wave_length': 0,
            'current_progress': 0,
            'is_early_entry': False,
            'wave_lengths': []
        }

    # EMA200 Context (текущий + история)
    ema200_data = candidate.ema200_context

    # ✅ НОВОЕ: История EMA200 (последние 50 баров)
    ema200_history = _extract_ema200_history(candles_4h)

    return {
        'sr_analysis': sr_data,
        'wave_analysis': wave_data,
        'ema200_context': ema200_data,
        'sr_history': sr_history,
        'ema200_history': ema200_history
    }


def _extract_sr_levels_history(sr_analysis, candles) -> List[Dict]:
    """
    ✅ НОВОЕ: Извлечь историю уровней S/R

    Возвращает список уровней с их параметрами за последние 50 свечей
    """
    if not sr_analysis or not sr_analysis.all_levels:
        return []

    history = []
    for level in sr_analysis.all_levels[:10]:  # Топ 10 уровней
        history.append({
            'price': level.price,
            'type': level.level_type,
            'touches': level.touches,
            'strength': level.strength,
            'distance_pct': level.distance_from_current_pct
        })

    return history


def _extract_ema200_history(candles) -> List[float]:
    """
    ✅ НОВОЕ: Извлечь историю EMA200
    """
    if not candles or len(candles.closes) < 200:
        return []

    try:
        from indicators.ema import calculate_ema
        ema200 = calculate_ema(candles.closes, 200)

        # Последние 50 значений
        return [float(x) for x in ema200[-50:]]
    except:
        return []


def _calculate_full_indicators_stage2(candles, symbol: str = "UNKNOWN", tf: str = "UNKNOWN") -> Dict:
    """
    ✅ НОВОЕ: Рассчитать ПОЛНЫЕ индикаторы с историей 50 баров для Stage 2
    """
    try:
        if candles is None or not candles.is_valid:
            return None

        if len(candles.closes) < 50:
            return None

        from indicators.ema import calculate_ema
        from indicators.rsi import calculate_rsi
        from indicators.macd import calculate_macd
        from indicators.volume import calculate_volume_ratio
        from indicators.atr import calculate_atr
        from config import config

        ema9 = calculate_ema(candles.closes, config.EMA_FAST)
        ema21 = calculate_ema(candles.closes, config.EMA_MEDIUM)
        ema50 = calculate_ema(candles.closes, config.EMA_SLOW)
        rsi = calculate_rsi(candles.closes, config.RSI_PERIOD)
        volume_ratios = calculate_volume_ratio(candles.volumes, config.VOLUME_WINDOW)
        macd_data = calculate_macd(candles.closes)
        atr = calculate_atr(candles, config.ATR_PERIOD)

        current = {
            'price': float(candles.closes[-1]),
            'ema9': float(ema9[-1]),
            'ema21': float(ema21[-1]),
            'ema50': float(ema50[-1]),
            'rsi': float(rsi[-1]),
            'volume_ratio': float(volume_ratios[-1]),
            'macd_line': float(macd_data.line[-1]),
            'macd_histogram': float(macd_data.histogram[-1]),
            'macd_signal': float(macd_data.signal[-1]),
            'atr': atr
        }

        # ✅ ИСТОРИЯ 50 БАРОВ
        history_length = 50

        return {
            'current': current,

            # ✅ ПОЛНАЯ ИСТОРИЯ ИНДИКАТОРОВ
            'price_history': [float(x) for x in candles.closes[-history_length:]],
            'ema9_history': [float(x) for x in ema9[-history_length:]],
            'ema21_history': [float(x) for x in ema21[-history_length:]],
            'ema50_history': [float(x) for x in ema50[-history_length:]],
            'rsi_history': [float(x) for x in rsi[-history_length:]],
            'volume_ratio_history': [float(x) for x in volume_ratios[-history_length:]],
            'macd_line_history': [float(x) for x in macd_data.line[-history_length:]],
            'macd_histogram_history': [float(x) for x in macd_data.histogram[-history_length:]],
            'macd_signal_history': [float(x) for x in macd_data.signal[-history_length:]],

            # ✅ НОВОЕ: История OHLCV
            'highs_history': [float(x) for x in candles.highs[-history_length:]],
            'lows_history': [float(x) for x in candles.lows[-history_length:]],
            'volumes_history': [float(x) for x in candles.volumes[-history_length:]]
        }

    except Exception as e:
        logger.error(f"Stage 2: {symbol} {tf} - Full indicators error: {e}")
        return None


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


def _extract_last_candles(candles_raw: List, count: int) -> List:
    """Извлечь последние N свечей"""
    if not candles_raw:
        return []
    return candles_raw[-count:] if len(candles_raw) > count else candles_raw