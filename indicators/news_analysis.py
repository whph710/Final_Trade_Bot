"""
News Analysis Module
Файл: indicators/news_analysis.py

Модуль для поиска и анализа новостей по активам с помощью ИИ
"""

import logging
from typing import Dict, Optional
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


async def analyze_news(symbol: str, asset_type: str = 'auto') -> Dict:
    """
    Поиск и анализ новостей по активу за последние 72 часа (3 дня)
    
    Для swing trading на 1H/4H таймфреймах требуется более широкий контекст новостей.
    
    Args:
        symbol: Тикер актива (например, 'BTCUSDT', 'TSLA', 'DOGEUSDT', 'SBER')
        asset_type: Тип актива ('crypto', 'stock', 'auto'). Если 'auto', определяется автоматически
    
    Returns:
        Dict с ключами:
            - news_summary: str - Краткая сводка новостей
            - news_found: bool - Найдены ли новости
            - related_entities: List[str] - Связанные сущности (компании, личности)
            - timestamp: str - Время анализа
    """
    from ai.ai_router import AIRouter
    from ai.deepseek_client import load_prompt_cached
    from config import config
    
    try:
        logger.info(f"🔍 News analysis: Starting search for {symbol}")
        
        # Определяем тип актива
        if asset_type == 'auto':
            from utils.asset_detector import AssetTypeDetector
            asset_type = AssetTypeDetector.detect(symbol)
        
        logger.debug(f"News analysis: Asset type detected: {asset_type} for {symbol}")
        
        # Извлекаем базовый тикер (убираем USDT, USD и т.д.)
        base_symbol = _extract_base_symbol(symbol)
        logger.debug(f"News analysis: Base symbol extracted: {base_symbol} from {symbol}")
        
        # Загружаем соответствующий промпт
        if asset_type == 'stock':
            try:
                prompt_template = load_prompt_cached("prompt_news_stocks.txt")
                logger.debug("News analysis: Stock news prompt loaded successfully")
            except FileNotFoundError:
                logger.warning("Stock news prompt not found, using fallback")
                prompt_template = _get_fallback_prompt_stocks()
        else:  # crypto
            try:
                prompt_template = load_prompt_cached("prompt_news_crypto.txt")
                logger.debug("News analysis: Crypto news prompt loaded successfully")
            except FileNotFoundError:
                logger.warning("Crypto news prompt not found, using fallback")
                prompt_template = _get_fallback_prompt()
        
        # ✅ UTC время для промпта (72 часа = 3 дня для swing trading на 1H/4H)
        now_utc = datetime.now(timezone.utc)
        date_72h_ago_utc = (now_utc - timedelta(hours=72))
        
        # Формируем промпт с данными о символе и UTC временем
        prompt = prompt_template.format(
            symbol=base_symbol,
            full_symbol=symbol,
            date_start=date_72h_ago_utc.strftime('%Y-%m-%d %H:%M:%S UTC'),
            current_time_utc=now_utc.strftime('%Y-%m-%d %H:%M:%S UTC'),
            hours_period=72
        )
        
        logger.debug(f"News analysis: Prompt prepared for {symbol}")
        
        # Получаем клиент ИИ (используем Stage 3 провайдер для новостей)
        ai_router = AIRouter()
        provider_name, client = await ai_router._get_provider_client('stage3')
        
        if not client:
            logger.warning(f"News analysis: AI client unavailable for {symbol}")
            return _get_empty_news_result()
        
        # Вызываем ИИ для поиска новостей
        stage3_config = ai_router.stage_configs['stage3']
        
        try:
            if provider_name == 'deepseek':
                logger.info(f"🔍 News analysis: Calling DeepSeek API with web search enabled for {symbol}")
                
                # ✅ DeepSeek с веб-поиском
                # DeepSeek автоматически использует веб-поиск если в промпте явно указано
                # Используем явное указание в system message для активации веб-поиска
                if asset_type == 'stock':
                    system_message = (
                        "You are a stock market news analyst with access to web search. "
                        "You MUST perform DEEP, COMPREHENSIVE search of the internet for recent STOCK MARKET news about the given stock. "
                        "Use your web search capabilities to find real-time information from the last 72 hours (3 days). "
                        "CRITICAL: Focus ONLY on stock markets - ignore cryptocurrency, forex, commodities unless directly affecting stocks. "
                        "Search not only for direct news about the stock, but also for: "
                        "1) News about correlated markets (sector ETFs, S&P 500, NASDAQ), "
                        "2) News about inverse-correlated assets (bonds, VIX, safe havens), "
                        "3) Market-wide context and sentiment (S&P 500, sector trends, economic indicators), "
                        "4) Sector-specific trends and industry dynamics. "
                        "This is for stock swing trading analysis, so focus on news that affects medium-term stock price movements. "
                        "Do NOT rely on your training data - actively search the web for current stock market news. "
                        "Do NOT be superficial - perform deep analysis of how news affects the stock and related markets. "
                        "Respond in English language as most stock market news sources are in English."
                    )
                else:  # crypto
                    system_message = (
                        "You are a cryptocurrency news analyst with access to web search. "
                        "You MUST perform DEEP, COMPREHENSIVE search of the internet for recent CRYPTOCURRENCY news about the given crypto asset. "
                        "Use your web search capabilities to find real-time information from the last 72 hours (3 days). "
                        "CRITICAL: Focus ONLY on cryptocurrency markets - ignore stocks, forex, commodities unless directly affecting crypto. "
                        "Search not only for direct news about the crypto asset, but also for: "
                        "1) News about correlated crypto assets (that move together, e.g., BTC for alts, ETH for DeFi tokens), "
                        "2) News about inverse-correlated assets (that move opposite, e.g., DXY for crypto), "
                        "3) Crypto market-wide context and sentiment (BTC dominance, overall market trend), "
                        "4) Cryptocurrency sector trends (DeFi, Layer 2, institutional adoption, regulatory clarity). "
                        "This is for cryptocurrency swing trading analysis, so focus on news that affects medium-term crypto price movements. "
                        "Do NOT rely on your training data - actively search the web for current cryptocurrency news. "
                        "Do NOT be superficial - perform deep analysis of how news affects the crypto asset and related crypto markets. "
                        "Respond in English language as most cryptocurrency news sources are in English."
                    )
                
                response = await client.client.chat.completions.create(
                    model=client.model,
                    messages=[
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.7,
                    max_tokens=1500
                )
                
                news_text = response.choices[0].message.content.strip()
                logger.debug(f"News analysis: Response received for {symbol} ({len(news_text)} chars)")
                
            elif provider_name == 'claude':
                # Claude использует свой API
                news_text = await client.call(
                    prompt=prompt,
                    max_tokens=1500,
                    temperature=0.7,
                    timeout=60  # Увеличиваем timeout для поиска в интернете
                )
                news_text = news_text.strip() if news_text else ""
            else:
                logger.warning(f"News analysis: Unknown provider {provider_name}")
                return _get_empty_news_result()
        except Exception as e:
            logger.error(f"News analysis: AI call failed for {symbol}: {e}")
            return _get_empty_news_result()
        
        # Парсим результат
        result = _parse_news_response(news_text, symbol)
        
        logger.debug(f"News analysis: {symbol} - found={result['news_found']}")
        
        return result
        
    except Exception as e:
        logger.error(f"News analysis error for {symbol}: {e}", exc_info=True)
        return _get_empty_news_result()


def _extract_base_symbol(symbol: str) -> str:
    """
    Извлечь базовый тикер из символа
    
    Примеры:
        BTCUSDT -> BTC
        ETHUSDT -> ETH
        TSLA -> TSLA
        DOGEUSDT -> DOGE
    """
    # Убираем суффиксы валютных пар
    suffixes = ['USDT', 'USD', 'EUR', 'GBP', 'JPY', 'CNY', 'BUSD', 'USDC']
    
    for suffix in suffixes:
        if symbol.endswith(suffix):
            return symbol[:-len(suffix)]
    
    return symbol


def _parse_news_response(response_text: str, symbol: str) -> Dict:
    """
    Парсить ответ ИИ и извлечь структурированные данные
    
    Args:
        response_text: Текст ответа от ИИ
        symbol: Символ актива
    
    Returns:
        Dict с результатами анализа
    """
    if not response_text or len(response_text.strip()) < 50:
        return _get_empty_news_result()
    
    # Извлекаем связанные сущности (если упомянуты)
    related_entities = _extract_related_entities(response_text)
    
    # Проверяем, есть ли полезная информация
    # Если ответ слишком короткий или содержит только "не найдено", возвращаем пустой результат
    lower_text = response_text.lower()
    if any(phrase in lower_text for phrase in [
        'не найдено', 'not found', 'no news', 'нет новостей',
        'не удалось найти', 'could not find'
    ]) and len(response_text) < 100:
        return _get_empty_news_result()
    
    return {
        'news_summary': response_text.strip(),
        'news_found': True,
        'related_entities': related_entities,
        'timestamp': datetime.now().isoformat(),
        'symbol': symbol
    }


def _extract_related_entities(text: str) -> list:
    """
    Извлечь связанные сущности из текста новостей
    
    Ищет упоминания известных компаний, личностей, связанных с активом
    """
    # Список известных связанных сущностей
    known_entities = [
        'Elon Musk', 'SpaceX', 'Tesla', 'TSLA',
        'Michael Saylor', 'MicroStrategy', 'MSTR',
        'Grayscale', 'GBTC',
        'BlackRock', 'IBIT',
        'Coinbase', 'COIN',
        'Binance', 'CZ',
        'SEC', 'CFTC', 'FED', 'Federal Reserve',
        'China', 'Chinese', 'Korea', 'South Korea',
        'Bitcoin ETF', 'BTC ETF', 'Ethereum ETF', 'ETH ETF'
    ]
    
    found_entities = []
    text_lower = text.lower()
    
    for entity in known_entities:
        if entity.lower() in text_lower:
            found_entities.append(entity)
    
    return list(set(found_entities))  # Убираем дубликаты


def _get_empty_news_result() -> Dict:
    """Возвратить пустой результат анализа новостей"""
    return {
        'news_summary': '',
        'news_found': False,
        'related_entities': [],
        'timestamp': datetime.now().isoformat()
    }


# Используем централизованный детектор
# Функция удалена, используйте utils.asset_detector.AssetTypeDetector


def _get_fallback_prompt() -> str:
    """Fallback prompt if file not found - cryptocurrency only"""
    return """Find all recent cryptocurrency news from the last 72 hours (3 days) regarding crypto asset {symbol} ({full_symbol}) on the internet.

IMPORTANT:
- Focus ONLY on cryptocurrency markets - ignore stocks, forex, commodities
- Search for news that may affect medium-term crypto price movements (swing trading on 1H/4H)
- Consider indirect connections (e.g., for DOGE - mentions of Elon Musk, for BTC - mentions of Tesla, MicroStrategy, Bitcoin ETF)
- Search for news about correlated crypto assets (BTC for alts, ETH for DeFi tokens)
- Provide a brief summary (3-6 sentences), concise but without losing the essence
- If no news found, write "No cryptocurrency news found"

Response format: Only summary text, without additional explanations. Use English language. Focus on cryptocurrency markets only."""


def _get_fallback_prompt_stocks() -> str:
    """Fallback prompt if file not found - stocks only"""
    return """Find all recent stock market news from the last 72 hours (3 days) regarding stock {symbol} ({full_symbol}) on the internet.

IMPORTANT:
- Focus ONLY on stock markets - ignore cryptocurrency, forex, commodities
- Search for news that may affect medium-term stock price movements (swing trading on 1H/4H)
- Consider indirect connections (earnings, corporate actions, analyst ratings, sector trends)
- Search for news about correlated markets (sector ETFs, S&P 500, bonds, VIX)
- Provide a brief summary (3-6 sentences), concise but without losing the essence
- If no news found, write "No stock market news found"

Response format: Only summary text, without additional explanations. Use English language. Focus on stock markets only."""

