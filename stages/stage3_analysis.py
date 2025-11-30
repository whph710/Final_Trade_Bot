"""
Stage 3: Comprehensive Analysis - FULL RESTORATION
Файл: stages/stage3_analysis.py

ВОССТАНОВЛЕНО:
- Market Data (funding, OI, orderbook)
- BTC Correlation
- Volume Profile
"""

import logging
from typing import List, Dict
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass
class TradingSignal:
    """
    Финальный торговый сигнал

    Attributes:
        symbol: Торговая пара
        signal: 'LONG' | 'SHORT' | 'NO_SIGNAL'
        confidence: Confidence score (0-100)
        entry_price: Цена входа
        stop_loss: Stop loss цена
        take_profit_levels: [TP1, TP2, TP3]
        risk_reward_ratio: R/R ratio
        analysis: Текстовое описание анализа
        comprehensive_data: Все данные использованные для анализа
        timestamp: Timestamp создания сигнала
    """
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
    """
    Stage 3: Comprehensive analysis для выбранных пар

    ✅ ВОССТАНОВЛЕНО: FULL PIPELINE (Market Data, Correlation, Volume Profile)

    Args:
        selected_pairs: Список символов выбранных в Stage 2

    Returns:
        (approved_signals: List[TradingSignal], rejected_signals: List[Dict])
    """
    from data_providers import fetch_candles, normalize_candles, get_market_snapshot
    from data_providers.bybit_client import get_session
    from ai.ai_router import AIRouter
    from config import config

    if not selected_pairs:
        logger.warning("Stage 3: No pairs provided")
        return [], []

    logger.info(
        f"Stage 3: Analyzing {len(selected_pairs)} pairs "
        f"(provider: {config.STAGE3_PROVIDER})"
    )

    # ✅ ВОССТАНОВЛЕНО: Загрузка BTC свечей
    logger.debug("Stage 3: Loading BTC candles for correlation analysis")

    btc_candles_1h_raw = await fetch_candles(
        'BTCUSDT',
        config.TIMEFRAME_SHORT,
        config.STAGE3_CANDLES_1H
    )

    btc_candles_4h_raw = await fetch_candles(
        'BTCUSDT',
        config.TIMEFRAME_LONG,
        config.STAGE3_CANDLES_4H
    )

    if not btc_candles_1h_raw or not btc_candles_4h_raw:
        logger.error("Stage 3: Failed to load BTC candles (critical)")
        return [], []

    # Нормализация BTC
    btc_candles_1h = normalize_candles(
        btc_candles_1h_raw,
        symbol='BTCUSDT',
        interval=config.TIMEFRAME_SHORT
    )

    btc_candles_4h = normalize_candles(
        btc_candles_4h_raw,
        symbol='BTCUSDT',
        interval=config.TIMEFRAME_LONG
    )

    if not btc_candles_1h or not btc_candles_4h:
        logger.error("Stage 3: BTC candles normalization failed")
        return [], []

    approved_signals = []
    rejected_signals = []

    ai_router = AIRouter()
    session = await get_session()

    # Анализ каждой пары
    for symbol in selected_pairs:
        try:
            logger.info(f"Stage 3: Analyzing {symbol}...")

            # Загрузка свечей
            candles_1h_raw, candles_4h_raw = await _load_candles(symbol)

            if not candles_1h_raw or not candles_4h_raw:
                logger.warning(f"Stage 3: Missing candles for {symbol}")
                rejected_signals.append({
                    'symbol': symbol,
                    'signal': 'NO_SIGNAL',
                    'rejection_reason': 'Missing 1H/4H candles'
                })
                continue

            # Нормализация
            candles_1h = normalize_candles(
                candles_1h_raw, symbol, config.TIMEFRAME_SHORT
            )
            candles_4h = normalize_candles(
                candles_4h_raw, symbol, config.TIMEFRAME_LONG
            )

            if not candles_1h or not candles_4h:
                rejected_signals.append({
                    'symbol': symbol,
                    'signal': 'NO_SIGNAL',
                    'rejection_reason': 'Candle validation failed'
                })
                continue

            # Рассчитываем полные индикаторы
            indicators_1h = _calculate_full_indicators(candles_1h)
            indicators_4h = _calculate_full_indicators(candles_4h)

            if not indicators_1h or not indicators_4h:
                rejected_signals.append({
                    'symbol': symbol,
                    'signal': 'NO_SIGNAL',
                    'rejection_reason': 'Indicators calculation failed'
                })
                continue

            current_price = float(candles_1h.closes[-1])

            # ✅ ВОССТАНОВЛЕНО: Market Data
            logger.debug(f"Stage 3: {symbol} - Loading market data (funding, OI, orderbook)")
            market_data = await get_market_snapshot(symbol, session)

            # ✅ ВОССТАНОВЛЕНО: BTC Correlation
            logger.debug(f"Stage 3: {symbol} - Analyzing BTC correlation")
            from indicators import get_comprehensive_correlation_analysis

            correlation_data = get_comprehensive_correlation_analysis(
                symbol=symbol,
                symbol_candles=candles_1h,
                btc_candles=btc_candles_1h,
                signal_direction='UNKNOWN'  # Пока неизвестно
            )

            # ✅ ВОССТАНОВЛЕНО: Volume Profile
            logger.debug(f"Stage 3: {symbol} - Calculating Volume Profile")
            from indicators import calculate_volume_profile, analyze_volume_profile

            vp_data = calculate_volume_profile(candles_4h, num_bins=50)
            vp_analysis = analyze_volume_profile(vp_data, current_price) if vp_data else None

            # Собираем comprehensive data
            comprehensive_data = {
                'symbol': symbol,
                'candles_1h': candles_1h_raw,
                'candles_4h': candles_4h_raw,
                'indicators_1h': indicators_1h,
                'indicators_4h': indicators_4h,
                'current_price': current_price,
                'market_data': market_data,           # ✅ ВОССТАНОВЛЕНО
                'correlation_data': correlation_data,  # ✅ ВОССТАНОВЛЕНО
                'volume_profile': vp_data,            # ✅ ВОССТАНОВЛЕНО
                'vp_analysis': vp_analysis,           # ✅ ВОССТАНОВЛЕНО
                'btc_candles_1h': btc_candles_1h_raw,
                'btc_candles_4h': btc_candles_4h_raw
            }

            logger.debug(
                f"Stage 3: {symbol} - Comprehensive data assembled: "
                f"market_data={'✓' if market_data else '✗'}, "
                f"correlation={'✓' if correlation_data else '✗'}, "
                f"volume_profile={'✓' if vp_data else '✗'}"
            )

            # AI анализ с ПОЛНЫМИ данными
            analysis_result = await ai_router.analyze_pair_comprehensive(
                symbol,
                comprehensive_data
            )

            signal_type = analysis_result.get('signal', 'NO_SIGNAL')
            confidence = analysis_result.get('confidence', 0)

            # Проверка результата
            if signal_type != 'NO_SIGNAL' and confidence >= config.MIN_CONFIDENCE:
                # Создаём TradingSignal
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

                logger.info(
                    f"Stage 3: ✓ APPROVED {symbol} {signal_type} "
                    f"(confidence: {confidence}%)"
                )

            else:
                rejection_reason = analysis_result.get(
                    'rejection_reason',
                    'Low confidence or no signal'
                )

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
            continue

    logger.info(
        f"Stage 3 complete: {len(approved_signals)} approved, "
        f"{len(rejected_signals)} rejected"
    )

    return approved_signals, rejected_signals


async def _load_candles(symbol: str) -> tuple:
    """Загрузка 1H и 4H свечей"""
    from data_providers import fetch_candles
    from config import config
    import asyncio

    candles_1h, candles_4h = await asyncio.gather(
        fetch_candles(symbol, config.TIMEFRAME_SHORT, config.STAGE3_CANDLES_1H),
        fetch_candles(symbol, config.TIMEFRAME_LONG, config.STAGE3_CANDLES_4H)
    )

    return candles_1h, candles_4h


def _calculate_full_indicators(candles) -> Dict:
    """
    Рассчитать полные индикаторы для Stage 3

    Returns:
        {
            'current': {...},
            'ema9_history': [...],
            'ema21_history': [...],
            'ema50_history': [...],
            'rsi_history': [...],
            'macd_line_history': [...],
            'macd_histogram_history': [...],
            'volume_ratio_history': [...]
        }
    """
    from indicators.ema import calculate_ema
    from indicators.rsi import calculate_rsi
    from indicators.macd import calculate_macd
    from indicators.volume import calculate_volume_ratio
    from indicators.atr import calculate_atr
    from config import config

    try:
        # Рассчитываем все индикаторы
        ema9 = calculate_ema(candles.closes, config.EMA_FAST)
        ema21 = calculate_ema(candles.closes, config.EMA_MEDIUM)
        ema50 = calculate_ema(candles.closes, config.EMA_SLOW)
        rsi = calculate_rsi(candles.closes, config.RSI_PERIOD)
        macd_data = calculate_macd(candles.closes)
        volume_ratios = calculate_volume_ratio(candles.volumes, config.VOLUME_WINDOW)

        # Текущие значения
        current = {
            'price': float(candles.closes[-1]),
            'ema9': float(ema9[-1]),
            'ema21': float(ema21[-1]),
            'ema50': float(ema50[-1]),
            'rsi': float(rsi[-1]),
            'macd_line': float(macd_data.line[-1]),
            'macd_histogram': float(macd_data.histogram[-1]),
            'volume_ratio': float(volume_ratios[-1]),
            'atr': calculate_atr(candles, config.ATR_PERIOD)
        }

        # История (последние 30 значений)
        history_length = config.FINAL_INDICATORS_HISTORY

        return {
            'current': current,
            'ema9_history': [float(x) for x in ema9[-history_length:]],
            'ema21_history': [float(x) for x in ema21[-history_length:]],
            'ema50_history': [float(x) for x in ema50[-history_length:]],
            'rsi_history': [float(x) for x in rsi[-history_length:]],
            'macd_line_history': [float(x) for x in macd_data.line[-history_length:]],
            'macd_histogram_history': [float(x) for x in macd_data.histogram[-history_length:]],
            'volume_ratio_history': [float(x) for x in volume_ratios[-history_length:]]
        }

    except Exception as e:
        logger.error(f"Full indicators calculation error: {e}")
        return {}


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