"""
Data Providers Package
Модули для получения и нормализации данных с биржи Bybit и Tinkoff Investments
"""

import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

from .bybit_client import (
    fetch_candles as fetch_candles_bybit,
    fetch_multiple_candles as fetch_multiple_candles_bybit,
    get_all_trading_pairs,
    cleanup_session
)

from .data_normalizer import (
    normalize_candles,
    NormalizedCandles
)

from .market_data import (
    MarketDataCollector,
    get_market_snapshot
)

# Tinkoff Investments (опционально)
try:
    from .tinkoff_client import (
        get_all_stocks,
        fetch_stock_candles,
        fetch_moex_index_candles,
        get_tinkoff_client
    )
    TINKOFF_AVAILABLE = True
except ImportError:
    TINKOFF_AVAILABLE = False
    # Заглушки для функций
    async def get_all_stocks():
        return []
    
    async def fetch_stock_candles(*args, **kwargs):
        return []
    
    async def fetch_moex_index_candles(*args, **kwargs):
        return []
    
    async def get_tinkoff_client():
        return None


# Используем централизованный детектор
from utils.asset_detector import AssetTypeDetector

def _detect_asset_type(symbol: str) -> str:
    """
    Определить тип актива по символу (обертка для обратной совместимости)
    
    Args:
        symbol: Тикер актива
    
    Returns:
        'stock' или 'crypto'
    """
    return AssetTypeDetector.detect(symbol)


async def fetch_candles(
    symbol: str,
    interval: str,
    limit: Optional[int] = None,
    start_time: Optional[int] = None
) -> List:
    """
    Универсальная функция для получения свечей (автоматически определяет тип актива)
    
    Args:
        symbol: Тикер актива (например, 'BTCUSDT' или 'SBER')
        interval: Интервал ('60' = 1H, '240' = 4H, 'D' = 1D)
        limit: Количество свечей
        start_time: Начальный timestamp в миллисекундах (опционально, только для crypto)
    
    Returns:
        Список свечей в формате Bybit [timestamp_ms, open, high, low, close, volume, turnover]
    """
    asset_type = _detect_asset_type(symbol)
    
    if asset_type == 'stock':
        if not TINKOFF_AVAILABLE:
            logger.warning(f"Tinkoff not available, cannot fetch candles for stock {symbol}")
            return []
        
        logger.debug(f"Fetching stock candles for {symbol} via Tinkoff")
        # Tinkoff использует datetime для from_time, но для упрощения игнорируем start_time для stocks
        # (можно добавить конвертацию timestamp_ms -> datetime если нужно)
        return await fetch_stock_candles(symbol, interval, limit)
    else:
        logger.debug(f"Fetching crypto candles for {symbol} via Bybit")
        return await fetch_candles_bybit(symbol, interval, limit, start_time=start_time)


async def fetch_multiple_candles(
    requests: List[Dict]
) -> List[Dict]:
    """
    Универсальная batch загрузка свечей (автоматически определяет тип актива для каждого символа)
    
    Args:
        requests: Список запросов вида:
            [
                {'symbol': 'BTCUSDT', 'interval': '60', 'limit': 100, 'timeframe': '1H'},
                {'symbol': 'SBER', 'interval': '240', 'limit': 60, 'timeframe': '4H'},
                ...
            ]
    
    Returns:
        Список результатов вида:
            [
                {'symbol': 'BTCUSDT', 'klines': [...], 'success': True, 'timeframe': '1H'},
                {'symbol': 'SBER', 'klines': [...], 'success': True, 'timeframe': '4H'},
                ...
            ]
    """
    if not requests:
        return []
    
    import asyncio
    import time
    
    # Группируем запросы по типу актива для оптимизации
    grouped = AssetTypeDetector.group_by_type([req['symbol'] for req in requests])
    stock_count = len(grouped['stock'])
    crypto_count = len(grouped['crypto'])
    
    if stock_count > 0 or crypto_count > 0:
        logger.info(f"Batch: {stock_count} stocks, {crypto_count} crypto (total: {len(requests)})")
    
    start_time = time.time()
    completed = 0
    
    async def _fetch_single_request(req: Dict) -> Dict:
        """Обработка одного запроса с автоматическим определением типа актива"""
        nonlocal completed
        try:
            symbol = req['symbol']
            asset_type = _detect_asset_type(symbol)
            
            from config import config
            default_limit = req.get('limit', config.BYBIT_DEFAULT_CANDLES_LIMIT)
            interval = req.get('interval', '60')
            
            if asset_type == 'stock':
                if not TINKOFF_AVAILABLE:
                    completed += 1
                    return {
                        'symbol': symbol,
                        'klines': [],
                        'success': False
                    }
                
                # Минимальное логирование для ускорения batch загрузки
                klines = await fetch_stock_candles(symbol, interval, default_limit)
            else:
                # Crypto - используем прямой вызов для оптимизации
                klines = await fetch_candles_bybit(symbol, interval, default_limit)
            
            completed += 1
            # Логируем прогресс только для больших батчей (>50) и каждые 50 элементов
            if len(requests) > 50 and completed % 50 == 0:
                elapsed = time.time() - start_time
                rate = completed / elapsed if elapsed > 0 else 0
                logger.info(f"Batch progress: {completed}/{len(requests)} ({rate:.1f} req/s)")
            
            result = {
                'symbol': symbol,
                'klines': klines,
                'success': len(klines) > 0
            }
            
            if 'timeframe' in req:
                result['timeframe'] = req['timeframe']
            
            return result
            
        except Exception as e:
            completed += 1
            logger.debug(f"Error fetching {req.get('symbol', 'UNKNOWN')}: {e}")
            
            return {
                'symbol': req.get('symbol', 'UNKNOWN'),
                'klines': [],
                'success': False,
                'timeframe': req.get('timeframe')
            }
    
    tasks = [_fetch_single_request(req) for req in requests]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    successful = []
    errors = 0
    
    for result in results:
        if isinstance(result, dict) and result.get('success'):
            successful.append(result)
        else:
            errors += 1
    
    elapsed = time.time() - start_time
    if len(requests) > 10:
        logger.info(f"Batch complete: {len(successful)}/{len(requests)} successful in {elapsed:.1f}s")
    
    if errors > 0:
        logger.debug(f"Batch fetch: {errors}/{len(requests)} failed")
    
    return successful

__all__ = [
    # Universal functions (auto-detect asset type)
    'fetch_candles',
    'fetch_multiple_candles',
    '_detect_asset_type',  # Экспортируем для использования в других модулях
    
    # Bybit client (direct access)
    'get_all_trading_pairs',
    'cleanup_session',

    # Data normalizer
    'normalize_candles',
    'NormalizedCandles',

    # Market data
    'MarketDataCollector',
    'get_market_snapshot',
    
    # Tinkoff Investments
    'get_all_stocks',
    'fetch_stock_candles',
    'fetch_moex_index_candles',
    'get_tinkoff_client',
    'TINKOFF_AVAILABLE',
]