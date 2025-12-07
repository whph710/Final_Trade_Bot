"""
Logging Configuration
Файл: utils/logger.py

ОБНОВЛЕНО:
- Логи сохраняются в logs/
- Красный цвет для консоли (как было)
"""

import logging
import sys
from pathlib import Path
from datetime import datetime


class ColorCodes:
    """ANSI color codes для консоли"""
    RED = '\033[91m'
    RESET = '\033[0m'


class ColoredFormatter(logging.Formatter):
    """Красный цвет для всех сообщений в консоли"""

    def format(self, record):
        log_message = super().format(record)
        return f"{ColorCodes.RED}{log_message}{ColorCodes.RESET}"


def setup_logger(
        module_name: str,
        log_dir: Path = None,
        console_level: int = logging.INFO,
        file_level: int = logging.DEBUG
) -> logging.Logger:
    """
    Настройка логгера для модуля

    Args:
        module_name: __name__ модуля
        log_dir: Path к директории логов (по умолчанию config.LOGS_DIR)
        console_level: Уровень для консоли
        file_level: Уровень для файла

    Returns:
        Настроенный logger
    """
    logger = logging.getLogger(module_name)

    # Если уже настроен - возвращаем
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)

    # Используем logs/ из config
    if log_dir is None:
        try:
            from config import config
            log_dir = config.LOGS_DIR
        except:
            log_dir = Path("logs")

    log_dir.mkdir(exist_ok=True)

    # Формат логов
    file_formatter = logging.Formatter(
        '%(asctime)s [%(levelname)-8s] %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    console_formatter = ColoredFormatter(
        '%(asctime)s [%(levelname)-8s] %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # FILE: Все логи
    today = datetime.now().strftime('%Y%m%d')
    file_handler = logging.FileHandler(
        log_dir / f"bot_{today}.log",
        encoding='utf-8'
    )
    file_handler.setLevel(file_level)
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)

    # FILE: Только ошибки
    error_handler = logging.FileHandler(
        log_dir / f"bot_errors_{today}.log",
        encoding='utf-8'
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)
    logger.addHandler(error_handler)

    # CONSOLE: Красный цвет
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(console_level)
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    return logger


def get_logger(module_name: str) -> logging.Logger:
    """
    Получить или создать логгер для модуля

    Args:
        module_name: __name__ модуля

    Returns:
        Logger instance
    """
    return setup_logger(module_name)