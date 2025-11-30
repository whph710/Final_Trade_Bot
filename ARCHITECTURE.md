# 🏗️ Architecture Guide - Правила модульности

> **Цель:** Сохранить модульную архитектуру, лёгкую заменяемость компонентов и простоту расширения

---

## 📐 Основные принципы

### 1. **Единый формат данных (Data Contract)**

Все модули работают с **единым форматом данных** - это основа модульности.

```python
# ✅ ПРАВИЛЬНО: Единый формат
@dataclass
class NormalizedCandles:
    timestamps: np.ndarray
    opens: np.ndarray
    highs: np.ndarray
    lows: np.ndarray
    closes: np.ndarray
    volumes: np.ndarray
    is_valid: bool
    symbol: str
    interval: str
```

**Правило:** Если создаёшь новый источник данных (не Bybit), создай адаптер который преобразует в `NormalizedCandles`.

---

### 2. **Separation of Concerns (Разделение ответственности)**

Каждый модуль отвечает **только за одну вещь**:

```
data_providers/  → Получение данных
indicators/      → Расчёт индикаторов
stages/          → Бизнес-логика pipeline
ai/              → AI провайдеры
telegram/        → Интерфейс для пользователя
utils/           → Вспомогательные функции
```

**❌ НЕ ДЕЛАЙ:**
```python
# indicators/ema.py
def analyze_ema(candles):
    # ...
    # ❌ ПЛОХО: индикатор отправляет в Telegram
    await bot.send_message("EMA signal!")
```

**✅ ДЕЛАЙ:**
```python
# indicators/ema.py
def analyze_ema(candles) -> EMAAnalysis:
    # Только расчёт и возврат результата
    return EMAAnalysis(...)

# stages/stage1_filter.py
ema_result = analyze_ema(candles)
# Здесь решаем что делать с результатом
```

---

### 3. **Input/Output контракты**

Каждая функция должна иметь **чёткий контракт**:

```python
# ✅ ПРАВИЛЬНО: Чёткие типы
def analyze_triple_ema(
    candles: NormalizedCandles,
    fast: int = 9,
    medium: int = 21,
    slow: int = 50
) -> Optional[EMAAnalysis]:
    """
    Анализ Triple EMA
    
    Args:
        candles: Нормализованные свечи
        fast: Период быстрой EMA
        medium: Период средней EMA
        slow: Период медленной EMA
        
    Returns:
        EMAAnalysis объект или None при ошибке
    """
    pass
```

**Правило:** Всегда используй type hints + docstrings.

---

## 🧩 Как добавить новый компонент

### 📊 Добавление нового индикатора

**Шаг 1:** Создай файл `indicators/my_indicator.py`

```python
"""
My Indicator
Файл: indicators/my_indicator.py

Описание индикатора
"""

import numpy as np
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class MyIndicatorAnalysis:
    """
    Результат анализа индикатора
    
    Attributes:
        value: Основное значение
        trend: 'UP' | 'DOWN' | 'NEUTRAL'
        confidence_adjustment: Корректировка confidence (-15 до +15)
        details: Текстовое описание
    """
    value: float
    trend: str
    confidence_adjustment: int
    details: str


def calculate_my_indicator(
    prices: np.ndarray,
    period: int = 14
) -> np.ndarray:
    """
    Расчёт индикатора
    
    Args:
        prices: Массив цен
        period: Период
        
    Returns:
        Массив значений индикатора
    """
    # Твоя логика
    pass


def analyze_my_indicator(
    candles: 'NormalizedCandles',  # Единый формат!
    period: int = 14
) -> Optional[MyIndicatorAnalysis]:
    """
    Анализ индикатора
    
    Args:
        candles: NormalizedCandles объект
        period: Период
        
    Returns:
        MyIndicatorAnalysis или None при ошибке
    """
    if not candles or not candles.is_valid:
        return None
    
    try:
        # 1. Рассчитай значения
        values = calculate_my_indicator(candles.closes, period)
        
        # 2. Определи тренд
        trend = _determine_trend(values)
        
        # 3. Рассчитай корректировку confidence
        adjustment = _calculate_adjustment(values, trend)
        
        # 4. Создай результат
        return MyIndicatorAnalysis(
            value=float(values[-1]),
            trend=trend,
            confidence_adjustment=adjustment,
            details=f"My indicator: {values[-1]:.2f}"
        )
        
    except Exception as e:
        logger.error(f"My indicator error: {e}")
        return None


def _determine_trend(values: np.ndarray) -> str:
    """Вспомогательная функция"""
    # Логика определения тренда
    pass


def _calculate_adjustment(values: np.ndarray, trend: str) -> int:
    """Вспомогательная функция"""
    # Логика расчёта adjustment
    pass
```

**Шаг 2:** Добавь в `indicators/__init__.py`

```python
from .my_indicator import (
    calculate_my_indicator,
    analyze_my_indicator,
    MyIndicatorAnalysis
)

__all__ = [
    # ... existing
    'calculate_my_indicator',
    'analyze_my_indicator',
    'MyIndicatorAnalysis',
]
```

**Шаг 3:** Используй в stages/

```python
from indicators import analyze_my_indicator

# В stage1_filter.py или stage3_analysis.py
my_result = analyze_my_indicator(candles)

if my_result:
    confidence += my_result.confidence_adjustment
```

---

### 🔄 Добавление нового data provider (не Bybit)

**Шаг 1:** Создай `data_providers/binance_client.py` (пример)

```python
"""
Binance API Client
"""

async def fetch_candles_binance(
    symbol: str,
    interval: str,
    limit: int
) -> List[List]:
    """
    Получить свечи с Binance
    
    Returns:
        Raw данные в формате Binance
    """
    # Твоя логика работы с Binance API
    pass
```

**Шаг 2:** Используй существующий `normalize_candles`

```python
from data_providers import normalize_candles

# Получаем данные с Binance
raw_candles = await fetch_candles_binance('BTCUSDT', '1h', 100)

# Нормализуем в единый формат
candles = normalize_candles(
    raw_candles,
    symbol='BTCUSDT',
    interval='1h'
)

# Теперь все индикаторы работают!
ema_result = analyze_triple_ema(candles)
```

**Правило:** Любой новый источник данных ДОЛЖЕН нормализоваться в `NormalizedCandles`.

---

### 🤖 Добавление нового AI провайдера

**Шаг 1:** Создай `ai/openai_client.py` (пример)

```python
"""
OpenAI GPT Client
"""

import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


class OpenAIClient:
    """Клиент для OpenAI API"""
    
    def __init__(self, api_key: str, model: str = "gpt-4"):
        self.api_key = api_key
        self.model = model
        logger.info(f"OpenAI client initialized: {model}")
    
    async def select_pairs(
        self,
        pairs_data: List[Dict],
        max_pairs: int = 3,
        temperature: float = 0.3,
        max_tokens: int = 2000
    ) -> List[str]:
        """
        Stage 2: Выбор пар
        
        ВАЖНО: Должен иметь ту же сигнатуру что DeepSeek/Claude!
        """
        # Твоя логика
        pass
    
    async def analyze_comprehensive(
        self,
        symbol: str,
        comprehensive_data: Dict,
        temperature: float = 0.7,
        max_tokens: int = 4000
    ) -> Dict:
        """
        Stage 3: Comprehensive analysis
        
        ВАЖНО: Должен иметь ту же сигнатуру что DeepSeek/Claude!
        """
        # Твоя логика
        pass
```

**Шаг 2:** Добавь в `ai/ai_router.py`

```python
class AIRouter:
    async def _get_openai_client(self) -> Optional['OpenAIClient']:
        """Получить OpenAI клиент"""
        if self.openai_client:
            return self.openai_client
        
        from config import config
        
        if not config.OPENAI_API_KEY:
            return None
        
        from ai.openai_client import OpenAIClient
        
        self.openai_client = OpenAIClient(
            api_key=config.OPENAI_API_KEY,
            model=config.OPENAI_MODEL
        )
        
        return self.openai_client
    
    async def _get_provider_client(self, stage: str):
        provider = self.stage_providers.get(stage, 'deepseek')
        
        # Добавляем новый провайдер
        if provider == 'openai':
            client = await self._get_openai_client()
            return 'openai', client
        
        # ... existing providers
```

**Шаг 3:** Добавь в `config.py`

```python
# OpenAI Configuration
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4-turbo')
```

**Шаг 4:** В `.env` выбери провайдера

```env
STAGE2_PROVIDER=openai  # Теперь можем использовать OpenAI!
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4-turbo
```

**Правило:** Новые AI провайдеры должны иметь те же методы `select_pairs()` и `analyze_comprehensive()`.

---

### 🎯 Добавление нового Stage (Stage 4, 5...)

**Шаг 1:** Создай `stages/stage4_validation.py`

```python
"""
Stage 4: Custom Validation
"""

import logging
from typing import List

logger = logging.getLogger(__name__)


async def run_stage4(
    signals: List['TradingSignal']
) -> tuple[List['TradingSignal'], List[Dict]]:
    """
    Stage 4: Дополнительная валидация
    
    Args:
        signals: Сигналы из Stage 3
        
    Returns:
        (approved, rejected)
    """
    logger.info(f"Stage 4: Validating {len(signals)} signals")
    
    approved = []
    rejected = []
    
    for signal in signals:
        try:
            # Твоя логика валидации
            if _custom_validation(signal):
                approved.append(signal)
            else:
                rejected.append({
                    'symbol': signal.symbol,
                    'reason': 'Failed Stage 4 validation'
                })
        except Exception as e:
            logger.error(f"Stage 4 error for {signal.symbol}: {e}")
            rejected.append({
                'symbol': signal.symbol,
                'reason': f'Error: {str(e)}'
            })
    
    logger.info(
        f"Stage 4 complete: {len(approved)} approved, "
        f"{len(rejected)} rejected"
    )
    
    return approved, rejected


def _custom_validation(signal: 'TradingSignal') -> bool:
    """Твоя кастомная валидация"""
    # Пример: проверка минимального R/R
    if signal.risk_reward_ratio < 2.0:
        return False
    
    # Пример: проверка времени суток
    from datetime import datetime
    hour = datetime.now().hour
    if hour < 8 or hour > 22:  # Не торгуем ночью
        return False
    
    return True
```

**Шаг 2:** Добавь в `stages/__init__.py`

```python
from .stage4_validation import run_stage4

__all__ = [
    # ... existing
    'run_stage4',
]
```

**Шаг 3:** Интегрируй в pipeline (в `main.py` или `telegram/bot_main.py`)

```python
# После Stage 3
approved_signals, rejected_signals = await run_stage3(selected_pairs)

# Добавляем Stage 4
if approved_signals:
    from stages import run_stage4
    
    final_approved, stage4_rejected = await run_stage4(approved_signals)
    rejected_signals.extend(stage4_rejected)
    approved_signals = final_approved
```

---

### 📱 Добавление нового интерфейса (Discord, Web API)

**Пример: Discord бот**

**Шаг 1:** Создай `discord/bot_main.py`

```python
"""
Discord Bot
"""

import discord
import logging

logger = logging.getLogger(__name__)


class TradingBotDiscord(discord.Client):
    """Discord бот для торговой системы"""
    
    async def on_ready(self):
        logger.info(f"Discord bot ready: {self.user}")
    
    async def on_message(self, message):
        if message.content.startswith('!analyze'):
            # Используем существующий pipeline!
            from stages import run_stage1, run_stage2, run_stage3
            from data_providers import get_all_trading_pairs
            
            # Запускаем анализ
            pairs = await get_all_trading_pairs()
            candidates = await run_stage1(pairs)
            selected = await run_stage2(candidates)
            approved, rejected = await run_stage3(selected)
            
            # Форматируем для Discord
            await message.channel.send(
                f"Found {len(approved)} signals!"
            )
```

**Правило:** Новые интерфейсы используют существующие stages/, не дублируют логику.

---

## 🔒 Правила конфигурации

### 1. Секреты → `.env`

```env
# ✅ ПРАВИЛЬНО: Секреты в .env
DEEPSEEK_API_KEY=sk-...
TELEGRAM_BOT_TOKEN=123456:ABC...
```

### 2. Параметры стратегии → `config.py`

```python
# ✅ ПРАВИЛЬНО: Параметры в config.py
EMA_FAST = 9
EMA_MEDIUM = 21
EMA_SLOW = 50
MIN_CONFIDENCE = 60
```

### 3. Провайдеры → `.env`

```env
# ✅ ПРАВИЛЬНО: Выбор провайдера в .env
STAGE2_PROVIDER=deepseek
STAGE3_PROVIDER=claude
```

**Правило:** Легко менять провайдеров без изменения кода.

---

## 📦 Правила импортов

### ✅ ПРАВИЛЬНО:

```python
# Импорт из пакетов
from data_providers import fetch_candles, normalize_candles
from indicators import analyze_triple_ema
from stages import run_stage1

# Импорт конфигурации
from config import config

# Импорт типов
from typing import List, Dict, Optional
```

### ❌ НЕПРАВИЛЬНО:

```python
# ❌ Абсолютные пути из старой структуры
from trade_bot_programm.func_async import fetch_klines

# ❌ Циклические импорты
# indicators/ema.py
from stages import run_stage1  # ❌ Индикатор не должен знать о stages

# ❌ Прямые импорты модулей вместо пакетов
from indicators.ema import analyze_triple_ema  # ❌ Используй через __init__.py
```

---

## 🧪 Правила тестирования

### 1. Тестируй модули отдельно

```python
# test_indicators.py

async def test_ema_analysis():
    """Тест Triple EMA индикатора"""
    from data_providers import fetch_candles, normalize_candles
    from indicators import analyze_triple_ema
    
    # Получаем тестовые данные
    raw_candles = await fetch_candles('BTCUSDT', '240', 100)
    candles = normalize_candles(raw_candles, 'BTCUSDT', '240')
    
    # Тестируем индикатор
    result = analyze_triple_ema(candles)
    
    assert result is not None
    assert result.alignment in ['BULLISH', 'BEARISH', 'NEUTRAL']
    assert 0 <= result.confidence_score <= 100
```

### 2. Mock внешние зависимости

```python
# test_stages.py

async def test_stage1_with_mock_data():
    """Тест Stage 1 с mock данными"""
    from stages import run_stage1
    
    # Mock данные (не реальный API call)
    mock_pairs = ['BTCUSDT', 'ETHUSDT']
    
    candidates = await run_stage1(mock_pairs)
    
    assert isinstance(candidates, list)
```

---

## 📊 Мониторинг модульности

### Checklist для новых фич:

- [ ] Использует `NormalizedCandles` для работы со свечами?
- [ ] Имеет чёткие type hints?
- [ ] Имеет docstrings?
- [ ] Не зависит от других модулей напрямую?
- [ ] Экспортируется через `__init__.py`?
- [ ] Конфигурация в `config.py` или `.env`?
- [ ] Логирование через `utils.logger`?
- [ ] Можно протестировать отдельно?

---

## 🚨 Анти-паттерны (НЕ ДЕЛАЙ)

### ❌ 1. Жёсткие связи между модулями

```python
# indicators/ema.py

# ❌ ПЛОХО: Индикатор знает о Telegram
from telegram.bot_main import send_message

def analyze_ema(candles):
    result = ...
    send_message(f"EMA signal: {result}")  # ❌
    return result
```

**✅ Правильно:** Индикатор возвращает результат, telegram решает что с ним делать.

### ❌ 2. Дублирование логики

```python
# ❌ ПЛОХО: Каждый stage рассчитывает EMA по-своему
# stage1_filter.py
ema9 = some_custom_ema(candles, 9)

# stage2_selection.py  
ema9 = another_custom_ema(candles, 9)

# stage3_analysis.py
ema9 = yet_another_ema(candles, 9)
```

**✅ Правильно:** Используй один `calculate_ema` из `indicators/`.

### ❌ 3. Смешивание форматов данных

```python
# ❌ ПЛОХО: Каждый модуль ожидает свой формат
def my_indicator(candles_dict: Dict):  # ❌
    pass

def other_indicator(candles_list: List[List]):  # ❌
    pass
```

**✅ Правильно:** Все работают с `NormalizedCandles`.

---

## 📚 Дополнительные ресурсы

### Примеры кода:

- `indicators/ema.py` - образец модульного индикатора
- `stages/stage1_filter.py` - образец stage с чёткими boundaries
- `ai/ai_router.py` - образец легко расширяемого роутера

### Документация:

- `README.md` - Обзор проекта
- `TODO.md` - План развития
- `ARCHITECTURE.md` - Этот документ

---

## ✅ Принципы хорошей архитектуры

1. **DRY** (Don't Repeat Yourself) - Не дублируй код
2. **SOLID** - Особенно Single Responsibility Principle
3. **Loose Coupling** - Слабые связи между модулями
4. **High Cohesion** - Сильная связность внутри модуля
5. **Separation of Concerns** - Разделение ответственности
6. **Contract-Based Design** - Чёткие контракты input/output

**Помни:** Модульность = возможность заменить любой кусок без переписывания всего.

---

**Последнее обновление:** 2025-01-01  
**Версия:** 1.0