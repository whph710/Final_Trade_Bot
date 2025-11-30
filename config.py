"""
Trading Bot Configuration — Triple EMA Strategy
Файл: config.py

Все параметры стратегии и настройки системы.
Секретные данные (API keys) хранятся в .env
"""

import os
from pathlib import Path
from typing import Optional


def load_env():
    """Загрузить переменные из .env файла"""
    env_path = Path(__file__).parent / '.env'

    if not env_path.exists():
        raise FileNotFoundError(f".env file not found at {env_path}")

    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith('#') and '=' in line:
                key, value = line.split('=', 1)
                # Удаляем inline комментарии
                if '#' in value:
                    value = value.split('#')[0]
                os.environ[key.strip()] = value.strip()


def safe_int(value: str, default: int) -> int:
    """Безопасное преобразование в int"""
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


def safe_float(value: str, default: float) -> float:
    """Безопасное преобразование в float"""
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_bool(value: str) -> bool:
    """Безопасное преобразование в bool"""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ['true', '1', 'yes']
    return False


# Загружаем .env при импорте модуля
load_env()

# ============================================================================
# API KEYS (из .env)
# ============================================================================
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
TELEGRAM_USER_ID = safe_int(os.getenv('TELEGRAM_USER_ID', '0'), 0)
TELEGRAM_GROUP_ID = safe_int(os.getenv('TELEGRAM_GROUP_ID', '0'), 0)

# ============================================================================
# TIMEFRAMES
# ============================================================================
TIMEFRAME_SHORT = "60"  # 1H (для entry timing)
TIMEFRAME_LONG = "240"  # 4H (для major trend)

TIMEFRAME_SHORT_NAME = "1H"
TIMEFRAME_LONG_NAME = "4H"

# ============================================================================
# STAGE 1: TRIPLE EMA PARAMETERS (9/21/50)
# ============================================================================

# EMA periods
EMA_FAST = 9  # Быстрая EMA (краткосрочный momentum)
EMA_MEDIUM = 21  # Средняя EMA (среднесрочный тренд, pullback target)
EMA_SLOW = 50  # Медленная EMA (основной тренд, macro direction)

# Минимальный зазор между EMA для "perfect alignment" (в процентах)
EMA_MIN_GAP_PCT = 0.5  # 0.5% минимум между EMA для чистого тренда

# Lookback для поиска crossovers (пересечений)
EMA_CROSSOVER_LOOKBACK = 5  # Ищем crossover в последних 5 свечах

# Pullback параметры
PULLBACK_TOUCH_PCT = 1.5  # ±1.5% от EMA21 для "касания"
PULLBACK_BOUNCE_VOLUME = 1.2  # Минимум volume ratio для pullback bounce

# Compression (сжатие) параметры
COMPRESSION_MAX_SPREAD_PCT = 1.0  # <1% между EMA9 и EMA50 = compressed
COMPRESSION_BREAKOUT_VOLUME = 2.0  # Volume spike при пробое из compression

# Volume confirmation
MIN_VOLUME_RATIO = 1.0  # Минимум volume ratio для Stage 1 base signal

# Confidence threshold
MIN_CONFIDENCE = 60  # Минимальная уверенность для прохождения Stage 1

# ============================================================================
# ДОПОЛНИТЕЛЬНЫЕ ИНДИКАТОРЫ (для AI анализа в Stage 2/3)
# ============================================================================

# RSI
RSI_PERIOD = 14
RSI_MIN_LONG = 50  # Минимум для LONG (используется только AI)
RSI_MAX_LONG = 75  # Максимум для LONG
RSI_MIN_SHORT = 25  # Минимум для SHORT
RSI_MAX_SHORT = 50  # Максимум для SHORT

# Volume window
VOLUME_WINDOW = 20  # Окно для расчёта среднего объёма

# MACD (используется только в AI анализе)
MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

# ATR (для stop-loss calculation)
ATR_PERIOD = 14

# ============================================================================
# STAGE 1: SCANNING PARAMETERS
# ============================================================================
QUICK_SCAN_CANDLES = 100  # Достаточно для EMA50 + история

# ============================================================================
# STAGE 2: AI PAIR SELECTION (Compact Data)
# ============================================================================
STAGE2_PROVIDER = os.getenv('STAGE2_PROVIDER', 'deepseek')
STAGE2_MODEL = os.getenv('STAGE2_MODEL', 'deepseek-chat')
STAGE2_TEMPERATURE = safe_float(os.getenv('STAGE2_TEMPERATURE', '0.3'), 0.3)
STAGE2_MAX_TOKENS = safe_int(os.getenv('STAGE2_MAX_TOKENS', '2000'), 2000)

STAGE2_CANDLES_1H = 60  # Compact data для Stage 2
STAGE2_CANDLES_4H = 60

# ============================================================================
# STAGE 3: AI COMPREHENSIVE ANALYSIS (Full Data)
# ============================================================================
STAGE3_PROVIDER = os.getenv('STAGE3_PROVIDER', 'deepseek')
STAGE3_MODEL = os.getenv('STAGE3_MODEL', 'deepseek-chat')
STAGE3_TEMPERATURE = safe_float(os.getenv('STAGE3_TEMPERATURE', '0.7'), 0.7)
STAGE3_MAX_TOKENS = safe_int(os.getenv('STAGE3_MAX_TOKENS', '5000'), 5000)

STAGE3_CANDLES_1H = 100  # Full data для Stage 3
STAGE3_CANDLES_4H = 60

AI_INDICATORS_HISTORY = 30  # История индикаторов для compact data
FINAL_INDICATORS_HISTORY = 30  # История индикаторов для full data

# ============================================================================
# PAIR SELECTION
# ============================================================================
MAX_FINAL_PAIRS = 3  # 3-5 пар для глубокого анализа

# ============================================================================
# TRADING PARAMETERS
# ============================================================================
MIN_RISK_REWARD_RATIO = 1.5  # Минимум R/R для swing trading

# ============================================================================
# MARKET DATA THRESHOLDS
# ============================================================================
OI_CHANGE_GROWING_THRESHOLD = 2.0  # OI рост >2% = GROWING
OI_CHANGE_DECLINING_THRESHOLD = -2.0  # OI падение <-2% = DECLINING

# ============================================================================
# API SETTINGS
# ============================================================================
API_TIMEOUT = 30  # Общий timeout для API запросов
API_TIMEOUT_ANALYSIS = 120  # Увеличенный timeout для Stage 3
MAX_CONCURRENT = 50  # Максимум одновременных запросов

# ============================================================================
# DEEPSEEK CONFIGURATION
# ============================================================================
DEEPSEEK_URL = os.getenv('DEEPSEEK_URL', 'https://api.deepseek.com')
DEEPSEEK_MODEL = os.getenv('DEEPSEEK_MODEL', 'deepseek-chat')
DEEPSEEK_REASONING = safe_bool(os.getenv('DEEPSEEK_REASONING', 'false'))

# ============================================================================
# ANTHROPIC CONFIGURATION
# ============================================================================
ANTHROPIC_MODEL = os.getenv('ANTHROPIC_MODEL', 'claude-sonnet-4-5-20250929')
ANTHROPIC_THINKING = safe_bool(os.getenv('ANTHROPIC_THINKING', 'false'))

# ============================================================================
# PROMPTS PATHS
# ============================================================================
SELECTION_PROMPT = 'ai/prompts/prompt_select.txt'
ANALYSIS_PROMPT = 'ai/prompts/prompt_analyze.txt'

# ============================================================================
# AI TEMPERATURE & TOKENS (legacy, используются как fallback)
# ============================================================================
AI_TEMPERATURE_SELECT = safe_float(os.getenv('AI_TEMPERATURE_SELECT', '0.3'), 0.3)
AI_TEMPERATURE_ANALYZE = safe_float(os.getenv('AI_TEMPERATURE_ANALYZE', '0.7'), 0.7)
AI_MAX_TOKENS_SELECT = safe_int(os.getenv('AI_MAX_TOKENS_SELECT', '2000'), 2000)
AI_MAX_TOKENS_ANALYZE = safe_int(os.getenv('AI_MAX_TOKENS_ANALYZE', '5000'), 5000)

# ============================================================================
# RATE LIMITING
# ============================================================================
CLAUDE_RATE_LIMIT_DELAY = safe_int(os.getenv('CLAUDE_RATE_LIMIT_DELAY', '0'), 0)


# ============================================================================
# CONFIG CLASS (для удобного импорта)
# ============================================================================
class Config:
    """Централизованный класс конфигурации"""

    # API Keys
    DEEPSEEK_API_KEY = DEEPSEEK_API_KEY
    ANTHROPIC_API_KEY = ANTHROPIC_API_KEY
    TELEGRAM_BOT_TOKEN = TELEGRAM_BOT_TOKEN
    TELEGRAM_USER_ID = TELEGRAM_USER_ID
    TELEGRAM_GROUP_ID = TELEGRAM_GROUP_ID

    # Timeframes
    TIMEFRAME_SHORT = TIMEFRAME_SHORT
    TIMEFRAME_LONG = TIMEFRAME_LONG
    TIMEFRAME_SHORT_NAME = TIMEFRAME_SHORT_NAME
    TIMEFRAME_LONG_NAME = TIMEFRAME_LONG_NAME

    # Triple EMA
    EMA_FAST = EMA_FAST
    EMA_MEDIUM = EMA_MEDIUM
    EMA_SLOW = EMA_SLOW
    EMA_MIN_GAP_PCT = EMA_MIN_GAP_PCT
    EMA_CROSSOVER_LOOKBACK = EMA_CROSSOVER_LOOKBACK
    PULLBACK_TOUCH_PCT = PULLBACK_TOUCH_PCT
    PULLBACK_BOUNCE_VOLUME = PULLBACK_BOUNCE_VOLUME
    COMPRESSION_MAX_SPREAD_PCT = COMPRESSION_MAX_SPREAD_PCT
    COMPRESSION_BREAKOUT_VOLUME = COMPRESSION_BREAKOUT_VOLUME
    MIN_VOLUME_RATIO = MIN_VOLUME_RATIO
    MIN_CONFIDENCE = MIN_CONFIDENCE

    # Дополнительные индикаторы
    RSI_PERIOD = RSI_PERIOD
    RSI_MIN_LONG = RSI_MIN_LONG
    RSI_MAX_LONG = RSI_MAX_LONG
    RSI_MIN_SHORT = RSI_MIN_SHORT
    RSI_MAX_SHORT = RSI_MAX_SHORT
    VOLUME_WINDOW = VOLUME_WINDOW
    MACD_FAST = MACD_FAST
    MACD_SLOW = MACD_SLOW
    MACD_SIGNAL = MACD_SIGNAL
    ATR_PERIOD = ATR_PERIOD

    # Scanning
    QUICK_SCAN_CANDLES = QUICK_SCAN_CANDLES

    # Stage 2
    STAGE2_PROVIDER = STAGE2_PROVIDER
    STAGE2_MODEL = STAGE2_MODEL
    STAGE2_TEMPERATURE = STAGE2_TEMPERATURE
    STAGE2_MAX_TOKENS = STAGE2_MAX_TOKENS
    STAGE2_CANDLES_1H = STAGE2_CANDLES_1H
    STAGE2_CANDLES_4H = STAGE2_CANDLES_4H

    # Stage 3
    STAGE3_PROVIDER = STAGE3_PROVIDER
    STAGE3_MODEL = STAGE3_MODEL
    STAGE3_TEMPERATURE = STAGE3_TEMPERATURE
    STAGE3_MAX_TOKENS = STAGE3_MAX_TOKENS
    STAGE3_CANDLES_1H = STAGE3_CANDLES_1H
    STAGE3_CANDLES_4H = STAGE3_CANDLES_4H

    # Indicators history
    AI_INDICATORS_HISTORY = AI_INDICATORS_HISTORY
    FINAL_INDICATORS_HISTORY = FINAL_INDICATORS_HISTORY

    # Trading
    MAX_FINAL_PAIRS = MAX_FINAL_PAIRS
    MIN_RISK_REWARD_RATIO = MIN_RISK_REWARD_RATIO

    # Market data
    OI_CHANGE_GROWING_THRESHOLD = OI_CHANGE_GROWING_THRESHOLD
    OI_CHANGE_DECLINING_THRESHOLD = OI_CHANGE_DECLINING_THRESHOLD

    # API
    API_TIMEOUT = API_TIMEOUT
    API_TIMEOUT_ANALYSIS = API_TIMEOUT_ANALYSIS
    MAX_CONCURRENT = MAX_CONCURRENT

    # DeepSeek
    DEEPSEEK_URL = DEEPSEEK_URL
    DEEPSEEK_MODEL = DEEPSEEK_MODEL
    DEEPSEEK_REASONING = DEEPSEEK_REASONING

    # Anthropic
    ANTHROPIC_MODEL = ANTHROPIC_MODEL
    ANTHROPIC_THINKING = ANTHROPIC_THINKING

    # Prompts
    SELECTION_PROMPT = SELECTION_PROMPT
    ANALYSIS_PROMPT = ANALYSIS_PROMPT

    # AI legacy
    AI_TEMPERATURE_SELECT = AI_TEMPERATURE_SELECT
    AI_TEMPERATURE_ANALYZE = AI_TEMPERATURE_ANALYZE
    AI_MAX_TOKENS_SELECT = AI_MAX_TOKENS_SELECT
    AI_MAX_TOKENS_ANALYZE = AI_MAX_TOKENS_ANALYZE

    # Rate limiting
    CLAUDE_RATE_LIMIT_DELAY = CLAUDE_RATE_LIMIT_DELAY


# Создаём экземпляр для удобного импорта
config = Config()


# ============================================================================
# VALIDATION (проверка критичных параметров)
# ============================================================================
def validate_config():
    """Проверка обязательных параметров"""
    errors = []

    if not TELEGRAM_BOT_TOKEN:
        errors.append("TELEGRAM_BOT_TOKEN not set in .env")

    if TELEGRAM_USER_ID == 0:
        errors.append("TELEGRAM_USER_ID not set in .env")

    if TELEGRAM_GROUP_ID == 0:
        errors.append("TELEGRAM_GROUP_ID not set in .env")

    if not DEEPSEEK_API_KEY and not ANTHROPIC_API_KEY:
        errors.append("At least one AI API key required (DEEPSEEK or ANTHROPIC)")

    if errors:
        raise ValueError(
            "Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors)
        )


# Валидируем конфигурацию при импорте
validate_config()