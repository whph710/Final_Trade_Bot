"""
Triple EMA Indicator (9/21/50) + EMA200 Context
Файл: indicators/ema.py

ОБНОВЛЕНО: Добавлена функция analyze_ema200() для контекста тренда
"""

import numpy as np
import logging
from dataclasses import dataclass
from typing import Optional, Dict

logger = logging.getLogger(__name__)


@dataclass
class EMAAnalysis:
    """Результат анализа Triple EMA"""
    ema9_current: float
    ema21_current: float
    ema50_current: float
    alignment: str
    crossover: str
    pullback: str
    compression: str
    distance_from_ema50_pct: float
    confidence_score: int
    details: str


def calculate_ema(prices: np.ndarray, period: int) -> np.ndarray:
    """Рассчитать Exponential Moving Average"""
    if len(prices) < period:
        return np.full_like(prices, prices[0] if len(prices) > 0 else 0)

    try:
        prices = np.array(prices, dtype=np.float64)

        if np.all(prices == 0) or len(prices) == 0:
            return np.zeros_like(prices)

        ema = np.zeros_like(prices, dtype=np.float64)
        alpha = 2.0 / (period + 1)

        ema[0] = next((p for p in prices if p > 0), prices[0])

        for i in range(1, len(prices)):
            ema[i] = alpha * prices[i] + (1 - alpha) * ema[i - 1]

        return ema

    except Exception as e:
        logger.error(f"EMA calculation error: {e}")
        return np.full_like(prices, prices[0] if len(prices) > 0 else 0)


def analyze_ema200(
        candles: 'NormalizedCandles'
) -> Dict:
    """
    ✅ НОВОЕ: Упрощённый анализ EMA200 для контекста тренда

    Args:
        candles: NormalizedCandles объект

    Returns:
        Dict с данными EMA200:
        {
            'ema200_current': float,
            'price_above_ema200': bool,
            'distance_pct': float,
            'trend': 'BULLISH' | 'BEARISH' | 'FLAT'
        }
    """
    if not candles or not candles.is_valid:
        return {
            'ema200_current': 0,
            'price_above_ema200': False,
            'distance_pct': 0,
            'trend': 'FLAT'
        }

    if len(candles.closes) < 200:
        # Недостаточно данных для EMA200
        return {
            'ema200_current': 0,
            'price_above_ema200': False,
            'distance_pct': 0,
            'trend': 'FLAT'
        }

    try:
        ema200 = calculate_ema(candles.closes, 200)
        current_ema200 = float(ema200[-1])
        current_price = float(candles.closes[-1])

        if current_ema200 == 0:
            return {
                'ema200_current': 0,
                'price_above_ema200': False,
                'distance_pct': 0,
                'trend': 'FLAT'
            }

        # Расстояние от EMA200
        distance_pct = abs((current_price - current_ema200) / current_ema200 * 100)
        price_above = current_price > current_ema200

        # Определяем тренд по наклону EMA200
        ema200_slope = (ema200[-1] - ema200[-20]) / ema200[-20] * 100

        if ema200_slope > 0.5:
            trend = 'BULLISH'
        elif ema200_slope < -0.5:
            trend = 'BEARISH'
        else:
            trend = 'FLAT'

        return {
            'ema200_current': current_ema200,
            'price_above_ema200': price_above,
            'distance_pct': round(distance_pct, 2),
            'trend': trend
        }

    except Exception as e:
        logger.error(f"EMA200 analysis error: {e}")
        return {
            'ema200_current': 0,
            'price_above_ema200': False,
            'distance_pct': 0,
            'trend': 'FLAT'
        }


def analyze_triple_ema(
        candles,
        fast: int = 9,
        medium: int = 21,
        slow: int = 50,
        min_gap_pct: float = 0.5,
        crossover_lookback: int = 5,
        pullback_touch_pct: float = 1.5,
        pullback_volume_min: float = 1.2,
        compression_max_spread: float = 1.0,
        compression_breakout_volume: float = 2.0
) -> Optional[EMAAnalysis]:
    """Анализ Triple EMA (9/21/50) для определения паттернов"""
    if not candles or not candles.is_valid:
        return None

    if len(candles.closes) < max(fast, medium, slow) + 10:
        return None

    try:
        ema9 = calculate_ema(candles.closes, fast)
        ema21 = calculate_ema(candles.closes, medium)
        ema50 = calculate_ema(candles.closes, slow)

        current_price = float(candles.closes[-1])
        current_ema9 = float(ema9[-1])
        current_ema21 = float(ema21[-1])
        current_ema50 = float(ema50[-1])

        from .volume import calculate_volume_ratio
        volume_ratios = calculate_volume_ratio(candles.volumes)
        current_volume_ratio = float(volume_ratios[-1])

        alignment, alignment_score = _check_alignment(
            current_ema9, current_ema21, current_ema50, min_gap_pct
        )

        crossover, crossover_score = _check_crossover(
            ema9, ema21, ema50, crossover_lookback
        )

        pullback, pullback_score = _check_pullback(
            candles.closes, candles.lows, candles.highs,
            ema21, alignment, current_price, current_ema21,
            pullback_touch_pct, current_volume_ratio, pullback_volume_min
        )

        compression, compression_score = _check_compression(
            current_ema9, current_ema50, current_price,
            current_volume_ratio, compression_max_spread, compression_breakout_volume
        )

        bonus_score = _calculate_bonuses(
            ema9, ema21, ema50, current_price, current_ema9,
            current_ema50, current_volume_ratio, alignment
        )

        penalty = _calculate_penalties(
            ema21, volume_ratios, current_ema50, current_price,
            ema9, ema21
        )

        base_confidence = 50
        total_confidence = (
                base_confidence + alignment_score + crossover_score +
                pullback_score + compression_score + bonus_score + penalty
        )
        total_confidence = max(0, min(100, int(total_confidence)))

        distance_from_ema50 = abs((current_price - current_ema50) / current_ema50 * 100)

        details = _build_details(
            alignment, crossover, pullback, compression,
            alignment_score, crossover_score, pullback_score,
            compression_score, bonus_score, penalty
        )

        return EMAAnalysis(
            ema9_current=current_ema9,
            ema21_current=current_ema21,
            ema50_current=current_ema50,
            alignment=alignment,
            crossover=crossover,
            pullback=pullback,
            compression=compression,
            distance_from_ema50_pct=round(distance_from_ema50, 2),
            confidence_score=total_confidence,
            details=details
        )

    except Exception as e:
        logger.error(f"Triple EMA analysis error: {e}")
        return None


def _check_alignment(ema9, ema21, ema50, min_gap_pct):
    """Проверка alignment"""
    gap_9_21 = abs((ema9 - ema21) / ema21 * 100)
    gap_21_50 = abs((ema21 - ema50) / ema50 * 100)

    if ema9 > ema21 > ema50:
        alignment = 'BULLISH'
        score = 15 if (gap_9_21 >= min_gap_pct and gap_21_50 >= min_gap_pct) else 10
    elif ema9 < ema21 < ema50:
        alignment = 'BEARISH'
        score = 15 if (gap_9_21 >= min_gap_pct and gap_21_50 >= min_gap_pct) else 10
    else:
        alignment = 'NEUTRAL'
        score = 0

    return alignment, score


def _check_crossover(ema9, ema21, ema50, lookback):
    """Проверка crossover"""
    crossover = 'NONE'
    score = 0
    lookback = min(lookback, len(ema9) - 1)

    for i in range(1, lookback + 1):
        idx = -i
        if ema9[idx] > ema21[idx] and ema9[idx - 1] <= ema21[idx - 1]:
            if ema21[idx] > ema50[idx]:
                crossover = 'GOLDEN'
                score = 12
                break
        elif ema9[idx] < ema21[idx] and ema9[idx - 1] >= ema21[idx - 1]:
            if ema21[idx] < ema50[idx]:
                crossover = 'DEATH'
                score = 12
                break

    return crossover, score


def _check_pullback(closes, lows, highs, ema21, alignment, current_price,
                    current_ema21, touch_pct, volume_ratio, volume_min):
    """Проверка pullback"""
    pullback = 'NONE'
    score = 0

    for i in range(1, min(4, len(closes))):
        idx = -i
        low_price = float(lows[idx])
        high_price = float(highs[idx])
        ema21_value = float(ema21[idx])

        touch_upper = ema21_value * (1 + touch_pct / 100)
        touch_lower = ema21_value * (1 - touch_pct / 100)

        if alignment == 'BULLISH' and touch_lower <= low_price <= touch_upper:
            if current_price > current_ema21 and volume_ratio >= volume_min:
                pullback = 'BULLISH_BOUNCE'
                score = 10
                break
        elif alignment == 'BEARISH' and touch_lower <= high_price <= touch_upper:
            if current_price < current_ema21 and volume_ratio >= volume_min:
                pullback = 'BEARISH_BOUNCE'
                score = 10
                break

    return pullback, score


def _check_compression(ema9, ema50, price, volume_ratio, max_spread, breakout_volume):
    """Проверка compression"""
    compression = 'NONE'
    score = 0
    total_spread = abs((ema9 - ema50) / ema50 * 100)

    if total_spread <= max_spread:
        compression = 'COMPRESSED'
        if volume_ratio >= breakout_volume:
            if price > max(ema9, ema50):
                compression = 'BREAKOUT_UP'
                score = 12
            elif price < min(ema9, ema50):
                compression = 'BREAKOUT_DOWN'
                score = 12

    return compression, score


def _calculate_bonuses(ema9, ema21, ema50, price, current_ema9,
                       current_ema50, volume_ratio, alignment):
    """Бонусные баллы"""
    bonus = 0

    if alignment == 'BULLISH':
        if ema9[-1] > ema9[-5] and ema21[-1] > ema21[-5] and ema50[-1] > ema50[-5]:
            bonus += 10
    elif alignment == 'BEARISH':
        if ema9[-1] < ema9[-5] and ema21[-1] < ema21[-5] and ema50[-1] < ema50[-5]:
            bonus += 10

    if alignment == 'BULLISH' and price > current_ema9:
        bonus += 8
    elif alignment == 'BEARISH' and price < current_ema9:
        bonus += 8

    distance = abs((price - current_ema50) / current_ema50 * 100)
    if distance < 3.0:
        bonus += 8

    if volume_ratio >= 1.5:
        bonus += 8

    return bonus


def _calculate_penalties(ema21, volume_ratios, ema50, price, ema9_arr, ema21_arr):
    """Штрафы"""
    penalty = 0

    ema21_slope = abs((ema21[-1] - ema21[-10]) / ema21[-10] * 100)
    if ema21_slope < 0.5:
        penalty -= 10

    distance = abs((price - ema50) / ema50 * 100)
    if distance > 5.0:
        penalty -= 10

    recent_volume = [float(v) for v in volume_ratios[-3:]]
    if all(v < 0.8 for v in recent_volume):
        penalty -= 10

    crosses = 0
    for i in range(1, min(11, len(ema9_arr))):
        if (ema9_arr[-i] > ema21_arr[-i] and ema9_arr[-i - 1] <= ema21_arr[-i - 1]) or \
           (ema9_arr[-i] < ema21_arr[-i] and ema9_arr[-i - 1] >= ema21_arr[-i - 1]):
            crosses += 1

    if crosses >= 3:
        penalty -= 12

    return penalty


def _build_details(alignment, crossover, pullback, compression,
                   align_score, cross_score, pull_score, comp_score,
                   bonus, penalty):
    """Текстовое описание"""
    parts = []

    if alignment != 'NEUTRAL':
        parts.append(f"Alignment: {alignment} ({align_score:+d})")
    if crossover != 'NONE':
        parts.append(f"Crossover: {crossover} ({cross_score:+d})")
    if pullback != 'NONE':
        parts.append(f"Pullback: {pullback} ({pull_score:+d})")
    if compression not in ['NONE', 'COMPRESSED']:
        parts.append(f"Compression: {compression} ({comp_score:+d})")
    if bonus > 0:
        parts.append(f"Bonuses: {bonus:+d}")
    if penalty < 0:
        parts.append(f"Penalties: {penalty:+d}")

    return '; '.join(parts) if parts else 'No significant patterns'