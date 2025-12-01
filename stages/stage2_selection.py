"""
Stage 2: AI Pair Selection - SMC DATA ADAPTATION
Файл: stages/stage2_selection.py

ИЗМЕНЕНО:
- Передаём SMC данные (OB, FVG, Sweeps) в AI
- Упрощённый формат для быстрой селекции
"""

import logging
import asyncio
import numpy as np
from typing import List, Dict

logger = logging.getLogger(__name__)


async def run_stage2(
        candidates: List['SignalCandidate'],
        max_pairs: int = 3
) -> List[str]:
    """
    Stage 2: AI выбор лучших пар из SMC кандидатов
    """
    from data_providers import fetch_multiple_candles, normalize_candles
    from ai.ai_router import AIRouter
    from config import config
    import time

    if not candidates:
        logger.warning("Stage 2 (SMC): No candidates provided")
        return []

    logger.info(
        f"Stage 2 (SMC): Selecting from {len(candidates)} SMC candidates "
        f"(max: {max_pairs})"
    )

    start_time = time.time()

    # ===================================================================
    # ЗАГРУЗКА 1H СВЕЧЕЙ ДЛЯ MULTI-TF АНАЛИЗА
    # ===================================================================
    logger.info(f"Stage 2 (SMC): Loading 1H candles for {len(candidates)} pairs...")

    requests = []
    for candidate in candidates:
        symbol = candidate.symbol

        # 1H candles
        requests.append({
            'symbol': symbol,
            'interval': config.TIMEFRAME_SHORT,
            'limit': config.STAGE2_CANDLES_1H,
            'timeframe': '1H'
        })

        # 4H candles
        requests.append({
            'symbol': symbol,
            'interval': config.TIMEFRAME_LONG,
            'limit': config.STAGE2_CANDLES_4H,
            'timeframe': '4H'
        })

    batch_results = await fetch_multiple_candles(requests)

    load_time = time.time() - start_time
    logger.info(
        f"Stage 2 (SMC): Loaded {len(batch_results)}/{len(requests)} requests "
        f"in {load_time:.1f}s"
    )

    # Группируем по символам
    candles_by_symbol = _group_candles_by_symbol(batch_results)

    # ===================================================================
    # ФОРМИРУЕМ SMC DATA ДЛЯ AI
    # ===================================================================
    ai_input_data = []
    failed_symbols = []

    for idx, candidate in enumerate(candidates, 1):
        symbol = candidate.symbol

        try:
            logger.debug(f"Stage 2 (SMC): [{idx}/{len(candidates)}] Processing {symbol}...")

            # Получаем свечи
            symbol_data = candles_by_symbol.get(symbol, {})

            candles_1h_raw = symbol_data.get('1H')
            candles_4h_raw = symbol_data.get('4H')

            if not candles_1h_raw or not candles_4h_raw:
                logger.debug(f"Stage 2 (SMC): {symbol} SKIP - Missing candles")
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

            # ============================================================
            # ФОРМИРУЕМ SMC DATA
            # ============================================================
            smc_data = _prepare_smc_data(candidate)

            # Формируем данные для AI
            ai_input_data.append({
                'symbol': symbol,
                'direction': candidate.direction,
                'confidence': candidate.confidence,
                'pattern_type': candidate.pattern_type,

                # SMC Components (упрощённо для Stage 2)
                'ob_analysis': smc_data['ob_analysis'],
                'imbalance_analysis': smc_data['imbalance_analysis'],
                'sweep_analysis': smc_data['sweep_analysis'],

                # Context
                'ema_context': candidate.ema_context,
                'volume_ratio': candidate.volume_analysis.volume_ratio_current,
                'rsi_value': candidate.rsi_value,

                # Multi-TF data
                'candles_1h': _extract_last_candles(candles_1h_raw, 30),
                'candles_4h': _extract_last_candles(candles_4h_raw, 30),
                'indicators_1h': indicators_1h,
                'indicators_4h': indicators_4h
            })

            logger.info(f"Stage 2 (SMC): ✓ {symbol} prepared successfully")

        except Exception as e:
            logger.error(f"Stage 2 (SMC): {symbol} ERROR - {e}", exc_info=False)
            failed_symbols.append((symbol, f"Exception: {str(e)[:50]}"))
            continue

    prep_time = time.time() - start_time

    # Логирование результатов
    logger.info("=" * 70)
    logger.info(f"Stage 2 (SMC): Data preparation complete")
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
        logger.error("Stage 2 (SMC): No valid AI input data - CRITICAL FAILURE")
        return []

    logger.info(
        f"Stage 2 (SMC): Sending {len(ai_input_data)} pairs to AI "
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
        f"Stage 2 (SMC) complete: AI selected {len(selected_pairs)} pairs "
        f"(total time: {total_time:.1f}s)"
    )

    if selected_pairs:
        logger.info(f"Selected: {selected_pairs}")
    else:
        logger.warning("Stage 2 (SMC): AI selected 0 pairs")

    return selected_pairs


def _prepare_smc_data(candidate: 'SignalCandidate') -> Dict:
    """
    Подготовить SMC данные в упрощённом формате для AI
    """
    # Order Blocks (упрощённо)
    ob_data = {
        'total_blocks': candidate.ob_analysis.total_blocks_found,
        'bullish_blocks': candidate.ob_analysis.bullish_blocks,
        'bearish_blocks': candidate.ob_analysis.bearish_blocks
    }

    nearest_ob = candidate.ob_analysis.nearest_ob
    if nearest_ob:
        ob_data['nearest_ob'] = {
            'direction': nearest_ob.direction,
            'distance_pct': nearest_ob.distance_from_current,
            'is_mitigated': nearest_ob.is_mitigated,
            'strength': nearest_ob.strength
        }

    # Imbalances (упрощённо)
    imb_data = {}
    if candidate.imbalance_analysis:
        imb_data = {
            'total_imbalances': candidate.imbalance_analysis.total_imbalances,
            'unfilled_count': candidate.imbalance_analysis.unfilled_count,
            'bullish_count': candidate.imbalance_analysis.bullish_count,
            'bearish_count': candidate.imbalance_analysis.bearish_count
        }

        nearest_imb = candidate.imbalance_analysis.nearest_imbalance
        if nearest_imb:
            imb_data['nearest_imbalance'] = {
                'direction': nearest_imb.direction,
                'is_filled': nearest_imb.is_filled,
                'fill_percentage': nearest_imb.fill_percentage,
                'distance_pct': nearest_imb.distance_from_current
            }

    # Liquidity Sweep (упрощённо)
    sweep_data = {
        'sweep_detected': candidate.sweep_analysis.get('sweep_detected', False)
    }

    if sweep_data['sweep_detected']:
        sweep_obj = candidate.sweep_analysis.get('sweep_data')
        if sweep_obj:
            sweep_data['direction'] = sweep_obj.direction
            sweep_data['reversal_confirmed'] = sweep_obj.reversal_confirmed
            sweep_data['volume_confirmation'] = sweep_obj.volume_confirmation

    return {
        'ob_analysis': ob_data,
        'imbalance_analysis': imb_data,
        'sweep_analysis': sweep_data
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
    """Рассчитать compact indicators (без изменений)"""
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
        logger.error(f"Stage 2 (SMC): {symbol} {tf} - Indicators error: {e}")
        return None


def _extract_last_candles(candles_raw: List, count: int) -> List:
    """Извлечь последние N свечей"""
    if not candles_raw:
        return []
    return candles_raw[-count:] if len(candles_raw) > count else candles_raw