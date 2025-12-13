"""
Telegram Formatters
Файл: telegram/formatters.py

Форматирование сигналов для Telegram (template-based)
"""

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

# Импортируем функцию определения типа актива
try:
    from utils.asset_detector import AssetTypeDetector
    
    def _detect_asset_type(symbol: str) -> str:
        """Обертка для обратной совместимости"""
        return AssetTypeDetector.detect(symbol)
except ImportError:
    # Fallback функция если импорт не удался
    def _detect_asset_type(symbol: str) -> str:
        """Определить тип актива по символу"""
        crypto_suffixes = ['USDT', 'BUSD', 'USDC']
        symbol_upper = symbol.upper()
        for suffix in crypto_suffixes:
            if symbol_upper.endswith(suffix):
                return 'crypto'
        return 'stock'

SIGNAL_TEMPLATE_CRYPTO = """
{emoji} <b>{symbol}</b> | {signal}
━━━━━━━━━━━━━━━━━━━━━━

<b>📊 ПАРАМЕТРЫ:</b>

• Confidence: <b>{confidence}%</b>
• Risk/Reward: <b>1:{rr_ratio:.1f}</b>

<b>💰 УРОВНИ ВХОДА/ВЫХОДА:</b>

• Entry:  <code>{entry_price:.4f}</code> $ 
• Stop:   <code>{stop_loss:.4f}</code> $ 
• TP1:    <code>{tp1:.4f}</code> $ 
• TP2:    <code>{tp2:.4f}</code> $ 
• TP3:    <code>{tp3:.4f}</code> $ 

<b>📝 АНАЛИЗ:</b>

<i>{analysis}</i>
"""

SIGNAL_TEMPLATE_STOCK = """
{emoji} <b>{symbol}</b> | {signal}
━━━━━━━━━━━━━━━━━━━━━━

<b>📊 ПАРАМЕТРЫ:</b>

• Confidence: <b>{confidence}%</b>
• Risk/Reward: <b>1:{rr_ratio:.1f}</b>

<b>💰 УРОВНИ ВХОДА/ВЫХОДА:</b>

• Entry:  <code>{entry_price:.4f}</code> ₽ 
• Stop:   <code>{stop_loss:.4f}</code> ₽ 
• TP1:    <code>{tp1:.4f}</code> ₽ 
• TP2:    <code>{tp2:.4f}</code> ₽ 
• TP3:    <code>{tp3:.4f}</code> ₽ 

<b>📝 АНАЛИЗ:</b>

<i>{analysis}</i>
"""


def format_signal_for_telegram(signal) -> str:
    """
    Форматировать TradingSignal для Telegram

    Args:
        signal: TradingSignal объект

    Returns:
        HTML-форматированный текст
    """
    try:
        emoji = '🟢' if signal.signal == 'LONG' else '🔴'

        tp_levels = signal.take_profit_levels
        if len(tp_levels) < 3:
            tp_levels = tp_levels + [0] * (3 - len(tp_levels))

        # Рассчитываем R/R
        rr_ratio = signal.risk_reward_ratio

        # Обрезаем analysis если слишком длинный
        analysis = signal.analysis
        if len(analysis) > 500:
            analysis = analysis[:497] + "..."

        # Определяем тип актива для выбора правильного шаблона и валюты
        asset_type = 'crypto'  # По умолчанию
        if hasattr(signal, 'comprehensive_data') and signal.comprehensive_data:
            asset_type = signal.comprehensive_data.get('asset_type', 'crypto')
        else:
            # Определяем по символу если нет в comprehensive_data
            asset_type = _detect_asset_type(signal.symbol)
        
        # Выбираем соответствующий шаблон
        template = SIGNAL_TEMPLATE_CRYPTO if asset_type == 'crypto' else SIGNAL_TEMPLATE_STOCK

        return template.format(
            emoji=emoji,
            symbol=signal.symbol,
            signal=signal.signal,
            confidence=signal.confidence,
            rr_ratio=rr_ratio,
            entry_price=signal.entry_price,
            stop_loss=signal.stop_loss,
            tp1=tp_levels[0],
            tp2=tp_levels[1],
            tp3=tp_levels[2],
            analysis=analysis
        ).strip()

    except Exception as e:
        logger.error(f"Error formatting signal: {e}")
        return f"⚠️ Error formatting signal for {signal.symbol}"


def format_bot_result(result: Dict) -> str:
    """
    Форматировать результат работы бота

    Args:
        result: Словарь с результатами

    Returns:
        Форматированный текст
    """
    try:
        bot_result = result.get('result', 'UNKNOWN')
        total_time = result.get('stats', {}).get('total_time', 0)
        stats = result.get('stats', {})

        emoji_map = {
            'SUCCESS': '✅',
            'NO_VALIDATED_SIGNALS': '⚠️',
            'NO_SIGNAL_PAIRS': '❌',
            'NO_AI_SELECTION': '❌',
            'NO_ANALYSIS_SIGNALS': '❌',
            'ERROR': '💥'
        }

        emoji = emoji_map.get(bot_result, '❓')

        result_text = (
            f"<b>{emoji} РЕЗУЛЬТАТ: {bot_result}</b>\n\n"
            f"⏱️ <b>Время выполнения:</b> {total_time:.1f}s\n\n"
        )

        # Детализация по этапам
        stage_times = stats.get('stage_times', {})
        if stage_times and any(stage_times.values()):
            result_text += "<b>⏲️ ВРЕМЯ ПО ЭТАПАМ:</b>\n"
            if stage_times.get('stage1', 0) > 0:
                result_text += f"  • Stage 1 (Filter): {stage_times['stage1']:.1f}s\n"
            if stage_times.get('stage2', 0) > 0:
                result_text += f"  • Stage 2 (AI Select): {stage_times['stage2']:.1f}s\n"
            if stage_times.get('stage3', 0) > 0:
                result_text += f"  • Stage 3 (Analysis): {stage_times['stage3']:.1f}s\n"
            result_text += "\n"

        # Статистика
        result_text += "<b>📊 СТАТИСТИКА АНАЛИЗА:</b>\n"
        result_text += f"  • Пар отсканировано: {stats.get('pairs_scanned', 0)}\n"
        result_text += f"  • Сигналов найдено: {stats.get('signal_pairs_found', 0)}\n"
        result_text += f"  • AI отобрал: {stats.get('ai_selected', 0)}\n"
        result_text += f"  • Проанализировано: {stats.get('analyzed', 0)}\n"
        result_text += f"  • ✅ Одобрено: {stats.get('validated_signals', 0)}\n"
        result_text += f"  • ❌ Отклонено: {stats.get('rejected_signals', 0)}\n"

        if stats.get('processing_speed'):
            result_text += f"  • Скорость: {stats['processing_speed']:.1f} пар/сек\n"

        if result.get('error'):
            result_text += f"\n❌ <b>Ошибка:</b>\n{result['error']}"

        return result_text

    except Exception as e:
        logger.error(f"Error formatting bot result: {e}")
        return "⚠️ Error formatting result"


def format_stage_progress(stage: str, message: str) -> str:
    """
    Форматировать прогресс выполнения этапа

    Args:
        stage: Название этапа (Stage 1, Stage 2, Stage 3)
        message: Сообщение о прогрессе

    Returns:
        Форматированный текст
    """
    emoji_map = {
        'Stage 1': '1️⃣',
        'Stage 2': '2️⃣',
        'Stage 3': '3️⃣',
        'Complete': '✅',
        'Error': '❌'
    }

    emoji = emoji_map.get(stage, '📊')

    return f"{emoji} <b>{stage}</b>\n\n{message}"


def format_rejected_signal(symbol: str, reason: str) -> str:
    """
    Форматировать отклонённый сигнал

    Args:
        symbol: Торговая пара
        reason: Причина отклонения

    Returns:
        Форматированный текст
    """
    # ✅ УБРАНО: Обрезка текста - теперь показываем полное объяснение
    # if len(reason) > 200:
    #     reason = reason[:197] + "..."

    return f"<b>{symbol}</b>\n<i>{reason}</i>"