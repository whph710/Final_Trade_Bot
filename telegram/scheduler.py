"""
Telegram Scheduler - OPTIMIZED FOR CRYPTO MARKET
Файл: telegram/scheduler.py

✅ ОПТИМИЗИРОВАНО:
- ПН-ПТ: 4 запуска в день (привязка к 4H свечам + пики ликвидности)
- СБ-ВС: 2 запуска в день (меньше из-за низкой ликвидности)
- Все запуски привязаны к закрытию 4H свечей
"""

import asyncio
import logging
from datetime import datetime, timedelta, time as dtime
from typing import Callable, Optional
import pytz

logger = logging.getLogger(__name__)


class ScheduleManager:
    """
    Управление расписанием запуска бота

    ОПТИМИЗИРОВАНО ПОД КРИПТОРЫНОК 24/7:
    - Привязка к закрытию 4H свечей (09:00, 13:00, 17:00, 21:00)
    - Учет пиков ликвидности (Азия, Европа, США)
    - Больше запусков в будни, меньше в выходные
    """

    # ========================================================================
    # БУДНИ (ПН-ПТ): 4 запуска в день
    # ========================================================================
    WEEKDAY_SCHEDULE = [
        "09:15",  # 🌏 Азиатская сессия (после 4H свечи 09:00)
        "13:15",  # 🌍 Европейская сессия (после 4H свечи 13:00)
        "17:15",  # 🔥 ПИК: Европа+США (после 4H свечи 17:00)
        "21:15",  # 🌎 Американская сессия (после 4H свечи 21:00)
    ]

    # ========================================================================
    # ВЫХОДНЫЕ (СБ-ВС): 2 запуска в день
    # ========================================================================
    WEEKEND_SCHEDULE = [
        "09:15",  # 🌏 Утренний запуск (Азия)
        "17:15",  # 🔥 Вечерний запуск (лучшая ликвидность)
        "21:15",  # 🌎 Вечерний запуск (Америка)
    ]

    def __init__(self, timezone: str = 'Asia/Yekaterinburg'):
        """
        Инициализация планировщика

        Args:
            timezone: Timezone (default: Asia/Yekaterinburg - Пермь UTC+5)
        """
        self.timezone = pytz.timezone(timezone)
        self._scheduler_task: Optional[asyncio.Task] = None
        self._stopped = False

        logger.info(
            f"Scheduler initialized: {timezone}\n"
            f"  • Weekdays (Mon-Fri): {len(self.WEEKDAY_SCHEDULE)} runs/day\n"
            f"  • Weekends (Sat-Sun): {len(self.WEEKEND_SCHEDULE)} runs/day"
        )

    def setup_schedule(self, bot, callback_coro: Callable):
        """
        Запустить фоновую задачу планировщика

        Args:
            bot: Telegram Bot объект
            callback_coro: Async функция с сигнатурой async def callback(bot)
        """
        if self._scheduler_task is None:
            self._scheduler_task = asyncio.create_task(
                self._run_scheduler(bot, callback_coro)
            )
            logger.info("Scheduler task started")

    async def _run_scheduler(self, bot, callback_coro: Callable):
        """
        Основной цикл планировщика

        Args:
            bot: Telegram Bot объект
            callback_coro: Callback функция
        """
        while not self._stopped:
            try:
                next_run = self.get_next_run_time()
                now = datetime.now(self.timezone)
                wait_seconds = (next_run - now).total_seconds()

                if wait_seconds <= 0:
                    wait_seconds = 1

                day_type = "WEEKEND" if now.weekday() >= 5 else "WEEKDAY"

                logger.info(
                    f"Next scheduled run at "
                    f"{next_run.strftime('%Y-%m-%d %H:%M:%S %Z')} "
                    f"({day_type}, wait {wait_seconds:.0f}s)"
                )

                await asyncio.sleep(wait_seconds)

                # Запускаем callback в отдельной задаче
                asyncio.create_task(callback_coro(bot))

                # Ждём 60 секунд чтобы избежать двойного срабатывания
                await asyncio.sleep(60)

            except Exception as e:
                logger.exception(f"Scheduler error: {e}")
                await asyncio.sleep(10)

    def get_next_run_time(self) -> datetime:
        """
        Получить время следующего запуска

        ЛОГИКА:
        1. Определяем текущий день (будний/выходной)
        2. Берём соответствующее расписание
        3. Находим ближайшее время

        Returns:
            datetime объект следующего запуска
        """
        now = datetime.now(self.timezone)
        today = now.date()
        current_weekday = now.weekday()  # 0=Mon, 6=Sun

        # Определяем расписание для текущего дня
        if current_weekday >= 5:  # Суббота (5) или Воскресенье (6)
            schedule = self.WEEKEND_SCHEDULE
        else:  # Понедельник-Пятница (0-4)
            schedule = self.WEEKDAY_SCHEDULE

        # Кандидаты на сегодня
        candidate_datetimes = []

        for time_str in schedule:
            hour, minute = map(int, time_str.split(":"))
            candidate = self.timezone.localize(
                datetime.combine(today, dtime(hour=hour, minute=minute))
            )

            if candidate > now:
                candidate_datetimes.append(candidate)

        # Если есть время сегодня - возвращаем
        if candidate_datetimes:
            return min(candidate_datetimes)

        # ========================================================================
        # Все времена сегодня прошли - ищем на завтра
        # ========================================================================
        tomorrow = today + timedelta(days=1)
        tomorrow_weekday = (current_weekday + 1) % 7

        # Определяем расписание для завтра
        if tomorrow_weekday >= 5:  # Завтра выходной
            next_schedule = self.WEEKEND_SCHEDULE
        else:  # Завтра будний
            next_schedule = self.WEEKDAY_SCHEDULE

        # Берём первое время завтра
        hour, minute = map(int, next_schedule[0].split(":"))
        return self.timezone.localize(
            datetime.combine(tomorrow, dtime(hour=hour, minute=minute))
        )

    def is_trading_hour(self) -> bool:
        """
        Проверить, входит ли текущее время в торговые часы

        Returns:
            True если текущее время в расписании
        """
        now = datetime.now(self.timezone)
        current = now.time()
        current_weekday = now.weekday()

        # Определяем расписание
        if current_weekday >= 5:
            schedule = self.WEEKEND_SCHEDULE
        else:
            schedule = self.WEEKDAY_SCHEDULE

        # Проверяем попадание в окна (±1 час от запланированного времени)
        for time_str in schedule:
            hour, minute = map(int, time_str.split(":"))
            scheduled_time = dtime(hour=hour, minute=minute)

            # Окно: ±1 час
            start_time = dtime(
                hour=max(0, hour - 1),
                minute=minute
            )
            end_time = dtime(
                hour=min(23, hour + 1),
                minute=minute
            )

            if start_time <= current <= end_time:
                return True

        return False

    def get_schedule_info(self) -> str:
        """
        Получить информацию о расписании

        Returns:
            Строка с расписанием
        """
        now = datetime.now(self.timezone)
        is_weekend = now.weekday() >= 5

        info_lines = ["<b>📅 РАСПИСАНИЕ ЗАПУСКА (UTC+5)</b>\n", "<b>📊 Будни (Пн-Пт):</b>"]

        # Будни
        for time_str in self.WEEKDAY_SCHEDULE:
            emoji = self._get_session_emoji(time_str)
            info_lines.append(f"  {emoji} {time_str}")

        info_lines.append("")

        # Выходные
        info_lines.append("<b>🏖 Выходные (Сб-Вс):</b>")
        for time_str in self.WEEKEND_SCHEDULE:
            emoji = self._get_session_emoji(time_str)
            info_lines.append(f"  {emoji} {time_str}")

        # Следующий запуск
        next_run = self.get_next_run_time()
        day_type = "🏖 Выходной" if is_weekend else "📊 Будний"

        info_lines.append(
            f"\n<b>⏰ Следующий запуск:</b>\n"
            f"  {next_run.strftime('%Y-%m-%d %H:%M:%S')} ({day_type})"
        )

        return "\n".join(info_lines)

    def _get_session_emoji(self, time_str: str) -> str:
        """Получить эмодзи для торговой сессии"""
        hour = int(time_str.split(":")[0])

        if hour < 12:
            return "🌏"  # Азия
        elif hour < 18:
            return "🌍"  # Европа
        else:
            return "🌎"  # США

    def stop(self):
        """Остановить планировщик"""
        self._stopped = True

        if self._scheduler_task:
            self._scheduler_task.cancel()

        logger.info("Scheduler stopped")