# 🏗️ ARCHITECTURE & SCALING GUIDE

> **Trading Bot - Правила архитектуры и масштабирования**
> 
> **Last Updated:** 2025-01-13  
> **Version:** 4.0 - Модульная архитектура

---

## 📋 Содержание

1. [Основные принципы](#основные-принципы)
2. [Структура проекта](#структура-проекта)
3. [Правила модульности](#правила-модульности)
4. [Работа с типами активов](#работа-с-типами-активов)
5. [Добавление новых компонентов](#добавление-новых-компонентов)
6. [Оптимизация производительности](#оптимизация-производительности)
7. [Логирование](#логирование)
8. [Тестирование](#тестирование)

---

## Основные принципы

### 1. **Модульность и разделение ответственности**

Каждый модуль отвечает за свою область:
- `indicators/` - только технические расчеты
- `stages/` - только оркестрация этапов
- `ai/` - только AI провайдеры
- `telegram/` - только интерфейс
- `data_providers/` - универсальные функции загрузки данных (автоопределение типа актива)

**❌ ЗАПРЕЩЕНО:**
- Индикатор не должен обращаться к API напрямую
- Этап не должен содержать бизнес-логику индикаторов
- AI клиент не должен знать о структуре данных этапов

### 2. **Единый формат данных: NormalizedCandles**

**ВСЕ** индикаторы работают с `NormalizedCandles`:
```python
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

**Поток данных:**
```
Raw Data (Bybit/Tinkoff) → normalize_candles() → NormalizedCandles → indicators
```

### 3. **Централизованное определение типа актива**

**ВСЕГДА** используйте `utils.asset_detector.AssetTypeDetector`:

```python
from utils.asset_detector import AssetTypeDetector

# Один символ
asset_type = AssetTypeDetector.detect('BTCUSDT')  # 'crypto'
asset_type = AssetTypeDetector.detect('SBER')     # 'stock'

# Batch
types = AssetTypeDetector.detect_batch(['BTCUSDT', 'SBER', 'ETHUSDT'])
# {'BTCUSDT': 'crypto', 'SBER': 'stock', 'ETHUSDT': 'crypto'}

# Группировка
grouped = AssetTypeDetector.group_by_type(['BTCUSDT', 'SBER', 'ETHUSDT'])
# {'crypto': ['BTCUSDT', 'ETHUSDT'], 'stock': ['SBER']}
```

**❌ ЗАПРЕЩЕНО:**
- Дублировать логику определения типа актива
- Использовать `_detect_asset_type()` из других модулей
- Хардкодить суффиксы криптовалют

### 4. **Универсальные функции загрузки данных**

Используйте универсальные функции из `data_providers/`:
- `fetch_candles(symbol, interval, limit)` - автоматически определяет тип
- `fetch_multiple_candles(requests)` - batch загрузка с автоопределением

**Пример:**
```python
from data_providers import fetch_candles, normalize_candles

# Работает для любого типа актива
candles_raw = await fetch_candles('BTCUSDT', '60', 100)  # crypto
candles_raw = await fetch_candles('SBER', '60', 100)     # stock

# Нормализация одинаковая
candles = normalize_candles(candles_raw, symbol, interval)
```

---

## Структура проекта

```
trading_bot/
├── main.py                    # Точка входа
├── config.py                  # ВСЯ конфигурация
│
├── prompts/                   # ✅ Промпты для AI (перемещены из ai/prompts)
│   ├── prompt_analyze.txt
│   ├── prompt_select.txt
│   ├── prompt_news_crypto.txt
│   └── prompt_news_stocks.txt
│
├── data_providers/            # Провайдеры данных
│   ├── bybit_client.py        # Bybit API (крипто)
│   ├── tinkoff_client.py     # Tinkoff API (акции)
│   ├── data_normalizer.py     # normalize_candles() - КРИТИЧНО
│   └── market_data.py         # Рыночные данные
│
├── indicators/                # ✅ Каждый индикатор в отдельном файле
│   ├── ema.py
│   ├── rsi.py
│   ├── macd.py
│   ├── volume.py
│   ├── atr.py
│   ├── correlation.py
│   ├── volume_profile.py
│   ├── order_blocks.py
│   ├── imbalance.py
│   ├── liquidity_sweep.py
│   ├── support_resistance.py
│   ├── false_breakout.py
│   ├── candle_patterns.py
│   └── news_analysis.py
│
├── stages/                    # Этапы анализа
│   ├── stage1_filter.py       # Фильтрация
│   ├── stage2_selection.py    # AI выбор
│   └── stage3_analysis.py    # Комплексный анализ
│
├── ai/                        # AI провайдеры
│   ├── ai_router.py           # Роутер между провайдерами
│   ├── deepseek_client.py
│   └── anthropic_client.py
│
├── telegram/                  # Telegram бот
│   ├── bot_main.py
│   ├── formatters.py
│   └── scheduler.py
│
└── utils/                     # Утилиты
    ├── asset_detector.py      # ✅ Централизованное определение типа
    ├── logger.py              # Логирование
    ├── backtesting.py         # Бектестинг
    ├── signal_storage.py      # Хранение сигналов
    └── validators.py          # Валидация
```

---

## Правила модульности

### ✅ Правило 1: Индикаторы - чистые функции

**Каждый индикатор:**
- Принимает `NormalizedCandles`
- Возвращает `@dataclass` или `Optional[dataclass]`
- Не делает I/O операции
- Не знает о типах активов

**Пример:**
```python
# indicators/rsi.py
@dataclass
class RSIAnalysis:
    rsi_value: float
    is_overbought: bool
    is_oversold: bool
    confidence_adjustment: int

def analyze_rsi(candles: NormalizedCandles, period: int = 14) -> Optional[RSIAnalysis]:
    if not candles or not candles.is_valid:
        return None
    # ... расчеты
    return RSIAnalysis(...)
```

### ✅ Правило 2: Этапы понимают тип актива

**Каждый этап:**
- Определяет тип актива через `AssetTypeDetector`
- Загружает соответствующие данные (BTC для crypto, MOEX для stocks)
- Использует универсальные функции `fetch_candles()`

**Пример:**
```python
# stages/stage3_analysis.py
from utils.asset_detector import AssetTypeDetector
from data_providers import fetch_candles

# Определяем тип
asset_type = AssetTypeDetector.detect(symbol)

# Загружаем соответствующий индекс
if asset_type == 'crypto':
    btc_candles = await fetch_candles('BTCUSDT', interval, limit)
elif asset_type == 'stock':
    moex_candles = await fetch_moex_index_candles(interval, limit)
```

### ✅ Правило 3: Провайдеры данных - универсальные

**Функции в `data_providers/__init__.py`:**
- Автоматически определяют тип актива
- Используют соответствующий клиент (Bybit/Tinkoff)
- Возвращают единый формат

**Пример:**
```python
# data_providers/__init__.py
async def fetch_candles(symbol: str, interval: str, limit: int) -> List:
    asset_type = AssetTypeDetector.detect(symbol)
    
    if asset_type == 'stock':
        return await fetch_stock_candles(symbol, interval, limit)
    else:
        return await fetch_candles_bybit(symbol, interval, limit)
```

### ✅ Правило 4: Бектестинг понимает тип актива

**Бектестинг:**
- Автоматически определяет тип актива
- Загружает свечи из соответствующего источника
- Работает одинаково для crypto и stocks

**Пример:**
```python
# utils/backtesting.py
from utils.asset_detector import AssetTypeDetector
from data_providers import fetch_candles

asset_type = AssetTypeDetector.detect(symbol)
candles_5m = await fetch_candles(symbol, '5', limit)  # Автоматически выберет провайдер
```

---

## Работа с типами активов

### Определение типа

**ВСЕГДА** используйте `AssetTypeDetector`:

```python
from utils.asset_detector import AssetTypeDetector

# Один символ
asset_type = AssetTypeDetector.detect('BTCUSDT')  # 'crypto'

# Batch определение
types = AssetTypeDetector.detect_batch(['BTCUSDT', 'SBER'])
# {'BTCUSDT': 'crypto', 'SBER': 'stock'}

# Группировка
grouped = AssetTypeDetector.group_by_type(['BTCUSDT', 'SBER', 'ETHUSDT'])
# {'crypto': ['BTCUSDT', 'ETHUSDT'], 'stock': ['SBER']}
```

### Загрузка корреляционных данных

**Для крипто:**
- BTC свечи для корреляции
- BTC новости для анализа

**Для акций:**
- MOEX индекс для корреляции
- Новости фондового рынка

**Пример:**
```python
from utils.asset_detector import AssetTypeDetector
from data_providers import fetch_candles, fetch_moex_index_candles

asset_type = AssetTypeDetector.detect(symbol)

if asset_type == 'crypto':
    # Загружаем BTC для корреляции
    btc_candles = await fetch_candles('BTCUSDT', interval, limit)
    btc_news = await analyze_news('BTCUSDT')
elif asset_type == 'stock':
    # Загружаем MOEX для корреляции
    moex_candles = await fetch_moex_index_candles(interval, limit)
    stock_news = await analyze_news(symbol, asset_type='stock')
```

---

## Добавление новых компонентов

### ✅ Добавление нового индикатора

1. Создайте файл `indicators/my_indicator.py`:

```python
from dataclasses import dataclass
from typing import Optional
from data_providers.data_normalizer import NormalizedCandles

@dataclass
class MyIndicatorAnalysis:
    value: float
    signal: str
    confidence: int

def analyze_my_indicator(candles: NormalizedCandles) -> Optional[MyIndicatorAnalysis]:
    if not candles or not candles.is_valid:
        return None
    # ... расчеты
    return MyIndicatorAnalysis(...)
```

2. Экспортируйте через `indicators/__init__.py`:

```python
from .my_indicator import analyze_my_indicator, MyIndicatorAnalysis

__all__ = [
    # ... существующие
    'analyze_my_indicator',
    'MyIndicatorAnalysis',
]
```

3. Используйте в этапах:

```python
from indicators import analyze_my_indicator

result = analyze_my_indicator(candles)
if result:
    # используем result
```

### ✅ Добавление нового провайдера данных

1. Создайте клиент в `data_providers/new_client.py`
2. Добавьте в универсальную функцию:

```python
# data_providers/__init__.py
async def fetch_candles(symbol: str, interval: str, limit: int) -> List:
    asset_type = AssetTypeDetector.detect(symbol)
    
    if asset_type == 'new_type':
        return await fetch_from_new_provider(symbol, interval, limit)
    # ... существующие провайдеры
```

3. Используйте `normalize_candles()` для нормализации

### ✅ Добавление нового AI провайдера

1. Создайте клиент в `ai/new_client.py`:

```python
class NewAIClient:
    async def select_pairs(self, pairs_data, max_pairs, ...) -> List[str]:
        # Реализация Stage 2
        pass
    
    async def analyze_comprehensive(self, symbol, comprehensive_data, ...) -> Dict:
        # Реализация Stage 3
        pass
```

2. Зарегистрируйте в `ai/ai_router.py`:

```python
async def _get_provider_client(self, stage: str):
    provider = self.stage_providers.get(stage, 'deepseek')
    
    if provider == 'new_provider':
        return 'new_provider', await self._get_new_client()
    # ... существующие
```

3. Добавьте конфигурацию в `config.py`:

```python
NEW_PROVIDER_API_KEY = os.getenv('NEW_PROVIDER_API_KEY')
```

---

## Оптимизация производительности

### Batch загрузка

**Для больших батчей (>50 элементов):**
- Логируем прогресс каждые 50 элементов
- Минимальное логирование для каждого запроса
- Параллельная обработка через `asyncio.gather()`

**Пример:**
```python
# data_providers/__init__.py
async def fetch_multiple_candles(requests: List[Dict]) -> List[Dict]:
    # Группируем по типу для оптимизации
    grouped = AssetTypeDetector.group_by_type([req['symbol'] for req in requests])
    
    # Логируем только для больших батчей
    if len(requests) > 50:
        logger.info(f"Batch: {len(grouped['stock'])} stocks, {len(grouped['crypto'])} crypto")
    
    # Параллельная обработка
    tasks = [_fetch_single_request(req) for req in requests]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Прогресс каждые 50 элементов
    if len(requests) > 50 and completed % 50 == 0:
        logger.info(f"Progress: {completed}/{len(requests)}")
```

### Кэширование

**Промпты:**
- Кэшируются в памяти после первой загрузки
- Используется `load_prompt_cached()` из `ai/deepseek_client.py`

**Инструменты:**
- Tinkoff клиент кэширует инструменты по тикеру

---

## Логирование

### Уровни логирования

- **INFO**: Основные этапы, результаты, статистика
- **DEBUG**: Детальная информация (отключено по умолчанию)
- **ERROR**: Ошибки с полным traceback

### Правила логирования

**✅ ЛОГИРУЕМ:**
- Начало/конец этапов с результатами
- Количество обработанных элементов
- Время выполнения этапов
- Ошибки с контекстом

**❌ НЕ ЛОГИРУЕМ:**
- Каждый шаг внутри цикла
- Детали каждого запроса в batch (только прогресс)
- Промежуточные значения индикаторов (только результаты)

**Пример:**
```python
# ✅ ПРАВИЛЬНО
logger.info(f"Stage 1: Analyzing {len(pairs)} pairs")
logger.info(f"Stage 1: Loaded {len(results)}/{len(pairs)} in {time:.1f}s")
logger.info(f"Stage 1: Found {len(candidates)} signals")

# ❌ НЕПРАВИЛЬНО
for symbol in pairs:
    logger.info(f"Processing {symbol}...")  # Слишком много логов
    logger.debug(f"Symbol {symbol} has {len(candles)} candles")  # OK для DEBUG
```

### Формат логов

**Консоль:**
- Красный цвет для всех сообщений
- Формат: `YYYY-MM-DD HH:MM:SS [LEVEL] module - message`

**Файлы:**
- `logs/bot_YYYYMMDD.log` - все логи
- `logs/bot_errors_YYYYMMDD.log` - только ошибки

---

## Тестирование

### Ручное тестирование

```bash
# Одноразовый анализ
python main.py once

# Telegram бот
python main.py telegram
```

### Проверка модульности

1. **Проверка импортов:**
   - Нет циклических зависимостей
   - Индикаторы не импортируют этапы
   - Этапы не импортируют AI клиенты напрямую

2. **Проверка типов:**
   - Все функции имеют type hints
   - Используется `NormalizedCandles` для свечей
   - Используется `AssetTypeDetector` для типов

3. **Проверка логирования:**
   - Нет избыточных логов
   - Информативные сообщения на этапах

---

## Критические правила

### 🔴 НИКОГДА

1. **Не дублируйте логику определения типа актива**
   - Используйте только `AssetTypeDetector`

2. **Не используйте raw данные без нормализации**
   - Всегда `normalize_candles()` перед индикаторами

3. **Не смешивайте I/O и вычисления**
   - I/O = async функции
   - Вычисления = sync функции

4. **Не хардкодите значения**
   - Все параметры из `config.py`

5. **Не логируйте каждый шаг**
   - Только результаты этапов

### ✅ ВСЕГДА

1. **Используйте `NormalizedCandles` для индикаторов**
2. **Используйте `AssetTypeDetector` для типов**
3. **Используйте универсальные функции `fetch_candles()`**
4. **Логируйте результаты, а не процесс**
5. **Добавляйте type hints везде**

---

## Быстрая справка

### Ключевые модули

- `utils/asset_detector.py` - Определение типа актива
- `data_providers/data_normalizer.py` - Нормализация данных
- `data_providers/__init__.py` - Универсальные функции загрузки
- `indicators/` - Все индикаторы
- `stages/` - Этапы анализа

### Ключевые функции

```python
# Определение типа
from utils.asset_detector import AssetTypeDetector
asset_type = AssetTypeDetector.detect(symbol)

# Загрузка данных
from data_providers import fetch_candles, normalize_candles
candles_raw = await fetch_candles(symbol, interval, limit)
candles = normalize_candles(candles_raw, symbol, interval)

# Индикаторы
from indicators import analyze_rsi, analyze_ema
rsi_result = analyze_rsi(candles)
ema_result = analyze_ema(candles)
```

---

**Последнее обновление:** 2025-01-13  
**Версия:** 4.0 - Модульная архитектура
