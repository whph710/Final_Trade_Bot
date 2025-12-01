"""
Liquidity Sweep Indicator
Файл: indicators/liquidity_sweep.py

Детекция liquidity sweeps (ложные пробои для сбора стопов)
"""

import numpy as np
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class LiquiditySweepData:
    """
    Данные о liquidity sweep

    Attributes:
        sweep_level: Уровень который был swept
        sweep_candle_index: Индекс свечи sweep
        direction: 'SWEEP_HIGH' | 'SWEEP_LOW'
        reversal_confirmed: Подтверждён ли разворот
        reversal_strength: Сила разворота (0-100)
        volume_confirmation: Был ли volume spike при развороте
        details: Описание
    """
    sweep_level: float
    sweep_candle_index: int
    direction: str
    reversal_confirmed: bool
    reversal_strength: float
    volume_confirmation: bool
    details: str


def detect_liquidity_sweep(
        candles,  # NormalizedCandles
        lookback: int = 20,
        sweep_threshold_pct: float = 0.3,
        reversal_bars: int = 3
) -> Optional[LiquiditySweepData]:
    """
    Детекция liquidity sweep (ложный пробой)

    Логика:
    1. Цена пробивает recent high/low (sweep stops)
    2. Резко разворачивается обратно (крупный игрок загрузился)
    3. Подтверждение: impulsive move в обратную сторону

    Критерии:
    - Пробой уровня на 0.1-0.5%
    - Возврат внутрь за 1-3 свечи
    - Volume spike на свече разворота

    Args:
        candles: NormalizedCandles объект
        lookback: Период для поиска recent high/low
        sweep_threshold_pct: Максимальный размер пробоя (%)
        reversal_bars: Количество свечей для подтверждения разворота

    Returns:
        LiquiditySweepData или None
    """
    if not candles or not candles.is_valid:
        return None

    if len(candles.closes) < lookback + reversal_bars:
        return None

    try:
        # Анализируем последние свечи
        recent_highs = candles.highs[-(lookback + reversal_bars):-reversal_bars]
        recent_lows = candles.lows[-(lookback + reversal_bars):-reversal_bars]

        # Находим recent high и low
        swing_high = float(np.max(recent_highs))
        swing_low = float(np.min(recent_lows))

        # Проверяем последние reversal_bars свечей на sweep
        check_highs = candles.highs[-reversal_bars:]
        check_lows = candles.lows[-reversal_bars:]
        check_closes = candles.closes[-reversal_bars:]
        check_volumes = candles.volumes[-reversal_bars:]

        current_close = float(candles.closes[-1])

        # Проверка sweep high (для медвежьего разворота)
        for i in range(len(check_highs) - 1):
            high = float(check_highs[i])

            # Пробили ли swing high?
            if high > swing_high:
                sweep_pct = ((high - swing_high) / swing_high) * 100

                # Размер пробоя в пределах threshold?
                if 0.1 <= sweep_pct <= sweep_threshold_pct:
                    # Проверяем разворот обратно
                    reversal_check = _check_reversal(
                        check_closes[i:],
                        check_volumes[i:],
                        high,
                        'BEARISH'
                    )

                    if reversal_check['confirmed']:
                        return LiquiditySweepData(
                            sweep_level=swing_high,
                            sweep_candle_index=len(candles.closes) - reversal_bars + i,
                            direction='SWEEP_HIGH',
                            reversal_confirmed=True,
                            reversal_strength=reversal_check['strength'],
                            volume_confirmation=reversal_check['volume_spike'],
                            details=(
                                f"High swept at ${swing_high:.4f}, "
                                f"reverted {reversal_check['reversion_pct']:.1f}%"
                            )
                        )

        # Проверка sweep low (для бычьего разворота)
        for i in range(len(check_lows) - 1):
            low = float(check_lows[i])

            # Пробили ли swing low?
            if low < swing_low:
                sweep_pct = ((swing_low - low) / swing_low) * 100

                if 0.1 <= sweep_pct <= sweep_threshold_pct:
                    reversal_check = _check_reversal(
                        check_closes[i:],
                        check_volumes[i:],
                        low,
                        'BULLISH'
                    )

                    if reversal_check['confirmed']:
                        return LiquiditySweepData(
                            sweep_level=swing_low,
                            sweep_candle_index=len(candles.closes) - reversal_bars + i,
                            direction='SWEEP_LOW',
                            reversal_confirmed=True,
                            reversal_strength=reversal_check['strength'],
                            volume_confirmation=reversal_check['volume_spike'],
                            details=(
                                f"Low swept at ${swing_low:.4f}, "
                                f"reverted {reversal_check['reversion_pct']:.1f}%"
                            )
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
    """
    Проверить разворот после sweep

    Returns:
        {
            'confirmed': bool,
            'strength': float,
            'volume_spike': bool,
            'reversion_pct': float
        }
    """
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

        # Рассчитываем движение от sweep level
        if expected_direction == 'BULLISH':
            # После sweep low должна быть up-движение
            reversion_pct = ((current_close - sweep_level) / sweep_level) * 100

            # Подтверждение: цена выше sweep level
            confirmed = current_close > sweep_level and reversion_pct > 0.5

        else:  # BEARISH
            # После sweep high должна быть down-движение
            reversion_pct = ((sweep_level - current_close) / sweep_level) * 100

            confirmed = current_close < sweep_level and reversion_pct > 0.5

        # Проверка volume spike
        if len(volumes) >= 2:
            avg_volume = float(np.mean(volumes[:-1]))
            current_volume = float(volumes[-1])

            volume_spike = current_volume > avg_volume * 1.5
        else:
            volume_spike = False

        # Сила разворота
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


def analyze_liquidity_sweep(
        candles,  # NormalizedCandles
        signal_direction: str
) -> dict:
    """
    Анализ liquidity sweep для текущего сигнала

    Args:
        candles: NormalizedCandles объект
        signal_direction: 'LONG' | 'SHORT'

    Returns:
        {
            'sweep_detected': bool,
            'sweep_data': LiquiditySweepData или None,
            'confidence_adjustment': int,
            'details': str
        }
    """
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

        # Проверяем соответствие направлению сигнала
        if signal_direction == 'LONG' and sweep_data.direction == 'SWEEP_LOW':
            # Бычий сигнал после sweep low - идеально!
            adjustment = 15

            if sweep_data.volume_confirmation:
                adjustment += 5

            details = (
                f"✓ Bullish setup after liquidity sweep "
                f"(strength: {sweep_data.reversal_strength:.0f})"
            )

        elif signal_direction == 'SHORT' and sweep_data.direction == 'SWEEP_HIGH':
            # Медвежий сигнал после sweep high - идеально!
            adjustment = 15

            if sweep_data.volume_confirmation:
                adjustment += 5

            details = (
                f"✓ Bearish setup after liquidity sweep "
                f"(strength: {sweep_data.reversal_strength:.0f})"
            )

        else:
            # Sweep есть но не соответствует направлению
            adjustment = -8
            details = (
                f"⚠ Liquidity sweep detected but direction mismatch "
                f"({sweep_data.direction} vs {signal_direction})"
            )

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