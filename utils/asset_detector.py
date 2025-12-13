"""
Asset Type Detector
Файл: utils/asset_detector.py

Централизованное определение типа актива (crypto/stock)
"""

import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class AssetTypeDetector:
    """Детектор типа актива"""
    
    # Суффиксы криптовалют
    CRYPTO_SUFFIXES = ['USDT', 'BUSD', 'USDC', 'USD', 'EUR', 'GBP', 'JPY', 'CNY']
    
    # Известные тикеры акций (можно расширить)
    KNOWN_STOCKS = set()  # Можно добавить список известных акций
    
    @classmethod
    def detect(cls, symbol: str) -> str:
        """
        Определить тип актива по символу
        
        Args:
            symbol: Тикер актива (например, 'BTCUSDT', 'SBER')
        
        Returns:
            'crypto' или 'stock'
        """
        symbol_upper = symbol.upper()
        
        # Проверяем суффиксы криптовалют
        for suffix in cls.CRYPTO_SUFFIXES:
            if symbol_upper.endswith(suffix):
                return 'crypto'
        
        # По умолчанию считаем акцией
        return 'stock'
    
    @classmethod
    def detect_batch(cls, symbols: List[str]) -> Dict[str, str]:
        """
        Определить типы активов для списка символов
        
        Args:
            symbols: Список тикеров
        
        Returns:
            Dict {symbol: asset_type}
        """
        return {symbol: cls.detect(symbol) for symbol in symbols}
    
    @classmethod
    def group_by_type(cls, symbols: List[str]) -> Dict[str, List[str]]:
        """
        Сгруппировать символы по типу актива
        
        Args:
            symbols: Список тикеров
        
        Returns:
            {'crypto': [...], 'stock': [...]}
        """
        grouped = {'crypto': [], 'stock': []}
        
        for symbol in symbols:
            asset_type = cls.detect(symbol)
            grouped[asset_type].append(symbol)
        
        return grouped
