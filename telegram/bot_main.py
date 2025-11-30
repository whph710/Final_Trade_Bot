"""
Telegram Bot Main - FIXED SESSION CLEANUP
Файл: telegram/bot_main.py

ИЗМЕНЕНИЯ:
- Добавлен cleanup_session() при завершении
- Улучшенная обработка ошибок
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional, Callable

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import Command
from aiogram.enums import ChatAction

logger = logging.getLogger(__name__)


class TradingBotTelegram:
    """Telegram бот для торговой системы"""

    def __init__(
            self,
            bot_token: str,
            user_id: int,
            group_id: int
    ):
        self.bot = Bot(token=bot_token)
        self.dp = Dispatcher()

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
        self.dp.message.register(self.handle_message, F.text & ~F.command)

    async def start_command(self, message: Message):
        """Обработка команды /start"""
        user_id = message.from_user.id

        if user_id != self.user_id:
            await message.reply("❌ Доступ запрещён")
            return

        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="▶️ Запустить сейчас")],
                [KeyboardButton(text="📊 Статус"), KeyboardButton(text="📈 Статистика")],
                [KeyboardButton(text="🛑 Остановить")]
            ],
            resize_keyboard=True
        )

        await message.answer(
            "🤖 <b>Trading Bot активирован!</b>\n\n"
            "Бот работает по расписанию или по команде.\n\n"
            "<b>Доступные команды:</b>\n"
            "▶️ Запустить сейчас - ручной запуск анализа\n"
            "📊 Статус - текущее состояние\n"
            "📈 Статистика - статистика запусков\n"
            "🛑 Остановить - остановка бота",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    async def handle_message(self, message: Message):
        """Обработка текстовых сообщений"""
        user_id = message.from_user.id

        if user_id != self.user_id:
            return

        text = message.text

        if text == "▶️ Запустить сейчас":
            await self.run_trading_bot_manual(message)
        elif text == "📊 Статус":
            await self.show_status(message)
        elif text == "📈 Статистика":
            await self.show_statistics(message)
        elif text == "🛑 Остановить":
            await self.stop_bot(message)

    async def run_trading_bot_manual(self, message: Message):
        """Ручной запуск торгового бота"""
        try:
            await self.bot.send_message(
                chat_id=self.user_id,
                text="⏳ <b>Запуск анализа...</b>",
                parse_mode="HTML"
            )

            await self._start_typing_indicator(self.user_id)

            try:
                # Импортируем здесь чтобы избежать circular imports
                from stages import run_stage1, run_stage2, run_stage3
                from data_providers import get_all_trading_pairs, cleanup_session

                # Stage 1: Filter
                logger.info("Manual run: Starting Stage 1")
                pairs = await get_all_trading_pairs()
                candidates = await run_stage1(pairs)

                if not candidates:
                    await self.bot.send_message(
                        chat_id=self.user_id,
                        text="❌ <b>Stage 1: Сигналов не найдено</b>\n\n"
                             "Проверьте настройки фильтров (MIN_CONFIDENCE, MIN_VOLUME_RATIO)",
                        parse_mode="HTML"
                    )
                    await cleanup_session()
                    return

                await self.bot.send_message(
                    chat_id=self.user_id,
                    text=f"✅ <b>Stage 1: Найдено {len(candidates)} сигналов</b>",
                    parse_mode="HTML"
                )

                # Stage 2: AI Selection
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

                # Stage 3: Comprehensive Analysis
                logger.info("Manual run: Starting Stage 3")
                approved_signals, rejected_signals = await run_stage3(selected_pairs)

                # ✅ CLEANUP SESSION
                logger.info("Manual run: Cleaning up session")
                await cleanup_session()

            finally:
                await self._stop_typing_indicator()

            # Формируем результат
            if approved_signals:
                # Форматируем и отправляем сигналы
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

            # Отправляем rejected в личку (опционально)
            if rejected_signals:
                await self._send_rejected_signals(rejected_signals)

        except Exception as e:
            await self._stop_typing_indicator()
            logger.exception("Error running trading bot manually")

            # ✅ CLEANUP даже при ошибке
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
            # Группируем по 5
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

                    # Обрезаем длинные причины
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
        from datetime import datetime

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
                allowed_updates=["message"]
            )
        finally:
            await self._stop_typing_indicator()
            await self.bot.session.close()

            # ✅ CLEANUP SESSION при завершении
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