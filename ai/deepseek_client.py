"""
DeepSeek AI Client
Файл: ai/deepseek_client.py

Клиент для работы с DeepSeek API (Stage 2 и Stage 3)
"""

import json
import logging
from typing import List, Dict, Optional
from pathlib import Path
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

_prompt_cache: Dict[str, str] = {}


def load_prompt_cached(filename: str) -> str:
    """
    Загрузить промпт с кэшированием

    Args:
        filename: Имя файла промпта

    Returns:
        Содержимое промпта
    """
    if filename in _prompt_cache:
        logger.debug(f"Prompt loaded from cache: {filename}")
        return _prompt_cache[filename]

    search_paths = [
        Path(filename),
        Path(__file__).parent / "prompts" / Path(filename).name,
        Path(__file__).parent.parent / "prompts" / Path(filename).name,
    ]

    filepath = None
    for path in search_paths:
        if path.exists() and path.is_file():
            filepath = path
            logger.debug(f"Prompt found at: {filepath}")
            break

    if not filepath:
        error_msg = f"Prompt file '{filename}' not found. Searched in:\n"
        for path in search_paths:
            error_msg += f"  - {path.absolute()}\n"
        logger.error(error_msg)
        raise FileNotFoundError(error_msg)

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                raise ValueError(f"Prompt file is empty: {filename}")
            _prompt_cache[filename] = content
            logger.info(f"Prompt cached: {filepath.name} ({len(content)} chars)")
            return content
    except Exception as e:
        logger.error(f"Error loading prompt {filename}: {e}")
        raise


class DeepSeekClient:
    """Клиент для работы с DeepSeek API"""

    def __init__(
            self,
            api_key: str,
            model: str = "deepseek-chat",
            use_reasoning: bool = False,
            base_url: str = "https://api.deepseek.com"
    ):
        """
        Инициализация DeepSeek клиента

        Args:
            api_key: DeepSeek API key
            model: Название модели
            use_reasoning: Использовать reasoning mode (для deepseek-reasoner)
            base_url: Base URL для API
        """
        if not api_key:
            raise ValueError("DeepSeek API key is required")

        self.api_key = api_key
        self.model = model
        self.use_reasoning = use_reasoning
        self.base_url = base_url

        # Проверка reasoning совместимости
        self.is_reasoning_model = "reasoner" in model.lower()

        if use_reasoning and not self.is_reasoning_model:
            logger.warning(
                f"use_reasoning=True but model {model} doesn't support reasoning - disabling"
            )
            self.use_reasoning = False

        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

        logger.info(
            f"DeepSeek client initialized: model={self.model}, "
            f"reasoning={'ON' if self.use_reasoning else 'OFF'}"
        )

    async def select_pairs(
            self,
            pairs_data: List[Dict],
            max_pairs: Optional[int] = None,
            temperature: float = 0.3,
            max_tokens: int = 2000
    ) -> List[str]:
        """
        Stage 2: Выбор пар через DeepSeek

        Args:
            pairs_data: Данные о парах с compact indicators
            max_pairs: Максимальное количество пар
            temperature: Temperature для генерации
            max_tokens: Максимум токенов

        Returns:
            Список выбранных символов
        """
        if not pairs_data:
            logger.warning("DeepSeek Stage 2: No pairs data provided")
            return []

        try:
            # Загружаем промпт
            system_prompt = load_prompt_cached("prompt_select.txt")

            # Формируем описание пар
            pairs_info = []
            for pair in pairs_data:
                symbol = pair.get('symbol', 'UNKNOWN')

                info = [f"Symbol: {symbol}"]
                info.append(
                    f"Direction: {pair.get('direction', 'NONE')} "
                    f"({pair.get('confidence', 0)}%)"
                )

                # 1H indicators
                if pair.get('indicators_1h'):
                    current_1h = pair['indicators_1h'].get('current', {})
                    if current_1h:
                        info.append(
                            f"1H: RSI={current_1h.get('rsi', 0):.1f}, "
                            f"Price=${current_1h.get('price', 0):.2f}"
                        )

                # 4H indicators
                if pair.get('indicators_4h'):
                    current_4h = pair['indicators_4h'].get('current', {})
                    if current_4h:
                        info.append(
                            f"4H: RSI={current_4h.get('rsi', 0):.1f}, "
                            f"Vol={current_4h.get('volume_ratio', 0):.2f}"
                        )

                pairs_info.append('\n'.join(info))

            pairs_text = "\n---\n".join(pairs_info)

            # User prompt
            limit_text = f"максимум {max_pairs} пар" if max_pairs else "без ограничения"
            user_prompt = (
                f"Проанализируй {len(pairs_data)} торговых пар с компактными "
                f"multi-timeframe данными (1H/4H) и выбери {limit_text} "
                f"с наилучшим потенциалом для swing trading:\n\n{pairs_text}\n\n"
                f"Верни ТОЛЬКО JSON в формате: {{\"selected_pairs\": [\"BTCUSDT\", \"ETHUSDT\"]}}"
            )

            logger.info(
                f"DeepSeek Stage 2: analyzing {len(pairs_data)} pairs "
                f"(limit: {max_pairs})"
            )

            # API запрос
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature
            )

            # Извлечение reasoning (если есть)
            if self.use_reasoning and self.is_reasoning_model:
                if hasattr(response.choices[0].message, 'reasoning_content'):
                    reasoning = response.choices[0].message.reasoning_content
                    if reasoning:
                        logger.debug(
                            f"DeepSeek reasoning (first 500 chars): {reasoning[:500]}"
                        )

            content = response.choices[0].message.content.strip()

            # Парсинг JSON
            selected = self._parse_selected_pairs(content, max_pairs)

            logger.info(f"DeepSeek Stage 2: selected {len(selected)} pairs")
            if selected:
                logger.debug(f"Selected pairs: {selected}")

            return selected

        except Exception as e:
            logger.error(f"DeepSeek Stage 2 error: {e}")
            import traceback
            traceback.print_exc()
            return []

    async def chat(
            self,
            messages: List[Dict[str, str]],
            max_tokens: int = 2000,
            temperature: float = 0.7
    ) -> str:
        """
        Общий метод для чата с DeepSeek (используется для Stage 3)

        Args:
            messages: Сообщения в формате OpenAI
            max_tokens: Максимум токенов
            temperature: Temperature

        Returns:
            Ответ модели
        """
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature
            )

            # Извлечение reasoning
            if self.use_reasoning and self.is_reasoning_model:
                if hasattr(response.choices[0].message, 'reasoning_content'):
                    reasoning = response.choices[0].message.reasoning_content
                    if reasoning:
                        logger.debug(
                            f"DeepSeek reasoning (first 300 chars): {reasoning[:300]}"
                        )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"DeepSeek chat error: {e}")
            raise

    def _parse_selected_pairs(self, content: str, max_pairs: Optional[int]) -> List[str]:
        """
        Парсинг выбранных пар из ответа

        Args:
            content: Ответ от модели
            max_pairs: Максимальное количество пар

        Returns:
            Список символов
        """
        selected = []

        try:
            # Удаляем markdown code blocks
            if '```json' in content:
                start = content.find('```json') + 7
                end = content.find('```', start)
                if end != -1:
                    content = content[start:end].strip()
            elif '```' in content:
                start = content.find('```') + 3
                end = content.find('```', start)
                if end != -1:
                    content = content[start:end].strip()

            # Парсим JSON
            data = json.loads(content)
            selected_pairs = data.get('selected_pairs', [])

            for symbol in selected_pairs:
                if isinstance(symbol, str):
                    clean = symbol.strip().upper()
                    if clean and clean not in selected:
                        selected.append(clean)

        except json.JSONDecodeError:
            logger.warning("DeepSeek JSON parsing failed, using fallback")

            # Fallback: извлекаем символы из текста
            for line in content.split('\n'):
                line = line.strip()
                if not line or line.startswith('#') or line.startswith('//'):
                    continue

                tokens = line.replace(',', ' ').replace('"', ' ').split()
                for token in tokens:
                    token = token.strip().upper()
                    if 2 <= len(token) <= 10 and token not in selected:
                        # Проверка что это похоже на символ
                        clean = token.replace('USDT', '').replace('USD', '')
                        if clean and clean.isalnum():
                            selected.append(token)

        # Применяем лимит
        if max_pairs and len(selected) > max_pairs:
            logger.debug(f"Trimming from {len(selected)} to {max_pairs} pairs")
            selected = selected[:max_pairs]

        return selected