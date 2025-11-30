"""
Main Entry Point
Файл: main.py

Точка входа для запуска Trading Bot
"""

import asyncio
import sys
import argparse
import logging

# Настройка базового логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)-8s] %(name)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

logger = logging.getLogger(__name__)


async def run_telegram_bot():
    """Запустить Telegram бота"""
    try:
        from telegram import run_telegram_bot as telegram_main

        logger.info("Starting Telegram Bot with schedule...")
        await telegram_main()

    except Exception as e:
        logger.error(f"Telegram bot error: {e}", exc_info=True)
        sys.exit(1)


async def run_single_cycle():
    """Запустить один цикл анализа (для тестирования)"""
    try:
        from stages import run_stage1, run_stage2, run_stage3
        from data_providers import get_all_trading_pairs, cleanup_session
        from datetime import datetime

        logger.info("=" * 70)
        logger.info("SINGLE CYCLE MODE")
        logger.info("=" * 70)

        start_time = datetime.now()

        # Stage 1: Filter
        logger.info("Stage 1: Loading trading pairs...")
        pairs = await get_all_trading_pairs()

        logger.info(f"Stage 1: Analyzing {len(pairs)} pairs...")
        candidates = await run_stage1(pairs)

        if not candidates:
            logger.warning("Stage 1: No signal pairs found")
            await cleanup_session()
            return

        logger.info(f"Stage 1: Found {len(candidates)} signal pairs")

        # Stage 2: AI Selection
        logger.info("Stage 2: AI pair selection...")
        selected_pairs = await run_stage2(candidates)

        if not selected_pairs:
            logger.warning("Stage 2: AI selected 0 pairs")
            await cleanup_session()
            return

        logger.info(f"Stage 2: AI selected {len(selected_pairs)} pairs: {selected_pairs}")

        # Stage 3: Comprehensive Analysis
        logger.info("Stage 3: Comprehensive analysis...")
        approved_signals, rejected_signals = await run_stage3(selected_pairs)

        # Cleanup
        await cleanup_session()

        # Summary
        elapsed = (datetime.now() - start_time).total_seconds()

        logger.info("=" * 70)
        logger.info("CYCLE COMPLETE")
        logger.info("=" * 70)
        logger.info(f"Time: {elapsed:.1f}s")
        logger.info(f"Approved: {len(approved_signals)}")
        logger.info(f"Rejected: {len(rejected_signals)}")

        if approved_signals:
            logger.info("\nAPPROVED SIGNALS:")
            for sig in approved_signals:
                logger.info(f"  • {sig.symbol} {sig.signal} (confidence: {sig.confidence}%)")

        logger.info("=" * 70)

    except Exception as e:
        logger.error(f"Single cycle error: {e}", exc_info=True)
        sys.exit(1)


def parse_arguments():
    """Парсинг аргументов командной строки"""
    parser = argparse.ArgumentParser(
        description='Trading Bot - Triple EMA Strategy'
    )

    parser.add_argument(
        'mode',
        nargs='?',
        default='telegram',
        choices=['telegram', 'once'],
        help='Режим запуска: telegram (с расписанием) или once (один цикл для теста)'
    )

    return parser.parse_args()


async def main():
    """Главная функция"""
    args = parse_arguments()

    logger.info("=" * 70)
    logger.info("TRADING BOT - TRIPLE EMA STRATEGY")
    logger.info("=" * 70)

    if args.mode == 'once':
        logger.info("Mode: Single Cycle (test mode)")
        await run_single_cycle()
    else:
        logger.info("Mode: Telegram Bot (scheduled)")
        await run_telegram_bot()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nBot stopped by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)