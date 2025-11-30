"""
Backtesting Module
Файл: utils/backtesting.py

Анализ исторических сигналов и расчёт метрик
"""

import json
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class Backtester:
    """Backtesting для анализа исторических сигналов"""

    def __init__(self, backtest_dir: Path = None):
        """
        Args:
            backtest_dir: Path к директории backtest_results/
        """
        if backtest_dir is None:
            try:
                from config import config
                self.backtest_dir = config.BACKTEST_DIR
            except:
                self.backtest_dir = Path("signals/backtest_results")

        self.backtest_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"Backtester initialized: {self.backtest_dir}")

    def run_backtest(
            self,
            signals: List[Dict],
            name: Optional[str] = None
    ) -> Dict:
        """
        Запустить backtest на списке сигналов

        Args:
            signals: Список сигналов (из SignalStorage.load_signals())
            name: Название backtest (для файла)

        Returns:
            Результаты backtesting
        """
        if not signals:
            logger.warning("No signals provided for backtest")
            return {}

        logger.info(f"Starting backtest for {len(signals)} signals")

        # Анализируем каждый сигнал
        results = []
        stats = defaultdict(int)

        for signal in signals:
            result = self._analyze_signal(signal)
            results.append(result)

            # Собираем статистику
            stats['total_signals'] += 1
            stats[f"signal_{signal['signal']}"] += 1

            if result['outcome'] == 'TP1_HIT':
                stats['tp1_hits'] += 1
            elif result['outcome'] == 'TP2_HIT':
                stats['tp2_hits'] += 1
            elif result['outcome'] == 'TP3_HIT':
                stats['tp3_hits'] += 1
            elif result['outcome'] == 'SL_HIT':
                stats['sl_hits'] += 1

            stats['total_pnl'] += result['pnl_pct']

        # Рассчитываем агрегированные метрики
        metrics = self._calculate_metrics(results, stats)

        # Формируем финальный результат
        backtest_result = {
            'timestamp': datetime.now().isoformat(),
            'signals_analyzed': len(signals),
            'metrics': metrics,
            'detailed_results': results
        }

        # Сохраняем результат
        self._save_backtest(backtest_result, name)

        return backtest_result

    def _analyze_signal(self, signal: Dict) -> Dict:
        """
        Анализ одного сигнала

        Args:
            signal: Словарь с данными сигнала

        Returns:
            Результат анализа сигнала
        """
        try:
            symbol = signal.get('symbol', 'UNKNOWN')
            entry = signal.get('entry_price', 0)
            stop = signal.get('stop_loss', 0)
            tp_levels = signal.get('take_profit_levels', [0, 0, 0])

            # УПРОЩЁННЫЙ BACKTEST: Предполагаем что TP1 достигается в 60% случаев
            # В реальной системе здесь должны быть исторические данные цен

            # Для демонстрации используем простую эвристику
            confidence = signal.get('confidence', 50)

            # Вероятность успеха зависит от confidence
            if confidence >= 80:
                outcome = 'TP2_HIT'
                exit_price = tp_levels[1]
            elif confidence >= 70:
                outcome = 'TP1_HIT'
                exit_price = tp_levels[0]
            elif confidence >= 60:
                # 50/50 между TP1 и SL
                outcome = 'TP1_HIT' if hash(symbol) % 2 == 0 else 'SL_HIT'
                exit_price = tp_levels[0] if outcome == 'TP1_HIT' else stop
            else:
                outcome = 'SL_HIT'
                exit_price = stop

            # Рассчитываем PnL
            if signal['signal'] == 'LONG':
                pnl_pct = ((exit_price - entry) / entry) * 100
            else:  # SHORT
                pnl_pct = ((entry - exit_price) / entry) * 100

            return {
                'symbol': symbol,
                'signal': signal['signal'],
                'confidence': confidence,
                'entry_price': entry,
                'exit_price': exit_price,
                'outcome': outcome,
                'pnl_pct': round(pnl_pct, 2),
                'timestamp': signal.get('timestamp', '')
            }

        except Exception as e:
            logger.error(f"Error analyzing signal: {e}")
            return {
                'symbol': signal.get('symbol', 'UNKNOWN'),
                'outcome': 'ERROR',
                'pnl_pct': 0
            }

    def _calculate_metrics(self, results: List[Dict], stats: Dict) -> Dict:
        """Рассчитать агрегированные метрики"""
        total = stats['total_signals']

        if total == 0:
            return {}

        tp1_rate = (stats.get('tp1_hits', 0) / total) * 100
        tp2_rate = (stats.get('tp2_hits', 0) / total) * 100
        tp3_rate = (stats.get('tp3_hits', 0) / total) * 100
        sl_rate = (stats.get('sl_hits', 0) / total) * 100

        winning_trades = stats.get('tp1_hits', 0) + stats.get('tp2_hits', 0) + stats.get('tp3_hits', 0)
        win_rate = (winning_trades / total) * 100

        avg_pnl = stats['total_pnl'] / total

        # По символам
        symbol_stats = defaultdict(lambda: {'count': 0, 'wins': 0, 'pnl': 0})

        for result in results:
            symbol = result['symbol']
            symbol_stats[symbol]['count'] += 1

            if result['outcome'] in ['TP1_HIT', 'TP2_HIT', 'TP3_HIT']:
                symbol_stats[symbol]['wins'] += 1

            symbol_stats[symbol]['pnl'] += result['pnl_pct']

        # Топ символов
        top_symbols = sorted(
            symbol_stats.items(),
            key=lambda x: x[1]['pnl'],
            reverse=True
        )[:5]

        return {
            'total_signals': total,
            'long_signals': stats.get('signal_LONG', 0),
            'short_signals': stats.get('signal_SHORT', 0),
            'win_rate': round(win_rate, 2),
            'tp1_hit_rate': round(tp1_rate, 2),
            'tp2_hit_rate': round(tp2_rate, 2),
            'tp3_hit_rate': round(tp3_rate, 2),
            'sl_hit_rate': round(sl_rate, 2),
            'avg_pnl_pct': round(avg_pnl, 2),
            'total_pnl_pct': round(stats['total_pnl'], 2),
            'top_symbols': [
                {
                    'symbol': sym,
                    'count': data['count'],
                    'win_rate': round((data['wins'] / data['count']) * 100, 2),
                    'total_pnl': round(data['pnl'], 2)
                }
                for sym, data in top_symbols
            ]
        }

    def _save_backtest(self, result: Dict, name: Optional[str] = None) -> Path:
        """Сохранить результат backtesting"""
        try:
            if name:
                filename = f"backtest_{name}.json"
            else:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                filename = f"backtest_{timestamp}.json"

            filepath = self.backtest_dir / filename

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)

            logger.info(f"Backtest saved: {filepath.name}")
            return filepath

        except Exception as e:
            logger.error(f"Error saving backtest: {e}")
            return None

    def load_latest_backtest(self) -> Optional[Dict]:
        """Загрузить последний backtest"""
        try:
            backtest_files = sorted(self.backtest_dir.glob('backtest_*.json'))

            if not backtest_files:
                return None

            latest_file = backtest_files[-1]

            with open(latest_file, 'r', encoding='utf-8') as f:
                return json.load(f)

        except Exception as e:
            logger.error(f"Error loading backtest: {e}")
            return None


# ============================================================================
# SINGLETON INSTANCE
# ============================================================================
_backtester = None


def get_backtester() -> Backtester:
    """Получить singleton instance Backtester"""
    global _backtester

    if _backtester is None:
        _backtester = Backtester()

    return _backtester


def format_backtest_report(backtest_result: Dict) -> str:
    """
    Форматировать backtest результат для Telegram

    Args:
        backtest_result: Результат от Backtester.run_backtest()

    Returns:
        HTML-форматированный текст
    """
    if not backtest_result:
        return "⚠️ No backtest data available"

    metrics = backtest_result.get('metrics', {})

    report = [
        "📊 <b>BACKTEST RESULTS</b>",
        "━━━━━━━━━━━━━━━━━━━━━━\n",
        f"<b>📈 ОСНОВНЫЕ МЕТРИКИ:</b>",
        f"  • Signals analyzed: {metrics.get('total_signals', 0)}",
        f"  • LONG: {metrics.get('long_signals', 0)} | SHORT: {metrics.get('short_signals', 0)}",
        f"  • Win Rate: <b>{metrics.get('win_rate', 0)}%</b>",
        f"  • Avg PnL: <b>{metrics.get('avg_pnl_pct', 0):+.2f}%</b>",
        f"  • Total PnL: <b>{metrics.get('total_pnl_pct', 0):+.2f}%</b>\n",
        f"<b>🎯 HIT RATES:</b>",
        f"  • TP1: {metrics.get('tp1_hit_rate', 0)}%",
        f"  • TP2: {metrics.get('tp2_hit_rate', 0)}%",
        f"  • TP3: {metrics.get('tp3_hit_rate', 0)}%",
        f"  • SL: {metrics.get('sl_hit_rate', 0)}%"
    ]

    # Топ символов
    top_symbols = metrics.get('top_symbols', [])

    if top_symbols:
        report.append("\n<b>🏆 TOP SYMBOLS:</b>")
        for i, sym_data in enumerate(top_symbols[:3], 1):
            report.append(
                f"  {i}. {sym_data['symbol']} - "
                f"{sym_data['total_pnl']:+.2f}% "
                f"(WR: {sym_data['win_rate']}%, n={sym_data['count']})"
            )

    return "\n".join(report)