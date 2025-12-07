"""
Volume Indicator
Файл: indicators/volume.py

Volume ratio calculation and analysis
"""

import numpy as np
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class VolumeAnalysis:
    """
    Результат анализа объёма

    Attributes:
        volume_ratio_current: Текущий volume ratio
        volume_trend: 'INCREASING' | 'DECREASING' | 'STABLE'
        spike_detected: Обнаружен ли volume spike
        confidence_adjustment: Корректировка confidence (-10 до +15)
        details: Текстовое описание
    """
    volume_ratio_current: float
    volume_trend: str
    spike_detected: bool
    confidence_adjustment: int
    details: str


def calculate_volume_ratio(volumes: np.ndarray, window: int = 20) -> np.ndarray:
    """
    Рассчитать volume ratio (текущий объём / средний объём)

    Args:
        volumes: Массив объёмов
        window: Окно для среднего (default 20)

    Returns:
        Массив volume ratios той же длины что и volumes
    """
    try:
        volumes = np.array([float(v) for v in volumes])

        if len(volumes) < window:
            return np.ones_like(volumes)

        ratios = np.ones_like(volumes)

        for i in range(window, len(volumes)):
            avg_volume = np.mean(volumes[max(0, i - window):i])

            if avg_volume > 0:
                ratios[i] = volumes[i] / avg_volume
            else:
                ratios[i] = 1.0

        return ratios

    except Exception as e:
        logger.error(f"Volume ratio calculation error: {e}")
        return np.ones_like(volumes)


def analyze_volume(
        candles,  # NormalizedCandles
        window: int = None,
        spike_threshold: float = None
) -> Optional[VolumeAnalysis]:
    """
    Анализ объёма для подтверждения движений

    Args:
        candles: NormalizedCandles объект
        window: Окно для среднего (по умолчанию из config)
        spike_threshold: Порог для spike detection (по умолчанию из config)

    Returns:
        VolumeAnalysis объект или None при ошибке
    """
    from config import config
    
    if window is None:
        window = config.VOLUME_WINDOW
    if spike_threshold is None:
        spike_threshold = config.VOLUME_SPIKE_THRESHOLD
    
    if not candles or not candles.is_valid:
        return None

    if len(candles.volumes) < window + 5:
        return None

    try:
        volume_ratios = calculate_volume_ratio(candles.volumes, window)
        current_ratio = float(volume_ratios[-1])

        # Определяем тренд объёма
        trend = _determine_volume_trend(volume_ratios)

        # Проверка spike
        spike_detected = current_ratio >= spike_threshold

        # Корректировка confidence
        adjustment = _calculate_volume_adjustment(
            current_ratio, trend, spike_detected
        )

        # Детали
        details = _build_volume_details(
            current_ratio, trend, spike_detected, adjustment
        )

        return VolumeAnalysis(
            volume_ratio_current=round(current_ratio, 2),
            volume_trend=trend,
            spike_detected=spike_detected,
            confidence_adjustment=adjustment,
            details=details
        )

    except Exception as e:
        logger.error(f"Volume analysis error: {e}")
        return None


def _determine_volume_trend(ratios: np.ndarray, lookback: int = 5) -> str:
    """Определить тренд объёма"""
    if len(ratios) < lookback:
        return 'STABLE'

    try:
        recent = ratios[-lookback:]

        # Растущий тренд
        if np.all(np.diff(recent) > 0):
            return 'INCREASING'

        # Падающий тренд
        if np.all(np.diff(recent) < 0):
            return 'DECREASING'

        # Среднее значение
        avg_recent = np.mean(recent)
        avg_before = np.mean(ratios[-lookback * 2:-lookback])

        if avg_recent > avg_before * 1.2:
            return 'INCREASING'
        elif avg_recent < avg_before * 0.8:
            return 'DECREASING'

        return 'STABLE'

    except:
        return 'STABLE'


def _calculate_volume_adjustment(
        ratio: float,
        trend: str,
        spike: bool
) -> int:
    """Рассчитать корректировку confidence"""
    from config import config
    
    adjustment = 0

    # Volume spike
    if spike:
        adjustment += config.VOLUME_SPIKE_SCORE
    elif ratio >= config.VOLUME_STRONG_THRESHOLD:
        adjustment += config.VOLUME_STRONG_SCORE
    elif ratio >= config.VOLUME_GOOD_THRESHOLD:
        adjustment += config.VOLUME_GOOD_SCORE

    # Volume trend
    if trend == 'INCREASING':
        adjustment += config.VOLUME_TREND_INCREASING_BONUS
    elif trend == 'DECREASING':
        adjustment += config.VOLUME_TREND_DECREASING_PENALTY

    # Dead volume
    if ratio < config.VOLUME_DEAD_THRESHOLD:
        adjustment += config.VOLUME_DEAD_PENALTY

    return adjustment


def _build_volume_details(
        ratio: float,
        trend: str,
        spike: bool,
        adjustment: int
) -> str:
    """Построить текстовое описание"""
    parts = [f"Ratio: {ratio:.2f}", f"Trend: {trend}"]

    if spike:
        parts.append("Spike detected")

    if adjustment != 0:
        parts.append(f"Adjustment: {adjustment:+d}")

    return '; '.join(parts)