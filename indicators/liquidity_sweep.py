"""
Liquidity Sweep Indicator - FIXED THRESHOLD
Файл: indicators/liquidity_sweep.py

ИСПРАВЛЕНО:
✅ sweep_threshold_pct: 0.8% → 1.5% (более реалистичный диапазон)
✅ Минимальный порог: 0.2% → 0.3% (фильтр шума)
"""

import numpy as np
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class LiquiditySweepData:
    """Данные о liquidity sweep"""
    sweep_level: float
    sweep_candle_index: int
    direction: str
    reversal_confirmed: bool
    reversal_strength: float
    volume_confirmation: bool
    details: str


def detect_liquidity_sweep(
        candles,
        lookback: int = None,
        sweep_threshold_pct: float = None,
        min_sweep_pct: float = None,
        reversal_bars: int = None
) -> Optional[LiquiditySweepData]:
    """
    Детекция liquidity sweep

    Args:
        lookback: Период поиска (по умолчанию из config)
        sweep_threshold_pct: Максимальный размер пробоя (по умолчанию из config)
        min_sweep_pct: Минимальный порог (по умолчанию из config)
        reversal_bars: Окно проверки разворота (по умолчанию из config)
    """
    from config import config
    
    if lookback is None:
        lookback = config.SWEEP_LOOKBACK
    if sweep_threshold_pct is None:
        sweep_threshold_pct = config.SWEEP_THRESHOLD_PCT
    if min_sweep_pct is None:
        min_sweep_pct = config.SWEEP_MIN_PCT
    if reversal_bars is None:
        reversal_bars = config.SWEEP_REVERSAL_BARS
    
    if not candles or not candles.is_valid:
        return None

    if len(candles.closes) < lookback + reversal_bars:
        return None

    try:
        recent_highs = candles.highs[-(lookback + reversal_bars):-reversal_bars]
        recent_lows = candles.lows[-(lookback + reversal_bars):-reversal_bars]

        swing_high = float(np.max(recent_highs))
        swing_low = float(np.min(recent_lows))

        check_highs = candles.highs[-reversal_bars:]
        check_lows = candles.lows[-reversal_bars:]
        check_closes = candles.closes[-reversal_bars:]
        check_volumes = candles.volumes[-reversal_bars:]

        # ============================================================
        # SWEEP HIGH (Bearish reversal)
        # ============================================================
        for i in range(len(check_highs) - 1):
            high = float(check_highs[i])

            if high > swing_high:
                sweep_pct = ((high - swing_high) / swing_high) * 100

                # ✅ ИСПРАВЛЕНО: Реалистичный диапазон 0.3% - 1.5%
                if min_sweep_pct <= sweep_pct <= sweep_threshold_pct:
                    reversal_check = _check_reversal(
                        check_closes[i:],
                        check_volumes[i:],
                        high,
                        'BEARISH'
                    )

                    if reversal_check['confirmed']:
                        logger.info(
                            f"Liquidity Sweep HIGH: swept ${swing_high:.4f} by {sweep_pct:.2f}%, "
                            f"reversal {reversal_check['reversion_pct']:.1f}%"
                        )

                        return LiquiditySweepData(
                            sweep_level=swing_high,
                            sweep_candle_index=len(candles.closes) - reversal_bars + i,
                            direction='SWEEP_HIGH',
                            reversal_confirmed=True,
                            reversal_strength=reversal_check['strength'],
                            volume_confirmation=reversal_check['volume_spike'],
                            details=f"High swept at ${swing_high:.4f}, reverted {reversal_check['reversion_pct']:.1f}%"
                        )

        # ============================================================
        # SWEEP LOW (Bullish reversal)
        # ============================================================
        for i in range(len(check_lows) - 1):
            low = float(check_lows[i])

            if low < swing_low:
                sweep_pct = ((swing_low - low) / swing_low) * 100

                # ✅ ИСПРАВЛЕНО: Реалистичный диапазон 0.3% - 1.5%
                if min_sweep_pct <= sweep_pct <= sweep_threshold_pct:
                    reversal_check = _check_reversal(
                        check_closes[i:],
                        check_volumes[i:],
                        low,
                        'BULLISH'
                    )

                    if reversal_check['confirmed']:
                        logger.info(
                            f"Liquidity Sweep LOW: swept ${swing_low:.4f} by {sweep_pct:.2f}%, "
                            f"reversal {reversal_check['reversion_pct']:.1f}%"
                        )

                        return LiquiditySweepData(
                            sweep_level=swing_low,
                            sweep_candle_index=len(candles.closes) - reversal_bars + i,
                            direction='SWEEP_LOW',
                            reversal_confirmed=True,
                            reversal_strength=reversal_check['strength'],
                            volume_confirmation=reversal_check['volume_spike'],
                            details=f"Low swept at ${swing_low:.4f}, reverted {reversal_check['reversion_pct']:.1f}%"
                        )

        return None

    except Exception as e:
        logger.error(f"Liquidity sweep detection error: {e}")
        return None


def _check_reversal(
        closes: np.ndarray,
        volumes: np.ndarray,
        sweep_level: float,
        expected_direction: str
) -> dict:
    """Проверить разворот после sweep"""
    if len(closes) < 2:
        return {
            'confirmed': False,
            'strength': 0.0,
            'volume_spike': False,
            'reversion_pct': 0.0
        }

    try:
        first_close = float(closes[0])
        current_close = float(closes[-1])

        from config import config
        
        if expected_direction == 'BULLISH':
            reversion_pct = ((current_close - sweep_level) / sweep_level) * 100
            confirmed = current_close > sweep_level and reversion_pct > config.SWEEP_REVERSION_MIN_PCT

        else:  # BEARISH
            reversion_pct = ((sweep_level - current_close) / sweep_level) * 100
            confirmed = current_close < sweep_level and reversion_pct > config.SWEEP_REVERSION_MIN_PCT

        # Volume spike check
        if len(volumes) >= 2:
            avg_volume = float(np.mean(volumes[:-1]))
            current_volume = float(volumes[-1])
            volume_spike = current_volume > avg_volume * config.SWEEP_VOLUME_SPIKE_MULTIPLIER
        else:
            volume_spike = False

        strength = min(100, abs(reversion_pct) * 20)

        return {
            'confirmed': confirmed,
            'strength': strength,
            'volume_spike': volume_spike,
            'reversion_pct': abs(reversion_pct)
        }

    except Exception:
        return {
            'confirmed': False,
            'strength': 0.0,
            'volume_spike': False,
            'reversion_pct': 0.0
        }


def analyze_liquidity_sweep(candles, signal_direction: str) -> dict:
    """Анализ liquidity sweep для текущего сигнала"""
    if not candles:
        return {
            'sweep_detected': False,
            'sweep_data': None,
            'confidence_adjustment': 0,
            'details': 'No candles data'
        }

    try:
        sweep_data = detect_liquidity_sweep(candles)

        if not sweep_data or not sweep_data.reversal_confirmed:
            return {
                'sweep_detected': False,
                'sweep_data': None,
                'confidence_adjustment': 0,
                'details': 'No recent liquidity sweep detected'
            }

        from config import config
        
        # Проверяем соответствие направлению
        if signal_direction == 'LONG' and sweep_data.direction == 'SWEEP_LOW':
            adjustment = config.SWEEP_ALIGNED_ADJUSTMENT
            if sweep_data.volume_confirmation:
                adjustment += config.SWEEP_VOLUME_CONFIRMATION_BONUS
            details = f"✓ Bullish setup after sweep (strength: {sweep_data.reversal_strength:.0f})"

        elif signal_direction == 'SHORT' and sweep_data.direction == 'SWEEP_HIGH':
            adjustment = config.SWEEP_ALIGNED_ADJUSTMENT
            if sweep_data.volume_confirmation:
                adjustment += config.SWEEP_VOLUME_CONFIRMATION_BONUS
            details = f"✓ Bearish setup after sweep (strength: {sweep_data.reversal_strength:.0f})"

        else:
            # Sweep есть но не соответствует направлению
            adjustment = config.SWEEP_MISMATCH_PENALTY
            details = f"⚠ Sweep detected but direction mismatch ({sweep_data.direction} vs {signal_direction})"

        return {
            'sweep_detected': True,
            'sweep_data': sweep_data,
            'confidence_adjustment': adjustment,
            'details': details
        }

    except Exception as e:
        logger.error(f"Liquidity sweep analysis error: {e}")
        return {
            'sweep_detected': False,
            'sweep_data': None,
            'confidence_adjustment': 0,
            'details': f'Analysis error: {str(e)[:50]}'
        }