"""
Trading Bot Configuration — Triple EMA Strategy
Файл: config.py

ОБНОВЛЕНО:
- Добавлены пути для logs/ и signals/
- Автоматическое создание директорий
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
# DIRECTORIES (✅ НОВОЕ)
# ============================================================================
PROJECT_ROOT = Path(__file__).parent

LOGS_DIR = PROJECT_ROOT / 'logs'
SIGNALS_DIR = PROJECT_ROOT / 'signals'
BACKTEST_DIR = SIGNALS_DIR / 'backtest_results'

# Создаём директории если не существуют
LOGS_DIR.mkdir(exist_ok=True)
SIGNALS_DIR.mkdir(exist_ok=True)
BACKTEST_DIR.mkdir(exist_ok=True)

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
TIMEFRAME_SHORT = "60"  # 1H
TIMEFRAME_LONG = "240"  # 4H

TIMEFRAME_SHORT_NAME = "1H"
TIMEFRAME_LONG_NAME = "4H"

# ============================================================================
# STAGE 1: TRIPLE EMA PARAMETERS (9/21/50)
# ============================================================================
EMA_FAST = 9
EMA_MEDIUM = 21
EMA_SLOW = 50

EMA_MIN_GAP_PCT = 0.5
EMA_CROSSOVER_LOOKBACK = 5

PULLBACK_TOUCH_PCT = 1.5
PULLBACK_BOUNCE_VOLUME = 1.2

COMPRESSION_MAX_SPREAD_PCT = 1.0
COMPRESSION_BREAKOUT_VOLUME = 2.0

MIN_VOLUME_RATIO = 1.0
MIN_CONFIDENCE = 60

# ============================================================================
# ДОПОЛНИТЕЛЬНЫЕ ИНДИКАТОРЫ
# ============================================================================
RSI_PERIOD = 14
RSI_MIN_LONG = 50
RSI_MAX_LONG = 75
RSI_MIN_SHORT = 25
RSI_MAX_SHORT = 50

VOLUME_WINDOW = 20

MACD_FAST = 12
MACD_SLOW = 26
MACD_SIGNAL = 9

ATR_PERIOD = 14

# ============================================================================
# SCANNING PARAMETERS
# ============================================================================
QUICK_SCAN_CANDLES = 100

# ============================================================================
# STAGE 2: AI PAIR SELECTION
# ============================================================================
STAGE2_PROVIDER = os.getenv('STAGE2_PROVIDER', 'deepseek')
STAGE2_MODEL = os.getenv('STAGE2_MODEL', 'deepseek-chat')
STAGE2_TEMPERATURE = safe_float(os.getenv('STAGE2_TEMPERATURE', '0.3'), 0.3)
STAGE2_MAX_TOKENS = safe_int(os.getenv('STAGE2_MAX_TOKENS', '2000'), 2000)

STAGE2_CANDLES_1H = 60
STAGE2_CANDLES_4H = 60

# ============================================================================
# STAGE 3: AI COMPREHENSIVE ANALYSIS
# ============================================================================
STAGE3_PROVIDER = os.getenv('STAGE3_PROVIDER', 'deepseek')
STAGE3_MODEL = os.getenv('STAGE3_MODEL', 'deepseek-chat')
STAGE3_TEMPERATURE = safe_float(os.getenv('STAGE3_TEMPERATURE', '0.7'), 0.7)
STAGE3_MAX_TOKENS = safe_int(os.getenv('STAGE3_MAX_TOKENS', '5000'), 5000)

STAGE3_CANDLES_1H = 100
STAGE3_CANDLES_4H = 60

AI_INDICATORS_HISTORY = 30
FINAL_INDICATORS_HISTORY = 30

# ============================================================================
# PAIR SELECTION
# ============================================================================
MAX_FINAL_PAIRS = 3

# ============================================================================
# TRADING PARAMETERS
# ============================================================================
MIN_RISK_REWARD_RATIO = 1.5

# ============================================================================
# MARKET DATA THRESHOLDS
# ============================================================================
OI_CHANGE_GROWING_THRESHOLD = 2.0
OI_CHANGE_DECLINING_THRESHOLD = -2.0

# ============================================================================
# API SETTINGS
# ============================================================================
API_TIMEOUT = 30
API_TIMEOUT_ANALYSIS = 120
MAX_CONCURRENT = 50

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
# AI LEGACY
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
# CONFIG CLASS
# ============================================================================
class Config:
    """Централизованный класс конфигурации"""

    # Directories (✅ НОВОЕ)
    PROJECT_ROOT = PROJECT_ROOT
    LOGS_DIR = LOGS_DIR
    SIGNALS_DIR = SIGNALS_DIR
    BACKTEST_DIR = BACKTEST_DIR

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
# VALIDATION
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