"""
Telegram Scheduler
Файл: telegram/scheduler.py

Управление расписанием запуска бота
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

    Реализовано через фоновую задачу, которая ожидает ближайшего запуска
    и вызывает callback(bot).
    """

    # Расписание запусков (Пермь UTC+5)
    SCHEDULE_TIMES = [
        ("10:05", "11:05"),  # Первый период
        ("16:05", "17:05"),  # Второй период
        ("22:05", "23:05"),  # Третий период
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

        logger.info(f"Scheduler initialized with timezone: {timezone}")

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

                logger.info(
                    f"Next scheduled run at "
                    f"{next_run.strftime('%Y-%m-%d %H:%M:%S %Z')} "
                    f"(wait {wait_seconds:.0f}s)"
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

        Returns:
            datetime объект следующего запуска
        """
        now = datetime.now(self.timezone)
        today = now.date()

        candidate_datetimes = []

        for start_time_str, _ in self.SCHEDULE_TIMES:
            hour, minute = map(int, start_time_str.split(":"))
            candidate = self.timezone.localize(
                datetime.combine(today, dtime(hour=hour, minute=minute))
            )

            if candidate > now:
                candidate_datetimes.append(candidate)

        if candidate_datetimes:
            return min(candidate_datetimes)

        # Все времена сегодня прошли - вернуть первое завтрашнее
        tomorrow = today + timedelta(days=1)
        hour, minute = map(int, self.SCHEDULE_TIMES[0][0].split(":"))
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

        for start_time_str, end_time_str in self.SCHEDULE_TIMES:
            sh, sm = map(int, start_time_str.split(":"))
            eh, em = map(int, end_time_str.split(":"))

            start = dtime(hour=sh, minute=sm)
            end = dtime(hour=eh, minute=em)

            if start <= current < end:
                return True

        return False

    def get_schedule_info(self) -> str:
        """
        Получить информацию о расписании

        Returns:
            Строка с расписанием
        """
        info_lines = ["<b>📅 РАСПИСАНИЕ ЗАПУСКА:</b>\n"]

        for start_time, end_time in self.SCHEDULE_TIMES:
            info_lines.append(f"  • {start_time} - {end_time} (UTC+5)")

        next_run = self.get_next_run_time()
        info_lines.append(
            f"\n<b>⏰ Следующий запуск:</b>\n"
            f"  {next_run.strftime('%Y-%m-%d %H:%M:%S')}"
        )

        return "\n".join(info_lines)

    def stop(self):
        """Остановить планировщик"""
        self._stopped = True

        if self._scheduler_task:
            self._scheduler_task.cancel()

        logger.info("Scheduler stopped")