"""
Telegram Bot Main - Multi-User Support (BACKTEST FIX)
Файл: telegram/bot_main.py

✅ ИСПРАВЛЕНО:
- Async вызов backtester.run_backtest()
"""

import asyncio
import json
import logging
import html
from datetime import datetime
from typing import Optional, List
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


class AdminPanelStates(StatesGroup):
    """Состояния для админ-панели"""
    waiting_for_group_id = State()
    waiting_for_user_id_to_add = State()
    waiting_for_user_id_to_remove = State()
    waiting_for_admin_id_to_add = State()
    waiting_for_admin_id_to_remove = State()


# ============================================================================
# TELEGRAM BOT CLASS
# ============================================================================
class TradingBotTelegram:
    """Telegram бот для торговой системы"""

    def __init__(
            self,
            bot_token: str,
            user_ids: List[int],
            group_id: int,
            admin_ids: Optional[List[int]] = None
    ):
        self.bot = Bot(token=bot_token)
        self.storage = MemoryStorage()
        self.dp = Dispatcher(storage=self.storage)
        self.router = Router()
        self.dp.include_router(self.router)

        self.user_ids = user_ids if isinstance(user_ids, list) else [user_ids]
        self.primary_user_id = self.user_ids[0] if self.user_ids else 0
        # ✅ Список администраторов
        from config import config
        self.admin_ids = admin_ids if admin_ids is not None else config.TELEGRAM_ADMIN_IDS
        if not self.admin_ids:
            self.admin_ids = [632260351]  # Fallback к основному админу
        self.group_id = group_id
        self.trading_bot_running = False
        self.bot_stopped = False  # Флаг остановки бота
        self._typing_task = None

        from utils import get_signal_storage, get_backtester
        self.signal_storage = get_signal_storage()
        self.backtester = get_backtester()

        from config import config
        self.stats_file = config.LOGS_DIR / 'bot_statistics.json'

        # ✅ Инициализация scheduler
        from telegram.scheduler import ScheduleManager
        self.scheduler = ScheduleManager()

        self._register_handlers()

        logger.info(
            f"Trading Bot Telegram initialized: "
            f"user_ids={self.user_ids}, group_id={group_id}"
        )

    def _is_authorized(self, user_id: int) -> bool:
        """Проверка что пользователь имеет доступ"""
        return user_id in self.user_ids

    def _is_admin(self, user_id: int) -> bool:
        """Проверка что пользователь - админ"""
        return user_id in self.admin_ids

    def _register_handlers(self):
        """Регистрация обработчиков команд"""
        self.dp.message.register(self.start_command, Command(commands=["start"]))

        # Главное меню
        self.dp.message.register(
            self.handle_crypto_market_menu,
            F.text == "🪙 Crypto market"
        )
        self.dp.message.register(
            self.handle_stock_market_menu,
            F.text == "📈 Stock market"
        )
        self.dp.message.register(
            self.handle_info_menu,
            F.text == "ℹ️ Инфо"
        )
        self.dp.message.register(
            self.stop_bot,
            F.text == "🛑 Остановить"
        )

        # Crypto market подменю
        self.dp.message.register(
            self.handle_run_analysis,
            F.text == "▶️ Запустить сейчас"
        )
        self.dp.message.register(
            self.handle_manual_pair_analysis,
            F.text == "🔍 Проверка пары"
        )

        # Info подменю
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

        # Stock market подменю
        self.dp.message.register(
            self.handle_stock_run_analysis,
            F.text == "▶️ Запустить сейчас (Stock)"
        )
        self.dp.message.register(
            self.handle_stock_check_asset,
            F.text == "🔍 Проверить актив"
        )
        
        # Stock market FSM handlers - обрабатываются в process_symbol_input

        # ✅ АДМИН-ПАНЕЛЬ: Команды только для админа
        self.dp.message.register(
            self.handle_admin_panel,
            F.text == "⚙️ Админ-панель"
        )
        self.dp.message.register(
            self.handle_set_group,
            F.text == "📝 Изменить группу"
        )
        self.dp.message.register(
            self.handle_add_member,
            F.text == "➕ Добавить пользователя"
        )
        self.dp.message.register(
            self.handle_remove_member,
            F.text == "➖ Удалить пользователя"
        )
        self.dp.message.register(
            self.handle_add_admin,
            F.text == "👑 Добавить админа"
        )
        self.dp.message.register(
            self.handle_remove_admin,
            F.text == "🔻 Удалить админа"
        )
        self.dp.message.register(
            self.handle_back_to_main,
            F.text == "🔙 Назад"
        )
        self.dp.message.register(
            self.handle_list_users,
            F.text == "📋 Список пользователей"
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
        
        # ✅ АДМИН FSM handlers
        self.dp.message.register(
            self.process_group_id_input,
            AdminPanelStates.waiting_for_group_id
        )
        self.dp.message.register(
            self.process_add_member_input,
            AdminPanelStates.waiting_for_user_id_to_add
        )
        self.dp.message.register(
            self.process_remove_member_input,
            AdminPanelStates.waiting_for_user_id_to_remove
        )
        self.dp.message.register(
            self.process_add_admin_input,
            AdminPanelStates.waiting_for_admin_id_to_add
        )
        self.dp.message.register(
            self.process_remove_admin_input,
            AdminPanelStates.waiting_for_admin_id_to_remove
        )

    async def start_command(self, message: Message):
        """Обработка команды /start"""
        user_id = message.from_user.id

        if not self._is_authorized(user_id):
            await message.reply("❌ Доступ запрещён")
            return

        # Если бот был остановлен, возобновляем работу
        if self.bot_stopped:
            self.bot_stopped = False
            # Перезапускаем scheduler
            from telegram.scheduler import ScheduleManager
            self.scheduler = ScheduleManager()
            self.scheduler.setup_schedule(self, self._run_scheduled_analysis)
            logger.info("Bot resumed - scheduler restarted")

        await self._show_main_menu(message)

    def _get_main_menu_keyboard(self, user_id: int) -> ReplyKeyboardMarkup:
        """Получить клавиатуру главного меню"""
        keyboard_buttons = [
            [KeyboardButton(text="🪙 Crypto market")],
            [KeyboardButton(text="📈 Stock market")],
            [KeyboardButton(text="ℹ️ Инфо")],
            [KeyboardButton(text="🛑 Остановить")]
        ]
        
        # Добавляем админ-панель только для админа
        if self._is_admin(user_id):
            keyboard_buttons.append([KeyboardButton(text="⚙️ Админ-панель")])
        
        return ReplyKeyboardMarkup(
            keyboard=keyboard_buttons,
            resize_keyboard=True
        )

    async def _show_main_menu(self, message: Message):
        """Показать главное меню"""
        user_id = message.from_user.id
        keyboard = self._get_main_menu_keyboard(user_id)

        await message.answer(
            "🤖 <b>Trading Bot активирован!</b>\n\n"
            "Бот работает по расписанию или по команде.\n\n"
            "<b>Доступные разделы:</b>\n"
            "🪙 Crypto market - анализ криптовалютного рынка\n"
            "📈 Stock market - анализ фондового рынка (в разработке)\n"
            "ℹ️ Инфо - статус, статистика, backtest\n"
            "🛑 Остановить - остановка бота",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    # ========================================================================
    # НАВИГАЦИЯ ПО МЕНЮ
    # ========================================================================

    async def handle_crypto_market_menu(self, message: Message):
        """Показать меню Crypto market"""
        user_id = message.from_user.id

        if not self._is_authorized(user_id):
            return

        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="▶️ Запустить сейчас")],
                [KeyboardButton(text="🔍 Проверка пары")],
                [KeyboardButton(text="🔙 Назад")]
            ],
            resize_keyboard=True
        )

        await message.answer(
            "🪙 <b>CRYPTO MARKET</b>\n\n"
            "<b>Доступные действия:</b>\n"
            "▶️ Запустить сейчас - полный цикл анализа криптовалютного рынка\n"
            "🔍 Проверка пары - анализ конкретной криптопары (LONG/SHORT)",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    async def handle_stock_market_menu(self, message: Message):
        """Показать меню Stock market (заглушка)"""
        user_id = message.from_user.id

        if not self._is_authorized(user_id):
            return

        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="▶️ Запустить сейчас (Stock)")],
                [KeyboardButton(text="🔍 Проверить актив")],
                [KeyboardButton(text="🔙 Назад")]
            ],
            resize_keyboard=True
        )

        await message.answer(
            "📈 <b>STOCK MARKET</b>\n\n"
            "⚠️ <i>Функционал в разработке</i>\n\n"
            "<b>Доступные действия:</b>\n"
            "▶️ Запустить сейчас - полный цикл анализа фондового рынка\n"
            "🔍 Проверить актив - анализ конкретного актива",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    async def handle_info_menu(self, message: Message):
        """Показать меню Инфо"""
        user_id = message.from_user.id

        if not self._is_authorized(user_id):
            return

        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📊 Статус")],
                [KeyboardButton(text="📈 Статистика")],
                [KeyboardButton(text="📊 Backtest")],
                [KeyboardButton(text="🔙 Назад")]
            ],
            resize_keyboard=True
        )

        await message.answer(
            "ℹ️ <b>ИНФОРМАЦИЯ</b>\n\n"
            "<b>Доступные действия:</b>\n"
            "📊 Статус - текущее состояние бота\n"
            "📈 Статистика - статистика запусков\n"
            "📊 Backtest - backtest сохранённых сигналов",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    async def handle_stock_run_analysis(self, message: Message):
        """Обработчик запуска анализа фондового рынка"""
        if not self._is_authorized(message.from_user.id):
            return

        # Проверяем, не остановлен ли бот
        if self.bot_stopped:
            keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="▶️ Запустить сейчас (Stock)")],
                    [KeyboardButton(text="🔍 Проверить актив")],
                    [KeyboardButton(text="🔙 Назад")]
                ],
                resize_keyboard=True
            )
            await message.answer(
                "⚠️ <b>Бот остановлен</b>\n\n"
                "Используйте команду /start для возобновления работы",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            return

        await self.run_stock_analysis_manual(message)

    async def handle_stock_check_asset(self, message: Message, state: FSMContext):
        """Начать диалог для проверки актива фондового рынка"""
        user_id = message.from_user.id

        if not self._is_authorized(user_id):
            return

        # Проверяем, не остановлен ли бот
        if self.bot_stopped:
            keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="▶️ Запустить сейчас (Stock)")],
                    [KeyboardButton(text="🔍 Проверить актив")],
                    [KeyboardButton(text="🔙 Назад")]
                ],
                resize_keyboard=True
            )
            await message.answer(
                "⚠️ <b>Бот остановлен</b>\n\n"
                "Используйте команду /start для возобновления работы",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            return

        await state.set_state(ManualAnalysisStates.waiting_for_symbol)

        await message.answer(
            "🔍 <b>Проверка актива фондового рынка</b>\n\n"
            "Отправьте тикер акции (например: SBER, GAZP, YNDX, AAPL, TSLA)\n\n"
            "💡 <i>Поддерживаются российские и зарубежные акции</i>",
            parse_mode="HTML"
        )

    # ========================================================================
    # РУЧНОЙ АНАЛИЗ ПАРЫ
    # ========================================================================

    async def handle_manual_pair_analysis(self, message: Message, state: FSMContext):
        """Начать диалог для ручного анализа пары"""
        user_id = message.from_user.id

        if not self._is_authorized(user_id):
            return

        # Проверяем, не остановлен ли бот
        if self.bot_stopped:
            keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="▶️ Запустить сейчас")],
                    [KeyboardButton(text="🔍 Проверка пары")],
                    [KeyboardButton(text="🔙 Назад")]
                ],
                resize_keyboard=True
            )
            await message.answer(
                "⚠️ <b>Бот остановлен</b>\n\n"
                "Используйте команду /start для возобновления работы",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
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

        if not self._is_authorized(user_id):
            return

        if message.text and message.text.lower() in ['/cancel', 'отмена', 'cancel']:
            await state.clear()
            await message.answer("❌ Анализ отменён", parse_mode="HTML")
            return

        symbol = message.text.strip().upper()

        if not symbol or len(symbol) < 2 or len(symbol) > 20:
            await message.answer(
                "⚠️ Некорректный символ. Попробуйте ещё раз (например: <code>BTCUSDT</code> или <code>SBER</code>)",
                parse_mode="HTML"
            )
            return

        # Определяем тип актива
        is_stock = not symbol.endswith('USDT') and not symbol.endswith('USD') and not symbol.endswith('BUSD') and not symbol.endswith('USDC')
        
        if is_stock:
            # Это акция - используем логику для акций
            await state.update_data(symbol=symbol, asset_type='stock')
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
                f"✅ Акция: <b>{symbol}</b>\n\n"
                f"Выберите направление анализа:",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            return
        
        # Это криптовалюта
        if not symbol.endswith('USDT'):
            await message.answer(
                "⚠️ Бот работает только с парами USDT (например: <code>BTCUSDT</code>)\n\n"
                "Попробуйте ещё раз:",
                parse_mode="HTML"
            )
            return
        
        await state.update_data(symbol=symbol, asset_type='crypto')

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

        if not self._is_authorized(user_id):
            await callback.answer("❌ Доступ запрещён", show_alert=True)
            return

        data = await state.get_data()
        symbol = data.get('symbol', 'UNKNOWN')
        asset_type = data.get('asset_type', 'crypto')

        action = callback.data.split(':')[1]

        if action == 'CANCEL':
            await state.clear()
            await callback.message.edit_text("❌ Анализ отменён", parse_mode="HTML")
            await callback.answer()
            return

        await callback.answer(f"✅ Анализирую {symbol} {action}")

        asset_name = "Акция" if asset_type == 'stock' else "Пара"
        await callback.message.edit_text(
            f"⏳ <b>Запуск анализа...</b>\n\n"
            f"{asset_name}: <b>{symbol}</b>\n"
            f"Направление: <b>{action}</b>",
            parse_mode="HTML"
        )

        await self._run_manual_pair_analysis(symbol, action, user_id, asset_type)
        await state.clear()

    async def _run_manual_pair_analysis(self, symbol: str, direction: str, user_id: int, asset_type: str = 'crypto'):
        """Запуск Stage 3 для конкретной пары/акции и направления"""
        try:
            await self._start_typing_indicator(user_id)

            try:
                from stages.stage3_analysis import analyze_single_pair
                from data_providers import cleanup_session

                logger.info(f"Manual analysis: {symbol} {direction} (type: {asset_type})")

                result = await analyze_single_pair(symbol, direction, asset_type=asset_type)

                await cleanup_session()

            finally:
                await self._stop_typing_indicator()

            # Клавиатура для возврата в меню Crypto market
            crypto_keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="▶️ Запустить сейчас")],
                    [KeyboardButton(text="🔍 Проверка пары")],
                    [KeyboardButton(text="🔙 Назад")]
                ],
                resize_keyboard=True
            )

            if result and result.signal != 'NO_SIGNAL':
                self.signal_storage.save_signal(result)
                await self._send_signals_to_group([result])

                await self.bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"✅ <b>Анализ завершён</b>\n\n"
                        f"Пара: <b>{symbol}</b>\n"
                        f"Сигнал: <b>{result.signal}</b>\n"
                        f"Confidence: <b>{result.confidence}%</b>\n\n"
                        f"💾 Сигнал сохранён в signals/"
                    ),
                    reply_markup=crypto_keyboard,
                    parse_mode="HTML"
                )
            else:
                rejection_reason = result.comprehensive_data.get(
                    'rejection_reason',
                    'Сигнал не найден'
                ) if result else 'Ошибка анализа'

                rejection_reason = self._escape_html(rejection_reason)

                await self.bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"⚠️ <b>Сигнал не найден</b>\n\n"
                        f"Пара: <b>{symbol}</b>\n"
                        f"Причина: {rejection_reason}"
                    ),
                    reply_markup=crypto_keyboard,
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

            # Клавиатура для возврата в меню Crypto market
            crypto_keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="▶️ Запустить сейчас")],
                    [KeyboardButton(text="🔍 Проверка пары")],
                    [KeyboardButton(text="🔙 Назад")]
                ],
                resize_keyboard=True
            )

            await self.bot.send_message(
                chat_id=user_id,
                text=f"❌ <b>Ошибка анализа:</b> {str(e)[:200]}",
                reply_markup=crypto_keyboard,
                parse_mode="HTML"
            )

    # ========================================================================
    # ПОЛНЫЙ ЦИКЛ АНАЛИЗА
    # ========================================================================

    async def handle_run_analysis(self, message: Message):
        """Обработчик кнопки '▶️ Запустить сейчас'"""
        if not self._is_authorized(message.from_user.id):
            return

        # Проверяем, не остановлен ли бот
        if self.bot_stopped:
            keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="▶️ Запустить сейчас")],
                    [KeyboardButton(text="🔍 Проверка пары")],
                    [KeyboardButton(text="🔙 Назад")]
                ],
                resize_keyboard=True
            )
            await message.answer(
                "⚠️ <b>Бот остановлен</b>\n\n"
                "Используйте команду /start для возобновления работы",
                reply_markup=keyboard,
                parse_mode="HTML"
            )
            return

        await self.run_trading_bot_manual(message)

    async def run_trading_bot_manual(self, message: Message):
        """Ручной запуск торгового бота (полный цикл)"""
        user_id = message.from_user.id

        try:
            await self.bot.send_message(
                chat_id=user_id,
                text="⏳ <b>Запуск анализа...</b>",
                parse_mode="HTML"
            )

            await self._start_typing_indicator(user_id)

            try:
                from stages import run_stage1, run_stage2, run_stage3
                from data_providers import get_all_trading_pairs, cleanup_session

                logger.info("Manual run: Starting Stage 1")
                pairs = await get_all_trading_pairs()
                candidates = await run_stage1(pairs)

                if not candidates:
                    await self.bot.send_message(
                        chat_id=user_id,
                        text="❌ <b>Stage 1: Сигналов не найдено</b>",
                        parse_mode="HTML"
                    )
                    await cleanup_session()
                    return

                await self.bot.send_message(
                    chat_id=user_id,
                    text=f"✅ <b>Stage 1: Найдено {len(candidates)} сигналов</b>",
                    parse_mode="HTML"
                )

                logger.info("Manual run: Starting Stage 2")
                selected_pairs = await run_stage2(candidates)

                if not selected_pairs:
                    await self.bot.send_message(
                        chat_id=user_id,
                        text="❌ <b>Stage 2: AI не выбрал пары</b>",
                        parse_mode="HTML"
                    )
                    await cleanup_session()
                    return

                await self.bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"✅ <b>Stage 2: AI выбрал {len(selected_pairs)} пар</b>\n\n"
                        f"{'  •  '.join(selected_pairs)}"
                    ),
                    parse_mode="HTML"
                )

                logger.info("Manual run: Starting Stage 3")
                approved_signals, rejected_signals = await run_stage3(selected_pairs)

                await cleanup_session()

            finally:
                await self._stop_typing_indicator()

            # Клавиатура для возврата в меню Crypto market
            crypto_keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="▶️ Запустить сейчас")],
                    [KeyboardButton(text="🔍 Проверка пары")],
                    [KeyboardButton(text="🔙 Назад")]
                ],
                resize_keyboard=True
            )

            if approved_signals:
                saved = self.signal_storage.save_signals_batch(approved_signals)
                logger.info(f"Saved {saved} signals to storage")

            if approved_signals:
                await self._send_signals_to_group(approved_signals)

                await self.bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"✅ <b>Анализ завершён</b>\n\n"
                        f"Одобрено: {len(approved_signals)}\n"
                        f"Отклонено: {len(rejected_signals)}\n\n"
                        f"💾 Сигналы сохранены в signals/"
                    ),
                    reply_markup=crypto_keyboard,
                    parse_mode="HTML"
                )
            else:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"⚠️ <b>Сигналов не найдено</b>\n\n"
                        f"Отклонено: {len(rejected_signals)}"
                    ),
                    reply_markup=crypto_keyboard,
                    parse_mode="HTML"
                )

            if rejected_signals:
                await self._send_rejected_signals(rejected_signals, user_id)

            self._update_statistics(len(approved_signals), len(rejected_signals))

        except Exception as e:
            await self._stop_typing_indicator()
            logger.exception("Error running trading bot manually")

            try:
                from data_providers import cleanup_session
                await cleanup_session()
            except:
                pass

            # Клавиатура для возврата в меню Crypto market
            crypto_keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="▶️ Запустить сейчас")],
                    [KeyboardButton(text="🔍 Проверка пары")],
                    [KeyboardButton(text="🔙 Назад")]
                ],
                resize_keyboard=True
            )

            await self.bot.send_message(
                chat_id=user_id,
                text=f"❌ <b>Ошибка:</b> {str(e)[:200]}",
                reply_markup=crypto_keyboard,
                parse_mode="HTML"
            )

    async def run_stock_analysis_manual(self, message: Message):
        """Ручной запуск анализа фондового рынка (полный цикл)"""
        user_id = message.from_user.id

        try:
            await self.bot.send_message(
                chat_id=user_id,
                text="⏳ <b>Запуск анализа фондового рынка...</b>",
                parse_mode="HTML"
            )

            await self._start_typing_indicator(user_id)

            try:
                from stages import run_stage1, run_stage2, run_stage3
                from data_providers import get_all_stocks, cleanup_session

                logger.info("Stock analysis: Starting Stage 1")
                stocks = await get_all_stocks()
                
                if not stocks:
                    await self.bot.send_message(
                        chat_id=user_id,
                        text="❌ <b>Не удалось загрузить список акций</b>\n\n"
                             "Проверьте настройку TINKOFF_INVEST_TOKEN в .env",
                        parse_mode="HTML"
                    )
                    await cleanup_session()
                    return

                # Ограничиваем количество акций для анализа (топ-100 по ликвидности)
                stocks = stocks[:100]
                
                candidates = await run_stage1(stocks)

                if not candidates:
                    await self.bot.send_message(
                        chat_id=user_id,
                        text="❌ <b>Stage 1: Сигналов не найдено</b>",
                        parse_mode="HTML"
                    )
                    await cleanup_session()
                    return

                await self.bot.send_message(
                    chat_id=user_id,
                    text=f"✅ <b>Stage 1: Найдено {len(candidates)} сигналов</b>",
                    parse_mode="HTML"
                )

                logger.info("Stock analysis: Starting Stage 2")
                selected_stocks = await run_stage2(candidates)

                if not selected_stocks:
                    await self.bot.send_message(
                        chat_id=user_id,
                        text="❌ <b>Stage 2: AI не выбрал акции</b>",
                        parse_mode="HTML"
                    )
                    await cleanup_session()
                    return

                await self.bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"✅ <b>Stage 2: AI выбрал {len(selected_stocks)} акций</b>\n\n"
                        f"{'  •  '.join(selected_stocks)}"
                    ),
                    parse_mode="HTML"
                )

                logger.info("Stock analysis: Starting Stage 3")
                approved_signals, rejected_signals = await run_stage3(selected_stocks)

                await cleanup_session()

            finally:
                await self._stop_typing_indicator()

            # Клавиатура для возврата в меню Stock market
            stock_keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="▶️ Запустить сейчас (Stock)")],
                    [KeyboardButton(text="🔍 Проверить актив")],
                    [KeyboardButton(text="🔙 Назад")]
                ],
                resize_keyboard=True
            )

            if approved_signals:
                saved = self.signal_storage.save_signals_batch(approved_signals)
                logger.info(f"Saved {saved} stock signals to storage")

            if approved_signals:
                await self._send_signals_to_group(approved_signals)

                await self.bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"✅ <b>Анализ завершён</b>\n\n"
                        f"Одобрено: {len(approved_signals)}\n"
                        f"Отклонено: {len(rejected_signals)}\n\n"
                        f"💾 Сигналы сохранены в signals/"
                    ),
                    reply_markup=stock_keyboard,
                    parse_mode="HTML"
                )
            else:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=(
                        f"⚠️ <b>Сигналов не найдено</b>\n\n"
                        f"Отклонено: {len(rejected_signals)}"
                    ),
                    reply_markup=stock_keyboard,
                    parse_mode="HTML"
                )

            if rejected_signals:
                await self._send_rejected_signals(rejected_signals, user_id)

            self._update_statistics(len(approved_signals), len(rejected_signals))

        except Exception as e:
            await self._stop_typing_indicator()
            logger.exception("Error running stock analysis manually")

            try:
                from data_providers import cleanup_session
                await cleanup_session()
            except:
                pass

            # Клавиатура для возврата в меню Stock market
            stock_keyboard = ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="▶️ Запустить сейчас (Stock)")],
                    [KeyboardButton(text="🔍 Проверить актив")],
                    [KeyboardButton(text="🔙 Назад")]
                ],
                resize_keyboard=True
            )

            await self.bot.send_message(
                chat_id=user_id,
                text=f"❌ <b>Ошибка:</b> {str(e)[:200]}",
                reply_markup=stock_keyboard,
                parse_mode="HTML"
            )

    # ========================================================================
    # BACKTESTING (✅ FIXED)
    # ========================================================================

    async def handle_backtest(self, message: Message):
        """Запуск backtesting"""
        user_id = message.from_user.id

        if not self._is_authorized(user_id):
            return

        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📊 Статус")],
                [KeyboardButton(text="📈 Статистика")],
                [KeyboardButton(text="📊 Backtest")],
                [KeyboardButton(text="🔙 Назад")]
            ],
            resize_keyboard=True
        )

        try:
            await message.answer("⏳ <b>Запуск backtest...</b>", parse_mode="HTML")

            signals = self.signal_storage.load_signals()

            if not signals:
                await message.answer(
                    "⚠️ <b>Нет сохранённых сигналов</b>\n\n"
                    "Запустите анализ чтобы создать сигналы для backtest",
                    reply_markup=keyboard,
                    parse_mode="HTML"
                )
                return

            await message.answer(
                f"📊 Найдено <b>{len(signals)}</b> сигналов для backtest...",
                parse_mode="HTML"
            )

            # ✅ ИСПРАВЛЕНО: Async вызов
            result = await self.backtester.run_backtest(signals)

            from utils import format_backtest_report
            report = format_backtest_report(result)

            await message.answer(report, reply_markup=keyboard, parse_mode="HTML")

            await message.answer(
                f"💾 Результаты сохранены в signals/backtest_results/",
                reply_markup=keyboard,
                parse_mode="HTML"
            )

        except Exception as e:
            logger.exception("Backtest error")
            await message.answer(
                f"❌ <b>Ошибка backtest:</b> {str(e)[:200]}",
                reply_markup=keyboard,
                parse_mode="HTML"
            )

    # ========================================================================
    # СТАТИСТИКА И СТАТУС
    # ========================================================================

    async def show_status(self, message: Message):
        """Показать статус бота"""
        if not self._is_authorized(message.from_user.id):
            return

        bot_status = "🛑 Остановлен" if self.bot_stopped else "✅ Активен"
        scheduler_status = "⏸️ Остановлен" if self.bot_stopped else "▶️ Работает"
        trading_status = "⏳ Выполняется" if self.trading_bot_running else "💤 Ожидание"

        status_text = (
            "📊 <b>Статус бота:</b>\n\n"
            f"⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"👤 Пользователей: {len(self.user_ids)}\n"
            f"👥 Group ID: {self.group_id}\n"
            f"🤖 Бот: {bot_status}\n"
            f"📅 Планировщик: {scheduler_status}\n"
            f"🔄 Анализ: {trading_status}\n"
        )

        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📊 Статус")],
                [KeyboardButton(text="📈 Статистика")],
                [KeyboardButton(text="📊 Backtest")],
                [KeyboardButton(text="🔙 Назад")]
            ],
            resize_keyboard=True
        )

        await self.bot.send_message(
            chat_id=message.from_user.id,
            text=status_text,
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    async def show_statistics(self, message: Message):
        """Показать статистику"""
        if not self._is_authorized(message.from_user.id):
            return

        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📊 Статус")],
                [KeyboardButton(text="📈 Статистика")],
                [KeyboardButton(text="📊 Backtest")],
                [KeyboardButton(text="🔙 Назад")]
            ],
            resize_keyboard=True
        )

        try:
            if not self.stats_file.exists():
                await message.answer(
                    "⚠️ <b>Статистика недоступна</b>\n\n"
                    "Запустите анализ чтобы создать статистику",
                    reply_markup=keyboard,
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

            await message.answer("\n".join(stats_text), reply_markup=keyboard, parse_mode="HTML")

        except Exception as e:
            logger.exception("Error loading statistics")
            await message.answer(
                "❌ <b>Ошибка загрузки статистики</b>",
                reply_markup=keyboard,
                parse_mode="HTML"
            )

    def _update_statistics(self, approved: int, rejected: int):
        """Обновить статистику"""
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
        if not self._is_authorized(message.from_user.id):
            return

        # Останавливаем scheduler
        if self.scheduler:
            self.scheduler.stop()
            logger.info("Scheduler stopped by user")

        # Устанавливаем флаг остановки
        self.bot_stopped = True

        keyboard = self._get_main_menu_keyboard(message.from_user.id)

        await self.bot.send_message(
            chat_id=message.from_user.id,
            text=(
                "🛑 <b>Бот остановлен</b>\n\n"
                "✅ Автоматические запуски отключены\n"
                "⚠️ Текущий анализ (если запущен) будет завершён\n\n"
                "💡 Для возобновления работы используйте команду /start"
            ),
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    # ========================================================================
    # HELPER FUNCTIONS
    # ========================================================================

    def _escape_html(self, text: str) -> str:
        """Экранировать HTML символы"""
        if not text:
            return ""
        return html.escape(str(text), quote=False)

    async def _notify_all_users(self, text: str):
        """Отправить уведомление всем разрешенным пользователям"""
        for user_id in self.user_ids:
            try:
                await self.bot.send_message(
                    chat_id=user_id,
                    text=text,
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.warning(f"Failed to notify user {user_id}: {e}")

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

    async def _send_approved_signals(self, approved_signals: list, user_id: int):
        """Отправить одобренные сигналы конкретному пользователю"""
        from telegram.formatters import format_signal_for_telegram

        if not approved_signals:
            return

        try:
            for signal in approved_signals:
                formatted_text = format_signal_for_telegram(signal)

                await self.bot.send_message(
                    chat_id=user_id,
                    text=formatted_text,
                    parse_mode="HTML"
                )

                await asyncio.sleep(0.5)

            logger.info(f"Sent {len(approved_signals)} approved signals to user {user_id}")

        except Exception as e:
            logger.error(f"Error sending approved signals to user {user_id}: {e}")

    async def _send_rejected_signals(self, rejected_signals: list, user_id: int):
        """Отправить rejected signals конкретному пользователю"""
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

                    reason = self._escape_html(reason)

                    # ✅ УБРАНО: Обрезка текста - теперь показываем полное объяснение
                    # if len(reason) > 200:
                    #     reason = reason[:197] + "..."

                    message_parts.append(f"\n<b>{symbol}</b>")
                    message_parts.append(f"<i>{reason}</i>\n")

                full_message = "\n".join(message_parts)

                await self.bot.send_message(
                    chat_id=user_id,
                    text=full_message,
                    parse_mode="HTML"
                )

                await asyncio.sleep(0.5)

            logger.info(f"Sent {len(rejected_signals)} rejected signals to user {user_id}")

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

    # ========================================================================
    # АДМИН-ПАНЕЛЬ
    # ========================================================================

    async def handle_admin_panel(self, message: Message):
        """Показать админ-панель"""
        user_id = message.from_user.id

        if not self._is_admin(user_id):
            await message.reply("❌ Доступ запрещён. Только для администратора.")
            return

        keyboard = ReplyKeyboardMarkup(
            keyboard=[
                [KeyboardButton(text="📝 Изменить группу")],
                [
                    KeyboardButton(text="➕ Добавить пользователя"),
                    KeyboardButton(text="➖ Удалить пользователя")
                ],
                [
                    KeyboardButton(text="👑 Добавить админа"),
                    KeyboardButton(text="🔻 Удалить админа")
                ],
                [KeyboardButton(text="📋 Список пользователей")],
                [KeyboardButton(text="🔙 Назад")]
            ],
            resize_keyboard=True
        )

        # Получаем информацию о группе
        group_info = "❌ Группа не настроена"
        try:
            chat = await self.bot.get_chat(self.group_id)
            group_info = f"📊 <b>Текущая группа (для сигналов):</b>\n" \
                        f"  • ID: <code>{self.group_id}</code>\n" \
                        f"  • Название: {chat.title}\n" \
                        f"  • Тип: {chat.type}"
        except Exception as e:
            logger.debug(f"Error getting group info: {e}")

        # Информация о пользователях и админах
        users_count = len(self.user_ids)
        admins_count = len(self.admin_ids)
        users_list = ", ".join([str(uid) for uid in self.user_ids[:5]])
        if len(self.user_ids) > 5:
            users_list += f" ... (+{len(self.user_ids) - 5})"
        admins_list = ", ".join([str(uid) for uid in self.admin_ids[:5]])
        if len(self.admin_ids) > 5:
            admins_list += f" ... (+{len(self.admin_ids) - 5})"

        await message.answer(
            f"⚙️ <b>АДМИН-ПАНЕЛЬ</b>\n\n"
            f"{group_info}\n\n"
            f"👥 <b>Пользователи бота:</b> {users_count}\n"
            f"   <code>{users_list}</code>\n\n"
            f"👑 <b>Администраторы:</b> {admins_count}\n"
            f"   <code>{admins_list}</code>\n\n"
            f"<b>Доступные действия:</b>\n"
            f"📝 Изменить группу - изменить группу для сигналов\n"
            f"➕ Добавить пользователя - дать доступ к боту\n"
            f"➖ Удалить пользователя - убрать доступ к боту\n"
            f"👑 Добавить админа - дать права администратора\n"
            f"🔻 Удалить админа - убрать права администратора\n"
            f"📋 Список пользователей - показать всех",
            reply_markup=keyboard,
            parse_mode="HTML"
        )

    async def handle_set_group(self, message: Message, state: FSMContext):
        """Начать процесс изменения группы"""
        user_id = message.from_user.id

        if not self._is_admin(user_id):
            await message.reply("❌ Доступ запрещён")
            return

        await state.set_state(AdminPanelStates.waiting_for_group_id)
        await message.answer(
            "📝 <b>Изменение группы</b>\n\n"
            "Отправьте ID новой группы (число, например: -1001234567890)\n\n"
            "💡 <i>Как получить ID группы:\n"
            "1. Добавьте бота @userinfobot в группу\n"
            "2. Он покажет ID группы</i>",
            parse_mode="HTML"
        )

    async def process_group_id_input(self, message: Message, state: FSMContext):
        """Обработать ввод ID группы"""
        user_id = message.from_user.id

        if not self._is_admin(user_id):
            await state.clear()
            return

        try:
            new_group_id = int(message.text.strip())
            
            # Проверяем, что это валидная группа
            try:
                chat = await self.bot.get_chat(new_group_id)
                if chat.type not in ['group', 'supergroup']:
                    await message.answer("❌ Это не группа! Отправьте ID группы или супергруппы.")
                    return
            except Exception as e:
                await message.answer(f"❌ Ошибка: не удалось получить информацию о группе. {e}")
                return

            # Обновляем group_id
            old_group_id = self.group_id
            self.group_id = new_group_id

            # ✅ Сохраняем в config
            try:
                from config import config
                # Обновляем .env файл
                env_path = Path(__file__).parent.parent / '.env'
                if env_path.exists():
                    content = env_path.read_text(encoding='utf-8')
                    # Заменяем или добавляем TELEGRAM_GROUP_ID
                    if 'TELEGRAM_GROUP_ID=' in content:
                        lines = content.split('\n')
                        new_lines = []
                        for line in lines:
                            if line.startswith('TELEGRAM_GROUP_ID='):
                                new_lines.append(f'TELEGRAM_GROUP_ID={new_group_id}')
                            else:
                                new_lines.append(line)
                        env_path.write_text('\n'.join(new_lines), encoding='utf-8')
                    else:
                        env_path.write_text(content + f'\nTELEGRAM_GROUP_ID={new_group_id}', encoding='utf-8')
            except Exception as e:
                logger.error(f"Error saving group ID to .env: {e}")

            await state.clear()
            await message.answer(
                f"✅ <b>Группа успешно изменена!</b>\n\n"
                f"Старый ID: <code>{old_group_id}</code>\n"
                f"Новый ID: <code>{new_group_id}</code>\n"
                f"Название: {chat.title}",
                parse_mode="HTML"
            )

        except ValueError:
            await message.answer("❌ Неверный формат! Отправьте число (ID группы).")

    async def handle_add_member(self, message: Message, state: FSMContext):
        """Начать процесс добавления пользователя бота"""
        user_id = message.from_user.id

        if not self._is_admin(user_id):
            await message.reply("❌ Доступ запрещён")
            return

        await state.set_state(AdminPanelStates.waiting_for_user_id_to_add)
        await message.answer(
            "➕ <b>Добавление пользователя бота</b>\n\n"
            "Отправьте ID пользователя для добавления доступа к боту (число)\n\n"
            "💡 <i>Как получить ID пользователя:\n"
            "1. Попросите пользователя написать боту @userinfobot\n"
            "2. Он покажет ID пользователя</i>",
            parse_mode="HTML"
        )

    async def process_add_member_input(self, message: Message, state: FSMContext):
        """Обработать ввод ID пользователя для добавления доступа к боту"""
        user_id = message.from_user.id

        if not self._is_admin(user_id):
            await state.clear()
            return

        try:
            user_id_to_add = int(message.text.strip())
            
            # Проверяем, не добавлен ли уже
            if user_id_to_add in self.user_ids:
                await message.answer(
                    f"⚠️ Пользователь <code>{user_id_to_add}</code> уже имеет доступ к боту.",
                    parse_mode="HTML"
                )
                await state.clear()
                return
            
            # Добавляем пользователя в список
            self.user_ids.append(user_id_to_add)
            
            # ✅ Сохраняем в .env файл
            try:
                env_path = Path(__file__).parent.parent / '.env'
                if env_path.exists():
                    content = env_path.read_text(encoding='utf-8')
                    # Обновляем TELEGRAM_USER_IDS
                    user_ids_str = ','.join([str(uid) for uid in self.user_ids])
                    if 'TELEGRAM_USER_IDS=' in content:
                        lines = content.split('\n')
                        new_lines = []
                        for line in lines:
                            if line.startswith('TELEGRAM_USER_IDS='):
                                new_lines.append(f'TELEGRAM_USER_IDS={user_ids_str}')
                            else:
                                new_lines.append(line)
                        env_path.write_text('\n'.join(new_lines), encoding='utf-8')
                    else:
                        # Если нет TELEGRAM_USER_IDS, добавляем
                        env_path.write_text(content + f'\nTELEGRAM_USER_IDS={user_ids_str}', encoding='utf-8')
                    
                    logger.info(f"Added user {user_id_to_add} to bot access list")
            except Exception as e:
                logger.error(f"Error saving user ID to .env: {e}")
                await message.answer(
                    f"✅ Пользователь добавлен в память, но не сохранён в .env: {e}",
                    parse_mode="HTML"
                )
                await state.clear()
                return
                
            await state.clear()
            await message.answer(
                f"✅ <b>Пользователь добавлен!</b>\n\n"
                f"ID пользователя: <code>{user_id_to_add}</code>\n"
                f"Теперь у него есть доступ к боту.\n\n"
                f"Всего пользователей: {len(self.user_ids)}",
                parse_mode="HTML"
            )

        except ValueError:
            await message.answer("❌ Неверный формат! Отправьте число (ID пользователя).")

    async def handle_remove_member(self, message: Message, state: FSMContext):
        """Начать процесс удаления пользователя бота"""
        user_id = message.from_user.id

        if not self._is_admin(user_id):
            await message.reply("❌ Доступ запрещён")
            return

        await state.set_state(AdminPanelStates.waiting_for_user_id_to_remove)
        await message.answer(
            "➖ <b>Удаление пользователя бота</b>\n\n"
            "Отправьте ID пользователя для удаления доступа к боту (число)\n\n"
            f"💡 <i>Текущие пользователи: {len(self.user_ids)}</i>",
            parse_mode="HTML"
        )

    async def process_remove_member_input(self, message: Message, state: FSMContext):
        """Обработать ввод ID пользователя для удаления доступа к боту"""
        user_id = message.from_user.id

        if not self._is_admin(user_id):
            await state.clear()
            return

        try:
            user_id_to_remove = int(message.text.strip())
            
            # Проверяем, есть ли пользователь в списке
            if user_id_to_remove not in self.user_ids:
                await message.answer(
                    f"⚠️ Пользователь <code>{user_id_to_remove}</code> не имеет доступа к боту.",
                    parse_mode="HTML"
                )
                await state.clear()
                return
            
            # Нельзя удалить последнего пользователя
            if len(self.user_ids) <= 1:
                await message.answer(
                    "❌ Нельзя удалить последнего пользователя! Должен быть хотя бы один пользователь.",
                    parse_mode="HTML"
                )
                await state.clear()
                return
            
            # Удаляем пользователя из списка
            self.user_ids.remove(user_id_to_remove)
            
            # ✅ Сохраняем в .env файл
            try:
                env_path = Path(__file__).parent.parent / '.env'
                if env_path.exists():
                    content = env_path.read_text(encoding='utf-8')
                    # Обновляем TELEGRAM_USER_IDS
                    user_ids_str = ','.join([str(uid) for uid in self.user_ids])
                    if 'TELEGRAM_USER_IDS=' in content:
                        lines = content.split('\n')
                        new_lines = []
                        for line in lines:
                            if line.startswith('TELEGRAM_USER_IDS='):
                                new_lines.append(f'TELEGRAM_USER_IDS={user_ids_str}')
                            else:
                                new_lines.append(line)
                        env_path.write_text('\n'.join(new_lines), encoding='utf-8')
                    
                    logger.info(f"Removed user {user_id_to_remove} from bot access list")
            except Exception as e:
                logger.error(f"Error saving user ID to .env: {e}")
                await message.answer(
                    f"✅ Пользователь удалён из памяти, но изменения не сохранены в .env: {e}",
                    parse_mode="HTML"
                )
                await state.clear()
                return
                
            await state.clear()
            await message.answer(
                f"✅ <b>Пользователь удалён!</b>\n\n"
                f"ID пользователя: <code>{user_id_to_remove}</code>\n"
                f"Доступ к боту отозван.\n\n"
                f"Осталось пользователей: {len(self.user_ids)}",
                parse_mode="HTML"
            )

        except ValueError:
            await message.answer("❌ Неверный формат! Отправьте число (ID пользователя).")

    async def handle_add_admin(self, message: Message, state: FSMContext):
        """Начать процесс добавления администратора бота"""
        user_id = message.from_user.id

        if not self._is_admin(user_id):
            await message.reply("❌ Доступ запрещён")
            return

        await state.set_state(AdminPanelStates.waiting_for_admin_id_to_add)
        await message.answer(
            "👑 <b>Добавление администратора бота</b>\n\n"
            "Отправьте ID пользователя для добавления прав администратора (число)\n\n"
            f"💡 <i>Текущие администраторы: {len(self.admin_ids)}</i>",
            parse_mode="HTML"
        )

    async def process_add_admin_input(self, message: Message, state: FSMContext):
        """Обработать ввод ID пользователя для добавления прав администратора"""
        user_id = message.from_user.id

        if not self._is_admin(user_id):
            await state.clear()
            return

        try:
            admin_id_to_add = int(message.text.strip())
            
            # Проверяем, не добавлен ли уже
            if admin_id_to_add in self.admin_ids:
                await message.answer(
                    f"⚠️ Пользователь <code>{admin_id_to_add}</code> уже является администратором.",
                    parse_mode="HTML"
                )
                await state.clear()
                return
            
            # Добавляем администратора в список
            self.admin_ids.append(admin_id_to_add)
            
            # ✅ Сохраняем в .env файл
            try:
                env_path = Path(__file__).parent.parent / '.env'
                if env_path.exists():
                    content = env_path.read_text(encoding='utf-8')
                    # Обновляем TELEGRAM_ADMIN_IDS
                    admin_ids_str = ','.join([str(aid) for aid in self.admin_ids])
                    if 'TELEGRAM_ADMIN_IDS=' in content:
                        lines = content.split('\n')
                        new_lines = []
                        for line in lines:
                            if line.startswith('TELEGRAM_ADMIN_IDS='):
                                new_lines.append(f'TELEGRAM_ADMIN_IDS={admin_ids_str}')
                            else:
                                new_lines.append(line)
                        env_path.write_text('\n'.join(new_lines), encoding='utf-8')
                    else:
                        # Если нет TELEGRAM_ADMIN_IDS, добавляем
                        env_path.write_text(content + f'\nTELEGRAM_ADMIN_IDS={admin_ids_str}', encoding='utf-8')
                    
                    logger.info(f"Added admin {admin_id_to_add} to bot admin list")
            except Exception as e:
                logger.error(f"Error saving admin ID to .env: {e}")
                await message.answer(
                    f"✅ Администратор добавлен в память, но не сохранён в .env: {e}",
                    parse_mode="HTML"
                )
                await state.clear()
                return
                
            await state.clear()
            await message.answer(
                f"✅ <b>Администратор добавлен!</b>\n\n"
                f"ID администратора: <code>{admin_id_to_add}</code>\n"
                f"Теперь у него есть доступ к админ-панели.\n\n"
                f"Всего администраторов: {len(self.admin_ids)}",
                parse_mode="HTML"
            )

        except ValueError:
            await message.answer("❌ Неверный формат! Отправьте число (ID пользователя).")

    async def handle_remove_admin(self, message: Message, state: FSMContext):
        """Начать процесс удаления администратора бота"""
        user_id = message.from_user.id

        if not self._is_admin(user_id):
            await message.reply("❌ Доступ запрещён")
            return

        await state.set_state(AdminPanelStates.waiting_for_admin_id_to_remove)
        await message.answer(
            "🔻 <b>Удаление администратора бота</b>\n\n"
            "Отправьте ID администратора для удаления прав (число)\n\n"
            f"💡 <i>Текущие администраторы: {len(self.admin_ids)}</i>",
            parse_mode="HTML"
        )

    async def process_remove_admin_input(self, message: Message, state: FSMContext):
        """Обработать ввод ID администратора для удаления прав"""
        user_id = message.from_user.id

        if not self._is_admin(user_id):
            await state.clear()
            return

        try:
            admin_id_to_remove = int(message.text.strip())
            
            # Проверяем, есть ли администратор в списке
            if admin_id_to_remove not in self.admin_ids:
                await message.answer(
                    f"⚠️ Пользователь <code>{admin_id_to_remove}</code> не является администратором.",
                    parse_mode="HTML"
                )
                await state.clear()
                return
            
            # Нельзя удалить последнего администратора
            if len(self.admin_ids) <= 1:
                await message.answer(
                    "❌ Нельзя удалить последнего администратора! Должен быть хотя бы один администратор.",
                    parse_mode="HTML"
                )
                await state.clear()
                return
            
            # Удаляем администратора из списка
            self.admin_ids.remove(admin_id_to_remove)
            
            # ✅ Сохраняем в .env файл
            try:
                env_path = Path(__file__).parent.parent / '.env'
                if env_path.exists():
                    content = env_path.read_text(encoding='utf-8')
                    # Обновляем TELEGRAM_ADMIN_IDS
                    admin_ids_str = ','.join([str(aid) for aid in self.admin_ids])
                    if 'TELEGRAM_ADMIN_IDS=' in content:
                        lines = content.split('\n')
                        new_lines = []
                        for line in lines:
                            if line.startswith('TELEGRAM_ADMIN_IDS='):
                                new_lines.append(f'TELEGRAM_ADMIN_IDS={admin_ids_str}')
                            else:
                                new_lines.append(line)
                        env_path.write_text('\n'.join(new_lines), encoding='utf-8')
                    
                    logger.info(f"Removed admin {admin_id_to_remove} from bot admin list")
            except Exception as e:
                logger.error(f"Error saving admin ID to .env: {e}")
                await message.answer(
                    f"✅ Администратор удалён из памяти, но изменения не сохранены в .env: {e}",
                    parse_mode="HTML"
                )
                await state.clear()
                return
                
            await state.clear()
            await message.answer(
                f"✅ <b>Администратор удалён!</b>\n\n"
                f"ID администратора: <code>{admin_id_to_remove}</code>\n"
                f"Права администратора отозваны.\n\n"
                f"Осталось администраторов: {len(self.admin_ids)}",
                parse_mode="HTML"
            )

        except ValueError:
            await message.answer("❌ Неверный формат! Отправьте число (ID пользователя).")

    async def handle_list_users(self, message: Message):
        """Показать список всех пользователей и администраторов"""
        user_id = message.from_user.id

        if not self._is_admin(user_id):
            await message.reply("❌ Доступ запрещён")
            return

        # Формируем список пользователей
        users_text = "👥 <b>ПОЛЬЗОВАТЕЛИ БОТА</b> ({})\n".format(len(self.user_ids))
        for i, uid in enumerate(self.user_ids, 1):
            is_admin = "👑" if uid in self.admin_ids else ""
            users_text += f"{i}. {is_admin} <code>{uid}</code>\n"

        # Формируем список администраторов
        admins_text = "\n👑 <b>АДМИНИСТРАТОРЫ</b> ({})\n".format(len(self.admin_ids))
        for i, aid in enumerate(self.admin_ids, 1):
            admins_text += f"{i}. <code>{aid}</code>\n"

        await message.answer(
            users_text + admins_text,
            parse_mode="HTML"
        )

    async def handle_back_to_main(self, message: Message, state: FSMContext):
        """Вернуться в главное меню"""
        user_id = message.from_user.id

        if not self._is_authorized(user_id):
            return

        await state.clear()
        await self._show_main_menu(message)

    async def start(self):
        """Запустить бота"""
        logger.info("Starting Telegram bot...")
        
        # ✅ Очищаем все накопленные обновления перед запуском
        # Это предотвращает обработку старых команд, отправленных пока бот был выключен
        try:
            await self.bot.delete_webhook(drop_pending_updates=True)
            logger.info("Cleared pending updates before starting polling")
        except Exception as e:
            logger.warning(f"Error clearing pending updates: {e}")

        # ✅ Запускаем scheduler
        self.scheduler.setup_schedule(self, self._run_scheduled_analysis)
        logger.info("Scheduler started successfully")

        try:
            await self.dp.start_polling(
                self.bot,
                allowed_updates=["message", "callback_query"],
                drop_pending_updates=True  # ✅ Очищаем накопленные обновления
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

    async def _run_scheduled_analysis(self, bot):
        """
        Callback функция для scheduler - запускает полный цикл анализа
        
        Args:
            bot: TradingBotTelegram объект (self)
        """
        # Проверяем, не остановлен ли бот
        if self.bot_stopped:
            logger.info("Bot is stopped, skipping scheduled run")
            return

        if self.trading_bot_running:
            logger.warning("Trading bot is already running, skipping scheduled run")
            return

        try:
            self.trading_bot_running = True
            logger.info("=" * 70)
            logger.info("SCHEDULED RUN: Starting full trading cycle")
            logger.info("=" * 70)

            # Отправляем уведомление пользователям
            for user_id in self.user_ids:
                try:
                    await self.bot.send_message(
                        chat_id=user_id,
                        text="⏳ <b>Автоматический запуск анализа...</b>",
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.debug(f"Error sending notification to {user_id}: {e}")

            # Запускаем полный цикл
            await self._run_full_trading_cycle()

        except Exception as e:
            logger.error(f"Error in scheduled analysis: {e}", exc_info=True)
            
            # Отправляем ошибку пользователям
            for user_id in self.user_ids:
                try:
                    await self.bot.send_message(
                        chat_id=user_id,
                        text=f"❌ <b>Ошибка при автоматическом запуске:</b>\n\n<code>{str(e)}</code>",
                        parse_mode="HTML"
                    )
                except:
                    pass
        finally:
            self.trading_bot_running = False

    async def _run_full_trading_cycle(self):
        """Запуск полного цикла анализа (без отправки сообщений пользователю)"""
        from stages import run_stage1, run_stage2, run_stage3
        from data_providers import get_all_trading_pairs, cleanup_session

        try:
            logger.info("Scheduled run: Starting Stage 1")
            pairs = await get_all_trading_pairs()
            candidates = await run_stage1(pairs)

            if not candidates:
                logger.warning("Scheduled run: Stage 1 - No signals found")
                await cleanup_session()
                return

            logger.info(f"Scheduled run: Stage 1 - Found {len(candidates)} signals")

            logger.info("Scheduled run: Starting Stage 2")
            selected_pairs = await run_stage2(candidates)

            if not selected_pairs:
                logger.warning("Scheduled run: Stage 2 - AI selected 0 pairs")
                await cleanup_session()
                return

            logger.info(f"Scheduled run: Stage 2 - AI selected {len(selected_pairs)} pairs")

            logger.info("Scheduled run: Starting Stage 3")
            approved_signals, rejected_signals = await run_stage3(selected_pairs)

            # Сохраняем сигналы
            for signal in approved_signals:
                self.signal_storage.save_signal(signal)

            # Отправляем сигналы
            if approved_signals:
                await self._send_signals_to_group(approved_signals)
                # Отправляем одобренные сигналы всем пользователям
                for user_id in self.user_ids:
                    await self._send_approved_signals(approved_signals, user_id)
            
            if rejected_signals:
                # Отправляем отклонённые сигналы всем пользователям
                for user_id in self.user_ids:
                    await self._send_rejected_signals(rejected_signals, user_id)

            await cleanup_session()

            logger.info("=" * 70)
            logger.info(f"SCHEDULED RUN COMPLETE: {len(approved_signals)} approved, {len(rejected_signals)} rejected")
            logger.info("=" * 70)

        except Exception as e:
            logger.error(f"Error in full trading cycle: {e}", exc_info=True)
            raise


# ============================================================================
# RUN FUNCTION
# ============================================================================
async def run_telegram_bot():
    """Главная функция для запуска бота"""
    from config import config

    bot = TradingBotTelegram(
        bot_token=config.TELEGRAM_BOT_TOKEN,
        user_ids=config.TELEGRAM_USER_IDS,
        group_id=config.TELEGRAM_GROUP_ID,
        admin_ids=config.TELEGRAM_ADMIN_IDS
    )

    await bot.start()