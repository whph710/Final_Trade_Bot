import logging
from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

@dataclass
class TradingSignal:
    """Финальный торговый сигнал"""
    symbol: str
    signal: str
    confidence: int
    entry_price: float
    stop_loss: float
    take_profit_levels: List[float]
    risk_reward_ratio: float
    analysis: str
    comprehensive_data: Dict
    timestamp: str = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()

async def run_stage3(selected_pairs: List[str]) -> tuple[List[TradingSignal], List[Dict]]:
    """Stage 3: Comprehensive analysis с МАКСИМАЛЬНОЙ историей данных"""
    from data_providers import fetch_candles, normalize_candles, get_market_snapshot
    from data_providers.bybit_client import get_session
    from ai.ai_router import AIRouter
    from config import config

    if not selected_pairs:
        logger.warning("Stage 3: No pairs provided")
        return [], []

    logger.info(
        f"Stage 3 (ENHANCED): Analyzing {len(selected_pairs)} pairs "
        f"with MAXIMUM historical data (provider: {config.STAGE3_PROVIDER})"
    )

    # Загрузка BTC свечей (УВЕЛИЧЕНО для истории)
    logger.debug("Stage 3: Loading BTC candles with extended history")
    btc_candles_1h_raw = await fetch_candles('BTCUSDT', config.TIMEFRAME_SHORT, 200)
    btc_candles_4h_raw = await fetch_candles('BTCUSDT', config.TIMEFRAME_LONG, 200)

    if not btc_candles_1h_raw or not btc_candles_4h_raw:
        logger.error("Stage 3: Failed to load BTC candles (critical)")
        return [], []

    btc_candles_1h = normalize_candles(btc_candles_1h_raw, symbol='BTCUSDT', interval=config.TIMEFRAME_SHORT)
    btc_candles_4h = normalize_candles(btc_candles_4h_raw, symbol='BTCUSDT', interval=config.TIMEFRAME_LONG)

    if not btc_candles_1h or not btc_candles_4h:
        logger.error("Stage 3: BTC candles normalization failed")
        return [], []

    approved_signals = []
    rejected_signals = []
    ai_router = AIRouter()
    session = await get_session()

    for symbol in selected_pairs:
        try:
            logger.info(f"Stage 3: Analyzing {symbol} with FULL HISTORY...")
            candles_1h_raw, candles_4h_raw = await _load_candles_extended(symbol)

            if not candles_1h_raw or not candles_4h_raw:
                logger.warning(f"Stage 3: Missing candles for {symbol}")
                rejected_signals.append({
                    'symbol': symbol,
                    'signal': 'NO_SIGNAL',
                    'rejection_reason': 'Missing 1H/4H candles'
                })
                continue

            candles_1h = normalize_candles(candles_1h_raw, symbol, config.TIMEFRAME_SHORT)
            candles_4h = normalize_candles(candles_4h_raw, symbol, config.TIMEFRAME_LONG)

            if not candles_1h or not candles_4h:
                rejected_signals.append({
                    'symbol': symbol,
                    'signal': 'NO_SIGNAL',
                    'rejection_reason': 'Candle validation failed'
                })
                continue

            indicators_1h = _calculate_ultra_full_indicators(candles_1h, "1H")
            indicators_4h = _calculate_ultra_full_indicators(candles_4h, "4H")

            if not indicators_1h or not indicators_4h:
                rejected_signals.append({
                    'symbol': symbol,
                    'signal': 'NO_SIGNAL',
                    'rejection_reason': 'Indicators calculation failed'
                })
                continue

            current_price = float(candles_1h.closes[-1])

            # Уровни + ATR + EMA200 с ПОЛНОЙ ИСТОРИЕЙ
            sr_data_full = await _analyze_sr_with_full_history(candles_4h, current_price)
            wave_data_full = await _analyze_waves_with_full_history(candles_4h)
            ema200_data_full = await _analyze_ema200_with_full_history(candles_4h)

            # MARKET DATA с ИСТОРИЕЙ
            market_data = await get_market_snapshot(symbol, session)
            market_data_history = await _get_market_data_history(symbol, session)

            # BTC CORRELATION с ИСТОРИЕЙ
            correlation_data_full = await _analyze_correlation_with_history(
                symbol, candles_1h, candles_4h, btc_candles_1h, btc_candles_4h
            )

            # VOLUME PROFILE с ИСТОРИЕЙ
            vp_data_full = await _calculate_vp_with_history(candles_4h, current_price)

            # SMC ДАННЫЕ с ИСТОРИЕЙ
            smc_data_full = await _analyze_smc_with_history(candles_1h, candles_4h, current_price)

            # СОБИРАЕМ COMPREHENSIVE DATA с МАКСИМАЛЬНОЙ ИСТОРИЕЙ
            comprehensive_data = {
                'symbol': symbol,
                'candles_1h': candles_1h_raw[-100:],
                'candles_4h': candles_4h_raw[-100:],
                'indicators_1h': indicators_1h,
                'indicators_4h': indicators_4h,
                'current_price': current_price,
                'support_resistance_4h': sr_data_full['current'],
                'sr_history': sr_data_full['history'],
                'wave_analysis_4h': wave_data_full['current'],
                'wave_history': wave_data_full['history'],
                'ema200_context_4h': ema200_data_full['current'],
                'ema200_history': ema200_data_full['history'],
                'market_data': market_data,
                'market_data_history': market_data_history,
                'correlation_data': correlation_data_full['current'],
                'correlation_history': correlation_data_full['history'],
                'volume_profile': vp_data_full['current'],
                'vp_history': vp_data_full['history'],
                'vp_analysis': vp_data_full['analysis'],
                'order_blocks': smc_data_full['ob_current'],
                'ob_history': smc_data_full['ob_history'],
                'imbalances': smc_data_full['imb_current'],
                'imb_history': smc_data_full['imb_history'],
                'liquidity_sweep': smc_data_full['sweep_current'],
                'sweep_history': smc_data_full['sweep_history'],
                'btc_candles_1h': btc_candles_1h_raw[-100:],
                'btc_candles_4h': btc_candles_4h_raw[-100:],
                'btc_indicators': _calculate_ultra_full_indicators(btc_candles_4h, "BTC_4H")
            }

            logger.debug(
                f"Stage 3: {symbol} - Comprehensive data assembled with FULL HISTORY: "
                f"indicators={'✓' if indicators_1h and indicators_4h else '✗'}, "
                f"sr={'✓' if sr_data_full else '✗'}, "
                f"waves={'✓' if wave_data_full else '✗'}, "
                f"ema200={'✓' if ema200_data_full else '✗'}, "
                f"market={'✓' if market_data else '✗'}, "
                f"corr={'✓' if correlation_data_full else '✗'}, "
                f"vp={'✓' if vp_data_full else '✗'}, "
                f"smc={'✓' if smc_data_full else '✗'}"
            )

            # AI анализ
            analysis_result = await ai_router.analyze_pair_comprehensive(symbol, comprehensive_data)
            signal_type = analysis_result.get('signal', 'NO_SIGNAL')
            confidence = analysis_result.get('confidence', 0)

            if signal_type != 'NO_SIGNAL' and confidence >= config.MIN_CONFIDENCE:
                trading_signal = TradingSignal(
                    symbol=symbol,
                    signal=signal_type,
                    confidence=confidence,
                    entry_price=analysis_result.get('entry_price', 0),
                    stop_loss=analysis_result.get('stop_loss', 0),
                    take_profit_levels=analysis_result.get('take_profit_levels', [0, 0, 0]),
                    risk_reward_ratio=_calculate_rr_ratio(analysis_result),
                    analysis=analysis_result.get('analysis', 'No analysis provided'),
                    comprehensive_data=comprehensive_data
                )
                approved_signals.append(trading_signal)
                logger.info(f"Stage 3: ✓ APPROVED {symbol} {signal_type} (confidence: {confidence}%)")
            else:
                rejection_reason = analysis_result.get('rejection_reason', 'Low confidence or no signal')
                rejected_signals.append({
                    'symbol': symbol,
                    'signal': 'NO_SIGNAL',
                    'rejection_reason': rejection_reason
                })
                logger.info(f"Stage 3: ✗ REJECTED {symbol} - {rejection_reason}")
        except Exception as e:
            logger.error(f"Stage 3: Error analyzing {symbol}: {e}", exc_info=False)
            rejected_signals.append({
                'symbol': symbol,
                'signal': 'NO_SIGNAL',
                'rejection_reason': f'Analysis error: {str(e)[:100]}'
            })

    logger.info(f"Stage 3 complete: {len(approved_signals)} approved, {len(rejected_signals)} rejected")
    return approved_signals, rejected_signals

# ============================================================================
# НОВЫЕ ФУНКЦИИ ДЛЯ РАСШИРЕННОЙ ИСТОРИИ
# ============================================================================

async def _load_candles_extended(symbol: str) -> tuple:
    """Загрузка свечей с УВЕЛИЧЕННОЙ историей"""
    from data_providers import fetch_candles
    from config import config
    import asyncio

    candles_1h, candles_4h = await asyncio.gather(
        fetch_candles(symbol, config.TIMEFRAME_SHORT, 300),
        fetch_candles(symbol, config.TIMEFRAME_LONG, 300)
    )
    return candles_1h, candles_4h

def _calculate_ultra_full_indicators(candles, tf: str = "UNKNOWN") -> Dict:
    """Рассчитать индикаторы с МАКСИМАЛЬНОЙ историей (100+ баров)"""
    from indicators.ema import calculate_ema
    from indicators.rsi import calculate_rsi
    from indicators.macd import calculate_macd
    from indicators.volume import calculate_volume_ratio
    from indicators.atr import calculate_atr
    from config import config

    try:
        if not candles or len(candles.closes) < 100:
            return None

        ema9 = calculate_ema(candles.closes, config.EMA_FAST)
        ema21 = calculate_ema(candles.closes, config.EMA_MEDIUM)
        ema50 = calculate_ema(candles.closes, config.EMA_SLOW)
        ema200 = calculate_ema(candles.closes, 200)
        rsi = calculate_rsi(candles.closes, config.RSI_PERIOD)
        macd_data = calculate_macd(candles.closes)
        volume_ratios = calculate_volume_ratio(candles.volumes, config.VOLUME_WINDOW)
        atr = calculate_atr(candles, config.ATR_PERIOD)

        current = {
            'price': float(candles.closes[-1]),
            'ema9': float(ema9[-1]),
            'ema21': float(ema21[-1]),
            'ema50': float(ema50[-1]),
            'ema200': float(ema200[-1]),
            'rsi': float(rsi[-1]),
            'macd_line': float(macd_data.line[-1]),
            'macd_histogram': float(macd_data.histogram[-1]),
            'macd_signal': float(macd_data.signal[-1]),
            'volume_ratio': float(volume_ratios[-1]),
            'atr': atr
        }

        history_length = min(100, len(candles.closes))
        return {
            'current': current,
            'price_history': [float(x) for x in candles.closes[-history_length:]],
            'ema9_history': [float(x) for x in ema9[-history_length:]],
            'ema21_history': [float(x) for x in ema21[-history_length:]],
            'ema50_history': [float(x) for x in ema50[-history_length:]],
            'ema200_history': [float(x) for x in ema200[-history_length:]],
            'rsi_history': [float(x) for x in rsi[-history_length:]],
            'macd_line_history': [float(x) for x in macd_data.line[-history_length:]],
            'macd_histogram_history': [float(x) for x in macd_data.histogram[-history_length:]],
            'macd_signal_history': [float(x) for x in macd_data.signal[-history_length:]],
            'volume_ratio_history': [float(x) for x in volume_ratios[-history_length:]],
            'opens_history': [float(x) for x in candles.opens[-history_length:]],
            'highs_history': [float(x) for x in candles.highs[-history_length:]],
            'lows_history': [float(x) for x in candles.lows[-history_length:]],
            'closes_history': [float(x) for x in candles.closes[-history_length:]],
            'volumes_history': [float(x) for x in candles.volumes[-history_length:]],
            'timestamps': [int(x) for x in candles.timestamps[-history_length:]]
        }
    except Exception as e:
        logger.error(f"Ultra full indicators calculation error ({tf}): {e}")
        return None

async def _analyze_sr_with_full_history(candles, current_price) -> Dict:
    """S/R анализ с полной историей уровней"""
    from indicators import analyze_support_resistance, find_support_resistance_levels

    try:
        sr_analysis = analyze_support_resistance(candles, current_price, 'UNKNOWN')
        history = []

        for lookback in [50, 100, 150]:
            if len(candles.closes) >= lookback:
                levels = find_support_resistance_levels(candles, lookback=lookback)
                history.append({
                    'lookback': lookback,
                    'levels_count': len(levels),
                    'strongest_support': levels[0].price if levels and levels[0].level_type == 'SUPPORT' else None,
                    'strongest_resistance': levels[0].price if levels and levels[0].level_type == 'RESISTANCE' else None
                })
        return {'current': sr_analysis, 'history': history}
    except Exception as e:
        logger.error(f"SR history error: {e}")
        return {'current': None, 'history': []}

async def _analyze_waves_with_full_history(candles) -> Dict:
    """Волновой анализ с историей"""
    from indicators import analyze_waves_atr

    try:
        wave_analysis = analyze_waves_atr(candles, num_waves=5)
        history = []

        for num_waves in [3, 5, 7, 10]:
            wave_hist = analyze_waves_atr(candles, num_waves=num_waves)
            if wave_hist:
                history.append({
                    'num_waves': num_waves,
                    'wave_type': wave_hist.wave_type,
                    'average_length': wave_hist.average_wave_length,
                    'wave_lengths': wave_hist.wave_lengths
                })
        return {'current': wave_analysis, 'history': history}
    except Exception as e:
        logger.error(f"Wave history error: {e}")
        return {'current': None, 'history': []}

async def _analyze_ema200_with_full_history(candles) -> Dict:
    """EMA200 с полной историей"""
    from indicators import analyze_ema200
    from indicators.ema import calculate_ema

    try:
        ema200_context = analyze_ema200(candles)
        ema200_values = calculate_ema(candles.closes, 200)
        history = [float(x) for x in ema200_values[-100:]]
        return {'current': ema200_context, 'history': history}
    except Exception as e:
        logger.error(f"EMA200 history error: {e}")
        return {'current': None, 'history': []}

async def _get_market_data_history(symbol: str, session) -> List[Dict]:
    """История market data (последние значения)"""
    return []

async def _analyze_correlation_with_history(symbol, candles_1h, candles_4h, btc_1h, btc_4h) -> Dict:
    """Корреляция с историей"""
    from indicators import get_comprehensive_correlation_analysis, calculate_correlation

    try:
        corr_current = get_comprehensive_correlation_analysis(symbol, candles_1h, btc_1h, 'UNKNOWN')
        history = []

        for window in [12, 24, 48]:
            if len(candles_1h.closes) >= window and len(btc_1h.closes) >= window:
                corr = calculate_correlation(candles_1h.closes, btc_1h.closes, window=window)
                history.append({'window': window, 'correlation': corr})
        return {'current': corr_current, 'history': history}
    except Exception as e:
        logger.error(f"Correlation history error: {e}")
        return {'current': None, 'history': []}

async def _calculate_vp_with_history(candles, current_price) -> Dict:
    """Volume Profile с историей"""
    from indicators import calculate_volume_profile, analyze_volume_profile
    from data_providers.data_normalizer import NormalizedCandles

    try:
        vp_current = calculate_volume_profile(candles, num_bins=50)
        vp_analysis = analyze_volume_profile(vp_current, current_price) if vp_current else None
        history = []

        for lookback in [50, 100, 150]:
            if len(candles.closes) >= lookback:
                temp_candles = NormalizedCandles(
                    timestamps=candles.timestamps[-lookback:],
                    opens=candles.opens[-lookback:],
                    highs=candles.highs[-lookback:],
                    lows=candles.lows[-lookback:],
                    closes=candles.closes[-lookback:],
                    volumes=candles.volumes[-lookback:],
                    is_valid=True,
                    symbol=candles.symbol,
                    interval=candles.interval
                )
                vp_hist = calculate_volume_profile(temp_candles, num_bins=50)
                if vp_hist:
                    history.append({
                        'lookback': lookback,
                        'poc': vp_hist.poc,
                        'value_area_high': vp_hist.value_area_high,
                        'value_area_low': vp_hist.value_area_low
                    })
        return {'current': vp_current, 'analysis': vp_analysis, 'history': history}
    except Exception as e:
        logger.error(f"VP history error: {e}")
        return {'current': None, 'analysis': None, 'history': []}

async def _analyze_smc_with_history(candles_1h, candles_4h, current_price) -> Dict:
    """SMC данные с историей"""
    from indicators.order_blocks import analyze_order_blocks
    from indicators.imbalance import analyze_imbalances
    from indicators.liquidity_sweep import analyze_liquidity_sweep
    from data_providers.data_normalizer import NormalizedCandles

    try:
        ob_current = analyze_order_blocks(candles_4h, current_price, 'UNKNOWN', lookback=50)
        imb_current = analyze_imbalances(candles_4h, current_price, 'UNKNOWN', lookback=50)
        sweep_current = analyze_liquidity_sweep(candles_1h, 'UNKNOWN')

        ob_history = []
        for lookback in [30, 50, 70]:
            ob_hist = analyze_order_blocks(candles_4h, current_price, 'UNKNOWN', lookback=lookback)
            if ob_hist:
                ob_history.append({
                    'lookback': lookback,
                    'total_blocks': ob_hist.total_blocks_found,
                    'nearest_distance': ob_hist.nearest_ob.distance_from_current if ob_hist.nearest_ob else None
                })

        imb_history = []
        for lookback in [30, 50, 70]:
            imb_hist = analyze_imbalances(candles_4h, current_price, 'UNKNOWN', lookback=lookback)
            if imb_hist:
                imb_history.append({
                    'lookback': lookback,
                    'total_imbalances': imb_hist.total_imbalances,
                    'unfilled_count': imb_hist.unfilled_count
                })

        sweep_history = []
        for lookback in [10, 20, 30]:
            temp_candles = NormalizedCandles(
                timestamps=candles_1h.timestamps[-lookback:],
                opens=candles_1h.opens[-lookback:],
                highs=candles_1h.highs[-lookback:],
                lows=candles_1h.lows[-lookback:],
                closes=candles_1h.closes[-lookback:],
                volumes=candles_1h.volumes[-lookback:],
                is_valid=True,
                symbol=candles_1h.symbol,
                interval=candles_1h.interval
            )
            sweep_hist = analyze_liquidity_sweep(temp_candles, 'UNKNOWN')
            if sweep_hist:
                sweep_history.append({
                    'lookback': lookback,
                    'sweep_detected': sweep_hist['sweep_detected']
                })

        return {
            'ob_current': ob_current,
            'ob_history': ob_history,
            'imb_current': imb_current,
            'imb_history': imb_history,
            'sweep_current': sweep_current,
            'sweep_history': sweep_history
        }
    except Exception as e:
        logger.error(f"SMC history error: {e}")
        return {
            'ob_current': None,
            'ob_history': [],
            'imb_current': None,
            'imb_history': [],
            'sweep_current': None,
            'sweep_history': []
        }

def _calculate_rr_ratio(analysis_result: Dict) -> float:
    """Рассчитать R/R ratio"""
    entry = analysis_result.get('entry_price', 0)
    stop = analysis_result.get('stop_loss', 0)
    tp_levels = analysis_result.get('take_profit_levels', [0, 0, 0])

    if entry == 0 or stop == 0 or not tp_levels:
        return 0.0

    risk = abs(entry - stop)
    reward = abs(tp_levels[1] - entry) if len(tp_levels) > 1 else abs(tp_levels[0] - entry)

    if risk > 0:
        return round(reward / risk, 2)
    return 0.0

async def analyze_single_pair(symbol: str, direction: str) -> Optional[TradingSignal]:
    """Анализ ОДНОЙ конкретной пары с МАКСИМАЛЬНОЙ историей"""
    from data_providers import fetch_candles, normalize_candles, get_market_snapshot
    from data_providers.bybit_client import get_session
    from ai.ai_router import AIRouter
    from config import config

    logger.info(f"Manual analysis: {symbol} {direction}")

    try:
        # Загрузка BTC свечей с расширенной историей
        logger.debug(f"Loading BTC candles with extended history")
        btc_candles_1h_raw = await fetch_candles('BTCUSDT', config.TIMEFRAME_SHORT, 200)
        btc_candles_4h_raw = await fetch_candles('BTCUSDT', config.TIMEFRAME_LONG, 200)

        if not btc_candles_1h_raw or not btc_candles_4h_raw:
            logger.error(f"Failed to load BTC candles")
            return _create_no_signal(symbol, 'Failed to load BTC candles')

        btc_candles_1h = normalize_candles(btc_candles_1h_raw, 'BTCUSDT', config.TIMEFRAME_SHORT)
        btc_candles_4h = normalize_candles(btc_candles_4h_raw, 'BTCUSDT', config.TIMEFRAME_LONG)

        if not btc_candles_1h or not btc_candles_4h:
            logger.error(f"BTC candles normalization failed")
            return _create_no_signal(symbol, 'BTC candles normalization failed')

        # Загрузка свечей выбранной пары с расширенной историей
        logger.info(f"Loading extended candles for {symbol}")
        candles_1h_raw, candles_4h_raw = await _load_candles_extended(symbol)

        if not candles_1h_raw or not candles_4h_raw:
            return _create_no_signal(symbol, 'Missing candles')

        candles_1h = normalize_candles(candles_1h_raw, symbol, config.TIMEFRAME_SHORT)
        candles_4h = normalize_candles(candles_4h_raw, symbol, config.TIMEFRAME_LONG)

        if not candles_1h or not candles_4h:
            return _create_no_signal(symbol, 'Candle validation failed')

        # Рассчитываем индикаторы с максимальной историей
        indicators_1h = _calculate_ultra_full_indicators(candles_1h, "1H")
        indicators_4h = _calculate_ultra_full_indicators(candles_4h, "4H")

        if not indicators_1h or not indicators_4h:
            return _create_no_signal(symbol, 'Indicators calculation failed')

        current_price = float(candles_1h.closes[-1])

        # Собираем все данные с историей
        logger.debug(f"{symbol} - Analyzing with FULL HISTORY")
        sr_data_full = await _analyze_sr_with_full_history(candles_4h, current_price)
        wave_data_full = await _analyze_waves_with_full_history(candles_4h)
        ema200_data_full = await _analyze_ema200_with_full_history(candles_4h)
        session = await get_session()
        market_data = await get_market_snapshot(symbol, session)
        market_data_history = await _get_market_data_history(symbol, session)
        correlation_data_full = await _analyze_correlation_with_history(
            symbol, candles_1h, candles_4h, btc_candles_1h, btc_candles_4h
        )
        vp_data_full = await _calculate_vp_with_history(candles_4h, current_price)
        smc_data_full = await _analyze_smc_with_history(candles_1h, candles_4h, current_price)

        # Comprehensive data с forced_direction
        comprehensive_data = {
            'symbol': symbol,
            'candles_1h': candles_1h_raw[-100:],
            'candles_4h': candles_4h_raw[-100:],
            'indicators_1h': indicators_1h,
            'indicators_4h': indicators_4h,
            'current_price': current_price,
            'support_resistance_4h': sr_data_full['current'],
            'sr_history': sr_data_full['history'],
            'wave_analysis_4h': wave_data_full['current'],
            'wave_history': wave_data_full['history'],
            'ema200_context_4h': ema200_data_full['current'],
            'ema200_history': ema200_data_full['history'],
            'market_data': market_data,
            'market_data_history': market_data_history,
            'correlation_data': correlation_data_full['current'],
            'correlation_history': correlation_data_full['history'],
            'volume_profile': vp_data_full['current'],
            'vp_history': vp_data_full['history'],
            'vp_analysis': vp_data_full['analysis'],
            'order_blocks': smc_data_full['ob_current'],
            'ob_history': smc_data_full['ob_history'],
            'imbalances': smc_data_full['imb_current'],
            'imb_history': smc_data_full['imb_history'],
            'liquidity_sweep': smc_data_full['sweep_current'],
            'sweep_history': smc_data_full['sweep_history'],
            'btc_candles_1h': btc_candles_1h_raw[-100:],
            'btc_candles_4h': btc_candles_4h_raw[-100:],
            'btc_indicators': _calculate_ultra_full_indicators(btc_candles_4h, "BTC_4H"),
            'forced_direction': direction
        }

        # AI анализ
        logger.info(f"{symbol} - Running AI analysis (forced: {direction})")
        ai_router = AIRouter()
        analysis_result = await ai_router.analyze_pair_comprehensive(symbol, comprehensive_data)
        signal_type = analysis_result.get('signal', 'NO_SIGNAL')
        confidence = analysis_result.get('confidence', 0)

        if signal_type == direction and confidence >= config.MIN_CONFIDENCE:
            trading_signal = TradingSignal(
                symbol=symbol,
                signal=signal_type,
                confidence=confidence,
                entry_price=analysis_result.get('entry_price', 0),
                stop_loss=analysis_result.get('stop_loss', 0),
                take_profit_levels=analysis_result.get('take_profit_levels', [0, 0, 0]),
                risk_reward_ratio=_calculate_rr_ratio(analysis_result),
                analysis=analysis_result.get('analysis', 'No analysis provided'),
                comprehensive_data=comprehensive_data
            )
            logger.info(f"{symbol} - ✅ APPROVED {signal_type} (confidence: {confidence}%)")
            return trading_signal
        else:
            rejection_reason = analysis_result.get('rejection_reason', f'{direction} signal not found')
            logger.info(f"{symbol} - ❌ NO {direction} SIGNAL: {rejection_reason}")
            return TradingSignal(
                symbol=symbol,
                signal='NO_SIGNAL',
                confidence=confidence,
                entry_price=0,
                stop_loss=0,
                take_profit_levels=[0, 0, 0],
                risk_reward_ratio=0,
                analysis=f"❌ {direction} signal not found.\n\n{rejection_reason}",
                comprehensive_data={'rejection_reason': rejection_reason}
            )
    except Exception as e:
        logger.error(f"Error analyzing {symbol}: {e}", exc_info=False)
        return _create_no_signal(symbol, f'Exception: {str(e)[:100]}')

def _create_no_signal(symbol: str, reason: str) -> TradingSignal:
    """Helper для создания NO_SIGNAL"""
    return TradingSignal(
        symbol=symbol,
        signal='NO_SIGNAL',
        confidence=0,
        entry_price=0,
        stop_loss=0,
        take_profit_levels=[0, 0, 0],
        risk_reward_ratio=0,
        analysis=f'❌ Analysis failed: {reason}',
        comprehensive_data={'rejection_reason': reason}
    )
