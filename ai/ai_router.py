"""
AI Router
Файл: ai/ai_router.py

Роутер для работы с разными AI провайдерами (DeepSeek, Claude)

ИСПРАВЛЕНО:
- Добавлен _serialize_to_json() для корректной сериализации dataclass объектов
- Улучшена обработка take_profit_levels (защита от None)
"""

import logging
from typing import List, Dict, Optional
from dataclasses import is_dataclass, asdict

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
        """
        Получить DeepSeek клиент для конкретного stage

        Args:
            stage: 'stage2' или 'stage3'

        Returns:
            DeepSeekClient или None
        """
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
        """
        Получить Claude клиент

        Returns:
            AnthropicClient или None
        """
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
        """
        Получить клиент для конкретного stage

        Args:
            stage: 'stage2' или 'stage3'

        Returns:
            (provider_name: str, client: object) или (None, None)
        """
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
        """
        Stage 2: Выбор пар через AI

        Args:
            pairs_data: Данные о парах
            max_pairs: Максимальное количество пар

        Returns:
            Список выбранных символов
        """
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
        """
        Stage 3: Comprehensive analysis через AI

        Args:
            symbol: Торговая пара
            comprehensive_data: Полные данные для анализа

        Returns:
            Результат анализа
        """
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
        """
        DeepSeek comprehensive analysis implementation

        Args:
            symbol: Торговая пара
            comprehensive_data: Данные
            client: DeepSeek клиент
            config: Конфигурация (temperature, max_tokens)

        Returns:
            Результат анализа
        """
        import json
        from pathlib import Path

        try:
            from ai.deepseek_client import load_prompt_cached

            # Загружаем промпт
            system_prompt = load_prompt_cached("prompt_analyze.txt")

            # Сериализуем данные с конвертацией dataclass → dict
            analysis_data = {
                'symbol': symbol,
                'candles_1h': comprehensive_data.get('candles_1h', [])[-100:],
                'candles_4h': comprehensive_data.get('candles_4h', [])[-60:],
                'indicators_1h': comprehensive_data.get('indicators_1h', {}),
                'indicators_4h': comprehensive_data.get('indicators_4h', {}),
                'current_price': comprehensive_data.get('current_price', 0),
                'market_data': comprehensive_data.get('market_data', {}),
                'correlation_data': self._serialize_to_json(comprehensive_data.get('correlation_data', {})),
                'volume_profile': self._serialize_to_json(comprehensive_data.get('volume_profile')),
                'vp_analysis': self._serialize_to_json(comprehensive_data.get('vp_analysis')),
                'btc_candles_1h': comprehensive_data.get('btc_candles_1h', [])[-100:],
                'btc_candles_4h': comprehensive_data.get('btc_candles_4h', [])[-60:]
            }

            data_json = json.dumps(analysis_data, separators=(',', ':'))

            logger.debug(
                f"Stage 3 {symbol}: analysis data size = {len(data_json)} chars"
            )

            # Формируем промпт
            user_prompt = f"{system_prompt}\n\nData:\n{data_json}"

            # Вызов DeepSeek
            response = await client.chat(
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert institutional swing trader with 20 years experience."
                    },
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=config['max_tokens'],
                temperature=config['temperature']
            )

            # Парсинг JSON из ответа
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

            # ✅ УЛУЧШЕННАЯ нормализация take_profit_levels
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

    def _normalize_take_profit_levels(self, result: Dict, symbol: str) -> Dict:
        """
        ✅ НОВАЯ ФУНКЦИЯ: Нормализация take_profit_levels с защитой от None и неправильных типов

        Args:
            result: Результат от AI
            symbol: Символ (для логирования)

        Returns:
            result с нормализованным take_profit_levels
        """
        try:
            tp_levels = result.get('take_profit_levels')
            entry_price = result.get('entry_price', 0)

            # Случай 1: None или отсутствует
            if tp_levels is None:
                logger.warning(f"{symbol}: take_profit_levels is None, generating defaults")
                if entry_price > 0:
                    result['take_profit_levels'] = [
                        entry_price * 1.02,  # TP1 = +2%
                        entry_price * 1.04,  # TP2 = +4%
                        entry_price * 1.06   # TP3 = +6%
                    ]
                else:
                    result['take_profit_levels'] = [0, 0, 0]
                return result

            # Случай 2: Не список (может быть число, строка и т.д.)
            if not isinstance(tp_levels, list):
                logger.warning(f"{symbol}: take_profit_levels is not list ({type(tp_levels)}), converting")
                try:
                    # Пытаемся конвертировать в float
                    single_tp = float(tp_levels)
                    result['take_profit_levels'] = [
                        single_tp,
                        single_tp * 1.1,
                        single_tp * 1.2
                    ]
                except (ValueError, TypeError):
                    # Не удалось конвертировать - генерируем дефолты
                    logger.warning(f"{symbol}: Could not convert tp_levels to float, using defaults")
                    if entry_price > 0:
                        result['take_profit_levels'] = [
                            entry_price * 1.02,
                            entry_price * 1.04,
                            entry_price * 1.06
                        ]
                    else:
                        result['take_profit_levels'] = [0, 0, 0]
                return result

            # Случай 3: Список, но меньше 3 элементов
            if len(tp_levels) < 3:
                logger.debug(f"{symbol}: take_profit_levels has {len(tp_levels)} elements, extending to 3")

                # Фильтруем None и конвертируем в float
                valid_tps = []
                for tp in tp_levels:
                    if tp is not None:
                        try:
                            valid_tps.append(float(tp))
                        except (ValueError, TypeError):
                            pass

                # Если есть хоть один валидный TP - используем его
                if valid_tps:
                    while len(valid_tps) < 3:
                        last_tp = valid_tps[-1]
                        valid_tps.append(last_tp * 1.1)
                    result['take_profit_levels'] = valid_tps
                else:
                    # Нет валидных TP - генерируем дефолты
                    if entry_price > 0:
                        result['take_profit_levels'] = [
                            entry_price * 1.02,
                            entry_price * 1.04,
                            entry_price * 1.06
                        ]
                    else:
                        result['take_profit_levels'] = [0, 0, 0]
                return result

            # Случай 4: Список из 3+ элементов - проверяем на None
            cleaned_tps = []
            for tp in tp_levels[:3]:  # Берём первые 3
                if tp is None:
                    logger.warning(f"{symbol}: Found None in take_profit_levels")
                    # Если есть предыдущий TP - используем его * 1.1, иначе используем entry_price
                    if cleaned_tps:
                        cleaned_tps.append(cleaned_tps[-1] * 1.1)
                    elif entry_price > 0:
                        cleaned_tps.append(entry_price * 1.02)
                    else:
                        cleaned_tps.append(0)
                else:
                    try:
                        cleaned_tps.append(float(tp))
                    except (ValueError, TypeError):
                        logger.warning(f"{symbol}: Could not convert TP to float: {tp}")
                        if cleaned_tps:
                            cleaned_tps.append(cleaned_tps[-1] * 1.1)
                        else:
                            cleaned_tps.append(0)

            result['take_profit_levels'] = cleaned_tps
            return result

        except Exception as e:
            logger.error(f"{symbol}: Error normalizing take_profit_levels: {e}")
            # В случае любой ошибки - возвращаем безопасные дефолты
            result['take_profit_levels'] = [0, 0, 0]
            return result

    def _serialize_to_json(self, obj):
        """
        Рекурсивно конвертирует dataclass объекты в dict для JSON сериализации

        Args:
            obj: Любой объект (может быть dataclass, dict, list, примитив)

        Returns:
            JSON-сериализуемый объект
        """
        if obj is None:
            return None

        # Если это dataclass - конвертируем в dict
        if is_dataclass(obj):
            return asdict(obj)

        # Если это dict - рекурсивно обрабатываем значения
        if isinstance(obj, dict):
            return {k: self._serialize_to_json(v) for k, v in obj.items()}

        # Если это list/tuple - рекурсивно обрабатываем элементы
        if isinstance(obj, (list, tuple)):
            return [self._serialize_to_json(item) for item in obj]

        # Примитивы (str, int, float, bool) возвращаем как есть
        return obj

    def _extract_json_from_response(self, text: str) -> Optional[Dict]:
        """Извлечь JSON из ответа (используем метод из AnthropicClient)"""
        from ai.anthropic_client import AnthropicClient

        # Используем метод из AnthropicClient
        temp_client = type('obj', (object,), {
            '_extract_json_from_response': AnthropicClient._extract_json_from_response
        })()

        return temp_client._extract_json_from_response(text)

    def get_config(self) -> Dict:
        """Получить текущую конфигурацию"""
        return {
            'stage_providers': self.stage_providers,
            'stage_configs': self.stage_configs
        }