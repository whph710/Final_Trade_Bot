"""
ATR Indicator + Wave Analysis
Файл: indicators/atr.py

✅ ДОБАВЛЕНО:
- WaveAnalysis dataclass для анализа волн через ATR
- analyze_waves_atr() функция для расчёта волн
"""

import numpy as np
import logging
from dataclasses import dataclass
from typing import Optional, List

logger = logging.getLogger(__name__)


@dataclass
class WaveAnalysis:
    """Анализ волн (бычьих/медвежьих)"""
    wave_type: str  # 'BULLISH' | 'BEARISH' | 'NEUTRAL'
    wave_lengths: List[float]  # Длины последних волн в %
    average_wave_length: float  # Средняя длина волны (ATR)
    current_wave_progress: float  # Прогресс текущей волны (%)
    is_early_entry: bool  # True если < 30% от ATR
    confidence_adjustment: int
    details: str


def calculate_atr(candles, period: int = 14) -> float:
    """
    Рассчитать Average True Range

    Args:
        candles: NormalizedCandles объект
        period: Период ATR (default 14)

    Returns:
        ATR значение (float)
    """
    if not candles or not candles.is_valid:
        return 0.0

    if len(candles.closes) < period + 1:
        return 0.0

    try:
        highs = candles.highs
        lows = candles.lows
        closes = candles.closes

        # Проверка на нулевые значения
        if np.any(highs <= 0) or np.any(lows <= 0) or np.any(closes <= 0):
            return 0.0

        # True Range calculation
        tr = np.zeros(len(candles.closes))

        for i in range(1, len(candles.closes)):
            tr[i] = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i - 1]),
                abs(lows[i] - closes[i - 1])
            )

        if len(tr) <= period:
            return float(np.mean(tr[1:]))

        # Экспоненциальное сглаживание
        atr = np.mean(tr[1:period + 1])

        for i in range(period + 1, len(candles.closes)):
            atr = (atr * (period - 1) + tr[i]) / period

        return float(atr)

    except Exception as e:
        logger.error(f"ATR calculation error: {e}")
        return 0.0


def suggest_stop_loss(
        entry_price: float,
        atr: float,
        signal_type: str,
        multiplier: float = None
) -> float:
    """
    Предложить stop-loss на основе ATR

    Args:
        entry_price: Цена входа
        atr: ATR значение
        signal_type: 'LONG' или 'SHORT'
        multiplier: Множитель ATR (по умолчанию из config)

    Returns:
        Предложенная цена stop-loss
    """
    from config import config
    
    if multiplier is None:
        multiplier = config.ATR_STOP_LOSS_MULTIPLIER
    
    if entry_price == 0 or atr == 0:
        return 0.0

    try:
        stop_distance = atr * multiplier

        if signal_type == 'LONG':
            stop_loss = entry_price - stop_distance
        elif signal_type == 'SHORT':
            stop_loss = entry_price + stop_distance
        else:
            return 0.0

        return float(stop_loss)

    except Exception as e:
        logger.error(f"Stop-loss calculation error: {e}")
        return 0.0


def analyze_waves_atr(
        candles: 'NormalizedCandles',
        num_waves: int = None
) -> Optional[WaveAnalysis]:
    """
    ✅ НОВОЕ: Анализ волн через ATR

    Алгоритм:
    1. Находим swing highs/lows (волны)
    2. Рассчитываем длину каждой волны в %
    3. Определяем среднюю длину (ATR волн)
    4. Проверяем прогресс текущей волны

    Args:
        candles: NormalizedCandles объект
        num_waves: Количество волн для анализа (по умолчанию из config)

    Returns:
        WaveAnalysis или None при ошибке
    """
    from config import config
    
    if num_waves is None:
        num_waves = config.WAVE_ANALYSIS_NUM_WAVES
    
    if not candles or not candles.is_valid:
        return None

    if len(candles.closes) < 50:
        return None

    try:
        highs = candles.highs
        lows = candles.lows
        closes = candles.closes
        current_price = float(closes[-1])

        # ============================================================
        # 1. НАХОДИМ SWING POINTS (волны)
        # ============================================================
        swing_highs = _find_swing_points(highs, 'high', window=config.WAVE_SWING_WINDOW)
        swing_lows = _find_swing_points(lows, 'low', window=config.WAVE_SWING_WINDOW)

        if len(swing_highs) < 2 or len(swing_lows) < 2:
            logger.debug("Not enough swing points for wave analysis")
            return None

        # ============================================================
        # 2. РАССЧИТЫВАЕМ ДЛИНЫ ВОЛН
        # ============================================================
        bullish_waves = []  # Волны снизу вверх (low → high)
        bearish_waves = []  # Волны сверху вниз (high → low)

        # Бычьи волны: от swing low до следующего swing high
        for i, low_idx in enumerate(swing_lows):
            # Находим следующий swing high после этого low
            next_highs = [h for h in swing_highs if h > low_idx]
            if next_highs:
                high_idx = next_highs[0]
                wave_start = float(lows[low_idx])
                wave_end = float(highs[high_idx])

                if wave_start > 0:
                    wave_length_pct = ((wave_end - wave_start) / wave_start) * 100
                    bullish_waves.append(wave_length_pct)

        # Медвежьи волны: от swing high до следующего swing low
        for i, high_idx in enumerate(swing_highs):
            next_lows = [l for l in swing_lows if l > high_idx]
            if next_lows:
                low_idx = next_lows[0]
                wave_start = float(highs[high_idx])
                wave_end = float(lows[low_idx])

                if wave_start > 0:
                    wave_length_pct = ((wave_start - wave_end) / wave_start) * 100
                    bearish_waves.append(wave_length_pct)

        if not bullish_waves and not bearish_waves:
            logger.debug("No complete waves found")
            return None

        # ============================================================
        # 3. ОПРЕДЕЛЯЕМ ТИП ТЕКУЩЕЙ ВОЛНЫ И СРЕДНЮЮ ДЛИНУ
        # ============================================================

        # Последний swing high/low
        last_swing_high_idx = swing_highs[-1] if swing_highs else 0
        last_swing_low_idx = swing_lows[-1] if swing_lows else 0

        if last_swing_low_idx > last_swing_high_idx:
            # Текущая волна бычья (начинается от последнего low)
            wave_type = 'BULLISH'
            wave_start_price = float(lows[last_swing_low_idx])
            relevant_waves = bullish_waves[-num_waves:] if bullish_waves else []

        elif last_swing_high_idx > last_swing_low_idx:
            # Текущая волна медвежья (начинается от последнего high)
            wave_type = 'BEARISH'
            wave_start_price = float(highs[last_swing_high_idx])
            relevant_waves = bearish_waves[-num_waves:] if bearish_waves else []

        else:
            wave_type = 'NEUTRAL'
            wave_start_price = current_price
            relevant_waves = []

        # Средняя длина волн
        if relevant_waves:
            average_wave_length = np.mean(relevant_waves)
        else:
            average_wave_length = 0

        # ============================================================
        # 4. ПРОГРЕСС ТЕКУЩЕЙ ВОЛНЫ
        # ============================================================
        if wave_start_price > 0 and average_wave_length > 0:
            if wave_type == 'BULLISH':
                current_move_pct = ((current_price - wave_start_price) / wave_start_price) * 100
            elif wave_type == 'BEARISH':
                current_move_pct = ((wave_start_price - current_price) / wave_start_price) * 100
            else:
                current_move_pct = 0

            # Прогресс = (текущее движение / средняя волна) * 100
            current_wave_progress = (current_move_pct / average_wave_length) * 100

        else:
            current_wave_progress = 0

        # ============================================================
        # 5. РАННИЙ ВХОД?
        # ============================================================
        is_early_entry = current_wave_progress < config.WAVE_EARLY_ENTRY_THRESHOLD

        # ============================================================
        # 6. CONFIDENCE ADJUSTMENT
        # ============================================================
        adjustment = 0

        if is_early_entry:
            adjustment += config.WAVE_EARLY_ENTRY_SCORE
        elif current_wave_progress < config.WAVE_GOOD_ENTRY_THRESHOLD:
            adjustment += config.WAVE_GOOD_ENTRY_SCORE
        elif current_wave_progress < config.WAVE_LATE_ENTRY_THRESHOLD:
            adjustment += config.WAVE_LATE_ENTRY_SCORE
        else:
            # Слишком поздно
            adjustment += config.WAVE_TOO_LATE_PENALTY

        # Бонус за сильное направление волн
        if wave_type == 'BULLISH' and len(bullish_waves) >= 3:
            if np.mean(bullish_waves[-3:]) > np.mean(bearish_waves[-3:] if bearish_waves else [0]):
                adjustment += 10

        elif wave_type == 'BEARISH' and len(bearish_waves) >= 3:
            if np.mean(bearish_waves[-3:]) > np.mean(bullish_waves[-3:] if bullish_waves else [0]):
                adjustment += 10

        # ============================================================
        # 7. ДЕТАЛИ
        # ============================================================
        details = (
            f"{wave_type} wave, progress: {current_wave_progress:.0f}%, "
            f"avg length: {average_wave_length:.1f}%"
        )

        if is_early_entry:
            details += " (early entry)"

        return WaveAnalysis(
            wave_type=wave_type,
            wave_lengths=relevant_waves,
            average_wave_length=round(average_wave_length, 2),
            current_wave_progress=round(current_wave_progress, 1),
            is_early_entry=is_early_entry,
            confidence_adjustment=adjustment,
            details=details
        )

    except Exception as e:
        logger.error(f"Wave analysis error: {e}")
        return None


def _find_swing_points(
        prices: np.ndarray,
        point_type: str,
        window: int = None
) -> List[int]:
    """
    Найти swing highs или swing lows

    Args:
        prices: Массив цен
        point_type: 'high' или 'low'
        window: Окно для проверки локального экстремума (по умолчанию из config)

    Returns:
        Список индексов swing points
    """
    from config import config
    
    if window is None:
        window = config.WAVE_SWING_WINDOW
    
    swings = []

    for i in range(window, len(prices) - window):
        if point_type == 'high':
            # Локальный максимум
            is_peak = all(
                prices[i] >= prices[i - j] for j in range(1, window + 1)
            ) and all(
                prices[i] >= prices[i + j] for j in range(1, window + 1)
            )

            if is_peak:
                swings.append(i)

        else:  # 'low'
            # Локальный минимум
            is_valley = all(
                prices[i] <= prices[i - j] for j in range(1, window + 1)
            ) and all(
                prices[i] <= prices[i + j] for j in range(1, window + 1)
            )

            if is_valley:
                swings.append(i)

    return swings