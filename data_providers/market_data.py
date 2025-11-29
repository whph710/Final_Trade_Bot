"""
Market Data Collector
Файл: data_providers/market_data.py

Сбор дополнительных рыночных данных: funding rate, open interest, orderbook
"""

import aiohttp
import asyncio
import logging
from typing import Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class MarketDataCollector:
    """Сборщик рыночных данных с Bybit"""

    def __init__(self, session: aiohttp.ClientSession):
        """
        Args:
            session: Aiohttp сессия (получить через bybit_client.get_session())
        """
        self.session = session
        self.base_url = "https://api.bybit.com"

    async def get_funding_rate(self, symbol: str) -> Optional[Dict]:
        """
        Получить текущий funding rate

        Args:
            symbol: Торговая пара

        Returns:
            {
                'funding_rate': float,
                'funding_rate_timestamp': str,
                'symbol': str
            }
            None при ошибке
        """
        try:
            params = {
                "category": "linear",
                "symbol": symbol
            }

            async with self.session.get(
                    f"{self.base_url}/v5/market/funding/history",
                    params=params
            ) as response:

                if response.status != 200:
                    return None

                data = await response.json()

                if data.get("retCode") != 0:
                    return None

                result_list = data.get("result", {}).get("list", [])
                if not result_list:
                    return None

                latest = result_list[0]

                return {
                    'funding_rate': float(latest.get('fundingRate', 0)),
                    'funding_rate_timestamp': latest.get('fundingRateTimestamp'),
                    'symbol': symbol
                }

        except Exception as e:
            logger.debug(f"Error getting funding rate for {symbol}: {e}")
            return None

    async def get_open_interest(
            self,
            symbol: str,
            interval: str = "1h"
    ) -> Optional[Dict]:
        """
        Получить Open Interest

        Args:
            symbol: Торговая пара
            interval: Интервал ('1h', '4h', '1d')

        Returns:
            {
                'open_interest': float,
                'oi_change_24h': float (в процентах),
                'oi_trend': 'GROWING' | 'DECLINING' | 'STABLE',
                'symbol': str
            }
            None при ошибке
        """
        try:
            params = {
                "category": "linear",
                "symbol": symbol,
                "intervalTime": interval,
                "limit": 24
            }

            async with self.session.get(
                    f"{self.base_url}/v5/market/open-interest",
                    params=params
            ) as response:

                if response.status != 200:
                    return None

                data = await response.json()

                if data.get("retCode") != 0:
                    return None

                result_list = data.get("result", {}).get("list", [])
                if len(result_list) < 2:
                    return None

                current_oi = float(result_list[0].get('openInterest', 0))
                old_oi = float(result_list[-1].get('openInterest', 0))

                if old_oi > 0:
                    oi_change = ((current_oi - old_oi) / old_oi) * 100
                else:
                    oi_change = 0

                # Определяем тренд (используем пороги из config)
                if oi_change > 2.0:
                    trend = 'GROWING'
                elif oi_change < -2.0:
                    trend = 'DECLINING'
                else:
                    trend = 'STABLE'

                return {
                    'open_interest': current_oi,
                    'oi_change_24h': round(oi_change, 2),
                    'oi_trend': trend,
                    'symbol': symbol
                }

        except Exception as e:
            logger.debug(f"Error getting OI for {symbol}: {e}")
            return None

    async def get_orderbook(
            self,
            symbol: str,
            depth: int = 50
    ) -> Optional[Dict]:
        """
        Получить Order Book (стакан)

        Args:
            symbol: Торговая пара
            depth: Глубина стакана (макс 200)

        Returns:
            {
                'bids': [[price, size], ...],
                'asks': [[price, size], ...],
                'best_bid': float,
                'best_ask': float,
                'mid_price': float,
                'spread': float,
                'spread_pct': float,
                'symbol': str
            }
            None при ошибке
        """
        try:
            params = {
                "category": "linear",
                "symbol": symbol,
                "limit": depth
            }

            async with self.session.get(
                    f"{self.base_url}/v5/market/orderbook",
                    params=params
            ) as response:

                if response.status != 200:
                    return None

                data = await response.json()

                if data.get("retCode") != 0:
                    return None

                result = data.get("result", {})

                raw_bids = [[float(p), float(s)] for p, s in result.get('b', [])]
                raw_asks = [[float(p), float(s)] for p, s in result.get('a', [])]

                if not raw_bids or not raw_asks:
                    return None

                best_bid = raw_bids[0][0]
                best_ask = raw_asks[0][0]
                mid_price = (best_bid + best_ask) / 2
                spread = best_ask - best_bid
                spread_pct = (spread / mid_price) * 100

                return {
                    'bids': raw_bids,
                    'asks': raw_asks,
                    'best_bid': best_bid,
                    'best_ask': best_ask,
                    'mid_price': mid_price,
                    'spread': spread,
                    'spread_pct': round(spread_pct, 4),
                    'symbol': symbol
                }

        except Exception as e:
            logger.debug(f"Error getting orderbook for {symbol}: {e}")
            return None


async def get_market_snapshot(
        symbol: str,
        session: aiohttp.ClientSession
) -> Dict:
    """
    Получить snapshot всех рыночных данных для символа

    Args:
        symbol: Торговая пара
        session: Aiohttp сессия

    Returns:
        {
            'symbol': str,
            'funding_rate': Dict или None,
            'open_interest': Dict или None,
            'orderbook': Dict или None,
            'timestamp': str
        }
    """
    collector = MarketDataCollector(session)

    # Параллельно получаем все данные
    tasks = [
        collector.get_funding_rate(symbol),
        collector.get_open_interest(symbol),
        collector.get_orderbook(symbol)
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    funding, oi, orderbook = results

    return {
        'symbol': symbol,
        'funding_rate': funding if isinstance(funding, dict) else None,
        'open_interest': oi if isinstance(oi, dict) else None,
        'orderbook': orderbook if isinstance(orderbook, dict) else None,
        'timestamp': datetime.now().isoformat()
    }