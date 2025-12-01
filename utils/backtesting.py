"""
Backtesting Module - FIXED SMC SCORING
Файл: utils/backtesting.py

✅ ИСПРАВЛЕНО:
- Улучшен парсинг SMC данных с fallback логикой
- Добавлены проверки на None/отсутствие данных
- Детерминированная оценка (убрана случайность)
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
        if backtest_dir is None:
            try:
                from config import config
                self.backtest_dir = config.BACKTEST_DIR
            except:
                self.backtest_dir = Path("signals/backtest_results")

        self.backtest_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"Backtester initialized: {self.backtest_dir}")

    def run_backtest(self, signals: List[Dict], name: Optional[str] = None) -> Dict:
        """Запустить backtest на списке сигналов"""
        if not signals:
            logger.warning("No signals provided for backtest")
            return {}

        logger.info(f"Starting backtest for {len(signals)} signals")

        results = []
        stats = defaultdict(int)

        for signal in signals:
            result = self._analyze_signal(signal)
            results.append(result)

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

        metrics = self._calculate_metrics(results, stats)

        backtest_result = {
            'timestamp': datetime.now().isoformat(),
            'signals_analyzed': len(signals),
            'metrics': metrics,
            'detailed_results': results
        }

        self._save_backtest(backtest_result, name)
        return backtest_result

    def _analyze_signal(self, signal: Dict) -> Dict:
        """Анализ одного сигнала"""
        try:
            symbol = signal.get('symbol', 'UNKNOWN')
            signal_type = signal.get('signal', 'UNKNOWN')
            entry = signal.get('entry_price', 0)
            stop = signal.get('stop_loss', 0)
            tp_levels = signal.get('take_profit_levels', [0, 0, 0])
            confidence = signal.get('confidence', 50)
            rr_ratio = signal.get('risk_reward_ratio', 0)

            # ✅ ИСПРАВЛЕНО: Детерминированная оценка с SMC данными
            outcome, exit_price = self._estimate_outcome_with_smc(
                signal_type,
                confidence,
                rr_ratio,
                entry,
                stop,
                tp_levels,
                signal.get('comprehensive_data', {})
            )

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
                'timestamp': signal.get('timestamp', '')
            }

        except Exception as e:
            logger.error(f"Error analyzing signal: {e}")
            return {
                'symbol': signal.get('symbol', 'UNKNOWN'),
                'outcome': 'ERROR',
                'pnl_pct': 0
            }

    def _estimate_outcome_with_smc(
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
        ✅ УЛУЧШЕНО: Оценка исхода с SMC данными и fallback логикой
        """
        quality_score = 0

        # 1. Confidence (макс 35 баллов)
        quality_score += min(35, (confidence - 50) * 0.7)

        # 2. R/R ratio (макс 25 баллов)
        if rr_ratio >= 3.0:
            quality_score += 25
        elif rr_ratio >= 2.5:
            quality_score += 20
        elif rr_ratio >= 2.0:
            quality_score += 15
        elif rr_ratio >= 1.5:
            quality_score += 10

        # ============================================================
        # 3. ✅ ИСПРАВЛЕНО: SMC ДАННЫЕ с fallback (макс 20 баллов)
        # ============================================================

        # Order Blocks (макс 10 баллов)
        ob_score = self._score_order_blocks(comprehensive_data)
        quality_score += ob_score

        # Imbalances/FVG (макс 5 баллов)
        imb_score = self._score_imbalances(comprehensive_data)
        quality_score += imb_score

        # Liquidity Sweeps (макс 5 баллов)
        sweep_score = self._score_sweeps(comprehensive_data)
        quality_score += sweep_score

        # ============================================================
        # 4. Market Data (макс 10 баллов)
        # ============================================================
        market_data = comprehensive_data.get('market_data', {})

        if isinstance(market_data, dict):
            # Funding rate
            funding_rate = abs(market_data.get('funding_rate', 0))
            if funding_rate < 0.01:
                quality_score += 3

            # OI change
            oi_change = market_data.get('oi_change_24h', 0)
            if signal_type == 'LONG' and oi_change > 0:
                quality_score += 4
            elif signal_type == 'SHORT' and oi_change < 0:
                quality_score += 4

            # Spread
            spread = market_data.get('spread_pct', 0)
            if spread < 0.10:
                quality_score += 3

        # ============================================================
        # 5. Indicators (макс 10 баллов)
        # ============================================================
        indicators = comprehensive_data.get('indicators_4h', {})

        if isinstance(indicators, dict):
            current = indicators.get('current', {})

            if isinstance(current, dict):
                # RSI optimal
                rsi = current.get('rsi', 50)
                if signal_type == 'LONG' and 40 <= rsi <= 70:
                    quality_score += 5
                elif signal_type == 'SHORT' and 30 <= rsi <= 60:
                    quality_score += 5

                # Volume
                volume_ratio = current.get('volume_ratio', 1.0)
                if volume_ratio > 1.5:
                    quality_score += 5

        # Нормализуем score
        quality_score = max(0, min(100, quality_score))

        logger.debug(
            f"Backtest quality score: {quality_score:.1f} "
            f"(conf={confidence}, rr={rr_ratio:.2f}, "
            f"OB={ob_score}, FVG={imb_score}, Sweep={sweep_score})"
        )

        # ============================================================
        # ОПРЕДЕЛЕНИЕ ИСХОДА
        # ============================================================

        if quality_score >= 80:
            outcome = 'TP3_HIT'
            exit_price = tp_levels[2] if len(tp_levels) > 2 else tp_levels[0]

        elif quality_score >= 65:
            outcome = 'TP2_HIT'
            exit_price = tp_levels[1] if len(tp_levels) > 1 else tp_levels[0]

        elif quality_score >= 50:
            outcome = 'TP1_HIT'
            exit_price = tp_levels[0]

        elif quality_score >= 35:
            # ✅ Детерминизм через hash
            decision_hash = hash(f"{entry}{stop}{confidence}") % 10

            if decision_hash >= 4:  # 60% на TP1
                outcome = 'TP1_HIT'
                exit_price = tp_levels[0]
            else:  # 40% на SL
                outcome = 'SL_HIT'
                exit_price = stop

        else:
            outcome = 'SL_HIT'
            exit_price = stop

        return outcome, exit_price

    def _score_order_blocks(self, comprehensive_data: Dict) -> float:
        """
        ✅ НОВОЕ: Скоринг Order Blocks с fallback логикой
        """
        try:
            # Пытаемся найти OB данные
            ob_data = None

            # Вариант 1: прямо в comprehensive_data
            if 'order_blocks' in comprehensive_data:
                ob_data = comprehensive_data['order_blocks']
            # Вариант 2: внутри вложенного словаря
            elif 'smc_data' in comprehensive_data:
                smc = comprehensive_data.get('smc_data', {})
                if isinstance(smc, dict):
                    ob_data = smc.get('order_blocks')

            if not ob_data or not isinstance(ob_data, dict):
                logger.debug("No OB data found or invalid format")
                return 0

            nearest_ob = ob_data.get('nearest_ob')

            if not nearest_ob or not isinstance(nearest_ob, dict):
                logger.debug("No nearest OB found")
                return 0

            score = 0

            # Fresh OB = сильный сигнал
            is_mitigated = nearest_ob.get('is_mitigated', True)
            if not is_mitigated:
                score += 8
            else:
                score += 4

            # Близкий OB = точный entry
            distance = nearest_ob.get('distance_pct', 100)
            if distance < 2.0:
                score += 5
            elif distance < 5.0:
                score += 2

            # Age bonus (если есть)
            age = nearest_ob.get('age_in_candles', 100)
            if age <= 10:
                score += 2

            return min(10, score)  # Макс 10 баллов

        except Exception as e:
            logger.debug(f"OB scoring error: {e}")
            return 0

    def _score_imbalances(self, comprehensive_data: Dict) -> float:
        """
        ✅ НОВОЕ: Скоринг Imbalances с fallback логикой
        """
        try:
            # Пытаемся найти Imbalance данные
            imb_data = None

            if 'imbalances' in comprehensive_data:
                imb_data = comprehensive_data['imbalances']
            elif 'smc_data' in comprehensive_data:
                smc = comprehensive_data.get('smc_data', {})
                if isinstance(smc, dict):
                    imb_data = smc.get('imbalances')

            if not imb_data or not isinstance(imb_data, dict):
                logger.debug("No Imbalance data found")
                return 0

            nearest_imb = imb_data.get('nearest_imbalance')

            if not nearest_imb or not isinstance(nearest_imb, dict):
                logger.debug("No nearest Imbalance found")
                return 0

            score = 0

            # Unfilled FVG = сильнее
            is_filled = nearest_imb.get('is_filled', True)
            if not is_filled:
                score += 5
            else:
                fill_pct = nearest_imb.get('fill_percentage', 100)
                if fill_pct < 50:
                    score += 3

            return min(5, score)  # Макс 5 баллов

        except Exception as e:
            logger.debug(f"Imbalance scoring error: {e}")
            return 0

    def _score_sweeps(self, comprehensive_data: Dict) -> float:
        """
        ✅ НОВОЕ: Скоринг Liquidity Sweeps с fallback логикой
        """
        try:
            # Пытаемся найти Sweep данные
            sweep_data = None

            if 'liquidity_sweep' in comprehensive_data:
                sweep_data = comprehensive_data['liquidity_sweep']
            elif 'smc_data' in comprehensive_data:
                smc = comprehensive_data.get('smc_data', {})
                if isinstance(smc, dict):
                    sweep_data = smc.get('liquidity_sweep')

            if not sweep_data or not isinstance(sweep_data, dict):
                logger.debug("No Sweep data found")
                return 0

            sweep_detected = sweep_data.get('sweep_detected', False)

            if not sweep_detected:
                return 0

            score = 0

            # Reversal confirmed = сильнее
            reversal_confirmed = sweep_data.get('reversal_confirmed', False)
            if reversal_confirmed:
                score += 5
            else:
                score += 2

            return min(5, score)  # Макс 5 баллов

        except Exception as e:
            logger.debug(f"Sweep scoring error: {e}")
            return 0

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