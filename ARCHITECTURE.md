# 🏗️ Architecture Rules - Свод правил расширения системы

> **Цель:** Гарантировать модульность, асинхронность и единообразие стиля при любом расширении функционала

---

## 📋 Оглавление

1. [Фундаментальные принципы](#фундаментальные-принципы)
2. [Правила модульности](#правила-модульности)
3. [Правила асинхронности](#правила-асинхронности)
4. [Правила именования](#правила-именования)
5. [Правила обработки ошибок](#правила-обработки-ошибок)
6. [Правила логирования](#правила-логирования)
7. [Правила работы с данными](#правила-работы-с-данными)
8. [Чеклист для нового компонента](#чеклист-для-нового-компонента)

---

## Фундаментальные принципы

### 1. **Единый контракт данных**

**ПРАВИЛО:** Все модули работают с `NormalizedCandles` как основным форматом.

```python
# ✅ ПРАВИЛЬНО
def my_indicator(candles: NormalizedCandles) -> Optional[MyAnalysis]:
    if not candles or not candles.is_valid:
        return None
    # ...

# ❌ НЕПРАВИЛЬНО
def my_indicator(data: List[List]) -> Dict:  # Прямая работа с raw data
    pass
```

**Если создаёшь новый источник данных:**
```python
# 1. Получаешь raw данные
raw_data = await fetch_from_new_source()

# 2. ОБЯЗАТЕЛЬНО нормализуешь
candles = normalize_candles(raw_data, symbol, interval)

# 3. Проверяешь валидность
if not candles or not candles.is_valid:
    return None
```

---

### 2. **Separation of Concerns**

**ПРАВИЛО:** Один модуль = одна зона ответственности.

```
data_providers/  → Только получение данных
indicators/      → Только расчёт индикаторов
stages/          → Только бизнес-логика pipeline
ai/              → Только AI провайдеры
telegram/        → Только интерфейс пользователя
```

**Запрещено:**
```python
# ❌ indicators/ema.py
async def analyze_ema(candles):
    result = calculate_ema(...)
    await telegram_bot.send_message("EMA signal!")  # НЕЛЬЗЯ!
    return result
```

**Правильно:**
```python
# ✅ indicators/ema.py
def analyze_ema(candles: NormalizedCandles) -> EMAAnalysis:
    # Только расчёт
    return EMAAnalysis(...)

# ✅ stages/stage1_filter.py
ema_result = analyze_ema(candles)
if ema_result.confidence > 80:
    # Здесь решаем что делать с результатом
    pass
```

---

### 3. **Асинхронность по умолчанию**

**ПРАВИЛО:** Все I/O операции ДОЛЖНЫ быть асинхронными.

```python
# ✅ ПРАВИЛЬНО: Async для I/O
async def fetch_data(symbol: str) -> List:
    async with session.get(url) as response:
        return await response.json()

# ✅ ПРАВИЛЬНО: Sync для вычислений
def calculate_ema(prices: np.ndarray, period: int) -> np.ndarray:
    # Чистые вычисления - синхронно
    return result

# ❌ НЕПРАВИЛЬНО: Sync для I/O
def fetch_data_sync(symbol: str) -> List:
    response = requests.get(url)  # Блокирует event loop!
    return response.json()
```

---

## Правила модульности

### ПРАВИЛО 1: Явные Input/Output контракты

**Каждая функция должна иметь:**
- Type hints для всех параметров
- Type hints для возвращаемого значения
- Docstring с описанием Args и Returns

```python
# ✅ ОБРАЗЕЦ
def analyze_my_indicator(
    candles: NormalizedCandles,
    period: int = 14,
    threshold: float = 70.0
) -> Optional[MyIndicatorAnalysis]:
    """
    Анализ моего индикатора
    
    Args:
        candles: Нормализованные свечи
        period: Период индикатора (default: 14)
        threshold: Порог для сигнала (default: 70.0)
        
    Returns:
        MyIndicatorAnalysis объект или None при ошибке
    """
    if not candles or not candles.is_valid:
        return None
    
    try:
        # Твоя логика
        return MyIndicatorAnalysis(...)
    except Exception as e:
        logger.error(f"My indicator error: {e}")
        return None
```

---

### ПРАВИЛО 2: Dataclass для результатов

**Всегда используй `@dataclass` для структурированных результатов.**

```python
# ✅ ПРАВИЛЬНО
from dataclasses import dataclass

@dataclass
class MyIndicatorAnalysis:
    """Результат анализа"""
    value: float
    trend: str  # 'UP' | 'DOWN' | 'NEUTRAL'
    confidence_adjustment: int
    details: str

# ❌ НЕПРАВИЛЬНО
def analyze_my_indicator(...) -> Dict:
    return {
        'value': 42.5,
        'trend': 'UP',
        # Нет type safety, легко ошибиться
    }
```

**Почему:** Type safety, автодополнение в IDE, легче рефакторить.

---

### ПРАВИЛО 3: Экспорт через `__init__.py`

**Структура:**
```
my_module/
├── __init__.py         # Экспорты
├── core.py             # Основная логика
└── helpers.py          # Вспомогательные функции
```

```python
# ✅ my_module/__init__.py
from .core import my_main_function, MyDataClass
from .helpers import helper_function

__all__ = [
    'my_main_function',
    'MyDataClass',
    'helper_function',
]
```

```python
# ✅ Использование
from my_module import my_main_function  # Чисто!

# ❌ Использование
from my_module.core import my_main_function  # Жёсткая привязка к структуре
```

---

### ПРАВИЛО 4: Private vs Public

**Используй `_` префикс для внутренних функций:**

```python
# ✅ ПРАВИЛЬНО
def analyze_indicator(candles: NormalizedCandles) -> Analysis:
    """Public API - это видят пользователи модуля"""
    value = _calculate_raw_value(candles)
    trend = _determine_trend(value)
    return Analysis(value=value, trend=trend)

def _calculate_raw_value(candles: NormalizedCandles) -> float:
    """Private helper - детали реализации"""
    # ...

def _determine_trend(value: float) -> str:
    """Private helper"""
    # ...
```

**Почему:** Явно показываем что Public API (можно менять внутренности не ломая клиентов).

---

## Правила асинхронности

### ПРАВИЛО 1: I/O = async, Compute = sync

```python
# ✅ I/O операции - ВСЕГДА async
async def fetch_candles(symbol: str) -> List:
    async with session.get(url) as resp:
        return await resp.json()

async def save_to_database(data: Dict) -> bool:
    async with db.connect() as conn:
        await conn.execute(query, data)
        return True

# ✅ Вычисления - ВСЕГДА sync
def calculate_ema(prices: np.ndarray, period: int) -> np.ndarray:
    # CPU-bound операции не нуждаются в async
    return ema_result

def analyze_pattern(candles: NormalizedCandles) -> Analysis:
    # Чистые вычисления - sync
    return analysis
```

---

### ПРАВИЛО 2: Batch загрузка для множественных запросов

**Вместо последовательных запросов:**

```python
# ❌ ПЛОХО: Последовательно
async def load_all_pairs_sequential(pairs: List[str]) -> List:
    results = []
    for symbol in pairs:  # Медленно!
        candles = await fetch_candles(symbol)
        results.append(candles)
    return results
```

**Используй параллельную загрузку:**

```python
# ✅ ХОРОШО: Параллельно
async def load_all_pairs_parallel(pairs: List[str]) -> List:
    tasks = [fetch_candles(symbol) for symbol in pairs]
    results = await asyncio.gather(*tasks)
    return results

# ✅ ЕЩЁ ЛУЧШЕ: Batch API с контролем concurrency
async def load_all_pairs_batch(pairs: List[str]) -> List:
    requests = [
        {'symbol': symbol, 'interval': '60', 'limit': 100}
        for symbol in pairs
    ]
    # Одна функция обрабатывает batch с семафором
    results = await fetch_multiple_candles(requests)
    return results
```

---

### ПРАВИЛО 3: Обрабатывай ошибки в async

```python
# ✅ ПРАВИЛЬНО
async def safe_fetch(symbol: str) -> Optional[List]:
    try:
        async with asyncio.timeout(10):  # Timeout
            return await fetch_candles(symbol)
    except asyncio.TimeoutError:
        logger.warning(f"Timeout fetching {symbol}")
        return None
    except Exception as e:
        logger.error(f"Error fetching {symbol}: {e}")
        return None

# ✅ Batch с gather + return_exceptions
results = await asyncio.gather(
    *tasks, 
    return_exceptions=True  # Не падаем если одна задача упала
)

for result in results:
    if isinstance(result, Exception):
        logger.error(f"Task failed: {result}")
    else:
        # Обрабатываем результат
        pass
```

---

### ПРАВИЛО 4: Используй семафоры для rate limiting

```python
# ✅ ПРАВИЛЬНО: Контроль concurrency
_semaphore = asyncio.Semaphore(50)  # Максимум 50 одновременно

async def fetch_with_limit(symbol: str) -> List:
    async with _semaphore:
        return await fetch_candles(symbol)
```

---

## Правила именования

### ПРАВИЛО 1: Константы = UPPER_CASE

```python
# ✅ config.py
EMA_FAST = 9
EMA_MEDIUM = 21
MIN_CONFIDENCE = 60
API_TIMEOUT = 30

# ❌ НЕПРАВИЛЬНО
ema_fast = 9
MinConfidence = 60
```

---

### ПРАВИЛО 2: Функции = глагол + существительное

```python
# ✅ ПРАВИЛЬНО
def calculate_ema(...)
def analyze_triple_ema(...)
def fetch_candles(...)
def normalize_candles(...)
def validate_signal(...)

# ❌ НЕПРАВИЛЬНО
def ema(...)          # Что делает?
def triple_ema(...)   # Calculate? Analyze?
def candles(...)      # Fetch? Process?
```

---

### ПРАВИЛО 3: Классы = существительное

```python
# ✅ ПРАВИЛЬНО
class EMAAnalysis
class NormalizedCandles
class AIRouter
class TradingSignal

# ❌ НЕПРАВИЛЬНО
class AnalyzeEMA      # Это функция, а не класс
class DoCalculation   # Глагол
```

---

### ПРАВИЛО 4: Переменные = существительное

```python
# ✅ ПРАВИЛЬНО
candles = normalize_candles(...)
ema_result = analyze_triple_ema(...)
confidence = 85
pairs = ['BTCUSDT', 'ETHUSDT']

# ❌ НЕПРАВИЛЬНО
analyze = analyze_triple_ema(...)  # Путаница с функцией
do_calculation = calculate_ema(...) # Глагол
```

---

### ПРАВИЛО 5: Boolean = is/has/can + существительное

```python
# ✅ ПРАВИЛЬНО
is_valid: bool
has_signal: bool
can_trade: bool
should_block: bool

# ❌ НЕПРАВИЛЬНО
valid: bool       # Не ясно что это boolean
signal: bool      # Может быть объект
tradeable: bool   # Не совсем ясно
```

---

## Правила обработки ошибок

### ПРАВИЛО 1: Всегда возвращай Optional[T]

```python
# ✅ ПРАВИЛЬНО: Explicit failure handling
def analyze_indicator(candles: NormalizedCandles) -> Optional[Analysis]:
    if not candles or not candles.is_valid:
        return None  # Явно сигнализируем об ошибке
    
    try:
        result = _calculate(candles)
        return Analysis(result)
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        return None  # Не бросаем exception вверх

# ✅ Использование
result = analyze_indicator(candles)
if result is None:
    # Обрабатываем ошибку
    pass
else:
    # Работаем с результатом
    pass
```

---

### ПРАВИЛО 2: Try-except на уровне функций

```python
# ✅ ПРАВИЛЬНО: Каждая функция защищена
def calculate_something(data: np.ndarray) -> float:
    try:
        if len(data) < 10:
            return 0.0
        
        result = np.mean(data) / np.std(data)
        
        if np.isnan(result) or np.isinf(result):
            return 0.0
        
        return float(result)
    
    except Exception as e:
        logger.error(f"Calculation error: {e}")
        return 0.0  # Safe default
```

---

### ПРАВИЛО 3: Validate early, return early

```python
# ✅ ПРАВИЛЬНО: Guard clauses
def analyze_data(candles: NormalizedCandles, period: int) -> Optional[Result]:
    # Validation в начале
    if not candles:
        return None
    
    if not candles.is_valid:
        return None
    
    if period < 1:
        return None
    
    if len(candles.closes) < period:
        return None
    
    # Основная логика без вложенных if
    try:
        value = calculate(candles, period)
        return Result(value)
    except Exception as e:
        logger.error(f"Error: {e}")
        return None

# ❌ НЕПРАВИЛЬНО: Pyramid of doom
def analyze_data(candles, period):
    if candles:
        if candles.is_valid:
            if period > 0:
                if len(candles.closes) >= period:
                    try:
                        # Логика глубоко внутри
                        pass
```

---

### ПРАВИЛО 4: Специфичные сообщения об ошибках

```python
# ✅ ПРАВИЛЬНО
logger.error(f"EMA calculation failed for {symbol}: insufficient data ({len(prices)} < {period})")
logger.warning(f"Stage 2: {symbol} skipped - volume {volume:.2f} < {min_volume}")

# ❌ НЕПРАВИЛЬНО
logger.error("Error")
logger.error("Something went wrong")
```

---

## Правила логирования

### ПРАВИЛО 1: Уровни логирования

```python
# DEBUG - детали для отладки
logger.debug(f"Calculating EMA with period={period}, data_length={len(prices)}")

# INFO - важные события
logger.info(f"Stage 1: Found {len(candidates)} signal pairs")

# WARNING - проблемы которые не критичны
logger.warning(f"Stage 2: {symbol} skipped - low confidence {conf}%")

# ERROR - ошибки которые нужно исправлять
logger.error(f"Failed to fetch candles for {symbol}: {e}")
```

---

### ПРАВИЛО 2: Структурированное логирование

```python
# ✅ ПРАВИЛЬНО: Структура для parsing
logger.info(
    f"Stage 1 complete: "
    f"processed={processed}, "
    f"signals={len(signals)}, "
    f"time={elapsed:.1f}s"
)

# ❌ НЕПРАВИЛЬНО: Неструктурированное
logger.info("Stage 1 done, found some signals")
```

---

### ПРАВИЛО 3: Не логируй в циклах (если много итераций)

```python
# ❌ ПЛОХО: Спамит логи
for symbol in pairs:  # 400+ пар
    logger.info(f"Processing {symbol}")
    process(symbol)

# ✅ ХОРОШО: Batch логирование
logger.info(f"Processing {len(pairs)} pairs...")
processed = 0
for symbol in pairs:
    process(symbol)
    processed += 1

logger.info(f"Processed {processed}/{len(pairs)} pairs")
```

---

### ПРАВИЛО 4: Context в exception логах

```python
# ✅ ПРАВИЛЬНО: Контекст + что пошло не так
try:
    result = calculate_complex_thing(data, param1, param2)
except Exception as e:
    logger.error(
        f"Complex calculation failed: {e}\n"
        f"  data_length={len(data)}, "
        f"  param1={param1}, "
        f"  param2={param2}"
    )
    return None

# ❌ НЕПРАВИЛЬНО: Нет контекста
try:
    result = calculate_complex_thing(data, param1, param2)
except Exception as e:
    logger.error(f"Error: {e}")
```

---

## Правила работы с данными

### ПРАВИЛО 1: Всегда проверяй is_valid

```python
# ✅ ПРАВИЛЬНО
candles = normalize_candles(raw_data, symbol, interval)

if not candles or not candles.is_valid:
    logger.warning(f"{symbol} - invalid candles")
    return None

# Теперь безопасно работать
ema = calculate_ema(candles.closes, 21)

# ❌ НЕПРАВИЛЬНО: Нет проверки
candles = normalize_candles(raw_data, symbol, interval)
ema = calculate_ema(candles.closes, 21)  # Может упасть!
```

---

### ПРАВИЛО 2: Защищайся от NaN/Inf

```python
# ✅ ПРАВИЛЬНО
def safe_calculation(value: float) -> float:
    if np.isnan(value) or np.isinf(value):
        return 0.0
    return float(value)

# Или для массивов
if np.any(np.isnan(arr)) or np.any(np.isinf(arr)):
    logger.warning("NaN/Inf detected in data")
    return None
```

---

### ПРАВИЛО 3: Defensive copying для numpy arrays

```python
# ✅ ПРАВИЛЬНО: Копия для безопасности
def modify_prices(prices: np.ndarray) -> np.ndarray:
    result = prices.copy()  # Не мутируем оригинал
    result[result < 0] = 0
    return result

# ❌ НЕПРАВИЛЬНО: Мутация оригинала
def modify_prices(prices: np.ndarray) -> np.ndarray:
    prices[prices < 0] = 0  # Изменяет исходный массив!
    return prices
```

---

### ПРАВИЛО 4: JSON serialization для dataclasses

```python
# ✅ ПРАВИЛЬНО: Helper для сериализации
from dataclasses import is_dataclass, asdict

def serialize_to_json(obj):
    """Рекурсивно конвертирует dataclass → dict"""
    if obj is None:
        return None
    
    if is_dataclass(obj):
        return asdict(obj)
    
    if isinstance(obj, dict):
        return {k: serialize_to_json(v) for k, v in obj.items()}
    
    if isinstance(obj, (list, tuple)):
        return [serialize_to_json(item) for item in obj]
    
    return obj

# Использование
data = {
    'analysis': my_dataclass_result,
    'indicators': another_dataclass
}

json_data = json.dumps(serialize_to_json(data))
```

---

## Чеклист для нового компонента

При добавлении **любого** нового компонента проверь:

### ✅ Модульность

- [ ] Компонент имеет одну чёткую ответственность
- [ ] Использует `NormalizedCandles` для свечных данных
- [ ] Не зависит напрямую от других модулей (кроме базовых)
- [ ] Экспортируется через `__init__.py`
- [ ] Private функции помечены `_` префиксом

### ✅ Типизация

- [ ] Все параметры имеют type hints
- [ ] Return type объявлен явно
- [ ] Используется `Optional[T]` для nullable
- [ ] Dataclass для структурированных результатов

### ✅ Документация

- [ ] Docstring для public функций
- [ ] Args описаны
- [ ] Returns описан
- [ ] Примеры использования (опционально)

### ✅ Асинхронность

- [ ] I/O операции асинхронные (`async def`)
- [ ] Вычисления синхронные
- [ ] Есть timeout для network запросов
- [ ] Batch операции для множественных запросов
- [ ] Семафоры для rate limiting (если нужно)

### ✅ Обработка ошибок

- [ ] Try-except блоки на уровне функций
- [ ] Возвращается `None` или default при ошибке
- [ ] Логирование ошибок с контекстом
- [ ] Early validation + early return

### ✅ Логирование

- [ ] Используется `logger = logging.getLogger(__name__)`
- [ ] INFO для важных событий
- [ ] DEBUG для деталей
- [ ] ERROR для ошибок с контекстом
- [ ] Нет спама в логах (не логируем каждую итерацию в больших циклах)

### ✅ Тестируемость

- [ ] Можно протестировать отдельно от других модулей
- [ ] Нет жёстких зависимостей
- [ ] Mock-friendly (можно подставить тестовые данные)

### ✅ Конфигурация

- [ ] Параметры вынесены в `config.py` или `.env`
- [ ] Нет hardcoded значений
- [ ] Легко менять без правки кода

---

## 🎯 Пример: Добавление нового индикатора (полный чеклист)

### Шаг 1: Создать файл

```
indicators/
└── bollinger_bands.py
```

### Шаг 2: Структура файла

```python
"""
Bollinger Bands Indicator
Файл: indicators/bollinger_bands.py

Расчёт Bollinger Bands и анализ позиции цены
"""

import numpy as np
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class BollingerAnalysis:
    """
    Результат анализа Bollinger Bands
    
    Attributes:
        upper_band: Верхняя полоса
        middle_band: Средняя линия (SMA)
        lower_band: Нижняя полоса
        position: 'ABOVE_UPPER' | 'ABOVE_MIDDLE' | 'BELOW_MIDDLE' | 'BELOW_LOWER'
        bandwidth_pct: Ширина полос в процентах
        confidence_adjustment: Корректировка confidence
        details: Текстовое описание
    """
    upper_band: float
    middle_band: float
    lower_band: float
    position: str
    bandwidth_pct: float
    confidence_adjustment: int
    details: str


def calculate_bollinger_bands(
    prices: np.ndarray,
    period: int = 20,
    std_dev: float = 2.0
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Рассчитать Bollinger Bands
    
    Args:
        prices: Массив цен закрытия
        period: Период SMA (default: 20)
        std_dev: Количество стандартных отклонений (default: 2.0)
        
    Returns:
        (upper_band, middle_band, lower_band) - кортеж массивов
    """
    if len(prices) < period:
        zero = np.zeros_like(prices)
        return zero, zero, zero
    
    try:
        # SMA как middle band
        middle_band = np.convolve(
            prices, 
            np.ones(period) / period, 
            mode='same'
        )
        
        # Rolling standard deviation
        std = np.zeros_like(prices)
        for i in range(period - 1, len(prices)):
            window = prices[i - period + 1:i + 1]
            std[i] = np.std(window)
        
        upper_band = middle_band + (std * std_dev)
        lower_band = middle_band - (std * std_dev)
        
        return upper_band, middle_band, lower_band
    
    except Exception as e:
        logger.error(f"Bollinger Bands calculation error: {e}")
        zero = np.zeros_like(prices)
        return zero, zero, zero


def analyze_bollinger_bands(
    candles,  # NormalizedCandles
    period: int = 20,
    std_dev: float = 2.0
) -> Optional[BollingerAnalysis]:
    """
    Анализ Bollinger Bands
    
    Args:
        candles: NormalizedCandles объект
        period: Период SMA
        std_dev: Количество стандартных отклонений
        
    Returns:
        BollingerAnalysis или None при ошибке
    """
    # ✅ Validation
    if not candles or not candles.is_valid:
        return None
    
    if len(candles.closes) < period + 10:
        return None
    
    try:
        # ✅ Calculation
        upper, middle, lower = calculate_bollinger_bands(
            candles.closes, period, std_dev
        )
        
        current_price = float(candles.closes[-1])
        current_upper = float(upper[-1])
        current_middle = float(middle[-1])
        current_lower = float(lower[-1])
        
        # ✅ NaN/Inf check
        if any(np.isnan(v) or np.isinf(v) for v in [
            current_upper, current_middle, current_lower
        ]):
            return None
        
        # ✅ Analysis
        position = _determine_position(
            current_price, current_upper, current_middle, current_lower
        )
        
        bandwidth_pct = ((current_upper - current_lower) / current_middle) * 100
        
        adjustment = _calculate_adjustment(position, bandwidth_pct)
        
        details = f"Position: {position}, Bandwidth: {bandwidth_pct:.2f}%"
        
        return BollingerAnalysis(
            upper_band=current_upper,
            middle_band=current_middle,
            lower_band=current_lower,
            position=position,
            bandwidth_pct=round(bandwidth_pct, 2),
            confidence_adjustment=adjustment,
            details=details
        )
    
    except Exception as e:
        logger.error(f"Bollinger Bands analysis error: {e}")
        return None


# ✅ Private helpers
def _determine_position(price: float, upper: float, middle: float, lower: float) -> str:
    """Определить позицию цены относительно полос"""
    if price > upper:
        return 'ABOVE_UPPER'
    elif price > middle:
        return 'ABOVE_MIDDLE'
    elif price > lower:
        return 'BELOW_MIDDLE'
    else:
        return 'BELOW_LOWER'


def _calculate_adjustment(position: str, bandwidth: float) -> int:
    """Рассчитать корректировку confidence"""
    adjustment = 0
    
    # Узкие полосы = сжатие = потенциальный breakout
    if bandwidth < 5.0:
        adjustment += 8
    
    # Extreme positions
    if position in ['ABOVE_UPPER', 'BELOW_LOWER']:
        adjustment -= 10  # Overbought/Oversold
    
    return adjustment
```

### Шаг 3: Добавить в `__init__.py`

```python
# indicators/__init__.py

from .bollinger_bands import (
    calculate_bollinger_bands,
    analyze_bollinger_bands,
    BollingerAnalysis
)

__all__ = [
    # ... existing
    'calculate_bollinger_bands',
    'analyze_bollinger_bands',
    'BollingerAnalysis',
]
```

### Шаг 4: Использовать в stages

```python
# stages/stage3_analysis.py

from indicators import analyze_bollinger_bands

bb_result = analyze_bollinger_bands(candles_4h)

if bb_result:
    confidence += bb_result.confidence_adjustment
    logger.info(f"{symbol}: Bollinger {bb_result.position}")
```

### Шаг 5: Проверка чеклиста

✅ **Модульность:**
- Один файл = один индикатор
- Использует `NormalizedCandles`
- Не зависит от других модулей
- Экспортируется через `__init__.py`
- Private функции с `_` префиксом

✅ **Типизация:**
- Type hints везде
- `Optional[BollingerAnalysis]` для return
- Dataclass для результата

✅ **Документация:**
- Docstrings для public функций
- Args/Returns описаны

✅ **Асинхронность:**
- Вычисления = sync (правильно)
- Нет I/O операций

✅ **Обработка ошибок:**
- Try-except на уровне функций
- Return None при ошибке
- Early validation

✅ **Логирование:**
- `logger = logging.getLogger(__name__)`
- ERROR с контекстом

---

## 🚨 Анти-паттерны (СТРОГО ЗАПРЕЩЕНО)

### ❌ 1. Циклические импорты

```python
# ❌ indicators/ema.py
from stages.stage1_filter import determine_direction

def analyze_ema(...):
    direction = determine_direction(...)  # НЕЛЬЗЯ!
```

**Почему плохо:** Индикатор не должен знать о stages. Это нарушает иерархию.

**Правильно:**
```python
# ✅ indicators/ema.py
def analyze_ema(...) -> EMAAnalysis:
    return EMAAnalysis(...)  # Только результат

# ✅ stages/stage1_filter.py
ema_result = analyze_ema(candles)
direction = determine_direction(ema_result)  # Здесь логика
```

---

### ❌ 2. Смешивание sync и async

```python
# ❌ ПЛОХО
async def process_data(symbol: str):
    candles = requests.get(url).json()  # Блокирует event loop!
    result = calculate_ema(candles)
    return result
```

**Правильно:**
```python
# ✅ ХОРОШО
async def process_data(symbol: str):
    async with session.get(url) as resp:  # Async I/O
        candles = await resp.json()
    
    result = calculate_ema(candles)  # Sync compute
    return result
```

---

### ❌ 3. Мутация входных данных

```python
# ❌ ПЛОХО
def normalize_prices(prices: np.ndarray) -> np.ndarray:
    prices[prices < 0] = 0  # Изменяет оригинал!
    return prices
```

**Правильно:**
```python
# ✅ ХОРОШО
def normalize_prices(prices: np.ndarray) -> np.ndarray:
    result = prices.copy()  # Копия
    result[result < 0] = 0
    return result
```

---

### ❌ 4. Hardcoded значения

```python
# ❌ ПЛОХО
def analyze_signal(candles):
    if confidence > 70:  # Magic number
        return 'STRONG'
```

**Правильно:**
```python
# ✅ ХОРОШО
# config.py
SIGNAL_STRONG_THRESHOLD = 70

# Использование
from config import config

def analyze_signal(candles, threshold: int = None):
    threshold = threshold or config.SIGNAL_STRONG_THRESHOLD
    if confidence > threshold:
        return 'STRONG'
```

---

### ❌ 5. Дублирование логики

```python
# ❌ ПЛОХО: Каждый stage рассчитывает EMA по-своему
# stage1_filter.py
ema9 = custom_ema_calculation(candles, 9)

# stage2_selection.py
ema9 = another_ema_calculation(candles, 9)

# stage3_analysis.py
ema9 = yet_another_ema(candles, 9)
```

**Правильно:**
```python
# ✅ ХОРОШО: Один источник истины
# indicators/ema.py
def calculate_ema(prices: np.ndarray, period: int) -> np.ndarray:
    # Единственная реализация
    return ema

# Все stages используют:
from indicators import calculate_ema
ema9 = calculate_ema(candles.closes, 9)
```

---

### ❌ 6. Глобальное состояние

```python
# ❌ ПЛОХО
# globals.py
current_signals = []  # Глобальный список

# stage3.py
from globals import current_signals
current_signals.append(signal)  # Опасно!
```

**Правильно:**
```python
# ✅ ХОРОШО: Явная передача
async def run_stage3(selected_pairs: List[str]) -> List[TradingSignal]:
    signals = []  # Локальное состояние
    
    for symbol in selected_pairs:
        signal = await analyze(symbol)
        if signal:
            signals.append(signal)
    
    return signals  # Явный возврат
```

---

### ❌ 7. Игнорирование Optional

```python
# ❌ ПЛОХО
result = analyze_indicator(candles)
confidence = result.confidence  # Может быть None!
```

**Правильно:**
```python
# ✅ ХОРОШО
result = analyze_indicator(candles)

if result is None:
    logger.warning("Analysis failed")
    return

confidence = result.confidence  # Теперь безопасно
```

---

### ❌ 8. Неинформативные имена

```python
# ❌ ПЛОХО
def process(data):
    result = calculate(data)
    return result

# ❌ ПЛОХО
a = fetch_data()
b = process(a)
c = validate(b)
```

**Правильно:**
```python
# ✅ ХОРОШО
def analyze_ema_crossover(candles: NormalizedCandles) -> EMAAnalysis:
    ema_values = calculate_ema(candles.closes, period=21)
    return EMAAnalysis(values=ema_values)

# ✅ ХОРОШО
raw_candles = fetch_candles(symbol)
normalized_candles = normalize_candles(raw_candles)
ema_result = analyze_triple_ema(normalized_candles)
```

---

## 📚 Примеры правильной архитектуры

### Пример 1: Добавление нового AI провайдера

```python
# ai/gemini_client.py
"""
Google Gemini AI Client
Файл: ai/gemini_client.py
"""

import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class GeminiClient:
    """Клиент для Google Gemini API"""
    
    def __init__(self, api_key: str, model: str = "gemini-pro"):
        self.api_key = api_key
        self.model = model
        logger.info(f"Gemini client initialized: {model}")
    
    async def select_pairs(
        self,
        pairs_data: List[Dict],
        max_pairs: int = 3,
        temperature: float = 0.3,
        max_tokens: int = 2000
    ) -> List[str]:
        """
        Stage 2: Выбор пар через Gemini
        
        ⚠️ ВАЖНО: Должна иметь ТУ ЖЕ сигнатуру что DeepSeek/Claude!
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
        Stage 3: Comprehensive analysis через Gemini
        
        ⚠️ ВАЖНО: Должна иметь ТУ ЖЕ сигнатуру что DeepSeek/Claude!
        """
        # Твоя логика
        pass
```

**Интеграция:**

```python
# ai/ai_router.py

class AIRouter:
    async def _get_gemini_client(self) -> Optional['GeminiClient']:
        """Получить Gemini клиент"""
        if self.gemini_client:
            return self.gemini_client
        
        from config import config
        
        if not config.GEMINI_API_KEY:
            return None
        
        from ai.gemini_client import GeminiClient
        
        self.gemini_client = GeminiClient(
            api_key=config.GEMINI_API_KEY,
            model=config.GEMINI_MODEL
        )
        
        return self.gemini_client
    
    async def _get_provider_client(self, stage: str):
        provider = self.stage_providers.get(stage, 'deepseek')
        
        if provider == 'gemini':  # ✅ Добавили новый провайдер
            client = await self._get_gemini_client()
            return 'gemini', client
        
        # ... existing providers
```

```python
# config.py
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-pro')
```

```env
# .env
STAGE2_PROVIDER=gemini
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-pro
```

**✅ Что правильно:**
- Та же сигнатура методов что у других провайдеров
- Добавлен без изменения существующего кода
- Конфигурация через `.env`
- Легко переключаться между провайдерами

---

### Пример 2: Добавление нового источника данных

```python
# data_providers/binance_client.py
"""
Binance API Client
Файл: data_providers/binance_client.py
"""

import aiohttp
import logging
from typing import List

logger = logging.getLogger(__name__)


async def fetch_candles_binance(
    symbol: str,
    interval: str,
    limit: int = 200
) -> List[List]:
    """
    Получить свечи с Binance
    
    Args:
        symbol: Торговая пара
        interval: Интервал ('1h', '4h', '1d')
        limit: Количество свечей
        
    Returns:
        Raw данные в формате Binance
    """
    async with aiohttp.ClientSession() as session:
        params = {
            'symbol': symbol,
            'interval': interval,
            'limit': limit
        }
        
        try:
            async with session.get(
                'https://api.binance.com/api/v3/klines',
                params=params
            ) as response:
                
                if response.status != 200:
                    logger.warning(f"Binance HTTP {response.status}")
                    return []
                
                data = await response.json()
                
                # Binance format: [timestamp, open, high, low, close, volume, ...]
                return data
        
        except Exception as e:
            logger.error(f"Binance fetch error: {e}")
            return []
```

**Использование:**

```python
# Где угодно в коде
from data_providers import normalize_candles
from data_providers.binance_client import fetch_candles_binance

# 1. Получаем raw данные
raw_candles = await fetch_candles_binance('BTCUSDT', '1h', 100)

# 2. ✅ ОБЯЗАТЕЛЬНО нормализуем в единый формат
candles = normalize_candles(
    raw_candles,
    symbol='BTCUSDT',
    interval='1h'
)

# 3. Теперь ВСЕ индикаторы работают!
if candles and candles.is_valid:
    ema_result = analyze_triple_ema(candles)
    rsi_result = analyze_rsi(candles)
    # ...
```

**✅ Что правильно:**
- Новый источник данных добавлен БЕЗ изменения индикаторов
- Обязательная нормализация в `NormalizedCandles`
- После нормализации работает весь существующий код

---

### Пример 3: Добавление нового Stage

```python
# stages/stage4_risk_check.py
"""
Stage 4: Risk Management Check
Файл: stages/stage4_risk_check.py

Дополнительная проверка рисков перед финальным одобрением
"""

import logging
from typing import List, Dict

logger = logging.getLogger(__name__)


async def run_stage4(
    signals: List['TradingSignal']
) -> tuple[List['TradingSignal'], List[Dict]]:
    """
    Stage 4: Проверка рисков
    
    Args:
        signals: Одобренные сигналы из Stage 3
        
    Returns:
        (approved, rejected) - финально одобренные и отклонённые
    """
    logger.info(f"Stage 4: Risk check for {len(signals)} signals")
    
    approved = []
    rejected = []
    
    for signal in signals:
        try:
            # Проверка 1: R/R ratio
            if signal.risk_reward_ratio < 2.0:
                rejected.append({
                    'symbol': signal.symbol,
                    'signal': signal.signal,
                    'rejection_reason': f'Low R/R: {signal.risk_reward_ratio:.2f} < 2.0'
                })
                logger.info(f"Stage 4: {signal.symbol} rejected - low R/R")
                continue
            
            # Проверка 2: Stop loss не больше 5%
            risk_pct = abs((signal.entry_price - signal.stop_loss) / signal.entry_price * 100)
            if risk_pct > 5.0:
                rejected.append({
                    'symbol': signal.symbol,
                    'signal': signal.signal,
                    'rejection_reason': f'Risk too high: {risk_pct:.2f}% > 5%'
                })
                logger.info(f"Stage 4: {signal.symbol} rejected - high risk")
                continue
            
            # Проверка 3: Время торговли (не торгуем ночью)
            from datetime import datetime
            hour = datetime.now().hour
            if hour < 8 or hour > 22:
                rejected.append({
                    'symbol': signal.symbol,
                    'signal': signal.signal,
                    'rejection_reason': f'Outside trading hours: {hour}:00'
                })
                logger.info(f"Stage 4: {signal.symbol} rejected - off hours")
                continue
            
            # Всё ОК - одобряем
            approved.append(signal)
            logger.info(f"Stage 4: ✓ {signal.symbol} approved")
        
        except Exception as e:
            logger.error(f"Stage 4 error for {signal.symbol}: {e}")
            rejected.append({
                'symbol': signal.symbol,
                'signal': 'ERROR',
                'rejection_reason': f'Stage 4 error: {str(e)[:100]}'
            })
    
    logger.info(
        f"Stage 4 complete: {len(approved)} approved, {len(rejected)} rejected"
    )
    
    return approved, rejected
```

**Интеграция:**

```python
# stages/__init__.py
from .stage4_risk_check import run_stage4

__all__ = [
    # ... existing
    'run_stage4',
]
```

```python
# main.py или telegram/bot_main.py
from stages import run_stage1, run_stage2, run_stage3, run_stage4

# ... existing Stage 1, 2, 3

# ✅ Добавляем Stage 4
approved_signals, rejected_stage3 = await run_stage3(selected_pairs)

if approved_signals:
    # Stage 4: Risk check
    final_approved, rejected_stage4 = await run_stage4(approved_signals)
    
    # Объединяем rejected
    all_rejected = rejected_stage3 + rejected_stage4
    
    logger.info(
        f"Pipeline complete: {len(final_approved)} final signals, "
        f"{len(all_rejected)} total rejected"
    )
```

**✅ Что правильно:**
- Новый stage добавлен БЕЗ изменения Stage 1/2/3
- Та же структура что у других stages
- Легко включать/выключать
- Явные входы/выходы

---

## 🎓 Заключение

### Главные правила (запомни):

1. **Один формат данных** - `NormalizedCandles` везде
2. **Одна зона ответственности** - модуль делает ЧТО-ТО ОДНО
3. **Async для I/O, sync для compute**
4. **Type hints везде**
5. **Return Optional[T]** для обработки ошибок
6. **Early validation, early return**
7. **Private функции с `_` префиксом**
8. **Экспорт через `__init__.py`**
9. **Конфигурация в `config.py`/`.env`**
10. **Логирование с контекстом**

### Перед добавлением нового кода спроси себя:

- ✅ Использует ли это `NormalizedCandles`?
- ✅ Имеет ли одну чёткую ответственность?
- ✅ Есть ли type hints?
- ✅ Есть ли docstrings?
- ✅ Async где нужно?
- ✅ Обработка ошибок?
- ✅ Можно ли протестировать отдельно?
- ✅ Нет hardcoded значений?

**Если хоть на один вопрос "нет" - переделай!**

---

**Последнее обновление:** 2025-01-01  
**Версия:** 2.0