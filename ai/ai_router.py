import logging
from typing import List, Dict, Optional
from dataclasses import is_dataclass, asdict
import numpy as np

logger = logging.getLogger(__name__)


class AIRouter:
    """AI Router для маршрутизации между провайдерами"""

    def __init__(self):
        """Инициализация роутера"""
        from config import config

        self.deepseek_clients: Dict[str, 'DeepSeekClient'] = {}
        self.claude_client: Optional['AnthropicClient'] = None

        self.stage_providers = {
            'stage2': config.STAGE2_PROVIDER,
            'stage3': config.STAGE3_PROVIDER
        }

        self.stage_configs = {
            'stage2': {
                'model': config.STAGE2_MODEL,
                'temperature': config.STAGE2_TEMPERATURE,
                'max_tokens': config.STAGE2_MAX_TOKENS
            },
            'stage3': {
                'model': config.STAGE3_MODEL,
                'temperature': config.STAGE3_TEMPERATURE,
                'max_tokens': config.STAGE3_MAX_TOKENS
            }
        }

        logger.info(
            f"AI Router initialized: "
            f"Stage2={config.STAGE2_PROVIDER.upper()} ({config.STAGE2_MODEL}), "
            f"Stage3={config.STAGE3_PROVIDER.upper()} ({config.STAGE3_MODEL})"
        )

    async def _get_deepseek_client(self, stage: str) -> Optional['DeepSeekClient']:
        """Получить DeepSeek клиент для конкретного stage"""
        if stage in self.deepseek_clients:
            return self.deepseek_clients[stage]

        from config import config

        if not config.DEEPSEEK_API_KEY:
            logger.warning("DEEPSEEK_API_KEY not found")
            return None

        try:
            from ai.deepseek_client import DeepSeekClient

            stage_config = self.stage_configs.get(stage, {})

            client = DeepSeekClient(
                api_key=config.DEEPSEEK_API_KEY,
                model=stage_config.get('model', 'deepseek-chat'),
                use_reasoning=config.DEEPSEEK_REASONING
            )

            self.deepseek_clients[stage] = client
            return client

        except Exception as e:
            logger.error(f"Failed to initialize DeepSeek for {stage}: {e}")
            return None

    async def _get_claude_client(self) -> Optional['AnthropicClient']:
        """Получить Claude клиент"""
        if self.claude_client:
            return self.claude_client

        from config import config

        if not config.ANTHROPIC_API_KEY:
            logger.warning("ANTHROPIC_API_KEY not found")
            return None

        try:
            from ai.anthropic_client import AnthropicClient

            self.claude_client = AnthropicClient(
                api_key=config.ANTHROPIC_API_KEY,
                model=config.ANTHROPIC_MODEL,
                use_thinking=config.ANTHROPIC_THINKING
            )
            return self.claude_client

        except ImportError:
            logger.error("Anthropic SDK not installed: pip install anthropic")
            return None
        except Exception as e:
            logger.error(f"Failed to initialize Claude: {e}")
            return None

    async def _get_provider_client(self, stage: str):
        """Получить клиент для конкретного stage"""
        provider = self.stage_providers.get(stage, 'deepseek')

        if provider == 'deepseek':
            client = await self._get_deepseek_client(stage)
            return 'deepseek', client

        elif provider == 'claude':
            client = await self._get_claude_client()
            return 'claude', client

        else:
            logger.error(f"Unknown provider: {provider}")
            return None, None

    async def select_pairs(
        self,
        pairs_data: List[Dict],
        max_pairs: Optional[int] = None
    ) -> List[str]:
        """Stage 2: Выбор пар через AI"""
        logger.info(
            f"Stage 2: selecting from {len(pairs_data)} pairs (limit: {max_pairs})"
        )

        provider_name, client = await self._get_provider_client('stage2')

        if not client:
            logger.error("Stage 2: Client unavailable")
            return []

        stage2_config = self.stage_configs['stage2']

        logger.debug(
            f"Stage 2: using {provider_name.upper()} "
            f"(model={stage2_config['model']}, temp={stage2_config['temperature']})"
        )

        try:
            selected = await client.select_pairs(
                pairs_data=pairs_data,
                max_pairs=max_pairs,
                temperature=stage2_config['temperature'],
                max_tokens=stage2_config['max_tokens']
            )

            logger.info(f"Stage 2 complete: selected {len(selected)} pairs")
            return selected

        except Exception as e:
            logger.error(f"Stage 2 error: {e}")
            import traceback
            traceback.print_exc()
            return []

    async def analyze_pair_comprehensive(
        self,
        symbol: str,
        comprehensive_data: Dict
    ) -> Dict:
        """Stage 3: Comprehensive analysis через AI"""
        logger.debug(f"Stage 3: analyzing {symbol}")

        provider_name, client = await self._get_provider_client('stage3')

        if not client:
            logger.error(f"Stage 3: Client unavailable for {symbol}")
            return {
                'symbol': symbol,
                'signal': 'NO_SIGNAL',
                'confidence': 0,
                'rejection_reason': 'AI client unavailable'
            }

        stage3_config = self.stage_configs['stage3']

        logger.debug(
            f"Stage 3: using {provider_name.upper()} "
            f"(model={stage3_config['model']})"
        )

        try:
            if provider_name == 'claude':
                result = await client.analyze_comprehensive(
                    symbol=symbol,
                    comprehensive_data=comprehensive_data,
                    temperature=stage3_config['temperature'],
                    max_tokens=stage3_config['max_tokens']
                )

                if result:
                    logger.debug(f"Stage 3: Claude analysis complete for {symbol}")
                    return result
                else:
                    return {
                        'symbol': symbol,
                        'signal': 'NO_SIGNAL',
                        'confidence': 0,
                        'rejection_reason': 'Claude returned no result'
                    }

            elif provider_name == 'deepseek':
                result = await self._deepseek_comprehensive_analysis(
                    symbol,
                    comprehensive_data,
                    client,
                    stage3_config
                )

                if result and result.get('signal') != 'NO_SIGNAL':
                    logger.debug(f"Stage 3: DeepSeek analysis complete for {symbol}")
                    return result
                else:
                    return {
                        'symbol': symbol,
                        'signal': 'NO_SIGNAL',
                        'confidence': 0,
                        'rejection_reason': result.get(
                            'rejection_reason',
                            'DeepSeek rejected signal'
                        )
                    }

            else:
                return {
                    'symbol': symbol,
                    'signal': 'NO_SIGNAL',
                    'confidence': 0,
                    'rejection_reason': f'Unknown provider: {provider_name}'
                }

        except Exception as e:
            logger.error(f"Stage 3 error for {symbol}: {e}")
            import traceback
            traceback.print_exc()
            return {
                'symbol': symbol,
                'signal': 'NO_SIGNAL',
                'confidence': 0,
                'rejection_reason': f'Exception: {str(e)[:100]}'
            }

    async def _deepseek_comprehensive_analysis(
        self,
        symbol: str,
        comprehensive_data: Dict,
        client: 'DeepSeekClient',
        config: Dict
    ) -> Dict:
        import json

        try:
            from ai.deepseek_client import load_prompt_cached
            from config import config as app_config

            system_prompt = load_prompt_cached("prompt_analyze.txt")
            forced_direction = comprehensive_data.get('forced_direction')

            if forced_direction:
                system_prompt += (
                    f"\n\nCRITICAL INSTRUCTION:\n"
                    f"Analyze only {forced_direction} opportunities. "
                    f"If conditions do not support {forced_direction}, return NO_SIGNAL.\n"
                )

            candles_1h = comprehensive_data.get('candles_1h', [])
            candles_4h = comprehensive_data.get('candles_4h', [])

            candles_1h_trimmed = candles_1h[-app_config.STAGE3_CANDLES_1H:] if candles_1h else []
            candles_4h_trimmed = candles_4h[-app_config.STAGE3_CANDLES_4H:] if candles_4h else []

            analysis_data = {
                'symbol': symbol,
                'candles_1h': candles_1h_trimmed,
                'candles_4h': candles_4h_trimmed,
                'indicators_1h': comprehensive_data.get('indicators_1h', {}),
                'indicators_4h': comprehensive_data.get('indicators_4h', {}),
                'current_price': comprehensive_data.get('current_price', 0),

                'support_resistance_4h': self._serialize_to_json(
                    comprehensive_data.get('support_resistance_4h')
                ),
                'wave_analysis_4h': self._serialize_to_json(
                    comprehensive_data.get('wave_analysis_4h')
                ),
                'ema200_context_4h': self._serialize_to_json(
                    comprehensive_data.get('ema200_context_4h')
                ),

                'market_data': comprehensive_data.get('market_data', {}),
                'correlation_data': self._serialize_to_json(
                    comprehensive_data.get('correlation_data', {})
                ),
                'volume_profile': self._serialize_to_json(
                    comprehensive_data.get('volume_profile')
                ),
                'vp_analysis': self._serialize_to_json(
                    comprehensive_data.get('vp_analysis')
                ),

                'order_blocks': self._serialize_to_json(
                    comprehensive_data.get('order_blocks')
                ),
                'imbalances': self._serialize_to_json(
                    comprehensive_data.get('imbalances')
                ),
                'liquidity_sweep': self._serialize_to_json(
                    comprehensive_data.get('liquidity_sweep')
                ),

                'btc_candles_1h': comprehensive_data.get('btc_candles_1h', [])[-100:],
                'btc_candles_4h': comprehensive_data.get('btc_candles_4h', [])[-60:]
            }

            if forced_direction:
                analysis_data['forced_direction'] = forced_direction

            data_json = json.dumps(
                analysis_data,
                separators=(',', ':'),
                default=self._json_serializer
            )

            user_prompt = f"{system_prompt}\n\nData:\n{data_json}"

            response = await client.chat(
                messages=[
                    {"role": "system", "content": "You are an expert trader."},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=config['max_tokens'],
                temperature=config['temperature']
            )

            result = self._extract_json_from_response(response)

            if not result:
                logger.warning(f"Stage 3 {symbol}: invalid JSON response")
                return {
                    'symbol': symbol,
                    'signal': 'NO_SIGNAL',
                    'confidence': 0,
                    'rejection_reason': 'Invalid JSON response from DeepSeek'
                }

            result['symbol'] = symbol
            result = self._normalize_take_profit_levels(result, symbol)

            return result

        except Exception as e:
            logger.error(f"Stage 3 DeepSeek analysis error for {symbol}: {e}")
            import traceback
            traceback.print_exc()
            return {
                'symbol': symbol,
                'signal': 'NO_SIGNAL',
                'confidence': 0,
                'rejection_reason': f'DeepSeek exception: {str(e)[:100]}'
            }

    def _serialize_to_json(self, obj):
        if obj is None:
            return None
        if is_dataclass(obj):
            return self._serialize_to_json(asdict(obj))
        if isinstance(obj, dict):
            return {k: self._serialize_to_json(v) for k, v in obj.items()}
        if isinstance(obj, (list, tuple)):
            return [self._serialize_to_json(item) for item in obj]
        if isinstance(obj, (np.integer, np.floating)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, bool):
            return bool(obj)
        if isinstance(obj, (int, float, str)):
            return obj
        try:
            return str(obj)
        except:
            return None

    def _json_serializer(self, obj):
        if isinstance(obj, (np.integer, np.floating)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, bool):
            return bool(obj)
        if is_dataclass(obj):
            return asdict(obj)
        return str(obj)

    def _normalize_take_profit_levels(self, result: Dict, symbol: str) -> Dict:
        try:
            tp_levels = result.get('take_profit_levels')
            entry_price = result.get('entry_price', 0)

            if tp_levels is None:
                if entry_price > 0:
                    result['take_profit_levels'] = [
                        entry_price * 1.02,
                        entry_price * 1.04,
                        entry_price * 1.06
                    ]
                else:
                    result['take_profit_levels'] = [0, 0, 0]
                return result

            if not isinstance(tp_levels, list):
                try:
                    single_tp = float(tp_levels)
                    result['take_profit_levels'] = [
                        single_tp,
                        single_tp * 1.1,
                        single_tp * 1.2
                    ]
                except:
                    if entry_price > 0:
                        result['take_profit_levels'] = [
                            entry_price * 1.02,
                            entry_price * 1.04,
                            entry_price * 1.06
                        ]
                    else:
                        result['take_profit_levels'] = [0, 0, 0]
                return result

            if len(tp_levels) == 0:
                if entry_price > 0:
                    result['take_profit_levels'] = [
                        entry_price * 1.02,
                        entry_price * 1.04,
                        entry_price * 1.06
                    ]
                else:
                    result['take_profit_levels'] = [0, 0, 0]
                return result

            if len(tp_levels) < 3:
                valid = []
                for tp in tp_levels:
                    try:
                        valid.append(float(tp))
                    except:
                        pass
                if valid:
                    while len(valid) < 3:
                        valid.append(valid[-1] * 1.1)
                    result['take_profit_levels'] = valid
                else:
                    if entry_price > 0:
                        result['take_profit_levels'] = [
                            entry_price * 1.02,
                            entry_price * 1.04,
                            entry_price * 1.06
                        ]
                    else:
                        result['take_profit_levels'] = [0, 0, 0]
                return result

            cleaned = []
            for tp in tp_levels[:3]:
                try:
                    cleaned.append(float(tp))
                except:
                    cleaned.append(cleaned[-1] * 1.1 if cleaned else 0)

            result['take_profit_levels'] = cleaned
            return result

        except Exception as e:
            logger.error(f"{symbol}: Error normalizing TP: {e}")
            entry_price = result.get('entry_price', 0)
            if entry_price > 0:
                result['take_profit_levels'] = [
                    entry_price * 1.02,
                    entry_price * 1.04,
                    entry_price * 1.06
                ]
            else:
                result['take_profit_levels'] = [0, 0, 0]
            return result

    def _extract_json_from_response(self, text: str) -> Optional[Dict]:
        from ai.anthropic_client import AnthropicClient
        temp = type('obj', (object,), {
            '_extract_json_from_response': AnthropicClient._extract_json_from_response
        })()
        return temp._extract_json_from_response(text)

    def get_config(self) -> Dict:
        return {
            'stage_providers': self.stage_providers,
            'stage_configs': self.stage_configs
        }
