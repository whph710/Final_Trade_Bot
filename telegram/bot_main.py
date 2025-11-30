"""
Telegram Bot Main - WITH MANUAL PAIR ANALYSIS
Файл: telegram/bot_main.py

ДОБАВЛЕНО:
- Кнопка "🔍 Анализ пары" для ручного анализа
- FSM для диалога (выбор пары → выбор направления)
- Прямой вызов Stage 3 для одной пары
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from aiogram import Bot, Dispatcher, F, Router
from aiogram.types import (
    Message,
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery
)
from aiogram.filters import Command
from aiogram.enums import ChatAction
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

logger = logging.getLogger(__name__)


# ============================================================================
# FSM STATES для диалога выбора пары
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

        # FSM storage
        self.storage = MemoryStorage()
        self.dp = Dispatcher(storage=self.storage)

        # Router для callback queries
        self.router = Router()
        self.dp.include_router(self.router)

        self.user_id = user_id
        self.group_id = group_id

        self.trading_bot_running = False
        self._typing_task = None

        # Регистрация хэндлеров
        self._register_handlers()

        logger.info(
            f"Trading Bot Telegram initialized: "
            f"user_id={user_id}, group_id={group_id}"
        )

    def _register_handlers(self):
        """Регистрация обработчиков команд"""
        self.dp.message.register(self.start_command, Command(commands=["start"]))

        # Текстовые сообщения (для кнопок)
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
            self.stop_bot,
            F.text == "🛑 Остановить"
        )

        # FSM: Ввод символа
        self.dp.message.register(
            self.process_symbol_input,
            ManualAnalysisStates.waiting_for_symbol
        )

        # Callback для выбора направления
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
                [KeyboardButton(text="🔍 Анализ пары")],  # ✅ НОВАЯ КНОПКА
                [KeyboardButton(text="📊 Статус"), KeyboardButton(text="📈 Статистика")],
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
            "🛑 Остановить - остановка бота",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    # ========================================================================
    # ✅ НОВЫЙ ФУНКЦИОНАЛ: Ручной анализ пары
    # ========================================================================

    async def handle_manual_pair_analysis(self, message: Message, state: FSMContext):
        """
        Начать диалог для ручного анализа пары

        Шаг 1: Просим ввести символ
        """
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
        """
        Обработка ввода символа

        Шаг 2: Показываем кнопки выбора направления
        """
        user_id = message.from_user.id

        if user_id != self.user_id:
            return

        # Проверка на отмену
        if message.text and message.text.lower() in ['/cancel', 'отмена', 'cancel']:
            await state.clear()
            await message.answer(
                "❌ Анализ отменён",
                parse_mode="HTML"
            )
            return

        symbol = message.text.strip().upper()

        # Валидация символа
        if not symbol or len(symbol) < 3 or len(symbol) > 20:
            await message.answer(
                "⚠️ Некорректный символ. Попробуйте ещё раз (например: <code>BTCUSDT</code>)",
                parse_mode="HTML"
            )
            return

        # Проверка что заканчивается на USDT
        if not symbol.endswith('USDT'):
            await message.answer(
                "⚠️ Бот работает только с парами USDT (например: <code>BTCUSDT</code>)\n\n"
                "Попробуйте ещё раз:",
                parse_mode="HTML"
            )
            return

        # Сохраняем символ в FSM
        await state.update_data(symbol=symbol)
        await state.set_state(ManualAnalysisStates.waiting_for_direction)

        # Показываем кнопки выбора направления
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
        """
        Обработка выбора направления

        Шаг 3: Запускаем Stage 3 для выбранной пары
        """
        user_id = callback.from_user.id

        if user_id != self.user_id:
            await callback.answer("❌ Доступ запрещён", show_alert=True)
            return

        # Получаем данные из FSM
        data = await state.get_data()
        symbol = data.get('symbol', 'UNKNOWN')

        # Парсим callback data
        action = callback.data.split(':')[1]

        # Отмена
        if action == 'CANCEL':
            await state.clear()
            await callback.message.edit_text(
                "❌ Анализ отменён",
                parse_mode="HTML"
            )
            await callback.answer()
            return

        # Подтверждаем выбор
        await callback.answer(f"✅ Анализирую {symbol} {action}")

        # Удаляем inline кнопки
        await callback.message.edit_text(
            f"⏳ <b>Запуск анализа...</b>\n\n"
            f"Пара: <b>{symbol}</b>\n"
            f"Направление: <b>{action}</b>",
            parse_mode="HTML"
        )

        # Запускаем анализ
        await self._run_manual_pair_analysis(symbol, action)

        # Очищаем FSM
        await state.clear()

    async def _run_manual_pair_analysis(self, symbol: str, direction: str):
        """
        Запуск Stage 3 для конкретной пары и направления

        Args:
            symbol: Торговая пара (например 'BTCUSDT')
            direction: 'LONG' или 'SHORT'
        """
        try:
            await self._start_typing_indicator(self.user_id)

            try:
                # Импортируем функцию анализа одной пары
                from stages.stage3_analysis import analyze_single_pair
                from data_providers import cleanup_session

                logger.info(f"Manual analysis: {symbol} {direction}")

                # Запускаем анализ
                result = await analyze_single_pair(symbol, direction)

                # Cleanup
                await cleanup_session()

            finally:
                await self._stop_typing_indicator()

            # Обрабатываем результат
            if result and result.signal != 'NO_SIGNAL':
                # Отправляем сигнал в группу
                await self._send_signals_to_group([result])

                await self.bot.send_message(
                    chat_id=self.user_id,
                    text=(
                        f"✅ <b>Анализ завершён</b>\n\n"
                        f"Пара: <b>{symbol}</b>\n"
                        f"Сигнал: <b>{result.signal}</b>\n"
                        f"Confidence: <b>{result.confidence}%</b>"
                    ),
                    parse_mode="HTML"
                )
            else:
                rejection_reason = result.comprehensive_data.get(
                    'rejection_reason',
                    'Сигнал не найден'
                ) if result else 'Ошибка анализа'

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

            # Cleanup даже при ошибке
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
    # EXISTING HANDLERS (без изменений)
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

            # Результат
            if approved_signals:
                await self._send_signals_to_group(approved_signals)

                await self.bot.send_message(
                    chat_id=self.user_id,
                    text=(
                        f"✅ <b>Анализ завершён</b>\n\n"
                        f"Одобрено: {len(approved_signals)}\n"
                        f"Отклонено: {len(rejected_signals)}"
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
        """Отправить rejected signals в личку"""
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
        """Показать статистику"""
        stats_text = (
            "📈 <b>СТАТИСТИКА</b>\n\n"
            "Функция в разработке"
        )

        await self.bot.send_message(
            chat_id=self.user_id,
            text=stats_text,
            parse_mode="HTML"
        )

    async def stop_bot(self, message: Message):
        """Остановка бота"""
        await self.bot.send_message(
            chat_id=self.user_id,
            text="🛑 <b>Бот остановлен.</b> Перезапустите для возобновления",
            parse_mode="HTML"
        )

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
                allowed_updates=["message", "callback_query"]  # ✅ Добавили callback_query
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