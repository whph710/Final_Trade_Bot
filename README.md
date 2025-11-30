# 🤖 Trading Bot - Triple EMA Strategy

Автоматизированная торговая система на базе стратегии Triple EMA (9/21/50) с AI анализом через DeepSeek и Claude.

---

## 📁 Структура проекта

```
trading_bot/
│
├── main.py                  # Точка входа
├── config.py                # Конфигурация
├── .env                     # Секретные данные (API keys)
├── requirements.txt         # Зависимости
│
├── 📂 data_providers/       # Получение данных с Bybit
│   ├── bybit_client.py      # Bybit API клиент
│   ├── data_normalizer.py   # Нормализация в NormalizedCandles
│   └── market_data.py       # Funding, OI, Orderbook
│
├── 📂 indicators/           # Технические индикаторы
│   ├── ema.py               # Triple EMA (9/21/50)
│   ├── rsi.py               # RSI
│   ├── macd.py              # MACD
│   ├── volume.py            # Volume Ratio
│   └── atr.py               # ATR (для stop-loss)
│
├── 📂 stages/               # Этапы pipeline
│   ├── stage1_filter.py     # Фильтр по базовым сигналам
│   ├── stage2_selection.py  # AI отбор пар
│   └── stage3_analysis.py   # Comprehensive AI анализ
│
├── 📂 ai/                   # AI провайдеры
│   ├── deepseek_client.py   # DeepSeek API
│   ├── anthropic_client.py  # Claude API
│   ├── ai_router.py         # Роутер между провайдерами
│   └── prompts/             # Промпты для AI
│       ├── prompt_select.txt
│       └── prompt_analyze.txt
│
├── 📂 telegram/             # Telegram бот
│   ├── bot_main.py          # Основной бот
│   ├── formatters.py        # Форматирование сообщений
│   └── scheduler.py         # Планировщик запусков
│
└── 📂 utils/                # Вспомогательные утилиты
    ├── logger.py            # Логирование
    └── validators.py        # Валидация данных
```

---

## 🚀 Быстрый старт

### 1. Установка зависимостей

```bash
pip install -r requirements.txt
```

### 2. Настройка .env

Создай файл `.env` в корне проекта:

```env
# API Keys
DEEPSEEK_API_KEY=your_deepseek_api_key_here
ANTHROPIC_API_KEY=your_anthropic_api_key_here

# Telegram
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_USER_ID=your_telegram_user_id
TELEGRAM_GROUP_ID=your_telegram_group_id

# Stage Configuration
STAGE2_PROVIDER=deepseek
STAGE2_MODEL=deepseek-chat
STAGE2_TEMPERATURE=0.3
STAGE2_MAX_TOKENS=2000

STAGE3_PROVIDER=claude
STAGE3_MODEL=claude-sonnet-4-5-20250929
STAGE3_TEMPERATURE=0.7
STAGE3_MAX_TOKENS=5000

# Triple EMA Parameters
EMA_FAST=9
EMA_MEDIUM=21
EMA_SLOW=50
MIN_VOLUME_RATIO=1.0
MIN_CONFIDENCE=60
```

### 3. Запуск

**Telegram бот (с расписанием):**
```bash
python main.py telegram
```

**Тестовый запуск (один цикл):**
```bash
python main.py once
```

---

## ⚙️ Конфигурация

Все параметры настраиваются через `config.py` и `.env`:

### Triple EMA Strategy
- `EMA_FAST=9` - Быстрая EMA (краткосрочный momentum)
- `EMA_MEDIUM=21` - Средняя EMA (среднесрочный тренд)
- `EMA_SLOW=50` - Медленная EMA (основной тренд)

### AI Providers
- **Stage 2** (Selection): DeepSeek или Claude
- **Stage 3** (Analysis): DeepSeek или Claude

### Timeframes
- `1H` - Timing и entry точки
- `4H` - Major trend context

---

## 🎯 Как работает бот

### Stage 1: Signal Filtering
- Сканирование ~200+ торговых пар на Bybit
- Анализ Triple EMA паттернов:
  - Perfect Alignment (EMA9 > EMA21 > EMA50)
  - Golden/Death Cross
  - Pullback to EMA21
  - Compression Breakout
- Фильтрация по confidence (минимум 60%)

### Stage 2: AI Pair Selection
- Compact multi-timeframe данные (1H + 4H)
- AI отбирает 3-5 лучших пар
- Провайдер: DeepSeek (быстрый) или Claude

### Stage 3: Comprehensive Analysis
- Полный анализ выбранных пар:
  - Triple EMA (1H + 4H)
  - RSI, MACD, Volume
  - Market Data (Funding, OI, Orderbook)
  - BTC Correlation
  - Volume Profile
- AI генерирует entry, stop-loss, TP1/TP2/TP3
- Провайдер: Claude (детальный анализ)

---

## 📊 Расписание запуска

Бот работает по расписанию (Пермь UTC+5):

- **10:05-11:05** - Азия активна
- **16:05-17:05** - Европа ↔ Азия
- **22:05-23:05** - Pre-US market

Или запуск вручную через Telegram команду.

---

## 📱 Telegram команды

- `/start` - Активация бота
- `▶️ Запустить сейчас` - Ручной запуск анализа
- `📊 Статус` - Текущее состояние
- `📈 Статистика` - Статистика запусков
- `🛑 Остановить` - Остановка бота

---

## 🔧 Разработка

### Добавление нового индикатора

1. Создай файл `indicators/my_indicator.py`
2. Реализуй функции с единым input/output:

```python
from dataclasses import dataclass

@dataclass
class MyIndicatorAnalysis:
    value: float
    trend: str
    confidence_adjustment: int
    details: str

def analyze_my_indicator(candles: NormalizedCandles) -> MyIndicatorAnalysis:
    # Твоя логика
    pass
```

3. Добавь в `indicators/__init__.py`

### Замена AI провайдера

В `.env` измени:
```env
STAGE2_PROVIDER=deepseek  # или claude
STAGE3_PROVIDER=claude    # или deepseek
```

---

## 📄 Лицензия

Proprietary - для личного использования

---

## 🤝 Поддержка

При возникновении проблем:
1. Проверь `.env` конфигурацию
2. Проверь логи в `bot_logs/`
3. Запусти тестовый режим: `python main.py once`