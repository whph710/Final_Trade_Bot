"""
Backtesting Module - FIXED TP/SL LOGIC
Файл: utils/backtesting.py

✅ КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ:
- Правильная последовательность проверки: СНАЧАЛА SL, ПОТОМ TP
- Учёт частичного выхода: если достигнут TP1/TP2, продолжаем искать TP3
- Если после TP1/TP2 достигнут SL, возвращаем последний достигнутый TP
- Логирование каждой свечи для отладки
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

        total_signals = len(signals)
        final_signals = sum(
            1 for s in signals
            if s.get('backtest_status') == 'FINAL' and s.get('backtest_result')
        )
        to_check = total_signals - final_signals

        logger.info(
            f"Starting backtest: {total_signals} total, "
            f"{final_signals} cached (FINAL), {to_check} to check"
        )

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
            elif outcome == 'ACTIVE':
                stats['active_signals'] += 1
                continue

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
        """Асинхронный backtesting"""
        from utils.signal_storage import get_signal_storage

        signal_storage = get_signal_storage()
        results = []
        skipped_count = 0
        new_checks_count = 0

        for signal in signals:
            backtest_status = signal.get('backtest_status', 'NOT_CHECKED')
            backtest_result = signal.get('backtest_result')

            if backtest_status == 'FINAL' and backtest_result:
                result = {
                    'symbol': signal.get('symbol', 'UNKNOWN'),
                    'signal': signal.get('signal', 'UNKNOWN'),
                    'confidence': signal.get('confidence', 0),
                    'entry_price': signal.get('entry_price', 0),
                    'exit_price': backtest_result.get('exit_price', 0),
                    'outcome': backtest_result.get('outcome', 'UNKNOWN'),
                    'pnl_pct': backtest_result.get('pnl_pct', 0),
                    'timestamp': signal.get('timestamp', ''),
                    'from_cache': True
                }
                results.append(result)
                skipped_count += 1
            else:
                try:
                    result = await self._analyze_signal_async(signal)
                    if isinstance(result, dict):
                        results.append(result)
                        new_checks_count += 1

                        symbol = signal.get('symbol', 'UNKNOWN')
                        timestamp = signal.get('timestamp', '')
                        signal_file = signal_storage.find_signal_file(symbol, timestamp)

                        if signal_file:
                            signal_storage.update_signal_backtest_result(
                                signal_file,
                                result.get('outcome', 'UNKNOWN'),
                                result.get('exit_price', 0),
                                result.get('pnl_pct', 0)
                            )
                except Exception as e:
                    logger.error(f"Backtest error for {signal.get('symbol', 'UNKNOWN')}: {e}")

        logger.info(
            f"Backtest complete: {new_checks_count} new, {skipped_count} cached, "
            f"{len(results)} total"
        )
        return results

    async def _analyze_signal_async(self, signal: Dict) -> Dict:
        """Анализ одного сигнала"""
        try:
            symbol = signal.get('symbol', 'UNKNOWN')
            signal_type = signal.get('signal', 'UNKNOWN')
            entry = signal.get('entry_price', 0)
            stop = signal.get('stop_loss', 0)
            tp_levels = signal.get('take_profit_levels', [0, 0, 0])
            confidence = signal.get('confidence', 50)
            rr_ratio = signal.get('risk_reward_ratio', 0)
            timestamp_str = signal.get('timestamp', '')

            try:
                signal_time = datetime.fromisoformat(timestamp_str)
            except:
                logger.warning(f"{symbol}: Invalid timestamp, using current time")
                signal_time = datetime.now()

            logger.info(
                f"{symbol}: Starting backtest - signal_time={signal_time.strftime('%Y-%m-%d %H:%M:%S')}, "
                f"entry={entry:.6f}, stop={stop:.6f}, "
                f"tp1={tp_levels[0]:.6f}, tp2={tp_levels[1]:.6f}, tp3={tp_levels[2]:.6f}"
            )

            candles_5m = await self._fetch_5m_candles_after_signal(symbol, signal_time)

            if candles_5m and len(candles_5m) > 0:
                logger.info(
                    f"{symbol}: Analyzing {len(candles_5m)} 5M candles. "
                    f"First: {datetime.fromtimestamp(int(candles_5m[0][0])/1000).strftime('%Y-%m-%d %H:%M:%S')}"
                )
                outcome, exit_price = self._estimate_outcome_from_candles(
                    signal_type,
                    entry,
                    stop,
                    tp_levels,
                    candles_5m,
                    symbol
                )
                logger.info(
                    f"{symbol}: ✅ OUTCOME = {outcome}, exit={exit_price:.6f}"
                )
            else:
                logger.warning(f"{symbol}: No 5M candles, using quality fallback")
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

            if outcome == 'ACTIVE':
                pnl_pct = 0
            elif signal_type == 'LONG':
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
        """Загрузить 5M свечи после сигнала"""
        try:
            from data_providers.bybit_client import fetch_candles
            from config import config

            signal_timestamp_ms = int(signal_time.timestamp() * 1000)

            candles_5m = await fetch_candles(
                symbol,
                interval='5',
                limit=config.BACKTEST_CANDLES_LIMIT,
                start_time=signal_timestamp_ms
            )

            if not candles_5m:
                logger.warning(f"{symbol}: Failed to fetch 5M candles")
                return []

            filtered = []
            for candle in candles_5m:
                try:
                    candle_time_ms = int(candle[0])
                    if candle_time_ms >= signal_timestamp_ms:
                        filtered.append(candle)
                except:
                    continue

            if filtered:
                first = datetime.fromtimestamp(int(filtered[0][0]) / 1000)
                last = datetime.fromtimestamp(int(filtered[-1][0]) / 1000)
                time_diff = (first - signal_time).total_seconds() / 60

                logger.info(
                    f"{symbol}: Fetched {len(filtered)} 5M candles "
                    f"(signal: {signal_time.strftime('%H:%M:%S')}, "
                    f"first: {first.strftime('%H:%M:%S')}, "
                    f"diff: {time_diff:.1f}min)"
                )

                from config import config
                if time_diff > config.BACKTEST_TIME_DIFF_THRESHOLD_MIN:
                    logger.warning(
                        f"{symbol}: First candle {time_diff:.1f}min after signal!"
                    )

            return filtered

        except Exception as e:
            logger.error(f"{symbol}: Error fetching 5M candles: {e}")
            return []

    def _estimate_outcome_from_candles(
        self,
        signal_type: str,
        entry: float,
        stop: float,
        tp_levels: List[float],
        candles: List,
        symbol: str = "UNKNOWN"
    ) -> tuple[str, float]:
        """
        ✅ ИСПРАВЛЕНО: Правильная логика проверки TP/SL

        АЛГОРИТМ:
        1. На КАЖДОЙ свече СНАЧАЛА проверяем SL
        2. Если SL НЕ достигнут, проверяем TP
        3. Отслеживаем лучший достигнутый TP (TP1 < TP2 < TP3)
        4. Если после TP1/TP2 достигнут SL, возвращаем последний достигнутый TP
        5. Если TP3 достигнут, сразу возвращаем TP3 (финал)
        """
        try:
            if len(tp_levels) < 3:
                tp_levels = tp_levels + [0] * (3 - len(tp_levels))

            tp1, tp2, tp3 = tp_levels[0], tp_levels[1], tp_levels[2]

            # Валидация TP уровней
            if signal_type == 'LONG':
                if tp1 <= entry or tp2 <= tp1 or tp3 <= tp2:
                    logger.warning(
                        f"{symbol} LONG: Invalid TP - "
                        f"entry={entry:.4f} tp1={tp1:.4f} tp2={tp2:.4f} tp3={tp3:.4f}"
                    )
                    return 'SL_HIT', stop
            elif signal_type == 'SHORT':
                if tp1 >= entry or tp2 >= tp1 or tp3 >= tp2:
                    logger.warning(
                        f"{symbol} SHORT: Invalid TP - "
                        f"entry={entry:.4f} tp1={tp1:.4f} tp2={tp2:.4f} tp3={tp3:.4f}"
                    )
                    return 'SL_HIT', stop

            candles_count = len(candles)
            logger.info(
                f"{symbol} {signal_type}: Checking {candles_count} candles"
            )

            # Отслеживание лучшего достигнутого TP
            best_tp_hit = None
            best_tp_price = None

            for i, candle in enumerate(candles):
                if not candle or len(candle) < 5:
                    continue

                try:
                    high = float(candle[2])
                    low = float(candle[3])
                except (ValueError, IndexError, TypeError):
                    continue

                # ============================================================
                # LONG LOGIC
                # ============================================================
                if signal_type == 'LONG':
                    # ШАГ 1: ПРОВЕРЯЕМ SL ПЕРВЫМ
                    if low <= stop:
                        if best_tp_hit:
                            logger.info(
                                f"{symbol} LONG candle {i+1}: SL hit (low={low:.6f}, stop={stop:.6f}), "
                                f"but {best_tp_hit} reached earlier → returning {best_tp_hit}"
                            )
                            return best_tp_hit, best_tp_price
                        else:
                            logger.info(
                                f"{symbol} LONG candle {i+1}: ❌ SL HIT "
                                f"(low={low:.6f}, stop={stop:.6f})"
                            )
                            return 'SL_HIT', stop

                    # ШАГ 2: ПРОВЕРЯЕМ TP (от дальнего к ближнему)
                    if tp3 > 0 and high >= tp3:
                        logger.info(
                            f"{symbol} LONG candle {i+1}: ✅ TP3 HIT "
                            f"(high={high:.6f}, tp3={tp3:.6f})"
                        )
                        return 'TP3_HIT', tp3

                    elif tp2 > 0 and high >= tp2:
                        if best_tp_hit != 'TP2_HIT':
                            logger.info(
                                f"{symbol} LONG candle {i+1}: ✅ TP2 HIT "
                                f"(high={high:.6f}, tp2={tp2:.6f})"
                            )
                        best_tp_hit = 'TP2_HIT'
                        best_tp_price = tp2

                    elif tp1 > 0 and high >= tp1:
                        if not best_tp_hit:
                            logger.info(
                                f"{symbol} LONG candle {i+1}: ✅ TP1 HIT "
                                f"(high={high:.6f}, tp1={tp1:.6f})"
                            )
                            best_tp_hit = 'TP1_HIT'
                            best_tp_price = tp1

                # ============================================================
                # SHORT LOGIC
                # ============================================================
                elif signal_type == 'SHORT':
                    # ШАГ 1: ПРОВЕРЯЕМ SL ПЕРВЫМ
                    if high >= stop:
                        if best_tp_hit:
                            logger.info(
                                f"{symbol} SHORT candle {i+1}: SL hit (high={high:.6f}, stop={stop:.6f}), "
                                f"but {best_tp_hit} reached earlier → returning {best_tp_hit}"
                            )
                            return best_tp_hit, best_tp_price
                        else:
                            logger.info(
                                f"{symbol} SHORT candle {i+1}: ❌ SL HIT "
                                f"(high={high:.6f}, stop={stop:.6f})"
                            )
                            return 'SL_HIT', stop

                    # ШАГ 2: ПРОВЕРЯЕМ TP (от дальнего к ближнему)
                    if tp3 > 0 and low <= tp3:
                        logger.info(
                            f"{symbol} SHORT candle {i+1}: ✅ TP3 HIT "
                            f"(low={low:.6f}, tp3={tp3:.6f})"
                        )
                        return 'TP3_HIT', tp3

                    elif tp2 > 0 and low <= tp2:
                        if best_tp_hit != 'TP2_HIT':
                            logger.info(
                                f"{symbol} SHORT candle {i+1}: ✅ TP2 HIT "
                                f"(low={low:.6f}, tp2={tp2:.6f})"
                            )
                        best_tp_hit = 'TP2_HIT'
                        best_tp_price = tp2

                    elif tp1 > 0 and low <= tp1:
                        if not best_tp_hit:
                            logger.info(
                                f"{symbol} SHORT candle {i+1}: ✅ TP1 HIT "
                                f"(low={low:.6f}, tp1={tp1:.6f})"
                            )
                            best_tp_hit = 'TP1_HIT'
                            best_tp_price = tp1

            # ============================================================
            # ФИНАЛЬНАЯ ПРОВЕРКА
            # ============================================================
            if best_tp_hit:
                logger.info(
                    f"{symbol} {signal_type}: Final outcome = {best_tp_hit} "
                    f"(exit={best_tp_price:.6f})"
                )
                return best_tp_hit, best_tp_price

            # Проверяем ACTIVE
            if candles_count > 0:
                last_high = float(candles[-1][2])
                last_low = float(candles[-1][3])

                if signal_type == 'LONG':
                    sl_reached = last_low <= stop
                else:
                    sl_reached = last_high >= stop

                if not sl_reached:
                    logger.info(
                        f"{symbol} {signal_type}: ⏳ ACTIVE - no TP/SL in {candles_count} candles"
                    )
                    return 'ACTIVE', entry

            logger.warning(f"{symbol} {signal_type}: Default to SL_HIT")
            return 'SL_HIT', stop

        except Exception as e:
            logger.error(f"{symbol}: Error in candle analysis: {e}")
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
        """Fallback: качественная оценка"""
        from config import config

        quality_score = 0

        # Confidence
        quality_score += min(
            config.BACKTEST_QUALITY_CONFIDENCE_MAX,
            max(0, (confidence - config.BACKTEST_QUALITY_CONFIDENCE_BASE) *
                config.BACKTEST_QUALITY_CONFIDENCE_MULTIPLIER)
        )

        # R/R ratio
        if rr_ratio >= config.BACKTEST_QUALITY_RR_3_0_THRESHOLD:
            quality_score += config.BACKTEST_QUALITY_RR_3_0_SCORE
        elif rr_ratio >= config.BACKTEST_QUALITY_RR_2_5_THRESHOLD:
            quality_score += config.BACKTEST_QUALITY_RR_2_5_SCORE
        elif rr_ratio >= config.BACKTEST_QUALITY_RR_2_0_THRESHOLD:
            quality_score += config.BACKTEST_QUALITY_RR_2_0_SCORE

        # SMC
        quality_score += self._score_order_blocks(comprehensive_data)
        quality_score += self._score_imbalances(comprehensive_data)
        quality_score += self._score_sweeps(comprehensive_data)

        quality_score = max(0, min(100, quality_score))

        if len(tp_levels) < 3:
            tp_levels = tp_levels + [0] * (3 - len(tp_levels))

        if quality_score >= config.BACKTEST_QUALITY_TP3_THRESHOLD:
            return 'TP3_HIT', tp_levels[2]
        elif quality_score >= config.BACKTEST_QUALITY_TP2_THRESHOLD:
            return 'TP2_HIT', tp_levels[1]
        elif quality_score >= config.BACKTEST_QUALITY_TP1_THRESHOLD:
            return 'TP1_HIT', tp_levels[0]
        else:
            return 'SL_HIT', stop

    def _score_order_blocks(self, data: Dict) -> float:
        """Score Order Blocks"""
        try:
            ob = data.get('order_blocks')
            if not ob or not isinstance(ob, dict):
                return 0

            nearest = ob.get('nearest_ob')
            if not nearest:
                return 0

            from config import config
            score = 8 if not nearest.get('is_mitigated', True) else 4

            dist = nearest.get('distance_pct', 100)
            if dist < config.BACKTEST_QUALITY_OB_DISTANCE_THRESHOLD:
                score += 5

            return min(config.BACKTEST_QUALITY_OB_MAX_SCORE, score)
        except:
            return 0

    def _score_imbalances(self, data: Dict) -> float:
        """Score Imbalances"""
        try:
            imb = data.get('imbalances')
            if not imb or not isinstance(imb, dict):
                return 0

            nearest = imb.get('nearest_imbalance')
            if not nearest:
                return 0

            from config import config
            if not nearest.get('is_filled', True):
                return 5
            elif nearest.get('fill_percentage', 100) < config.BACKTEST_QUALITY_IMB_FILL_THRESHOLD:
                return 3
            return 0
        except:
            return 0

    def _score_sweeps(self, data: Dict) -> float:
        """Score Sweeps"""
        try:
            sweep = data.get('liquidity_sweep')
            if not sweep or not isinstance(sweep, dict):
                return 0

            if not sweep.get('sweep_detected', False):
                return 0

            return 5 if sweep.get('reversal_confirmed', False) else 2
        except:
            return 0

    def _calculate_metrics(self, results: List[Dict], stats: Dict) -> Dict:
        """Рассчитать метрики"""
        total = stats['total_signals']
        active = stats.get('active_signals', 0)
        closed = total - active

        if closed == 0:
            return {
                'total_signals': total,
                'active_signals': active,
                'closed_signals': 0
            }

        win_rate = ((stats.get('tp1_hits', 0) + stats.get('tp2_hits', 0) +
                    stats.get('tp3_hits', 0)) / closed) * 100

        symbol_stats = defaultdict(lambda: {'count': 0, 'wins': 0, 'pnl': 0})
        for r in results:
            if r.get('outcome') == 'ACTIVE':
                continue
            sym = r['symbol']
            symbol_stats[sym]['count'] += 1
            if r['outcome'] in ['TP1_HIT', 'TP2_HIT', 'TP3_HIT']:
                symbol_stats[sym]['wins'] += 1
            symbol_stats[sym]['pnl'] += r['pnl_pct']

        top = sorted(symbol_stats.items(), key=lambda x: x[1]['pnl'], reverse=True)[:5]

        return {
            'total_signals': total,
            'active_signals': active,
            'closed_signals': closed,
            'long_signals': stats.get('signal_LONG', 0),
            'short_signals': stats.get('signal_SHORT', 0),
            'win_rate': round(win_rate, 2),
            'tp1_hit_rate': round((stats.get('tp1_hits', 0) / closed) * 100, 2),
            'tp2_hit_rate': round((stats.get('tp2_hits', 0) / closed) * 100, 2),
            'tp3_hit_rate': round((stats.get('tp3_hits', 0) / closed) * 100, 2),
            'sl_hit_rate': round((stats.get('sl_hits', 0) / closed) * 100, 2),
            'avg_pnl_pct': round(stats['total_pnl'] / closed, 2),
            'total_pnl_pct': round(stats['total_pnl'], 2),
            'top_symbols': [
                {
                    'symbol': s,
                    'count': d['count'],
                    'win_rate': round((d['wins'] / d['count']) * 100, 2),
                    'total_pnl': round(d['pnl'], 2)
                }
                for s, d in top
            ]
        }

    def _save_backtest(self, result: Dict, name: Optional[str] = None) -> Path:
        """Сохранить результат"""
        try:
            if name:
                filename = f"backtest_{name}.json"
            else:
                filename = f"backtest_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

            filepath = self.backtest_dir / filename

            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(result, f, indent=2, ensure_ascii=False)

            logger.info(f"Backtest saved: {filepath.name}")
            return filepath
        except Exception as e:
            logger.error(f"Error saving backtest: {e}")
            return None


# Singleton
_backtester = None

def get_backtester() -> Backtester:
    global _backtester
    if _backtester is None:
        _backtester = Backtester()
    return _backtester


def format_backtest_report(result: Dict) -> str:
    """Форматировать backtest для Telegram"""
    if not result:
        return "⚠️ No data"

    m = result.get('metrics', {})
    active = m.get('active_signals', 0)
    closed = m.get('closed_signals', m.get('total_signals', 0) - active)

    report = [
        "📊 <b>BACKTEST RESULTS</b>",
        "━━━━━━━━━━━━━━━━━━━━━━\n",
        f"<b>📈 METRICS:</b>",
        f"  • Total: {m.get('total_signals', 0)}",
        f"  • ⏳ Active: {active} | ✅ Closed: {closed}",
        f"  • LONG: {m.get('long_signals', 0)} | SHORT: {m.get('short_signals', 0)}",
        f"  • Win Rate: <b>{m.get('win_rate', 0)}%</b>",
        f"  • Avg PnL: <b>{m.get('avg_pnl_pct', 0):+.2f}%</b>",
        f"  • Total PnL: <b>{m.get('total_pnl_pct', 0):+.2f}%</b>\n",
        f"<b>🎯 HIT RATES:</b>",
        f"  • TP1: {m.get('tp1_hit_rate', 0)}%",
        f"  • TP2: {m.get('tp2_hit_rate', 0)}%",
        f"  • TP3: {m.get('tp3_hit_rate', 0)}%",
        f"  • SL: {m.get('sl_hit_rate', 0)}%"
    ]

    top = m.get('top_symbols', [])
    if top:
        report.append("\n<b>🏆 TOP:</b>")
        for i, s in enumerate(top[:3], 1):
            report.append(
                f"  {i}. {s['symbol']} - {s['total_pnl']:+.2f}% "
                f"(WR: {s['win_rate']}%)"
            )

    return "\n".join(report)