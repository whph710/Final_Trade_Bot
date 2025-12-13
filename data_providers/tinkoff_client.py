"""
Tinkoff Investments API Client
Файл: data_providers/tinkoff_client.py

Клиент для работы с Tinkoff Invest API (gRPC)
Использует официальную библиотеку t-tech-investments от Т-Банка

Установка:
    pip install t-tech-investments

Пример использования:
    from data_providers.tinkoff_client import fetch_stock_candles, get_all_stocks
    
    # Получить все тикеры акций
    stocks = await get_all_stocks()
    
    # Получить свечи для акции
    candles = await fetch_stock_candles('SBER', interval='60', limit=100)
"""

import logging
import asyncio
from typing import List, Dict, Optional
from datetime import datetime, timedelta

try:
    from t_tech.invest import Client, CandleInterval, InstrumentStatus
    from t_tech.invest.utils import now
    TINKOFF_AVAILABLE = True
except ImportError as e:
    TINKOFF_AVAILABLE = False
    logging.warning(
        f"t-tech-investments not installed. Install with: pip install t-tech-investments. Error: {e}"
    )

logger = logging.getLogger(__name__)

# Подавляем лишние логи Tinkoff SDK (хеши и внутренние операции)
_tinkoff_logger = logging.getLogger('t_tech.invest.logging')
_tinkoff_logger.setLevel(logging.WARNING)  # Показываем только WARNING и выше


class TinkoffClient:
    """Клиент для работы с Tinkoff Invest API"""

    def __init__(self, token: str):
        """
        Args:
            token: Токен доступа Tinkoff Invest API
        """
        if not TINKOFF_AVAILABLE:
            raise ImportError("t-tech-investments not installed. Install with: pip install t-tech-investments")
        
        self.token = token
        self.client = None
        self._instrument_cache: Dict[str, Dict] = {}  # Кэш для инструментов по тикеру

    def __enter__(self):
        """Контекстный менеджер: вход"""
        self.client = Client(token=self.token)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Контекстный менеджер: выход"""
        if self.client:
            self.client.__exit__(exc_type, exc_val, exc_tb)
    
    def clear_cache(self):
        """Очистить кэш инструментов"""
        self._instrument_cache.clear()
        logger.debug("Tinkoff instrument cache cleared")

    def _get_instruments_service(self):
        """
        Получить сервис instruments с проверкой структуры клиента
        
        Returns:
            Сервис instruments или None если не найден
        """
        if not self.client:
            raise RuntimeError("Client not initialized")
        
        # Пробуем разные варианты доступа к готовым сервисам
        if hasattr(self.client, 'instruments'):
            return self.client.instruments
        
        if hasattr(self.client, 'services') and hasattr(self.client.services, 'instruments'):
            return self.client.services.instruments
        
        # Если сервисы не найдены, пробуем создать вручную (только если структура клиента изменилась)
        # ВНИМАНИЕ: В новых версиях t-tech-investments может потребоваться metadata
        try:
            from t_tech.invest.services import InstrumentsService
            import grpc
            
            # Получаем channel из клиента
            channel = None
            if hasattr(self.client, '_channel'):
                channel = self.client._channel
            elif hasattr(self.client, 'channel'):
                channel = self.client.channel
            
            if channel:
                # Пробуем создать сервис с metadata
                # В gRPC metadata обычно передается при вызове методов, но некоторые библиотеки требуют при создании
                try:
                    # Сначала пробуем без metadata
                    return InstrumentsService(channel)
                except TypeError as e:
                    if 'metadata' in str(e).lower():
                        # Если требуется metadata, создаем его
                        # Пробуем получить metadata из клиента
                        if hasattr(self.client, '_metadata'):
                            metadata = self.client._metadata
                        elif hasattr(self.client, 'metadata'):
                            metadata = self.client.metadata
                        else:
                            # Создаем metadata с токеном авторизации
                            # В gRPC Python metadata - это кортеж кортежей (key, value)
                            metadata = (('authorization', f'Bearer {self.token}'),)
                        return InstrumentsService(channel, metadata=metadata)
                    else:
                        raise
        except (ImportError, AttributeError, TypeError) as e:
            logger.debug(f"Failed to create InstrumentsService directly: {e}")
        
        # Логируем доступные атрибуты для отладки
        available_attrs = [attr for attr in dir(self.client) if not attr.startswith('_')]
        logger.error(f"Instruments service not found. Available client attributes: {available_attrs}")
        raise AttributeError(
            "Could not find instruments service. "
            "The t-tech-investments library structure may have changed. "
            "Please check the library documentation or update the code."
        )

    def _get_market_data_service(self):
        """
        Получить сервис market_data с проверкой структуры клиента
        
        Returns:
            Сервис market_data или None если не найден
        """
        if not self.client:
            raise RuntimeError("Client not initialized")
        
        # Пробуем разные варианты доступа к готовым сервисам
        if hasattr(self.client, 'market_data'):
            return self.client.market_data
        
        if hasattr(self.client, 'services') and hasattr(self.client.services, 'market_data'):
            return self.client.services.market_data
        
        # Если сервисы не найдены, пробуем создать вручную (только если структура клиента изменилась)
        # ВНИМАНИЕ: В новых версиях t-tech-investments может потребоваться metadata
        try:
            from t_tech.invest.services import MarketDataService
            import grpc
            
            # Получаем channel из клиента
            channel = None
            if hasattr(self.client, '_channel'):
                channel = self.client._channel
            elif hasattr(self.client, 'channel'):
                channel = self.client.channel
            
            if channel:
                # Пробуем создать сервис с metadata
                try:
                    # Сначала пробуем без metadata
                    return MarketDataService(channel)
                except TypeError as e:
                    if 'metadata' in str(e).lower():
                        # Если требуется metadata, создаем его
                        # Пробуем получить metadata из клиента
                        if hasattr(self.client, '_metadata'):
                            metadata = self.client._metadata
                        elif hasattr(self.client, 'metadata'):
                            metadata = self.client.metadata
                        else:
                            # Создаем metadata с токеном авторизации
                            # В gRPC Python metadata - это кортеж кортежей (key, value)
                            metadata = (('authorization', f'Bearer {self.token}'),)
                        return MarketDataService(channel, metadata=metadata)
                    else:
                        raise
        except (ImportError, AttributeError, TypeError) as e:
            logger.debug(f"Failed to create MarketDataService directly: {e}")
        
        # Логируем доступные атрибуты для отладки
        available_attrs = [attr for attr in dir(self.client) if not attr.startswith('_')]
        logger.error(f"Market data service not found. Available client attributes: {available_attrs}")
        raise AttributeError(
            "Could not find market_data service. "
            "The t-tech-investments library structure may have changed. "
            "Please check the library documentation or update the code."
        )

    def get_all_shares(self, rub_only: bool = True) -> List[Dict]:
        """
        Получить список всех акций
        
        Args:
            rub_only: Если True, возвращать только российские акции (валюта RUB)
        
        Returns:
            Список словарей с информацией об акциях:
            [{
                'ticker': str,
                'figi': str,
                'name': str,
                'currency': str,
                'class_code': str,
                'lot': int,
                'min_price_increment': float
            }, ...]
        """
        if not self.client:
            raise RuntimeError("Client not initialized. Use context manager")
        
        try:
            # Получаем все акции со статусом INSTRUMENT_STATUS_BASE
            instruments_service = self._get_instruments_service()
            response = instruments_service.shares(instrument_status=InstrumentStatus.INSTRUMENT_STATUS_BASE)
            
            shares_list = []
            total_tradable = 0
            currency_samples = set()  # Для отладки - собираем примеры валют
            
            # Российские биржи и class_code для фильтрации
            # Московская биржа (MOEX) - основные площадки для российских акций
            russian_class_codes = {
                'TQBR',  # Т+ Акции (основной режим)
                'TQTD',  # Т+ Акции (дополнительный режим)
                'TQBS',  # Т+ Акции (специальный режим)
                'SMAL',  # Малые акции
                'TQIF',  # Инвестиционные фонды
            }
            
            for share in response.instruments:
                if share.api_trade_available_flag:  # Только торгуемые акции
                    total_tradable += 1
                    
                    # Собираем примеры валют для отладки (первые 10)
                    if len(currency_samples) < 10:
                        currency_samples.add(str(share.currency))
                    
                    if rub_only:
                        # Фильтруем российские акции несколькими способами:
                        # 1. По валюте (может быть строка 'RUB' или enum)
                        currency_str = str(share.currency).upper()
                        is_rub_currency = 'RUB' in currency_str or currency_str == 'RUB'
                        
                        # 2. По class_code (российские акции обычно на MOEX)
                        is_russian_class = share.class_code in russian_class_codes
                        
                        # 3. По бирже (если доступно)
                        exchange = getattr(share, 'exchange', '')
                        is_russian_exchange = 'MOEX' in str(exchange).upper() or 'MOSCOW' in str(exchange).upper()
                        
                        # Принимаем акцию, если соответствует хотя бы одному критерию
                        if not (is_rub_currency or is_russian_class or is_russian_exchange):
                            continue
                    
                    # Преобразуем Quotation в float
                    min_price_inc = float(share.min_price_increment.units) + float(share.min_price_increment.nano) / 1e9
                    
                    shares_list.append({
                        'ticker': share.ticker,
                        'figi': share.figi,
                        'name': share.name,
                        'currency': share.currency,
                        'class_code': share.class_code,
                        'lot': share.lot,
                        'min_price_increment': min_price_inc
                    })
            
            if rub_only:
                logger.info(f"Loaded {len(shares_list)} Russian stocks from {total_tradable} tradable shares")
                if currency_samples:
                    logger.debug(f"Sample currencies found: {currency_samples}")
            else:
                logger.info(f"Loaded {len(shares_list)} tradable shares from Tinkoff")
            return shares_list
            
        except Exception as e:
            logger.error(f"Error getting shares list: {e}", exc_info=True)
            return []

    def get_candles(
            self,
            figi: str,
            interval: str,
            limit: Optional[int] = None,
            from_time: Optional[datetime] = None
    ) -> List[List]:
        """
        Получить исторические свечи
        
        Args:
            figi: FIGI идентификатор инструмента
            interval: Интервал ('60' = 1H, '240' = 4H, 'D' = 1D)
            limit: Количество свечей (макс 1000)
            from_time: Начальное время (если None, берется последние N свечей)
        
        Returns:
            Список свечей в формате [timestamp_ms, open, high, low, close, volume, turnover]
            Совместимо с форматом Bybit для нормализатора
        """
        if not self.client:
            raise RuntimeError("Client not initialized. Use context manager")
        
        try:
            # Преобразуем интервал
            candle_interval_map = {
                '60': CandleInterval.CANDLE_INTERVAL_HOUR,
                '240': CandleInterval.CANDLE_INTERVAL_4_HOUR,
                'D': CandleInterval.CANDLE_INTERVAL_DAY,
                '1H': CandleInterval.CANDLE_INTERVAL_HOUR,
                '4H': CandleInterval.CANDLE_INTERVAL_4_HOUR,
                '1D': CandleInterval.CANDLE_INTERVAL_DAY
            }
            
            candle_interval = candle_interval_map.get(interval)
            if not candle_interval:
                logger.error(f"Unsupported interval: {interval}")
                return []
            
            # Определяем временной диапазон
            if from_time:
                from_timestamp = from_time
            else:
                # Если не указано, берем последние N свечей
                if limit:
                    # Приблизительно вычисляем время начала
                    hours_map = {'60': 1, '240': 4, 'D': 24}
                    hours = hours_map.get(interval, 1)
                    from_timestamp = now() - timedelta(hours=hours * limit)
                else:
                    from_timestamp = now() - timedelta(days=30)
            
            to_timestamp = now()
            
            # Преобразуем Quotation в float (вынесено для переиспользования)
            def quotation_to_float(quotation) -> float:
                """Преобразует Quotation в float"""
                if hasattr(quotation, 'units') and hasattr(quotation, 'nano'):
                    return float(quotation.units) + float(quotation.nano) / 1e9
                return float(quotation)
            
            # Получаем свечи через market_data сервис
            candles = []
            try:
                market_data_service = self._get_market_data_service()
                
                # Вызываем метод get_candles из market_data сервиса
                response = market_data_service.get_candles(
                    figi=figi,
                    from_=from_timestamp,
                    to=to_timestamp,
                    interval=candle_interval
                )
                
                # В новом SDK ответ содержит поле candles со списком свечей
                candles_list = response.candles if hasattr(response, 'candles') else []
                
                for candle in candles_list:
                    # Преобразуем в формат [timestamp_ms, open, high, low, close, volume, turnover]
                    # Время свечи (timestamp в миллисекундах)
                    # candle.time всегда является datetime объектом в t-tech-investments
                    if hasattr(candle.time, 'timestamp'):
                        timestamp_ms = int(candle.time.timestamp() * 1000)
                    elif hasattr(candle, 'time'):
                        # Если это уже timestamp
                        timestamp_ms = int(candle.time * 1000) if isinstance(candle.time, (int, float)) else int(candle.time)
                    else:
                        logger.warning(f"Candle missing time attribute for {figi}")
                        continue
                    
                    open_price = quotation_to_float(candle.open)
                    high_price = quotation_to_float(candle.high)
                    low_price = quotation_to_float(candle.low)
                    close_price = quotation_to_float(candle.close)
                    
                    volume = int(candle.volume) if hasattr(candle, 'volume') else 0
                    turnover = volume  # Tinkoff не предоставляет turnover отдельно, используем volume
                    
                    candles.append([
                        timestamp_ms,
                        open_price,
                        high_price,
                        low_price,
                        close_price,
                        volume,
                        turnover
                    ])
                    
                    # Ограничиваем количество если нужно
                    if limit and len(candles) >= limit:
                        break
            except Exception as e:
                logger.error(f"Error getting candles for {figi}: {e}", exc_info=True)
                return []
            
            logger.debug(f"Loaded {len(candles)} candles for {figi} ({interval})")
            return candles
            
        except Exception as e:
            logger.error(f"Error getting candles for {figi}: {e}", exc_info=True)
            return []

    def get_last_price(self, figi: str) -> Optional[float]:
        """
        Получить последнюю цену инструмента
        
        Args:
            figi: FIGI идентификатор
        
        Returns:
            Последняя цена или None при ошибке
        """
        if not self.client:
            raise RuntimeError("Client not initialized")
        
        try:
            market_data_service = self._get_market_data_service()
            response = market_data_service.get_last_prices(figi=[figi])
            
            if response.last_prices:
                last_price = response.last_prices[0]
                price = float(last_price.price.units) + float(last_price.price.nano) / 1e9
                return price
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting last price for {figi}: {e}")
            return None

    def get_trading_status(self, figi: str) -> Optional[Dict]:
        """
        Получить статус торговли инструмента
        
        Args:
            figi: FIGI идентификатор
        
        Returns:
            Dict с информацией о статусе или None
        """
        if not self.client:
            raise RuntimeError("Client not initialized")
        
        try:
            market_data_service = self._get_market_data_service()
            response = market_data_service.get_trading_status(figi=figi)
            
            return {
                'figi': figi,
                'trading_status': str(response.trading_status),
                'limit_order_available_flag': response.limit_order_available_flag,
                'market_order_available_flag': response.market_order_available_flag
            }
            
        except Exception as e:
            logger.error(f"Error getting trading status for {figi}: {e}")
            return None

    def find_instrument_by_ticker(self, ticker: str) -> Optional[Dict]:
        """
        Найти инструмент по тикеру (с кэшированием)
        
        Args:
            ticker: Тикер инструмента (например, 'SBER')
        
        Returns:
            Dict с информацией об инструменте или None
        """
        if not self.client:
            raise RuntimeError("Client not initialized")
        
        ticker_upper = ticker.upper()
        
        # Проверяем кэш
        if ticker_upper in self._instrument_cache:
            return self._instrument_cache[ticker_upper]
        
        try:
            # Сначала пробуем найти через поиск (быстрее для известных тикеров)
            try:
                instruments_service = self._get_instruments_service()
                response = instruments_service.find_instrument(query=ticker)
                
                # Ищем точное совпадение тикера среди результатов
                for instrument in response.instruments:
                    if instrument.ticker == ticker_upper:
                        # Если нашли, получаем полную информацию через shares
                        shares_response = instruments_service.shares(
                            instrument_status=InstrumentStatus.INSTRUMENT_STATUS_BASE
                        )
                        
                        for share in shares_response.instruments:
                            if share.ticker == ticker_upper and share.api_trade_available_flag:
                                min_price_inc = float(share.min_price_increment.units) + float(share.min_price_increment.nano) / 1e9
                                result = {
                                    'ticker': share.ticker,
                                    'figi': share.figi,
                                    'name': share.name,
                                    'currency': share.currency,
                                    'class_code': share.class_code,
                                    'lot': share.lot,
                                    'min_price_increment': min_price_inc
                                }
                                # Сохраняем в кэш
                                self._instrument_cache[ticker_upper] = result
                                return result
            except Exception as e:
                logger.debug(f"Search method failed for {ticker}, trying fallback: {e}")
            
            # Fallback: используем перебор всех акций (надежнее, но медленнее)
            logger.debug(f"Using fallback method to find {ticker}")
            shares = self.get_all_shares()
            for share in shares:
                if share['ticker'].upper() == ticker_upper:
                    logger.debug(f"Found {ticker} via fallback method")
                    # Сохраняем в кэш
                    self._instrument_cache[ticker_upper] = share
                    return share
            
            logger.warning(f"Instrument with ticker {ticker} not found or not tradeable")
            return None
            
        except Exception as e:
            logger.error(f"Error finding instrument by ticker {ticker}: {e}", exc_info=True)
            return None


# Глобальный клиент (singleton)
_tinkoff_client: Optional[TinkoffClient] = None

# Глобальный кэш тикер -> FIGI (заполняется при загрузке списка акций)
_ticker_to_figi_cache: Dict[str, str] = {}

# Семафор для ограничения параллельных запросов к Tinkoff API
_tinkoff_semaphore: Optional[asyncio.Semaphore] = None


async def get_tinkoff_client() -> Optional[TinkoffClient]:
    """
    Получить глобальный экземпляр клиента Tinkoff
    
    Returns:
        TinkoffClient или None если токен не настроен
    """
    global _tinkoff_client
    
    from config import config
    
    if not config.TINKOFF_INVEST_TOKEN:
        logger.warning("TINKOFF_INVEST_TOKEN not configured")
        return None
    
    if _tinkoff_client is None:
        _tinkoff_client = TinkoffClient(config.TINKOFF_INVEST_TOKEN)
    
    return _tinkoff_client


async def get_all_stocks(rub_only: bool = True) -> List[str]:
    """
    Получить список всех торгуемых акций (тикеры)
    
    Args:
        rub_only: Если True, возвращать только российские акции (валюта RUB)
    
    Returns:
        Список тикеров (например, ['SBER', 'GAZP', 'YNDX', ...])
    """
    global _ticker_to_figi_cache
    
    client = await get_tinkoff_client()
    if not client:
        return []
    
    try:
        # Выполняем синхронный вызов в executor для async-совместимости
        loop = asyncio.get_event_loop()
        with client:
            shares = await loop.run_in_executor(None, client.get_all_shares, rub_only)
            
            # Заполняем глобальный кэш тикер -> FIGI для быстрого доступа
            _ticker_to_figi_cache.clear()
            for share in shares:
                ticker = share['ticker'].upper()
                figi = share['figi']
                _ticker_to_figi_cache[ticker] = figi
                # Также сохраняем в кэш клиента для совместимости
                client._instrument_cache[ticker] = share
            
            tickers = [share['ticker'] for share in shares]
            if rub_only:
                logger.info(f"✅ Загружено {len(tickers)} российских акций (RUB) из Tinkoff, кэш FIGI заполнен")
            else:
                logger.info(f"Loaded {len(tickers)} stock tickers from Tinkoff, FIGI cache filled")
            return tickers
    except Exception as e:
        logger.error(f"Error getting stocks list: {e}", exc_info=True)
        return []


async def fetch_stock_candles(
        ticker: str,
        interval: str,
        limit: Optional[int] = None
) -> List[List]:
    """
    Получить свечи для акции по тикеру (оптимизировано с использованием кэша и семафора)
    
    Args:
        ticker: Тикер акции (например, 'SBER')
        interval: Интервал ('60' = 1H, '240' = 4H, 'D' = 1D)
        limit: Количество свечей
    
    Returns:
        Список свечей в формате Bybit [timestamp_ms, open, high, low, close, volume, turnover]
    """
    global _ticker_to_figi_cache, _tinkoff_semaphore
    
    # Инициализируем семафор при первом вызове (макс 10 параллельных запросов)
    if _tinkoff_semaphore is None:
        _tinkoff_semaphore = asyncio.Semaphore(10)
    
    from config import config
    
    if not config.TINKOFF_INVEST_TOKEN:
        logger.warning(f"TINKOFF_INVEST_TOKEN not configured")
        return []
    
    try:
        ticker_upper = ticker.upper()
        
        # Пробуем получить FIGI из кэша (быстро, без запроса к API)
        figi = _ticker_to_figi_cache.get(ticker_upper)
        
        if not figi:
            # FIGI нет в кэше - ищем через API (fallback, но это должно быть редко)
            async with _tinkoff_semaphore:
                # Создаем новый клиент для этого запроса (безопасно для параллельных запросов)
                temp_client = TinkoffClient(config.TINKOFF_INVEST_TOKEN)
                loop = asyncio.get_event_loop()
                with temp_client:
                    instrument = await loop.run_in_executor(
                        None, 
                        temp_client.find_instrument_by_ticker, 
                        ticker
                    )
                    
                    if not instrument:
                        logger.warning(f"❌ Инструмент не найден: {ticker}")
                        return []
                    
                    figi = instrument['figi']
                    # Сохраняем в кэш для следующих разов
                    _ticker_to_figi_cache[ticker_upper] = figi
        
        # Получаем свечи (асинхронно, с ограничением через семафор)
        # Создаем новый клиент для каждого запроса (gRPC клиент не потокобезопасен)
        async with _tinkoff_semaphore:
            temp_client = TinkoffClient(config.TINKOFF_INVEST_TOKEN)
            loop = asyncio.get_event_loop()
            with temp_client:
                candles = await loop.run_in_executor(
                    None,
                    temp_client.get_candles,
                    figi,
                    interval,
                    limit
                )
                
                if not candles:
                    logger.debug(f"⚠️ Свечи не загружены для {ticker} ({interval})")
                
                return candles
            
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки свечей для {ticker}: {e}", exc_info=True)
        return []


async def fetch_moex_index_candles(
        interval: str,
        limit: Optional[int] = None
) -> List[List]:
    """
    Получить свечи для индекса MOEX - индекс Московской биржи
    
    Args:
        interval: Интервал ('60' = 1H, '240' = 4H, 'D' = 1D)
        limit: Количество свечей
    
    Returns:
        Список свечей в формате Bybit [timestamp_ms, open, high, low, close, volume, turnover]
    """
    # Пробуем разные варианты тикера индекса MOEX (MOEX - основной тикер)
    moex_tickers = ['MOEX', 'IMOEX', 'INDEXMX']
    
    logger.info(f"Loading MOEX index candles (interval={interval}, limit={limit})")
    
    for ticker in moex_tickers:
        try:
            logger.debug(f"Trying to load MOEX candles with ticker: {ticker}")
            candles = await fetch_stock_candles(ticker, interval, limit)
            if candles:
                logger.info(f"✅ Successfully loaded MOEX candles using ticker {ticker}: {len(candles)} candles")
                return candles
        except Exception as e:
            logger.debug(f"Failed to load MOEX with ticker {ticker}: {e}")
            continue
    
    logger.warning("❌ Failed to load MOEX index candles with any ticker: MOEX, IMOEX, INDEXMX")
    return []
