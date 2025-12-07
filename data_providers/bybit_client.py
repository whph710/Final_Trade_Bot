"""
Bybit API Client
Файл: data_providers/bybit_client.py

Оптимизированный async клиент для работы с Bybit API

ОБНОВЛЕНО: Поддержка поля 'timeframe' в batch requests для Stage 2
"""

import aiohttp
import asyncio
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)

# Глобальная сессия и семафор
_session: Optional[aiohttp.ClientSession] = None
_semaphore: Optional[asyncio.Semaphore] = None

# Настройки
MAX_CONCURRENT_REQUESTS = 50
REQUEST_TIMEOUT = 15
CONNECT_TIMEOUT = 5


async def get_session() -> aiohttp.ClientSession:
    """
    Получить или создать оптимизированную сессию с connection pooling

    Returns:
        Настроенная aiohttp.ClientSession
    """
    global _session, _semaphore

    if _session is None or _session.closed:
        timeout = aiohttp.ClientTimeout(total=REQUEST_TIMEOUT, connect=CONNECT_TIMEOUT)
        connector = aiohttp.TCPConnector(
            limit=MAX_CONCURRENT_REQUESTS,
            limit_per_host=25,
            keepalive_timeout=120,
            enable_cleanup_closed=True
        )

        _session = aiohttp.ClientSession(
            timeout=timeout,
            connector=connector,
            headers={'User-Agent': 'TradingBot/6.0'}
        )

        _semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
        logger.debug("Created new aiohttp session with connection pooling")

    return _session


async def fetch_candles(
        symbol: str,
        interval: str,
        limit: int = 200,
        start_time: Optional[int] = None
) -> List[List]:
    """
    Получить свечи с Bybit

    Args:
        symbol: Торговая пара (например, 'BTCUSDT')
        interval: Интервал ('60' = 1H, '240' = 4H, 'D' = 1D)
        limit: Количество свечей (макс 1000)
        start_time: Начальный timestamp в миллисекундах (опционально)

    Returns:
        Список свечей в формате Bybit [timestamp, open, high, low, close, volume, turnover]
        Пустой список при ошибке
    """
    session = await get_session()

    params = {
        "category": "linear",
        "symbol": symbol,
        "interval": interval,
        "limit": limit
    }
    
    # ✅ ДОБАВЛЕНО: Если указан start_time, загружаем свечи начиная с этого времени
    if start_time is not None:
        params["start"] = start_time

    async with _semaphore:
        for attempt in range(2):  # 2 попытки
            try:
                async with session.get(
                        "https://api.bybit.com/v5/market/kline",
                        params=params
                ) as response:

                    if response.status != 200:
                        if attempt == 0:
                            await asyncio.sleep(0.1)
                            continue
                        logger.warning(f"HTTP {response.status} for {symbol} {interval}")
                        return []

                    data = await response.json()

                    if data.get("retCode") != 0:
                        if attempt == 0:
                            await asyncio.sleep(0.1)
                            continue
                        logger.warning(f"API error for {symbol}: {data.get('retMsg', 'Unknown')}")
                        return []

                    klines = data["result"]["list"]

                    # Bybit возвращает свечи в обратном порядке (новые → старые)
                    # Разворачиваем для правильного порядка (старые → новые)
                    if klines and len(klines) > 1:
                        if int(klines[0][0]) > int(klines[-1][0]):
                            klines.reverse()

                    # Убираем последнюю незавершённую свечу
                    if len(klines) > 1:
                        klines = klines[:-1]

                    logger.debug(f"Fetched {len(klines)} candles for {symbol} {interval}")
                    return klines

            except asyncio.TimeoutError:
                if attempt == 0:
                    continue
                logger.warning(f"Timeout fetching {symbol} {interval}")
                return []

            except Exception as e:
                if attempt == 0:
                    continue
                logger.warning(f"Error fetching {symbol} {interval}: {e}")
                return []

    return []


async def fetch_multiple_candles(
        requests: List[Dict]
) -> List[Dict]:
    """
    Batch загрузка свечей для нескольких пар

    Args:
        requests: Список запросов вида:
            [
                {'symbol': 'BTCUSDT', 'interval': '60', 'limit': 100, 'timeframe': '1H'},
                {'symbol': 'ETHUSDT', 'interval': '240', 'limit': 60, 'timeframe': '4H'},
                ...
            ]

            ✅ ОБНОВЛЕНО: Поле 'timeframe' опционально (для Stage 2)

    Returns:
        Список результатов вида:
            [
                {'symbol': 'BTCUSDT', 'klines': [...], 'success': True, 'timeframe': '1H'},
                {'symbol': 'ETHUSDT', 'klines': [], 'success': False, 'timeframe': '4H'},
                ...
            ]
    """
    if not requests:
        return []

    tasks = [_fetch_single_request(req) for req in requests]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    successful = []
    errors = 0

    for result in results:
        if isinstance(result, dict) and result.get('success'):
            successful.append(result)
        else:
            errors += 1

    if errors > 0:
        logger.debug(f"Batch fetch: {errors}/{len(requests)} failed")

    return successful


async def _fetch_single_request(req: Dict) -> Dict:
    """
    Обработка одного запроса с обработкой ошибок

    Args:
        req: {'symbol': str, 'interval': str, 'limit': int, 'timeframe': str (optional)}

    Returns:
        {'symbol': str, 'klines': List, 'success': bool, 'timeframe': str (optional)}
    """
    try:
        klines = await fetch_candles(
            req['symbol'],
            req.get('interval', '60'),
            req.get('limit', 100)
        )

        result = {
            'symbol': req['symbol'],
            'klines': klines,
            'success': len(klines) > 0
        }

        # ✅ ДОБАВЛЕНО: Пробрасываем timeframe если есть
        if 'timeframe' in req:
            result['timeframe'] = req['timeframe']

        return result

    except Exception as e:
        logger.debug(f"Error in single request {req['symbol']}: {e}")

        result = {
            'symbol': req['symbol'],
            'klines': [],
            'success': False
        }

        if 'timeframe' in req:
            result['timeframe'] = req['timeframe']

        return result


async def get_all_trading_pairs() -> List[str]:
    """
    Получить список всех торговых пар USDT на Bybit

    Returns:
        Список символов (например, ['BTCUSDT', 'ETHUSDT', ...])
        Fallback список при ошибке
    """
    session = await get_session()
    params = {"category": "linear"}

    try:
        async with session.get(
                "https://api.bybit.com/v5/market/instruments-info",
                params=params
        ) as response:

            if response.status != 200:
                logger.error(f"Failed to get trading pairs: HTTP {response.status}")
                return _get_fallback_pairs()

            data = await response.json()

            if data.get("retCode") != 0:
                logger.error("API error getting trading pairs")
                return _get_fallback_pairs()

            # Фильтруем только активные USDT пары
            symbols = [
                item["symbol"]
                for item in data["result"]["list"]
                if (
                        item["status"] == "Trading" and
                        item["symbol"].endswith("USDT") and
                        not item["symbol"].startswith("USDT") and
                        "-" not in item["symbol"]  # Исключаем пары с дефисом
                )
            ]

            logger.info(f"Loaded {len(symbols)} trading pairs from Bybit")
            return symbols

    except Exception as e:
        logger.error(f"Critical error getting trading pairs: {e}")
        return _get_fallback_pairs()


def _get_fallback_pairs() -> List[str]:
    """
    Fallback список популярных пар на случай ошибки API

    Returns:
        Список топовых торговых пар
    """
    pairs = [
        'BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'SOLUSDT', 'XRPUSDT',
        'ADAUSDT', 'DOTUSDT', 'DOGEUSDT', 'AVAXUSDT', 'MATICUSDT',
        'LINKUSDT', 'LTCUSDT', 'UNIUSDT', 'ATOMUSDT', 'FILUSDT',
        'AAVEUSDT', 'SUSHIUSDT', 'COMPUSDT', 'YFIUSDT', 'SNXUSDT',
        'NEARUSDT', 'FTMUSDT', 'SANDUSDT', 'MANAUSDT', 'CRVUSDT'
    ]

    logger.warning(f"Using fallback pairs: {len(pairs)} symbols")
    return pairs


async def cleanup_session():
    """
    Очистка ресурсов (закрытие сессии)
    Вызывать в конце работы программы
    """
    global _session, _semaphore

    if _session and not _session.closed:
        try:
            await _session.close()
            await asyncio.sleep(0.1)  # Даём время на cleanup
            logger.debug("Closed aiohttp session")
        except Exception as e:
            logger.debug(f"Error closing session: {e}")
        finally:
            _session = None
            _semaphore = None