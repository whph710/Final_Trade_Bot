"""
Signal Storage Manager
Файл: utils/signal_storage.py

Сохранение сигналов в signals/ и загрузка для backtesting
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import asdict

logger = logging.getLogger(__name__)


class SignalStorage:
    """Управление сохранением сигналов"""

    def __init__(self, signals_dir: Path = None):
        """
        Args:
            signals_dir: Path к директории signals/ (по умолчанию из config)
        """
        if signals_dir is None:
            try:
                from config import config
                self.signals_dir = config.SIGNALS_DIR
            except:
                self.signals_dir = Path("signals")

        self.signals_dir.mkdir(exist_ok=True)

        logger.info(f"Signal storage initialized: {self.signals_dir}")

    def save_signal(self, signal: 'TradingSignal') -> Optional[Path]:
        """
        Сохранить сигнал в JSON файл

        Args:
            signal: TradingSignal объект

        Returns:
            Path к сохранённому файлу или None при ошибке
        """
        try:
            # Формируем имя файла: signal_YYYYMMDD_HHMMSS_SYMBOL.json
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"signal_{timestamp}_{signal.symbol}.json"
            filepath = self.signals_dir / filename

            # Конвертируем в dict
            signal_dict = self._signal_to_dict(signal)

            # Сохраняем
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(signal_dict, f, indent=2, ensure_ascii=False)

            logger.info(f"Signal saved: {filepath.name}")
            return filepath

        except Exception as e:
            logger.error(f"Error saving signal {signal.symbol}: {e}")
            return None

    def save_signals_batch(self, signals: List['TradingSignal']) -> int:
        """
        Сохранить batch сигналов

        Args:
            signals: Список TradingSignal объектов

        Returns:
            Количество сохранённых сигналов
        """
        saved_count = 0

        for signal in signals:
            if self.save_signal(signal):
                saved_count += 1

        logger.info(f"Batch save: {saved_count}/{len(signals)} signals saved")
        return saved_count

    def load_signals(
            self,
            from_date: Optional[datetime] = None,
            to_date: Optional[datetime] = None,
            symbol: Optional[str] = None
    ) -> List[Dict]:
        """
        Загрузить сигналы для backtesting

        Args:
            from_date: Начальная дата (опционально)
            to_date: Конечная дата (опционально)
            symbol: Фильтр по символу (опционально)

        Returns:
            Список сигналов в виде словарей
        """
        signals = []

        try:
            # Находим все JSON файлы сигналов
            signal_files = sorted(self.signals_dir.glob('signal_*.json'))

            logger.info(f"Found {len(signal_files)} signal files")

            for filepath in signal_files:
                try:
                    # Загружаем сигнал
                    with open(filepath, 'r', encoding='utf-8') as f:
                        signal_data = json.load(f)

                    # Фильтр по символу
                    if symbol and signal_data.get('symbol') != symbol:
                        continue

                    # Фильтр по датам
                    signal_time = datetime.fromisoformat(signal_data.get('timestamp', ''))

                    if from_date and signal_time < from_date:
                        continue

                    if to_date and signal_time > to_date:
                        continue

                    signals.append(signal_data)

                except Exception as e:
                    logger.debug(f"Error loading {filepath.name}: {e}")
                    continue

            logger.info(f"Loaded {len(signals)} signals for backtest")
            return signals

        except Exception as e:
            logger.error(f"Error loading signals: {e}")
            return []

    def _signal_to_dict(self, signal: 'TradingSignal') -> Dict:
        """
        Конвертировать TradingSignal в dict для JSON

        Args:
            signal: TradingSignal объект

        Returns:
            Dict готовый для сериализации
        """
        from dataclasses import is_dataclass

        # Базовые поля
        signal_dict = {
            'symbol': signal.symbol,
            'signal': signal.signal,
            'confidence': signal.confidence,
            'entry_price': signal.entry_price,
            'stop_loss': signal.stop_loss,
            'take_profit_levels': signal.take_profit_levels,
            'risk_reward_ratio': signal.risk_reward_ratio,
            'analysis': signal.analysis,
            'timestamp': signal.timestamp
        }

        # Comprehensive data (упрощённая версия для хранения)
        comprehensive = signal.comprehensive_data or {}

        signal_dict['comprehensive_data'] = {
            'current_price': comprehensive.get('current_price', 0),
            'indicators_1h': self._simplify_indicators(comprehensive.get('indicators_1h')),
            'indicators_4h': self._simplify_indicators(comprehensive.get('indicators_4h')),
            'market_data': self._simplify_market_data(comprehensive.get('market_data')),
            'correlation': self._simplify_correlation(comprehensive.get('correlation_data')),
            'volume_profile': self._simplify_volume_profile(comprehensive.get('volume_profile'))
        }

        return signal_dict

    def _simplify_indicators(self, indicators: Optional[Dict]) -> Dict:
        """Упростить indicators для хранения (только current)"""
        if not indicators or not isinstance(indicators, dict):
            return {}

        current = indicators.get('current', {})

        return {
            'price': current.get('price', 0),
            'ema9': current.get('ema9', 0),
            'ema21': current.get('ema21', 0),
            'ema50': current.get('ema50', 0),
            'rsi': current.get('rsi', 0),
            'volume_ratio': current.get('volume_ratio', 0)
        }

    def _simplify_market_data(self, market_data: Optional[Dict]) -> Dict:
        """Упростить market data"""
        if not market_data or not isinstance(market_data, dict):
            return {}

        funding = market_data.get('funding_rate', {})
        oi = market_data.get('open_interest', {})
        orderbook = market_data.get('orderbook', {})

        return {
            'funding_rate': funding.get('funding_rate', 0) if funding else 0,
            'oi_change_24h': oi.get('oi_change_24h', 0) if oi else 0,
            'spread_pct': orderbook.get('spread_pct', 0) if orderbook else 0
        }

    def _simplify_correlation(self, correlation: Optional[Dict]) -> Dict:
        """Упростить correlation data"""
        if not correlation or not isinstance(correlation, dict):
            return {}

        btc_corr = correlation.get('btc_correlation', {})

        if hasattr(btc_corr, '__dict__'):
            # Dataclass
            return {
                'correlation': btc_corr.correlation,
                'should_block': btc_corr.should_block
            }
        elif isinstance(btc_corr, dict):
            return {
                'correlation': btc_corr.get('correlation', 0),
                'should_block': btc_corr.get('should_block', False)
            }

        return {}

    def _simplify_volume_profile(self, vp_data) -> Dict:
        """Упростить volume profile"""
        if not vp_data:
            return {}

        if hasattr(vp_data, '__dict__'):
            # Dataclass
            return {
                'poc': vp_data.poc,
                'value_area_high': vp_data.value_area_high,
                'value_area_low': vp_data.value_area_low
            }
        elif isinstance(vp_data, dict):
            return {
                'poc': vp_data.get('poc', 0),
                'value_area_high': vp_data.get('value_area_high', 0),
                'value_area_low': vp_data.get('value_area_low', 0)
            }

        return {}


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================
_signal_storage = None


def get_signal_storage() -> SignalStorage:
    """Получить singleton instance SignalStorage"""
    global _signal_storage

    if _signal_storage is None:
        _signal_storage = SignalStorage()

    return _signal_storage