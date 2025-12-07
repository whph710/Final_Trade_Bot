"""
AI Package
Модули для работы с AI провайдерами (DeepSeek, Claude)
"""

from .deepseek_client import DeepSeekClient, load_prompt_cached
from .anthropic_client import AnthropicClient
from .ai_router import AIRouter

__all__ = [
    # DeepSeek
    'DeepSeekClient',
    'load_prompt_cached',

    # Anthropic
    'AnthropicClient',

    # Router
    'AIRouter',
]