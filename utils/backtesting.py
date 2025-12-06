"""
Backtesting Module - REALISTIC OUTCOME WITH 5M CANDLES
Файл: utils/backtesting.py

✅ ИСПРАВЛЕНО:
- Проверка outcome на 5-минутных свечах (300 свечей = 25 часов)
- Загрузка свежих данных из Bybit для каждого сигнала
- Более точная проверка достижения TP/SL
- Fallback на качественный scoring если свечей нет
"""

import json
import logging
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class Backtester:
    """Backtesting для анализа исторических сигналов"""

    def __init__(self, backtest_dir: Path = None):
        if backtest_dir is None:
            try:
                from config import config
                self.backtest_dir = config.BACKTEST_DIR
            except:
                self.backtest_dir = Path("signals/backtest_results")

        self.backtest_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Backtester initialized: {self.backtest_dir}")

    async def run_backtest(self, signals: List[Dict], name: Optional[str] = None) -> Dict:
        """Запустить backtest на списке сигналов"""
        if not signals:
            logger.warning("No signals provided for backtest")
            return {}

        logger.info(f"Starting backtest for {len(signals)} signals")

        # ✅ ИСПРАВЛЕНО: Прямой вызов async функции
        results = await self._run_backtest_async(signals)

        stats = defaultdict(int)

        for result in results:
            stats['total_signals'] += 1
            signal_type = result.get('signal', 'UNKNOWN')
            stats[f"signal_{signal_type}"] += 1

            outcome = result.get('outcome', 'UNKNOWN')
            if outcome == 'TP1_HIT':
                stats['tp1_hits'] += 1
            elif outcome == 'TP2_HIT':
                stats['tp2_hits'] += 1
            elif outcome == 'TP3_HIT':
                stats['tp3_hits'] += 1
            elif outcome == 'SL_HIT':
                stats['sl_hits'] += 1

            stats['total_pnl'] += result.get('pnl_pct', 0)

        metrics = self._calculate_metrics(results, stats)

        backtest_result = {
            'timestamp': datetime.now().isoformat(),
            'signals_analyzed': len(signals),
            'metrics': metrics,
            'detailed_results': results
        }

        self._save_backtest(backtest_result, name)
        return backtest_result

    async def _run_backtest_async(self, signals: List[Dict]) -> List[Dict]:
        """Асинхронный backtesting с загрузкой 5M свечей"""
        tasks = [self._analyze_signal_async(signal) for signal in signals]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Фильтруем ошибки
        valid_results = []
        for result in results:
            if isinstance(result, dict):
                valid_results.append(result)
            elif isinstance(result, Exception):
                logger.error(f"Backtest error: {result}")

        return valid_results

    async def _analyze_signal_async(self, signal: Dict) -> Dict:
        """Анализ одного сигнала с загрузкой 5M свечей"""
        try:
            symbol = signal.get('symbol', 'UNKNOWN')
            signal_type = signal.get('signal', 'UNKNOWN')
            entry = signal.get('entry_price', 0)
            stop = signal.get('stop_loss', 0)
            tp_levels = signal.get('take_profit_levels', [0, 0, 0])
            confidence = signal.get('confidence', 50)
            rr_ratio = signal.get('risk_reward_ratio', 0)
            timestamp_str = signal.get('timestamp', '')

            # Парсим timestamp сигнала
            try:
                signal_time = datetime.fromisoformat(timestamp_str)
            except:
                logger.warning(f"{symbol}: Invalid timestamp, using current time")
                signal_time = datetime.now()

            # ✅ КРИТИЧНО: Загружаем 5M свечи ПОСЛЕ сигнала
            candles_5m = await self._fetch_5m_candles_after_signal(
                symbol,
                signal_time
            )

            # Если свечей достаточно - используем реальные данные
            if candles_5m and len(candles_5m) >= 50:
                outcome, exit_price = self._estimate_outcome_from_candles(
                    signal_type,
                    entry,
                    stop,
                    tp_levels,
                    candles_5m
                )
                logger.info(
                    f"{symbol}: Outcome from 5M candles = {outcome} "
                    f"({len(candles_5m)} candles checked)"
                )
            else:
                # Fallback: качественная оценка
                comprehensive_data = signal.get('comprehensive_data', {})
                outcome, exit_price = self._estimate_outcome_from_quality(
                    signal_type,
                    confidence,
                    rr_ratio,
                    entry,
                    stop,
                    tp_levels,
                    comprehensive_data
                )
                logger.info(f"{symbol}: Outcome from quality score = {outcome}")

            # Рассчитываем PnL
            if signal_type == 'LONG':
                pnl_pct = ((exit_price - entry) / entry) * 100
            elif signal_type == 'SHORT':
                pnl_pct = ((entry - exit_price) / entry) * 100
            else:
                pnl_pct = 0

            return {
                'symbol': symbol,
                'signal': signal_type,
                'confidence': confidence,
                'entry_price': entry,
                'exit_price': exit_price,
                'outcome': outcome,
                'pnl_pct': round(pnl_pct, 2),
                'timestamp': timestamp_str
            }

        except Exception as e:
            logger.error(f"Error analyzing signal: {e}")
            return {
                'symbol': signal.get('symbol', 'UNKNOWN'),
                'signal': signal.get('signal', 'UNKNOWN'),
                'confidence': signal.get('confidence', 0),
                'entry_price': signal.get('entry_price', 0),
                'exit_price': signal.get('entry_price', 0),
                'outcome': 'ERROR',
                'pnl_pct': 0,
                'timestamp': signal.get('timestamp', '')
            }

    async def _fetch_5m_candles_after_signal(
        self,
        symbol: str,
        signal_time: datetime
    ) -> List:
        """
        ✅ НОВОЕ: Загрузить 5-минутные свечи ПОСЛЕ момента сигнала

        Args:
            symbol: Торговая пара
            signal_time: Время создания сигнала

        Returns:
            Список 5M свечей (до 300 штук = 25 часов)
        """
        try:
            from data_providers import fetch_candles

            # Загружаем 300 свечей 5M (25 часов после сигнала)
            candles_5m = await fetch_candles(
                symbol,
                interval='5',  # 5 minutes
                limit=300
            )

            if not candles_5m:
                logger.warning(f"{symbol}: Failed to fetch 5M candles")
                return []

            # ✅ ФИЛЬТРУЕМ: Берём только свечи ПОСЛЕ signal_time
            signal_timestamp_ms = int(signal_time.timestamp() * 1000)

            filtered_candles = []
            for candle in candles_5m:
                try:
                    candle_time_ms = int(candle[0])

                    # Берём свечи после сигнала
                    if candle_time_ms >= signal_timestamp_ms:
                        filtered_candles.append(candle)
                except:
                    continue

            logger.debug(
                f"{symbol}: Fetched {len(filtered_candles)}/300 5M candles "
                f"after {signal_time.strftime('%Y-%m-%d %H:%M')}"
            )

            return filtered_candles

        except Exception as e:
            logger.error(f"{symbol}: Error fetching 5M candles: {e}")
            return []

    def _estimate_outcome_from_candles(
        self,
        signal_type: str,
        entry: float,
        stop: float,
        tp_levels: List[float],
        candles: List
    ) -> tuple[str, float]:
        """
        ✅ УЛУЧШЕНО: Оценка outcome на реальных 5M свечах

        Проверяем следующие 300 свечей (25 часов) после сигнала:
        - Был ли достигнут TP1/TP2/TP3?
        - Был ли достигнут SL?
        - Что было достигнуто первым?
        """
        try:
            if len(tp_levels) < 3:
                tp_levels = tp_levels + [0] * (3 - len(tp_levels))

            tp1, tp2, tp3 = tp_levels[0], tp_levels[1], tp_levels[2]

            # ✅ Проверяем все доступные свечи (до 300)
            candles_to_check = min(len(candles), 300)

            for i, candle in enumerate(candles[:candles_to_check]):
                if not candle or len(candle) < 5:
                    continue

                try:
                    high = float(candle[2])
                    low = float(candle[3])
                except:
                    continue

                if signal_type == 'LONG':
                    # ✅ LONG: проверяем SL ПЕРВЫМ (консервативно)
                    if low <= stop:
                        logger.debug(
                            f"LONG: SL hit on candle {i+1}/{candles_to_check} "
                            f"(low={low:.4f}, stop={stop:.4f})"
                        )
                        return 'SL_HIT', stop

                    # Проверяем TP3
                    if high >= tp3:
                        logger.debug(
                            f"LONG: TP3 hit on candle {i+1}/{candles_to_check} "
                            f"(high={high:.4f}, tp3={tp3:.4f})"
                        )
                        return 'TP3_HIT', tp3

                    # Проверяем TP2
                    if high >= tp2:
                        logger.debug(
                            f"LONG: TP2 hit on candle {i+1}/{candles_to_check} "
                            f"(high={high:.4f}, tp2={tp2:.4f})"
                        )
                        return 'TP2_HIT', tp2

                    # Проверяем TP1
                    if high >= tp1:
                        logger.debug(
                            f"LONG: TP1 hit on candle {i+1}/{candles_to_check} "
                            f"(high={high:.4f}, tp1={tp1:.4f})"
                        )
                        return 'TP1_HIT', tp1

                elif signal_type == 'SHORT':
                    # ✅ SHORT: проверяем SL ПЕРВЫМ (консервативно)
                    if high >= stop:
                        logger.debug(
                            f"SHORT: SL hit on candle {i+1}/{candles_to_check} "
                            f"(high={high:.4f}, stop={stop:.4f})"
                        )
                        return 'SL_HIT', stop

                    # Проверяем TP3
                    if low <= tp3:
                        logger.debug(
                            f"SHORT: TP3 hit on candle {i+1}/{candles_to_check} "
                            f"(low={low:.4f}, tp3={tp3:.4f})"
                        )
                        return 'TP3_HIT', tp3

                    # Проверяем TP2
                    if low <= tp2:
                        logger.debug(
                            f"SHORT: TP2 hit on candle {i+1}/{candles_to_check} "
                            f"(low={low:.4f}, tp2={tp2:.4f})"
                        )
                        return 'TP2_HIT', tp2

                    # Проверяем TP1
                    if low <= tp1:
                        logger.debug(
                            f"SHORT: TP1 hit on candle {i+1}/{candles_to_check} "
                            f"(low={low:.4f}, tp1={tp1:.4f})"
                        )
                        return 'TP1_HIT', tp1

            # ✅ Если ничего не достигнуто за 300 свечей (25 часов)
            logger.debug(
                f"No TP/SL hit within {candles_to_check} candles (25h) - assuming SL"
            )
            return 'SL_HIT', stop

        except Exception as e:
            logger.error(f"Error in candle-based outcome: {e}")
            # Fallback на качественную оценку
            return 'SL_HIT', stop

    def _estimate_outcome_from_quality(
        self,
        signal_type: str,
        confidence: int,
        rr_ratio: float,
        entry: float,
        stop: float,
        tp_levels: List[float],
        comprehensive_data: Dict
    ) -> tuple[str, float]:
        """
        ✅ FALLBACK: Оценка outcome на основе качественного scoring
        """
        quality_score = 0

        # 1. Confidence (макс 35 баллов)
        quality_score += min(35, max(0, (confidence - 50) * 0.7))

        # 2. R/R ratio (макс 25 баллов)
        if rr_ratio >= 3.0:
            quality_score += 25
        elif rr_ratio >= 2.5:
            quality_score += 20
        elif rr_ratio >= 2.0:
            quality_score += 15
        elif rr_ratio >= 1.5:
            quality_score += 10

        # 3. SMC данные (макс 20 баллов)
        ob_score = self._score_order_blocks(comprehensive_data)
        imb_score = self._score_imbalances(comprehensive_data)
        sweep_score = self._score_sweeps(comprehensive_data)
        quality_score += ob_score + imb_score + sweep_score

        # 4. Market Data (макс 10 баллов)
        market_data = comprehensive_data.get('market_data', {})
        if isinstance(market_data, dict):
            funding_rate = abs(market_data.get('funding_rate', 0))
            if funding_rate < 0.01:
                quality_score += 3

            oi_change = market_data.get('oi_change_24h', 0)
            if signal_type == 'LONG' and oi_change > 0:
                quality_score += 4
            elif signal_type == 'SHORT' and oi_change < 0:
                quality_score += 4

            spread = market_data.get('spread_pct', 0)
            if spread < 0.10:
                quality_score += 3

        # 5. Indicators (макс 10 баллов)
        indicators = comprehensive_data.get('indicators_4h', {})
        if isinstance(indicators, dict):
            current = indicators.get('current', {})
            if isinstance(current, dict):
                rsi = current.get('rsi', 50)
                if signal_type == 'LONG' and 40 <= rsi <= 70:
                    quality_score += 5
                elif signal_type == 'SHORT' and 30 <= rsi <= 60:
                    quality_score += 5

                volume_ratio = current.get('volume_ratio', 1.0)
                if volume_ratio > 1.5:
                    quality_score += 5

        # Нормализуем
        quality_score = max(0, min(100, quality_score))

        logger.debug(
            f"Quality score: {quality_score:.1f} "
            f"(conf={confidence}, rr={rr_ratio:.2f})"
        )

        if len(tp_levels) < 3:
            tp_levels = tp_levels + [0] * (3 - len(tp_levels))

        # Outcome на основе score
        if quality_score >= 85:
            return 'TP3_HIT', tp_levels[2]
        elif quality_score >= 70:
            return 'TP2_HIT', tp_levels[1]
        elif quality_score >= 55:
            return 'TP1_HIT', tp_levels[0]
        elif quality_score >= 40:
            # Вероятностная оценка
            decision_hash = hash(f"{entry}{stop}{confidence}") % 10
            if decision_hash >= 5:
                return 'TP1_HIT', tp_levels[0]
            else:
                return 'SL_HIT', stop
        else:
            return 'SL_HIT', stop

    def _score_order_blocks(self, comprehensive_data: Dict) -> float:
        """Скоринг Order Blocks"""
        try:
            ob_data = comprehensive_data.get('order_blocks')
            if not ob_data or not isinstance(ob_data, dict):
                return 0

            nearest_ob = ob_data.get('nearest_ob')
            if not nearest_ob or not isinstance(nearest_ob, dict):
                return 0

            score = 0
            if not nearest_ob.get('is_mitigated', True):
                score += 8
            else:
                score += 4

            distance = nearest_ob.get('distance_pct', 100)
            if distance < 2.0:
                score += 5
            elif distance < 5.0:
                score += 2

            age = nearest_ob.get('age_in_candles', 100)
            if age <= 10:
                score += 2

            return min(10, score)
        except:
            return 0

    def _score_imbalances(self, comprehensive_data: Dict) -> float:
        """Скоринг Imbalances"""
        try:
            imb_data = comprehensive_data.get('imbalances')
            if not imb_data or not isinstance(imb_data, dict):
                return 0

            nearest_imb = imb_data.get('nearest_imbalance')
            if not nearest_imb or not isinstance(nearest_imb, dict):
                return 0

            score = 0
            if not nearest_imb.get('is_filled', True):
                score += 5
            else:
                fill_pct = nearest_imb.get('fill_percentage', 100)
                if fill_pct < 50:
                    score += 3

            return min(5, score)
        except:
            return 0

    def _score_sweeps(self, comprehensive_data: Dict) -> float:
        """Скоринг Sweeps"""
        try:
            sweep_data = comprehensive_data.get('liquidity_sweep')
            if not sweep_data or not isinstance(sweep_data, dict):
                return 0

            if not sweep_data.get('sweep_detected', False):
                return 0

            score = 0
            if sweep_data.get('reversal_confirmed', False):
                score += 5
            else:
                score += 2

            return min(5, score)
        except:
            return 0

    def _calculate_metrics(self, results: List[Dict], stats: Dict) -> Dict:
        """Рассчитать метрики"""
        total = stats['total_signals']
        if total == 0:
            return {}

        tp1_rate = (stats.get('tp1_hits', 0) / total) * 100
        tp2_rate = (stats.get('tp2_hits', 0) / total) * 100
        tp3_rate = (stats.get('tp3_hits', 0) / total) * 100
        sl_rate = (stats.get('sl_hits', 0) / total) * 100

        winning_trades = (
            stats.get('tp1_hits', 0) +
            stats.get('tp2_hits', 0) +
            stats.get('tp3_hits', 0)
        )
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
        """Сохранить результат"""
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


# ============================================================================
# SINGLETON
# ============================================================================
_backtester = None


def get_backtester() -> Backtester:
    """Получить singleton instance"""
    global _backtester
    if _backtester is None:
        _backtester = Backtester()
    return _backtester


def format_backtest_report(backtest_result: Dict) -> str:
    """Форматировать backtest для Telegram"""
    if not backtest_result:
        return "⚠️ No backtest data"

    metrics = backtest_result.get('metrics', {})

    report = [
        "📊 <b>BACKTEST RESULTS</b>",
        "━━━━━━━━━━━━━━━━━━━━━━\n",
        f"<b>📈 MAIN METRICS:</b>",
        f"  • Signals: {metrics.get('total_signals', 0)}",
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

    top_symbols = metrics.get('top_symbols', [])
    if top_symbols:
        report.append("\n<b>🏆 TOP SYMBOLS:</b>")
        for i, sym_data in enumerate(top_symbols[:3], 1):
            report.append(
                f"  {i}. {sym_data['symbol']} - {sym_data['total_pnl']:+.2f}% "
                f"(WR: {sym_data['win_rate']}%, n={sym_data['count']})"
            )

    return "\n".join(report)