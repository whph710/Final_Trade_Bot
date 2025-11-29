"""
Anthropic Claude AI Client
Файл: ai/anthropic_client.py

Клиент для работы с Claude API (Stage 2 и Stage 3)
"""

import asyncio
import json
import logging
from typing import List, Dict, Optional
from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)


class AnthropicClient:
    """Клиент для работы с Anthropic Claude API"""

    def __init__(
            self,
            api_key: str,
            model: str = "claude-sonnet-4-5-20250929",
            use_thinking: bool = False
    ):
        """
        Инициализация Claude клиента

        Args:
            api_key: Anthropic API key
            model: Название модели Claude
            use_thinking: Использовать extended thinking
        """
        if not api_key:
            raise ValueError("Anthropic API key is required")

        self.api_key = api_key
        self.model = model
        self.use_thinking = use_thinking

        self.client = AsyncAnthropic(api_key=self.api_key)

        logger.info(
            f"Anthropic client initialized: model={self.model}, "
            f"thinking={'ON' if self.use_thinking else 'OFF'}"
        )

    async def call(
            self,
            prompt: str,
            max_tokens: int = 2000,
            temperature: float = 0.7,
            use_thinking: Optional[bool] = None,
            timeout: int = 30
    ) -> str:
        """
        Базовый метод для вызова Claude API

        Args:
            prompt: Промпт для модели
            max_tokens: Максимум токенов
            temperature: Temperature
            use_thinking: Использовать thinking (override)
            timeout: Timeout в секундах

        Returns:
            Ответ модели
        """
        if use_thinking is None:
            use_thinking = self.use_thinking

        try:
            logger.debug(
                f"Claude API call: max_tokens={max_tokens}, "
                f"thinking={use_thinking}"
            )

            kwargs = {
                'model': self.model,
                'max_tokens': max_tokens,
                'messages': [{'role': 'user', 'content': prompt}],
                'temperature': temperature
            }

            if use_thinking:
                budget_tokens = min(10000, max_tokens * 3)
                kwargs['thinking'] = {
                    'type': 'enabled',
                    'budget_tokens': budget_tokens
                }

            response = await asyncio.wait_for(
                self.client.messages.create(**kwargs),
                timeout=timeout
            )

            # Извлечение thinking
            if use_thinking and hasattr(response, 'thinking'):
                thinking_text = str(response.thinking)
                logger.debug(
                    f"Claude thinking (first 300 chars): {thinking_text[:300]}"
                )

            result = response.content[0].text
            logger.debug(f"Claude response: {len(result)} chars")

            return result

        except asyncio.TimeoutError:
            logger.error(f"Claude timeout: {timeout}s")
            raise
        except Exception as e:
            logger.error(f"Claude API error: {e}")
            raise

    async def select_pairs(
            self,
            pairs_data: List[Dict],
            max_pairs: Optional[int] = None,
            temperature: float = 0.3,
            max_tokens: int = 2000
    ) -> List[str]:
        """
        Stage 2: Выбор пар через Claude

        Args:
            pairs_data: Данные о парах
            max_pairs: Максимальное количество пар
            temperature: Temperature
            max_tokens: Максимум токенов

        Returns:
            Список выбранных символов
        """
        if not pairs_data:
            logger.warning("Claude Stage 2: No pairs data provided")
            return []

        try:
            from ai.deepseek_client import load_prompt_cached

            # Загружаем промпт
            system_prompt = load_prompt_cached("prompt_select.txt")

            # Формируем compact данные
            compact_data = {}
            for item in pairs_data:
                symbol = item['symbol']

                indicators_1h = item.get('indicators_1h', {})
                indicators_4h = item.get('indicators_4h', {})

                if not indicators_1h or not indicators_4h:
                    continue

                compact_data[symbol] = {
                    'base_signal': {
                        'direction': item.get('direction', 'NONE'),
                        'confidence': item.get('confidence', 0)
                    },
                    'candles_1h': item.get('candles_1h', [])[-30:],
                    'candles_4h': item.get('candles_4h', [])[-30:],
                    'indicators_1h': indicators_1h,
                    'indicators_4h': indicators_4h
                }

            if not compact_data:
                logger.warning("Claude Stage 2: No valid compact data")
                return []

            # JSON payload
            json_payload = json.dumps(compact_data, separators=(',', ':'))

            logger.info(
                f"Claude Stage 2: analyzing {len(compact_data)} pairs "
                f"(data size: {len(json_payload)} chars)"
            )

            # Полный промпт
            full_prompt = f"{system_prompt}\n\nData:\n{json_payload}"

            # Вызов Claude
            response = await self.call(
                prompt=full_prompt,
                max_tokens=max_tokens,
                temperature=temperature
            )

            # Парсинг результата
            result = self._extract_json_from_response(response)

            if result and 'selected_pairs' in result:
                selected_pairs = result['selected_pairs']

                if max_pairs:
                    selected_pairs = selected_pairs[:max_pairs]

                logger.info(
                    f"Claude Stage 2: selected {len(selected_pairs)} pairs"
                )
                return selected_pairs

            logger.warning("Claude Stage 2: No pairs in response")
            return []

        except asyncio.TimeoutError:
            logger.error("Claude Stage 2: timeout")
            return []
        except Exception as e:
            logger.error(f"Claude Stage 2 error: {e}")
            return []

    async def analyze_comprehensive(
            self,
            symbol: str,
            comprehensive_data: Dict,
            temperature: float = 0.7,
            max_tokens: int = 4000
    ) -> Dict:
        """
        Stage 3: Comprehensive analysis через Claude

        Args:
            symbol: Торговая пара
            comprehensive_data: Полные данные для анализа
            temperature: Temperature
            max_tokens: Максимум токенов

        Returns:
            Результат анализа
        """
        try:
            from ai.deepseek_client import load_prompt_cached

            logger.debug(f"Claude Stage 3: analyzing {symbol}")

            # Загружаем промпт
            prompt_template = load_prompt_cached("prompt_analyze.txt")

            # JSON данных
            data_json = json.dumps(comprehensive_data, separators=(',', ':'))

            logger.debug(f"Claude Stage 3: data size = {len(data_json)} chars")

            # Полный промпт
            full_prompt = f"{prompt_template}\n\nData:\n{data_json}"

            # Вызов Claude
            response = await self.call(
                prompt=full_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=120  # Увеличенный timeout для анализа
            )

            # Парсинг результата
            result = self._extract_json_from_response(response)

            if result:
                result['symbol'] = symbol
                logger.debug(f"Claude Stage 3: analysis complete for {symbol}")
                return result
            else:
                logger.warning(f"Claude Stage 3: invalid response for {symbol}")
                return {
                    'symbol': symbol,
                    'signal': 'NO_SIGNAL',
                    'confidence': 0,
                    'rejection_reason': 'Invalid Claude response'
                }

        except Exception as e:
            logger.error(f"Claude Stage 3 error for {symbol}: {e}")
            return {
                'symbol': symbol,
                'signal': 'NO_SIGNAL',
                'confidence': 0,
                'rejection_reason': f'Exception: {str(e)[:100]}'
            }

    def _extract_json_from_response(self, text: str) -> Optional[Dict]:
        """
        Извлечь JSON из ответа Claude

        Args:
            text: Ответ от модели

        Returns:
            Словарь или None
        """
        if not text or len(text) < 10:
            return None

        try:
            text = text.strip()

            # Удаляем markdown code blocks
            if '```json' in text:
                start = text.find('```json') + 7
                end = text.find('```', start)
                if end != -1:
                    text = text[start:end].strip()
            elif '```' in text:
                start = text.find('```') + 3
                end = text.find('```', start)
                if end != -1:
                    text = text[start:end].strip()

            # Ищем JSON объект
            start_idx = text.find('{')
            if start_idx == -1:
                return None

            brace_count = 0
            for i, char in enumerate(text[start_idx:], start_idx):
                if char == '{':
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        json_str = text[start_idx:i + 1]
                        return json.loads(json_str)

            return None

        except json.JSONDecodeError as e:
            logger.warning(f"Claude JSON parsing error: {e}")
            return None
        except Exception as e:
            logger.error(f"Claude parsing error: {e}")
            return None