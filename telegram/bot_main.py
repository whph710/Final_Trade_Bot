"""
Telegram Bot Main - FIXED HTML ESCAPING
Файл: telegram/bot_main.py

ИСПРАВЛЕНО:
✅ Экранирование HTML символов в rejection_reason для Telegram
✅ Удалены проблемные символы < > & которые ломают HTML parsing
"""

import asyncio
import json
import logging
import html
from datetime import datetime
from typing import Optional
from pathlib import Path

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    CallbackQuery
)
from aiogram.filters import Command
from aiogram.enums import ChatAction
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

logger = logging.getLogger(__name__)


# ============================================================================
# FSM STATES
# ============================================================================
class ManualAnalysisStates(StatesGroup):
    """Состояния для ручного анализа пары"""
    waiting_for_symbol = State()
    waiting_for_direction = State()


# ============================================================================
# TELEGRAM BOT CLASS
# ============================================================================
class TradingBotTelegram:
    """Telegram бот для торговой системы"""

    def __init__(
            self,
            bot_token: str,
            user_id: int,
            group_id: int
    ):
        self.bot = Bot(token=bot_token)
        self.storage = MemoryStorage()
        self.dp = Dispatcher(storage=self.storage)
        self.router = Router()
        self.dp.include_router(self.router)

        self.user_id = user_id
        self.group_id = group_id
        self.trading_bot_running = False
        self._typing_task = None

        # Signal Storage & Backtester
        from utils import get_signal_storage, get_backtester
        self.signal_storage = get_signal_storage()
        self.backtester = get_backtester()

        # Statistics file
        from config import config
        self.stats_file = config.LOGS_DIR / 'bot_statistics.json'

        self._register_handlers()

        logger.info(
            f"Trading Bot Telegram initialized: "
            f"user_id={user_id}, group_id={group_id}"
        )

    def _register_handlers(self):
        """Регистрация обработчиков команд"""
        self.dp.message.register(self.start_command, Command(commands=["start"]))

        # Текстовые сообщения
        self.dp.message.register(
            self.handle_run_analysis,
            F.text == "▶️ Запустить сейчас"
        )
        self.dp.message.register(
            self.handle_manual_pair_analysis,
            F.text == "🔍 Анализ пары"
        )
        self.dp.message.register(
            self.show_status,
            F.text == "📊 Статус"
        )
        self.dp.message.register(
            self.show_statistics,
            F.text == "📈 Статистика"
        )
        self.dp.message.register(
            self.handle_backtest,
            F.text == "📊 Backtest"
        )
        self.dp.message.register(
            self.stop_bot,
            F.text == "🛑 Остановить"
        )

        # FSM handlers
        self.dp.message.register(
            self.process_symbol_input,
            ManualAnalysisStates.waiting_for_symbol
        )
        self.router.callback_query.register(
            self.process_direction_selection,
            ManualAnalysisStates.waiting_for_direction
        )

    async def start_command(self, message: Message):
        """Обработка команды /start"""
        user_id = message.from_user.id

        if user_id != self.user_id:
            await message.reply("❌ Доступ запрещён")
            return

        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="▶️ Запустить сейчас")],
                [KeyboardButton(text="🔍 Анализ пары")],
                [
                    KeyboardButton(text="📊 Статус"),
                    KeyboardButton(text="📈 Статистика")
                ],
                [KeyboardButton(text="📊 Backtest")],
                [KeyboardButton(text="🛑 Остановить")]
            ],
            resize_keyboard=True
        )

        await message.answer(
            "🤖 <b>Trading Bot активирован!</b>\n\n"
            "Бот работает по расписанию или по команде.\n\n"
            "<b>Доступные команды:</b>\n"
            "▶️ Запустить сейчас - полный цикл анализа\n"
            "🔍 Анализ пары - анализ конкретной пары (LONG/SHORT)\n"
            "📊 Статус - текущее состояние\n"
            "📈 Статистика - статистика запусков\n"
            "📊 Backtest - backtest сохранённых сигналов\n"
            "🛑 Остановить - остановка бота",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    # ========================================================================
    # РУЧНОЙ АНАЛИЗ ПАРЫ
    # ========================================================================

    async def handle_manual_pair_analysis(self, message: Message, state: FSMContext):
        """Начать диалог для ручного анализа пары"""
        user_id = message.from_user.id

        if user_id != self.user_id:
            return

        await state.set_state(ManualAnalysisStates.waiting_for_symbol)

        await message.answer(
            "🔍 <b>Ручной анализ пары</b>\n\n"
            "Введите символ торговой пары (например: <code>BTCUSDT</code>, <code>ETHUSDT</code>):\n\n"
            "💡 Отправьте <code>/cancel</code> для отмены",
            parse_mode="HTML"
        )

    async def process_symbol_input(self, message: Message, state: FSMContext):
        """Обработка ввода символа"""
        user_id = message.from_user.id

        if user_id != self.user_id:
            return

        if message.text and message.text.lower() in ['/cancel', 'отмена', 'cancel']:
            await state.clear()
            await message.answer("❌ Анализ отменён", parse_mode="HTML")
            return

        symbol = message.text.strip().upper()

        if not symbol or len(symbol) < 3 or len(symbol) > 20:
            await message.answer(
                "⚠️ Некорректный символ. Попробуйте ещё раз (например: <code>BTCUSDT</code>)",
                parse_mode="HTML"
            )
            return

        if not symbol.endswith('USDT'):
            await message.answer(
                "⚠️ Бот работает только с парами USDT (например: <code>BTCUSDT</code>)\n\n"
                "Попробуйте ещё раз:",
                parse_mode="HTML"
            )
            return

        await state.update_data(symbol=symbol)
        await state.set_state(ManualAnalysisStates.waiting_for_direction)

        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="🟢 LONG", callback_data="direction:LONG"),
                    InlineKeyboardButton(text="🔴 SHORT", callback_data="direction:SHORT")
                ],
                [
                    InlineKeyboardButton(text="❌ Отмена", callback_data="direction:CANCEL")
                ]
            ]
        )

        await message.answer(
            f"✅ Пара: <b>{symbol}</b>\n\n"
            f"Выберите направление анализа:",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    async def process_direction_selection(self, callback: CallbackQuery, state: FSMContext):
        """Обработка выбора направления"""
        user_id = callback.from_user.id

        if user_id != self.user_id:
            await callback.answer("❌ Доступ запрещён", show_alert=True)
            return

        data = await state.get_data()
        symbol = data.get('symbol', 'UNKNOWN')

        action = callback.data.split(':')[1]

        if action == 'CANCEL':
            await state.clear()
            await callback.message.edit_text("❌ Анализ отменён", parse_mode="HTML")
            await callback.answer()
            return

        await callback.answer(f"✅ Анализирую {symbol} {action}")

        await callback.message.edit_text(
            f"⏳ <b>Запуск анализа...</b>\n\n"
            f"Пара: <b>{symbol}</b>\n"
            f"Направление: <b>{action}</b>",
            parse_mode="HTML"
        )

        await self._run_manual_pair_analysis(symbol, action)
        await state.clear()

    async def _run_manual_pair_analysis(self, symbol: str, direction: str):
        """Запуск Stage 3 для конкретной пары и направления"""
        try:
            await self._start_typing_indicator(self.user_id)

            try:
                from stages.stage3_analysis import analyze_single_pair
                from data_providers import cleanup_session

                logger.info(f"Manual analysis: {symbol} {direction}")

                result = await analyze_single_pair(symbol, direction)

                await cleanup_session()

            finally:
                await self._stop_typing_indicator()

            if result and result.signal != 'NO_SIGNAL':
                # Сохраняем сигнал
                self.signal_storage.save_signal(result)

                # Отправляем в группу
                await self._send_signals_to_group([result])

                await self.bot.send_message(
                    chat_id=self.user_id,
                    text=(
                        f"✅ <b>Анализ завершён</b>\n\n"
                        f"Пара: <b>{symbol}</b>\n"
                        f"Сигнал: <b>{result.signal}</b>\n"
                        f"Confidence: <b>{result.confidence}%</b>\n\n"
                        f"💾 Сигнал сохранён в signals/"
                    ),
                    parse_mode="HTML"
                )
            else:
                rejection_reason = result.comprehensive_data.get(
                    'rejection_reason',
                    'Сигнал не найден'
                ) if result else 'Ошибка анализа'

                # ✅ ИСПРАВЛЕНО: Экранируем HTML
                rejection_reason = self._escape_html(rejection_reason)

                await self.bot.send_message(
                    chat_id=self.user_id,
                    text=(
                        f"⚠️ <b>Сигнал не найден</b>\n\n"
                        f"Пара: <b>{symbol}</b>\n"
                        f"Причина: {rejection_reason}"
                    ),
                    parse_mode="HTML"
                )

        except Exception as e:
            await self._stop_typing_indicator()
            logger.exception(f"Error in manual pair analysis: {e}")

            try:
                from data_providers import cleanup_session
                await cleanup_session()
            except:
                pass

            await self.bot.send_message(
                chat_id=self.user_id,
                text=f"❌ <b>Ошибка анализа:</b> {str(e)[:200]}",
                parse_mode="HTML"
            )

    # ========================================================================
    # ПОЛНЫЙ ЦИКЛ АНАЛИЗА
    # ========================================================================

    async def handle_run_analysis(self, message: Message):
        """Обработчик кнопки '▶️ Запустить сейчас'"""
        await self.run_trading_bot_manual(message)

    async def run_trading_bot_manual(self, message: Message):
        """Ручной запуск торгового бота (полный цикл)"""
        try:
            await self.bot.send_message(
                chat_id=self.user_id,
                text="⏳ <b>Запуск анализа...</b>",
                parse_mode="HTML"
            )

            await self._start_typing_indicator(self.user_id)

            try:
                from stages import run_stage1, run_stage2, run_stage3
                from data_providers import get_all_trading_pairs, cleanup_session

                # Stage 1
                logger.info("Manual run: Starting Stage 1")
                pairs = await get_all_trading_pairs()
                candidates = await run_stage1(pairs)

                if not candidates:
                    await self.bot.send_message(
                        chat_id=self.user_id,
                        text="❌ <b>Stage 1: Сигналов не найдено</b>",
                        parse_mode="HTML"
                    )
                    await cleanup_session()
                    return

                await self.bot.send_message(
                    chat_id=self.user_id,
                    text=f"✅ <b>Stage 1: Найдено {len(candidates)} сигналов</b>",
                    parse_mode="HTML"
                )

                # Stage 2
                logger.info("Manual run: Starting Stage 2")
                selected_pairs = await run_stage2(candidates)

                if not selected_pairs:
                    await self.bot.send_message(
                        chat_id=self.user_id,
                        text="❌ <b>Stage 2: AI не выбрал пары</b>",
                        parse_mode="HTML"
                    )
                    await cleanup_session()
                    return

                await self.bot.send_message(
                    chat_id=self.user_id,
                    text=(
                        f"✅ <b>Stage 2: AI выбрал {len(selected_pairs)} пар</b>\n\n"
                        f"{'  •  '.join(selected_pairs)}"
                    ),
                    parse_mode="HTML"
                )

                # Stage 3
                logger.info("Manual run: Starting Stage 3")
                approved_signals, rejected_signals = await run_stage3(selected_pairs)

                await cleanup_session()

            finally:
                await self._stop_typing_indicator()

            # Сохраняем сигналы
            if approved_signals:
                saved = self.signal_storage.save_signals_batch(approved_signals)
                logger.info(f"Saved {saved} signals to storage")

            # Отправляем результат
            if approved_signals:
                await self._send_signals_to_group(approved_signals)

                await self.bot.send_message(
                    chat_id=self.user_id,
                    text=(
                        f"✅ <b>Анализ завершён</b>\n\n"
                        f"Одобрено: {len(approved_signals)}\n"
                        f"Отклонено: {len(rejected_signals)}\n\n"
                        f"💾 Сигналы сохранены в signals/"
                    ),
                    parse_mode="HTML"
                )
            else:
                await self.bot.send_message(
                    chat_id=self.user_id,
                    text=(
                        f"⚠️ <b>Сигналов не найдено</b>\n\n"
                        f"Отклонено: {len(rejected_signals)}"
                    ),
                    parse_mode="HTML"
                )

            if rejected_signals:
                await self._send_rejected_signals(rejected_signals)

            # Обновляем статистику
            self._update_statistics(len(approved_signals), len(rejected_signals))

        except Exception as e:
            await self._stop_typing_indicator()
            logger.exception("Error running trading bot manually")

            try:
                from data_providers import cleanup_session
                await cleanup_session()
            except:
                pass

            await self.bot.send_message(
                chat_id=self.user_id,
                text=f"❌ <b>Ошибка:</b> {str(e)[:200]}",
                parse_mode="HTML"
            )

    # ========================================================================
    # BACKTESTING
    # ========================================================================

    async def handle_backtest(self, message: Message):
        """Запуск backtesting"""
        user_id = message.from_user.id

        if user_id != self.user_id:
            return

        try:
            await message.answer("⏳ <b>Запуск backtest...</b>", parse_mode="HTML")

            # Загружаем сигналы
            signals = self.signal_storage.load_signals()

            if not signals:
                await message.answer(
                    "⚠️ <b>Нет сохранённых сигналов</b>\n\n"
                    "Запустите анализ чтобы создать сигналы для backtest",
                    parse_mode="HTML"
                )
                return

            await message.answer(
                f"📊 Найдено <b>{len(signals)}</b> сигналов для backtest...",
                parse_mode="HTML"
            )

            # Запускаем backtest
            result = self.backtester.run_backtest(signals)

            # Форматируем отчёт
            from utils import format_backtest_report
            report = format_backtest_report(result)

            await message.answer(report, parse_mode="HTML")

            await message.answer(
                f"💾 Результаты сохранены в signals/backtest_results/",
                parse_mode="HTML"
            )

        except Exception as e:
            logger.exception("Backtest error")
            await message.answer(
                f"❌ <b>Ошибка backtest:</b> {str(e)[:200]}",
                parse_mode="HTML"
            )

    # ========================================================================
    # СТАТИСТИКА И СТАТУС
    # ========================================================================

    async def show_status(self, message: Message):
        """Показать статус бота"""
        status_text = (
            "📊 <b>Статус бота:</b>\n\n"
            f"⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"👤 User ID: {self.user_id}\n"
            f"👥 Group ID: {self.group_id}\n"
            f"🤖 Статус: Активен\n"
        )

        await self.bot.send_message(
            chat_id=self.user_id,
            text=status_text,
            parse_mode="HTML"
        )

    async def show_statistics(self, message: Message):
        """Показать статистику из logs/bot_statistics.json"""
        try:
            if not self.stats_file.exists():
                await message.answer(
                    "⚠️ <b>Статистика недоступна</b>\n\n"
                    "Запустите анализ чтобы создать статистику",
                    parse_mode="HTML"
                )
                return

            with open(self.stats_file, 'r', encoding='utf-8') as f:
                stats = json.load(f)

            stats_text = [
                "📈 <b>СТАТИСТИКА БОТА</b>",
                "━━━━━━━━━━━━━━━━━━━━━━\n",
                f"<b>Всего запусков:</b> {stats.get('total_runs', 0)}",
                f"<b>Одобренных сигналов:</b> {stats.get('total_approved', 0)}",
                f"<b>Отклонённых сигналов:</b> {stats.get('total_rejected', 0)}",
                f"\n<b>Последний запуск:</b>",
                f"{stats.get('last_run', 'N/A')}"
            ]

            await message.answer("\n".join(stats_text), parse_mode="HTML")

        except Exception as e:
            logger.exception("Error loading statistics")
            await message.answer(
                "❌ <b>Ошибка загрузки статистики</b>",
                parse_mode="HTML"
            )

    def _update_statistics(self, approved: int, rejected: int):
        """Обновить статистику в logs/bot_statistics.json"""
        try:
            if self.stats_file.exists():
                with open(self.stats_file, 'r', encoding='utf-8') as f:
                    stats = json.load(f)
            else:
                stats = {
                    'total_runs': 0,
                    'total_approved': 0,
                    'total_rejected': 0,
                    'last_run': None
                }

            stats['total_runs'] += 1
            stats['total_approved'] += approved
            stats['total_rejected'] += rejected
            stats['last_run'] = datetime.now().isoformat()

            with open(self.stats_file, 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=2, ensure_ascii=False)

            logger.info("Statistics updated")

        except Exception as e:
            logger.error(f"Error updating statistics: {e}")

    async def stop_bot(self, message: Message):
        """Остановка бота"""
        await self.bot.send_message(
            chat_id=self.user_id,
            text="🛑 <b>Бот остановлен.</b> Перезапустите для возобновления",
            parse_mode="HTML"
        )

    # ========================================================================
    # HELPER FUNCTIONS
    # ========================================================================

    def _escape_html(self, text: str) -> str:
        """
        ✅ НОВОЕ: Экранировать HTML символы для безопасной отправки в Telegram

        Заменяет проблемные символы:
        - < на &lt;
        - > на &gt;
        - & на &amp;
        """
        if not text:
            return ""

        # Используем стандартный html.escape
        return html.escape(str(text), quote=False)

    async def _send_signals_to_group(self, signals: list):
        """Отправить сигналы в группу"""
        from telegram.formatters import format_signal_for_telegram

        try:
            for signal in signals:
                formatted_text = format_signal_for_telegram(signal)

                await self.bot.send_message(
                    chat_id=self.group_id,
                    text=formatted_text,
                    parse_mode="HTML"
                )

                await asyncio.sleep(0.5)

            logger.info(f"Sent {len(signals)} signals to group {self.group_id}")

        except Exception as e:
            logger.error(f"Error sending signals to group: {e}")

    async def _send_rejected_signals(self, rejected_signals: list):
        """
        ✅ ИСПРАВЛЕНО: Отправить rejected signals с экранированием HTML
        """
        if not rejected_signals:
            return

        try:
            batch_size = 5
            for i in range(0, len(rejected_signals), batch_size):
                batch = rejected_signals[i:i + batch_size]

                message_parts = [
                    f"❌ <b>ОТКЛОНЁННЫЕ СИГНАЛЫ "
                    f"({i + 1}-{min(i + batch_size, len(rejected_signals))} "
                    f"из {len(rejected_signals)})</b>\n"
                ]

                for sig in batch:
                    symbol = sig.get('symbol', 'UNKNOWN')
                    reason = sig.get('rejection_reason', 'Unknown reason')

                    # ✅ КРИТИЧНО: Экранируем HTML символы
                    reason = self._escape_html(reason)

                    # Обрезаем если слишком длинный
                    if len(reason) > 200:
                        reason = reason[:197] + "..."

                    message_parts.append(f"\n<b>{symbol}</b>")
                    message_parts.append(f"<i>{reason}</i>\n")

                full_message = "\n".join(message_parts)

                await self.bot.send_message(
                    chat_id=self.user_id,
                    text=full_message,
                    parse_mode="HTML"
                )

                await asyncio.sleep(0.5)

            logger.info(f"Sent {len(rejected_signals)} rejected signals to user")

        except Exception as e:
            logger.error(f"Error sending rejected signals: {e}")

    async def _start_typing_indicator(self, chat_id: int):
        """Запустить индикатор печати"""
        async def send_typing():
            try:
                while True:
                    await self.bot.send_chat_action(
                        chat_id=chat_id,
                        action=ChatAction.TYPING
                    )
                    await asyncio.sleep(4)
            except asyncio.CancelledError:
                pass
            except Exception as e:
                logger.error(f"Error in typing indicator: {e}")

        self._typing_task = asyncio.create_task(send_typing())

    async def _stop_typing_indicator(self):
        """Остановить индикатор печати"""
        if self._typing_task:
            self._typing_task.cancel()
            try:
                await self._typing_task
            except asyncio.CancelledError:
                pass
            self._typing_task = None

    async def start(self):
        """Запустить бота"""
        logger.info("Starting Telegram bot...")

        try:
            await self.dp.start_polling(
                self.bot,
                allowed_updates=["message", "callback_query"]
            )
        finally:
            await self._stop_typing_indicator()
            await self.bot.session.close()

            try:
                from data_providers import cleanup_session
                await cleanup_session()
                logger.info("Session cleaned up on bot shutdown")
            except Exception as e:
                logger.debug(f"Cleanup on shutdown: {e}")


async def run_telegram_bot():
    """Главная функция для запуска бота"""
    from config import config

    bot = TradingBotTelegram(
        bot_token=config.TELEGRAM_BOT_TOKEN,
        user_id=config.TELEGRAM_USER_ID,
        group_id=config.TELEGRAM_GROUP_ID
    )

    await bot.start()