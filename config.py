"""
Trading Bot Configuration — Triple EMA Strategy
Файл: config.py

✅ ОБНОВЛЕНО:
- Добавлена поддержка нескольких пользователей через TELEGRAM_USER_IDS
- Обратная совместимость с TELEGRAM_USER_ID
"""

import os
from pathlib import Path
from typing import Optional, List


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


def parse_user_ids(ids_str: str) -> List[int]:
    """
    Парсинг списка user IDs из строки через запятую

    Args:
        ids_str: Строка вида "123456,789012,345678"

    Returns:
        Список int ID (без нулевых)
    """
    try:
        ids = [int(id.strip()) for id in ids_str.split(',') if id.strip()]
        return [id for id in ids if id != 0]
    except Exception:
        return []


# Загружаем .env при импорте модуля
load_env()

# ============================================================================
# DIRECTORIES
# ============================================================================
PROJECT_ROOT = Path(__file__).parent

LOGS_DIR = PROJECT_ROOT / 'logs'
SIGNALS_DIR = PROJECT_ROOT / 'signals'
BACKTEST_DIR = SIGNALS_DIR / 'backtest_results'

LOGS_DIR.mkdir(exist_ok=True)
SIGNALS_DIR.mkdir(exist_ok=True)
BACKTEST_DIR.mkdir(exist_ok=True)

# ============================================================================
# API KEYS
# ============================================================================
DEEPSEEK_API_KEY = os.getenv('DEEPSEEK_API_KEY')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# ✅ НОВОЕ: Поддержка нескольких пользователей
TELEGRAM_USER_IDS_STR = os.getenv('TELEGRAM_USER_IDS', os.getenv('TELEGRAM_USER_ID', '0'))

# Парсим список ID
TELEGRAM_USER_IDS = parse_user_ids(TELEGRAM_USER_IDS_STR)

# Для обратной совместимости (первый ID как primary)
TELEGRAM_USER_ID = TELEGRAM_USER_IDS[0] if TELEGRAM_USER_IDS else 0

# ✅ Администраторы бота (список ID через запятую)
TELEGRAM_ADMIN_IDS_STR = os.getenv('TELEGRAM_ADMIN_IDS', '632260351')
TELEGRAM_ADMIN_IDS = parse_user_ids(TELEGRAM_ADMIN_IDS_STR)

TELEGRAM_GROUP_ID = safe_int(os.getenv('TELEGRAM_GROUP_ID', '0'), 0)

# ============================================================================
# TIMEFRAMES
# ============================================================================
TIMEFRAME_SHORT = "60"   # 1H
TIMEFRAME_LONG = "240"   # 4H

TIMEFRAME_SHORT_NAME = "1H"
TIMEFRAME_LONG_NAME = "4H"

# ============================================================================
# STAGE 1: TRIPLE EMA PARAMETERS
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
# ИНДИКАТОРЫ
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
# SCANNING
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

STAGE3_MAX_TOKENS = safe_int(os.getenv('STAGE3_MAX_TOKENS', '8000'), 8000)

# Исторические данные увеличены
STAGE3_CANDLES_1H = 200
STAGE3_CANDLES_4H = 100

# История индикаторов увеличена
AI_INDICATORS_HISTORY = 50
FINAL_INDICATORS_HISTORY = 50

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
# BYBIT API SETTINGS
# ============================================================================
BYBIT_MAX_CONCURRENT_REQUESTS = safe_int(os.getenv('BYBIT_MAX_CONCURRENT_REQUESTS', '50'), 50)
BYBIT_REQUEST_TIMEOUT = safe_int(os.getenv('BYBIT_REQUEST_TIMEOUT', '15'), 15)
BYBIT_CONNECT_TIMEOUT = safe_int(os.getenv('BYBIT_CONNECT_TIMEOUT', '5'), 5)
BYBIT_LIMIT_PER_HOST = safe_int(os.getenv('BYBIT_LIMIT_PER_HOST', '25'), 25)
BYBIT_KEEPALIVE_TIMEOUT = safe_int(os.getenv('BYBIT_KEEPALIVE_TIMEOUT', '120'), 120)
BYBIT_DEFAULT_CANDLES_LIMIT = safe_int(os.getenv('BYBIT_DEFAULT_CANDLES_LIMIT', '200'), 200)

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
# STAGE 1: SUPPORT/RESISTANCE LEVELS THRESHOLDS
# ============================================================================
# Расстояние до уровня для фильтрации
SR_LEVEL_MAX_DISTANCE_PCT = safe_float(os.getenv('SR_LEVEL_MAX_DISTANCE_PCT', '1.5'), 1.5)
SR_LEVEL_NEAR_DISTANCE_PCT = safe_float(os.getenv('SR_LEVEL_NEAR_DISTANCE_PCT', '1.0'), 1.0)
SR_LEVEL_IDEAL_DISTANCE_PCT = safe_float(os.getenv('SR_LEVEL_IDEAL_DISTANCE_PCT', '0.5'), 0.5)

# Пороги для scoring в Stage 1
SR_LEVEL_TOUCHES_PREMIUM = safe_int(os.getenv('SR_LEVEL_TOUCHES_PREMIUM', '5'), 5)
SR_LEVEL_TOUCHES_STRONG = safe_int(os.getenv('SR_LEVEL_TOUCHES_STRONG', '4'), 4)
SR_LEVEL_TOUCHES_VALID = safe_int(os.getenv('SR_LEVEL_TOUCHES_VALID', '3'), 3)

# Scoring пороги для расстояния
SR_DISTANCE_IDEAL_SCORE = safe_int(os.getenv('SR_DISTANCE_IDEAL_SCORE', '30'), 30)
SR_DISTANCE_GOOD_SCORE = safe_int(os.getenv('SR_DISTANCE_GOOD_SCORE', '25'), 25)
SR_DISTANCE_ACCEPTABLE_SCORE = safe_int(os.getenv('SR_DISTANCE_ACCEPTABLE_SCORE', '15'), 15)

# Scoring пороги для touches
SR_TOUCHES_PREMIUM_SCORE = safe_int(os.getenv('SR_TOUCHES_PREMIUM_SCORE', '40'), 40)
SR_TOUCHES_STRONG_SCORE = safe_int(os.getenv('SR_TOUCHES_STRONG_SCORE', '35'), 35)
SR_TOUCHES_VALID_SCORE = safe_int(os.getenv('SR_TOUCHES_VALID_SCORE', '25'), 25)

# Пороги для S/R анализа
SR_TOUCH_TOLERANCE_PCT = safe_float(os.getenv('SR_TOUCH_TOLERANCE_PCT', '0.5'), 0.5)
SR_MIN_TOUCHES = safe_int(os.getenv('SR_MIN_TOUCHES', '3'), 3)
SR_LOOKBACK = safe_int(os.getenv('SR_LOOKBACK', '100'), 100)
SR_ADJUSTMENT_NEAR = safe_int(os.getenv('SR_ADJUSTMENT_NEAR', '25'), 25)
SR_ADJUSTMENT_MODERATE = safe_int(os.getenv('SR_ADJUSTMENT_MODERATE', '15'), 15)
SR_ADJUSTMENT_BONUS_TOUCHES = safe_int(os.getenv('SR_ADJUSTMENT_BONUS_TOUCHES', '10'), 10)

# ============================================================================
# STAGE 1: WAVE ANALYSIS THRESHOLDS
# ============================================================================
WAVE_ANALYSIS_NUM_WAVES = safe_int(os.getenv('WAVE_ANALYSIS_NUM_WAVES', '5'), 5)
WAVE_EARLY_ENTRY_THRESHOLD = safe_float(os.getenv('WAVE_EARLY_ENTRY_THRESHOLD', '30.0'), 30.0)
WAVE_GOOD_ENTRY_THRESHOLD = safe_float(os.getenv('WAVE_GOOD_ENTRY_THRESHOLD', '50.0'), 50.0)
WAVE_LATE_ENTRY_THRESHOLD = safe_float(os.getenv('WAVE_LATE_ENTRY_THRESHOLD', '70.0'), 70.0)

WAVE_EARLY_ENTRY_SCORE = safe_int(os.getenv('WAVE_EARLY_ENTRY_SCORE', '20'), 20)
WAVE_GOOD_ENTRY_SCORE = safe_int(os.getenv('WAVE_GOOD_ENTRY_SCORE', '15'), 15)
WAVE_LATE_ENTRY_SCORE = safe_int(os.getenv('WAVE_LATE_ENTRY_SCORE', '5'), 5)
WAVE_TOO_LATE_PENALTY = safe_int(os.getenv('WAVE_TOO_LATE_PENALTY', '-10'), -10)

# ============================================================================
# STAGE 1: EMA200 THRESHOLDS
# ============================================================================
EMA200_OVEREXTENDED_PCT = safe_float(os.getenv('EMA200_OVEREXTENDED_PCT', '10.0'), 10.0)
EMA200_EXTENDED_PCT = safe_float(os.getenv('EMA200_EXTENDED_PCT', '5.0'), 5.0)
EMA200_SLOPE_THRESHOLD = safe_float(os.getenv('EMA200_SLOPE_THRESHOLD', '0.5'), 0.5)

EMA200_OVEREXTENDED_PENALTY = safe_int(os.getenv('EMA200_OVEREXTENDED_PENALTY', '-15'), -15)
EMA200_EXTENDED_PENALTY = safe_int(os.getenv('EMA200_EXTENDED_PENALTY', '-8'), -8)
EMA200_ALIGNMENT_BONUS = safe_int(os.getenv('EMA200_ALIGNMENT_BONUS', '10'), 10)

# ============================================================================
# STAGE 1: RSI THRESHOLDS
# ============================================================================
RSI_EXTREME_HIGH = safe_float(os.getenv('RSI_EXTREME_HIGH', '85.0'), 85.0)
RSI_EXTREME_LOW = safe_float(os.getenv('RSI_EXTREME_LOW', '15.0'), 15.0)
RSI_OPTIMAL_LONG_MIN = safe_float(os.getenv('RSI_OPTIMAL_LONG_MIN', '40.0'), 40.0)
RSI_OPTIMAL_LONG_MAX = safe_float(os.getenv('RSI_OPTIMAL_LONG_MAX', '70.0'), 70.0)
RSI_OPTIMAL_SHORT_MIN = safe_float(os.getenv('RSI_OPTIMAL_SHORT_MIN', '30.0'), 30.0)
RSI_OPTIMAL_SHORT_MAX = safe_float(os.getenv('RSI_OPTIMAL_SHORT_MAX', '60.0'), 60.0)
RSI_OVERBOUGHT = safe_float(os.getenv('RSI_OVERBOUGHT', '75.0'), 75.0)
RSI_OVERSOLD = safe_float(os.getenv('RSI_OVERSOLD', '25.0'), 25.0)

RSI_OPTIMAL_BONUS = safe_int(os.getenv('RSI_OPTIMAL_BONUS', '5'), 5)
RSI_EXTREME_PENALTY = safe_int(os.getenv('RSI_EXTREME_PENALTY', '-10'), -10)

# ============================================================================
# STAGE 1: VOLUME THRESHOLDS
# ============================================================================
VOLUME_SPIKE_THRESHOLD = safe_float(os.getenv('VOLUME_SPIKE_THRESHOLD', '2.0'), 2.0)
VOLUME_STRONG_THRESHOLD = safe_float(os.getenv('VOLUME_STRONG_THRESHOLD', '1.5'), 1.5)
VOLUME_GOOD_THRESHOLD = safe_float(os.getenv('VOLUME_GOOD_THRESHOLD', '1.2'), 1.2)
VOLUME_DEAD_THRESHOLD = safe_float(os.getenv('VOLUME_DEAD_THRESHOLD', '0.8'), 0.8)

VOLUME_SPIKE_SCORE = safe_int(os.getenv('VOLUME_SPIKE_SCORE', '10'), 10)
VOLUME_STRONG_SCORE = safe_int(os.getenv('VOLUME_STRONG_SCORE', '8'), 8)
VOLUME_GOOD_SCORE = safe_int(os.getenv('VOLUME_GOOD_SCORE', '5'), 5)
VOLUME_TREND_INCREASING_BONUS = safe_int(os.getenv('VOLUME_TREND_INCREASING_BONUS', '8'), 8)
VOLUME_TREND_DECREASING_PENALTY = safe_int(os.getenv('VOLUME_TREND_DECREASING_PENALTY', '-10'), -10)
VOLUME_DEAD_PENALTY = safe_int(os.getenv('VOLUME_DEAD_PENALTY', '-10'), -10)

# ============================================================================
# STAGE 1: SCORING THRESHOLDS
# ============================================================================
STAGE1_MIN_SCORE = safe_int(os.getenv('STAGE1_MIN_SCORE', '60'), 60)
STAGE1_CONFLICTING_SCORE_DIFF = safe_int(os.getenv('STAGE1_CONFLICTING_SCORE_DIFF', '15'), 15)
STAGE1_PERFECT_PATTERN_SCORE = safe_int(os.getenv('STAGE1_PERFECT_PATTERN_SCORE', '85'), 85)
STAGE1_STRONG_PATTERN_SCORE = safe_int(os.getenv('STAGE1_STRONG_PATTERN_SCORE', '70'), 70)
STAGE1_BASE_CONFIDENCE = safe_int(os.getenv('STAGE1_BASE_CONFIDENCE', '50'), 50)
STAGE1_MAX_CONFIDENCE = safe_int(os.getenv('STAGE1_MAX_CONFIDENCE', '95'), 95)

# ============================================================================
# ORDER BLOCKS THRESHOLDS
# ============================================================================
OB_LOOKBACK = safe_int(os.getenv('OB_LOOKBACK', '50'), 50)
OB_MIN_IMPULSE_PCT = safe_float(os.getenv('OB_MIN_IMPULSE_PCT', '2.0'), 2.0)
OB_MIN_IMBALANCE_BARS = safe_int(os.getenv('OB_MIN_IMBALANCE_BARS', '2'), 2)
OB_MAX_AGE_CANDLES = safe_int(os.getenv('OB_MAX_AGE_CANDLES', '30'), 30)
OB_SWING_WINDOW = safe_int(os.getenv('OB_SWING_WINDOW', '3'), 3)
OB_CLEAN_IMPULSE_RATIO = safe_float(os.getenv('OB_CLEAN_IMPULSE_RATIO', '0.7'), 0.7)
OB_MITIGATION_TOLERANCE = safe_float(os.getenv('OB_MITIGATION_TOLERANCE', '0.01'), 0.01)

OB_BASE_ADJUSTMENT = safe_int(os.getenv('OB_BASE_ADJUSTMENT', '8'), 8)
OB_STRENGTH_BONUS_THRESHOLD = safe_float(os.getenv('OB_STRENGTH_BONUS_THRESHOLD', '70.0'), 70.0)
OB_STRENGTH_BONUS = safe_int(os.getenv('OB_STRENGTH_BONUS', '5'), 5)
OB_FRESH_BONUS = safe_int(os.getenv('OB_FRESH_BONUS', '10'), 10)
OB_AGE_VERY_FRESH = safe_int(os.getenv('OB_AGE_VERY_FRESH', '5'), 5)
OB_AGE_FRESH = safe_int(os.getenv('OB_AGE_FRESH', '10'), 10)
OB_AGE_MEDIUM = safe_int(os.getenv('OB_AGE_MEDIUM', '20'), 20)
OB_AGE_OLD = safe_int(os.getenv('OB_AGE_OLD', '30'), 30)
OB_AGE_VERY_FRESH_BONUS = safe_int(os.getenv('OB_AGE_VERY_FRESH_BONUS', '8'), 8)
OB_AGE_FRESH_BONUS = safe_int(os.getenv('OB_AGE_FRESH_BONUS', '5'), 5)
OB_AGE_MEDIUM_BONUS = safe_int(os.getenv('OB_AGE_MEDIUM_BONUS', '2'), 2)
OB_AGE_OLD_PENALTY = safe_int(os.getenv('OB_AGE_OLD_PENALTY', '-5'), -5)
OB_DISTANCE_FAR_PCT = safe_float(os.getenv('OB_DISTANCE_FAR_PCT', '5.0'), 5.0)
OB_DISTANCE_CLOSE_PCT = safe_float(os.getenv('OB_DISTANCE_CLOSE_PCT', '1.0'), 1.0)
OB_DISTANCE_FAR_PENALTY = safe_int(os.getenv('OB_DISTANCE_FAR_PENALTY', '-8'), -8)
OB_DISTANCE_CLOSE_BONUS = safe_int(os.getenv('OB_DISTANCE_CLOSE_BONUS', '5'), 5)

# ============================================================================
# IMBALANCE (FVG) THRESHOLDS
# ============================================================================
IMB_LOOKBACK = safe_int(os.getenv('IMB_LOOKBACK', '50'), 50)
IMB_MIN_GAP_SIZE_PCT = safe_float(os.getenv('IMB_MIN_GAP_SIZE_PCT', '0.1'), 0.1)
IMB_FILL_THRESHOLD_PCT = safe_float(os.getenv('IMB_FILL_THRESHOLD_PCT', '50.0'), 50.0)
IMB_FILL_TOTAL_THRESHOLD = safe_float(os.getenv('IMB_FILL_TOTAL_THRESHOLD', '100.0'), 100.0)
IMB_FILL_TOUCH_COUNT = safe_int(os.getenv('IMB_FILL_TOUCH_COUNT', '3'), 3)
IMB_PARTIAL_FILL_30_PCT = safe_float(os.getenv('IMB_PARTIAL_FILL_30_PCT', '30.0'), 30.0)
IMB_PARTIAL_FILL_50_PCT = safe_float(os.getenv('IMB_PARTIAL_FILL_50_PCT', '50.0'), 50.0)

IMB_BASE_ADJUSTMENT = safe_int(os.getenv('IMB_BASE_ADJUSTMENT', '5'), 5)
IMB_UNFILLED_BONUS = safe_int(os.getenv('IMB_UNFILLED_BONUS', '8'), 8)
IMB_PARTIAL_30_BONUS = safe_int(os.getenv('IMB_PARTIAL_30_BONUS', '5'), 5)
IMB_PARTIAL_50_BONUS = safe_int(os.getenv('IMB_PARTIAL_50_BONUS', '3'), 3)
IMB_DISTANCE_FAR_PCT = safe_float(os.getenv('IMB_DISTANCE_FAR_PCT', '5.0'), 5.0)
IMB_DISTANCE_CLOSE_PCT = safe_float(os.getenv('IMB_DISTANCE_CLOSE_PCT', '1.0'), 1.0)
IMB_DISTANCE_FAR_PENALTY = safe_int(os.getenv('IMB_DISTANCE_FAR_PENALTY', '-5'), -5)
IMB_DISTANCE_CLOSE_BONUS = safe_int(os.getenv('IMB_DISTANCE_CLOSE_BONUS', '5'), 5)

# ============================================================================
# LIQUIDITY SWEEP THRESHOLDS
# ============================================================================
SWEEP_LOOKBACK = safe_int(os.getenv('SWEEP_LOOKBACK', '20'), 20)
SWEEP_THRESHOLD_PCT = safe_float(os.getenv('SWEEP_THRESHOLD_PCT', '1.5'), 1.5)
SWEEP_MIN_PCT = safe_float(os.getenv('SWEEP_MIN_PCT', '0.3'), 0.3)
SWEEP_REVERSAL_BARS = safe_int(os.getenv('SWEEP_REVERSAL_BARS', '3'), 3)
SWEEP_REVERSION_MIN_PCT = safe_float(os.getenv('SWEEP_REVERSION_MIN_PCT', '0.5'), 0.5)
SWEEP_VOLUME_SPIKE_MULTIPLIER = safe_float(os.getenv('SWEEP_VOLUME_SPIKE_MULTIPLIER', '1.5'), 1.5)

SWEEP_ALIGNED_ADJUSTMENT = safe_int(os.getenv('SWEEP_ALIGNED_ADJUSTMENT', '20'), 20)
SWEEP_VOLUME_CONFIRMATION_BONUS = safe_int(os.getenv('SWEEP_VOLUME_CONFIRMATION_BONUS', '5'), 5)
SWEEP_MISMATCH_PENALTY = safe_int(os.getenv('SWEEP_MISMATCH_PENALTY', '-10'), -10)

# ============================================================================
# VOLUME PROFILE THRESHOLDS
# ============================================================================
VP_NUM_BINS = safe_int(os.getenv('VP_NUM_BINS', '50'), 50)
VP_VALUE_AREA_PCT = safe_float(os.getenv('VP_VALUE_AREA_PCT', '0.70'), 0.70)
VP_HVN_MULTIPLIER = safe_float(os.getenv('VP_HVN_MULTIPLIER', '1.5'), 1.5)
VP_LVN_MULTIPLIER = safe_float(os.getenv('VP_LVN_MULTIPLIER', '0.5'), 0.5)

VP_POC_STRONG_DISTANCE_PCT = safe_float(os.getenv('VP_POC_STRONG_DISTANCE_PCT', '1.0'), 1.0)
VP_POC_MODERATE_DISTANCE_PCT = safe_float(os.getenv('VP_POC_MODERATE_DISTANCE_PCT', '2.5'), 2.5)
VP_POC_WEAK_DISTANCE_PCT = safe_float(os.getenv('VP_POC_WEAK_DISTANCE_PCT', '5.0'), 5.0)
VP_POC_STRONG_ADJUSTMENT = safe_int(os.getenv('VP_POC_STRONG_ADJUSTMENT', '8'), 8)
VP_POC_MODERATE_ADJUSTMENT = safe_int(os.getenv('VP_POC_MODERATE_ADJUSTMENT', '5'), 5)

VP_VA_OVEREXTENDED_PCT = safe_float(os.getenv('VP_VA_OVEREXTENDED_PCT', '3.0'), 3.0)
VP_VA_OVEREXTENDED_PENALTY = safe_int(os.getenv('VP_VA_OVEREXTENDED_PENALTY', '-5'), -5)
VP_VA_STRONG_BONUS = safe_int(os.getenv('VP_VA_STRONG_BONUS', '5'), 5)

VP_HVN_BONUS = safe_int(os.getenv('VP_HVN_BONUS', '5'), 5)
VP_LVN_PENALTY = safe_int(os.getenv('VP_LVN_PENALTY', '-3'), -3)

# ============================================================================
# CORRELATION THRESHOLDS
# ============================================================================
CORR_WINDOW = safe_int(os.getenv('CORR_WINDOW', '24'), 24)
CORR_STRONG_THRESHOLD = safe_float(os.getenv('CORR_STRONG_THRESHOLD', '0.7'), 0.7)
CORR_MODERATE_THRESHOLD = safe_float(os.getenv('CORR_MODERATE_THRESHOLD', '0.4'), 0.4)
CORR_BLOCK_THRESHOLD = safe_float(os.getenv('CORR_BLOCK_THRESHOLD', '0.85'), 0.85)
CORR_SIGNIFICANT_THRESHOLD = safe_float(os.getenv('CORR_SIGNIFICANT_THRESHOLD', '0.5'), 0.5)

CORR_ALIGNED_BONUS = safe_int(os.getenv('CORR_ALIGNED_BONUS', '8'), 8)
CORR_MISALIGNED_PENALTY = safe_int(os.getenv('CORR_MISALIGNED_PENALTY', '-12'), -12)

CORR_ANOMALY_DECOUPLING_MULTIPLIER = safe_float(os.getenv('CORR_ANOMALY_DECOUPLING_MULTIPLIER', '1.5'), 1.5)
CORR_ANOMALY_STRENGTH_BONUS = safe_int(os.getenv('CORR_ANOMALY_STRENGTH_BONUS', '10'), 10)
CORR_ANOMALY_WEAKNESS_PENALTY = safe_int(os.getenv('CORR_ANOMALY_WEAKNESS_PENALTY', '-15'), -15)

CORR_BTC_TREND_WINDOW = safe_int(os.getenv('CORR_BTC_TREND_WINDOW', '20'), 20)
CORR_BTC_TREND_THRESHOLD_PCT = safe_float(os.getenv('CORR_BTC_TREND_THRESHOLD_PCT', '1.0'), 1.0)

# ============================================================================
# ATR THRESHOLDS
# ============================================================================
ATR_STOP_LOSS_MULTIPLIER = safe_float(os.getenv('ATR_STOP_LOSS_MULTIPLIER', '2.0'), 2.0)
WAVE_SWING_WINDOW = safe_int(os.getenv('WAVE_SWING_WINDOW', '3'), 3)

# ============================================================================
# EMA THRESHOLDS
# ============================================================================
EMA_DISTANCE_OPTIMAL_PCT = safe_float(os.getenv('EMA_DISTANCE_OPTIMAL_PCT', '3.0'), 3.0)
EMA_DISTANCE_OPTIMAL_BONUS = safe_int(os.getenv('EMA_DISTANCE_OPTIMAL_BONUS', '8'), 8)
EMA_DISTANCE_FAR_PCT = safe_float(os.getenv('EMA_DISTANCE_FAR_PCT', '5.0'), 5.0)
EMA_DISTANCE_FAR_PENALTY = safe_int(os.getenv('EMA_DISTANCE_FAR_PENALTY', '-10'), -10)
EMA_SLOPE_FLAT_THRESHOLD = safe_float(os.getenv('EMA_SLOPE_FLAT_THRESHOLD', '0.5'), 0.5)
EMA_SLOPE_FLAT_PENALTY = safe_int(os.getenv('EMA_SLOPE_FLAT_PENALTY', '-10'), -10)
EMA_CROSSES_CHOPPY_THRESHOLD = safe_int(os.getenv('EMA_CROSSES_CHOPPY_THRESHOLD', '3'), 3)
EMA_CROSSES_CHOPPY_PENALTY = safe_int(os.getenv('EMA_CROSSES_CHOPPY_PENALTY', '-12'), -12)
EMA_VOLUME_LOW_THRESHOLD = safe_float(os.getenv('EMA_VOLUME_LOW_THRESHOLD', '0.8'), 0.8)
EMA_VOLUME_LOW_PENALTY = safe_int(os.getenv('EMA_VOLUME_LOW_PENALTY', '-10'), -10)

# ============================================================================
# STAGE 3: SIMPLE S/R VALIDATION
# ============================================================================
STAGE3_SR_LOOKBACK = safe_int(os.getenv('STAGE3_SR_LOOKBACK', '50'), 50)
STAGE3_SR_NEAR_DISTANCE_PCT = safe_float(os.getenv('STAGE3_SR_NEAR_DISTANCE_PCT', '1.5'), 1.5)

# ============================================================================
# BACKTESTING SETTINGS
# ============================================================================
BACKTEST_CANDLES_LIMIT = safe_int(os.getenv('BACKTEST_CANDLES_LIMIT', '1000'), 1000)
BACKTEST_DEBUG_CANDLES = safe_int(os.getenv('BACKTEST_DEBUG_CANDLES', '20'), 20)
BACKTEST_TIME_DIFF_THRESHOLD_MIN = safe_float(os.getenv('BACKTEST_TIME_DIFF_THRESHOLD_MIN', '10.0'), 10.0)

# ============================================================================
# BACKTESTING: QUALITY SCORING THRESHOLDS (Fallback when no candles)
# ============================================================================
# Confidence scoring (макс 35 баллов)
BACKTEST_QUALITY_CONFIDENCE_MAX = safe_int(os.getenv('BACKTEST_QUALITY_CONFIDENCE_MAX', '35'), 35)
BACKTEST_QUALITY_CONFIDENCE_BASE = safe_int(os.getenv('BACKTEST_QUALITY_CONFIDENCE_BASE', '50'), 50)
BACKTEST_QUALITY_CONFIDENCE_MULTIPLIER = safe_float(os.getenv('BACKTEST_QUALITY_CONFIDENCE_MULTIPLIER', '0.7'), 0.7)

# R/R ratio scoring (макс 25 баллов)
BACKTEST_QUALITY_RR_3_0_SCORE = safe_int(os.getenv('BACKTEST_QUALITY_RR_3_0_SCORE', '25'), 25)
BACKTEST_QUALITY_RR_2_5_SCORE = safe_int(os.getenv('BACKTEST_QUALITY_RR_2_5_SCORE', '20'), 20)
BACKTEST_QUALITY_RR_2_0_SCORE = safe_int(os.getenv('BACKTEST_QUALITY_RR_2_0_SCORE', '15'), 15)
BACKTEST_QUALITY_RR_1_5_SCORE = safe_int(os.getenv('BACKTEST_QUALITY_RR_1_5_SCORE', '10'), 10)
BACKTEST_QUALITY_RR_3_0_THRESHOLD = safe_float(os.getenv('BACKTEST_QUALITY_RR_3_0_THRESHOLD', '3.0'), 3.0)
BACKTEST_QUALITY_RR_2_5_THRESHOLD = safe_float(os.getenv('BACKTEST_QUALITY_RR_2_5_THRESHOLD', '2.5'), 2.5)
BACKTEST_QUALITY_RR_2_0_THRESHOLD = safe_float(os.getenv('BACKTEST_QUALITY_RR_2_0_THRESHOLD', '2.0'), 2.0)
BACKTEST_QUALITY_RR_1_5_THRESHOLD = safe_float(os.getenv('BACKTEST_QUALITY_RR_1_5_THRESHOLD', '1.5'), 1.5)

# SMC scoring (макс 20 баллов)
BACKTEST_QUALITY_SMC_MAX = safe_int(os.getenv('BACKTEST_QUALITY_SMC_MAX', '20'), 20)

# Market Data scoring (макс 10 баллов)
BACKTEST_QUALITY_MARKET_MAX = safe_int(os.getenv('BACKTEST_QUALITY_MARKET_MAX', '10'), 10)
BACKTEST_QUALITY_FUNDING_RATE_THRESHOLD = safe_float(os.getenv('BACKTEST_QUALITY_FUNDING_RATE_THRESHOLD', '0.01'), 0.01)
BACKTEST_QUALITY_FUNDING_RATE_SCORE = safe_int(os.getenv('BACKTEST_QUALITY_FUNDING_RATE_SCORE', '3'), 3)
BACKTEST_QUALITY_OI_CHANGE_SCORE = safe_int(os.getenv('BACKTEST_QUALITY_OI_CHANGE_SCORE', '4'), 4)
BACKTEST_QUALITY_SPREAD_THRESHOLD = safe_float(os.getenv('BACKTEST_QUALITY_SPREAD_THRESHOLD', '0.10'), 0.10)
BACKTEST_QUALITY_SPREAD_SCORE = safe_int(os.getenv('BACKTEST_QUALITY_SPREAD_SCORE', '3'), 3)

# Indicators scoring (макс 10 баллов)
BACKTEST_QUALITY_INDICATORS_MAX = safe_int(os.getenv('BACKTEST_QUALITY_INDICATORS_MAX', '10'), 10)
BACKTEST_QUALITY_RSI_LONG_MIN = safe_int(os.getenv('BACKTEST_QUALITY_RSI_LONG_MIN', '40'), 40)
BACKTEST_QUALITY_RSI_LONG_MAX = safe_int(os.getenv('BACKTEST_QUALITY_RSI_LONG_MAX', '70'), 70)
BACKTEST_QUALITY_RSI_SHORT_MIN = safe_int(os.getenv('BACKTEST_QUALITY_RSI_SHORT_MIN', '30'), 30)
BACKTEST_QUALITY_RSI_SHORT_MAX = safe_int(os.getenv('BACKTEST_QUALITY_RSI_SHORT_MAX', '60'), 60)
BACKTEST_QUALITY_RSI_SCORE = safe_int(os.getenv('BACKTEST_QUALITY_RSI_SCORE', '5'), 5)
BACKTEST_QUALITY_VOLUME_RATIO_THRESHOLD = safe_float(os.getenv('BACKTEST_QUALITY_VOLUME_RATIO_THRESHOLD', '1.5'), 1.5)
BACKTEST_QUALITY_VOLUME_RATIO_SCORE = safe_int(os.getenv('BACKTEST_QUALITY_VOLUME_RATIO_SCORE', '5'), 5)

# Quality score thresholds for outcome
BACKTEST_QUALITY_TP3_THRESHOLD = safe_int(os.getenv('BACKTEST_QUALITY_TP3_THRESHOLD', '85'), 85)
BACKTEST_QUALITY_TP2_THRESHOLD = safe_int(os.getenv('BACKTEST_QUALITY_TP2_THRESHOLD', '70'), 70)
BACKTEST_QUALITY_TP1_THRESHOLD = safe_int(os.getenv('BACKTEST_QUALITY_TP1_THRESHOLD', '55'), 55)
BACKTEST_QUALITY_MIN_THRESHOLD = safe_int(os.getenv('BACKTEST_QUALITY_MIN_THRESHOLD', '40'), 40)

# Order Blocks scoring (для quality fallback)
BACKTEST_QUALITY_OB_DISTANCE_THRESHOLD = safe_float(os.getenv('BACKTEST_QUALITY_OB_DISTANCE_THRESHOLD', '2.0'), 2.0)
BACKTEST_QUALITY_OB_AGE_FRESH = safe_int(os.getenv('BACKTEST_QUALITY_OB_AGE_FRESH', '10'), 10)
BACKTEST_QUALITY_OB_MAX_SCORE = safe_int(os.getenv('BACKTEST_QUALITY_OB_MAX_SCORE', '10'), 10)

# Imbalance scoring (для quality fallback)
BACKTEST_QUALITY_IMB_FILL_THRESHOLD = safe_int(os.getenv('BACKTEST_QUALITY_IMB_FILL_THRESHOLD', '50'), 50)


# ============================================================================
# CONFIG CLASS
# ============================================================================
class Config:
    PROJECT_ROOT = PROJECT_ROOT
    LOGS_DIR = LOGS_DIR
    SIGNALS_DIR = SIGNALS_DIR
    BACKTEST_DIR = BACKTEST_DIR

    DEEPSEEK_API_KEY = DEEPSEEK_API_KEY
    ANTHROPIC_API_KEY = ANTHROPIC_API_KEY
    TELEGRAM_BOT_TOKEN = TELEGRAM_BOT_TOKEN

    # ✅ НОВОЕ: Multi-user support
    TELEGRAM_USER_IDS = TELEGRAM_USER_IDS
    TELEGRAM_USER_ID = TELEGRAM_USER_ID  # Обратная совместимость
    TELEGRAM_ADMIN_IDS = TELEGRAM_ADMIN_IDS  # ✅ Администраторы бота
    TELEGRAM_GROUP_ID = TELEGRAM_GROUP_ID

    TIMEFRAME_SHORT = TIMEFRAME_SHORT
    TIMEFRAME_LONG = TIMEFRAME_LONG
    TIMEFRAME_SHORT_NAME = TIMEFRAME_SHORT_NAME
    TIMEFRAME_LONG_NAME = TIMEFRAME_LONG_NAME

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

    QUICK_SCAN_CANDLES = QUICK_SCAN_CANDLES

    STAGE2_PROVIDER = STAGE2_PROVIDER
    STAGE2_MODEL = STAGE2_MODEL
    STAGE2_TEMPERATURE = STAGE2_TEMPERATURE
    STAGE2_MAX_TOKENS = STAGE2_MAX_TOKENS
    STAGE2_CANDLES_1H = STAGE2_CANDLES_1H
    STAGE2_CANDLES_4H = STAGE2_CANDLES_4H

    STAGE3_PROVIDER = STAGE3_PROVIDER
    STAGE3_MODEL = STAGE3_MODEL
    STAGE3_TEMPERATURE = STAGE3_TEMPERATURE
    STAGE3_MAX_TOKENS = STAGE3_MAX_TOKENS
    STAGE3_CANDLES_1H = STAGE3_CANDLES_1H
    STAGE3_CANDLES_4H = STAGE3_CANDLES_4H

    AI_INDICATORS_HISTORY = AI_INDICATORS_HISTORY
    FINAL_INDICATORS_HISTORY = FINAL_INDICATORS_HISTORY

    MAX_FINAL_PAIRS = MAX_FINAL_PAIRS
    MIN_RISK_REWARD_RATIO = MIN_RISK_REWARD_RATIO

    OI_CHANGE_GROWING_THRESHOLD = OI_CHANGE_GROWING_THRESHOLD
    OI_CHANGE_DECLINING_THRESHOLD = OI_CHANGE_DECLINING_THRESHOLD

    API_TIMEOUT = API_TIMEOUT
    API_TIMEOUT_ANALYSIS = API_TIMEOUT_ANALYSIS
    MAX_CONCURRENT = MAX_CONCURRENT

    DEEPSEEK_URL = DEEPSEEK_URL
    DEEPSEEK_MODEL = DEEPSEEK_MODEL
    DEEPSEEK_REASONING = DEEPSEEK_REASONING

    ANTHROPIC_MODEL = ANTHROPIC_MODEL
    ANTHROPIC_THINKING = ANTHROPIC_THINKING

    SELECTION_PROMPT = SELECTION_PROMPT
    ANALYSIS_PROMPT = ANALYSIS_PROMPT

    AI_TEMPERATURE_SELECT = AI_TEMPERATURE_SELECT
    AI_TEMPERATURE_ANALYZE = AI_TEMPERATURE_ANALYZE
    AI_MAX_TOKENS_SELECT = AI_MAX_TOKENS_SELECT
    AI_MAX_TOKENS_ANALYZE = AI_MAX_TOKENS_ANALYZE

    CLAUDE_RATE_LIMIT_DELAY = CLAUDE_RATE_LIMIT_DELAY

    # Support/Resistance thresholds
    SR_LEVEL_MAX_DISTANCE_PCT = SR_LEVEL_MAX_DISTANCE_PCT
    SR_LEVEL_NEAR_DISTANCE_PCT = SR_LEVEL_NEAR_DISTANCE_PCT
    SR_LEVEL_IDEAL_DISTANCE_PCT = SR_LEVEL_IDEAL_DISTANCE_PCT
    SR_LEVEL_TOUCHES_PREMIUM = SR_LEVEL_TOUCHES_PREMIUM
    SR_LEVEL_TOUCHES_STRONG = SR_LEVEL_TOUCHES_STRONG
    SR_LEVEL_TOUCHES_VALID = SR_LEVEL_TOUCHES_VALID
    SR_DISTANCE_IDEAL_SCORE = SR_DISTANCE_IDEAL_SCORE
    SR_DISTANCE_GOOD_SCORE = SR_DISTANCE_GOOD_SCORE
    SR_DISTANCE_ACCEPTABLE_SCORE = SR_DISTANCE_ACCEPTABLE_SCORE
    SR_TOUCHES_PREMIUM_SCORE = SR_TOUCHES_PREMIUM_SCORE
    SR_TOUCHES_STRONG_SCORE = SR_TOUCHES_STRONG_SCORE
    SR_TOUCHES_VALID_SCORE = SR_TOUCHES_VALID_SCORE
    SR_TOUCH_TOLERANCE_PCT = SR_TOUCH_TOLERANCE_PCT
    SR_MIN_TOUCHES = SR_MIN_TOUCHES
    SR_LOOKBACK = SR_LOOKBACK
    SR_ADJUSTMENT_NEAR = SR_ADJUSTMENT_NEAR
    SR_ADJUSTMENT_MODERATE = SR_ADJUSTMENT_MODERATE
    SR_ADJUSTMENT_BONUS_TOUCHES = SR_ADJUSTMENT_BONUS_TOUCHES

    # Wave analysis thresholds
    WAVE_ANALYSIS_NUM_WAVES = WAVE_ANALYSIS_NUM_WAVES
    WAVE_EARLY_ENTRY_THRESHOLD = WAVE_EARLY_ENTRY_THRESHOLD
    WAVE_GOOD_ENTRY_THRESHOLD = WAVE_GOOD_ENTRY_THRESHOLD
    WAVE_LATE_ENTRY_THRESHOLD = WAVE_LATE_ENTRY_THRESHOLD
    WAVE_EARLY_ENTRY_SCORE = WAVE_EARLY_ENTRY_SCORE
    WAVE_GOOD_ENTRY_SCORE = WAVE_GOOD_ENTRY_SCORE
    WAVE_LATE_ENTRY_SCORE = WAVE_LATE_ENTRY_SCORE
    WAVE_TOO_LATE_PENALTY = WAVE_TOO_LATE_PENALTY

    # EMA200 thresholds
    EMA200_OVEREXTENDED_PCT = EMA200_OVEREXTENDED_PCT
    EMA200_EXTENDED_PCT = EMA200_EXTENDED_PCT
    EMA200_SLOPE_THRESHOLD = EMA200_SLOPE_THRESHOLD
    EMA200_OVEREXTENDED_PENALTY = EMA200_OVEREXTENDED_PENALTY
    EMA200_EXTENDED_PENALTY = EMA200_EXTENDED_PENALTY
    EMA200_ALIGNMENT_BONUS = EMA200_ALIGNMENT_BONUS

    # RSI thresholds
    RSI_EXTREME_HIGH = RSI_EXTREME_HIGH
    RSI_EXTREME_LOW = RSI_EXTREME_LOW
    RSI_OPTIMAL_LONG_MIN = RSI_OPTIMAL_LONG_MIN
    RSI_OPTIMAL_LONG_MAX = RSI_OPTIMAL_LONG_MAX
    RSI_OPTIMAL_SHORT_MIN = RSI_OPTIMAL_SHORT_MIN
    RSI_OPTIMAL_SHORT_MAX = RSI_OPTIMAL_SHORT_MAX
    RSI_OVERBOUGHT = RSI_OVERBOUGHT
    RSI_OVERSOLD = RSI_OVERSOLD
    RSI_OPTIMAL_BONUS = RSI_OPTIMAL_BONUS
    RSI_EXTREME_PENALTY = RSI_EXTREME_PENALTY

    # Volume thresholds
    VOLUME_SPIKE_THRESHOLD = VOLUME_SPIKE_THRESHOLD
    VOLUME_STRONG_THRESHOLD = VOLUME_STRONG_THRESHOLD
    VOLUME_GOOD_THRESHOLD = VOLUME_GOOD_THRESHOLD
    VOLUME_DEAD_THRESHOLD = VOLUME_DEAD_THRESHOLD
    VOLUME_SPIKE_SCORE = VOLUME_SPIKE_SCORE
    VOLUME_STRONG_SCORE = VOLUME_STRONG_SCORE
    VOLUME_GOOD_SCORE = VOLUME_GOOD_SCORE
    VOLUME_TREND_INCREASING_BONUS = VOLUME_TREND_INCREASING_BONUS
    VOLUME_TREND_DECREASING_PENALTY = VOLUME_TREND_DECREASING_PENALTY
    VOLUME_DEAD_PENALTY = VOLUME_DEAD_PENALTY

    # Stage 1 scoring thresholds
    STAGE1_MIN_SCORE = STAGE1_MIN_SCORE
    STAGE1_CONFLICTING_SCORE_DIFF = STAGE1_CONFLICTING_SCORE_DIFF
    STAGE1_PERFECT_PATTERN_SCORE = STAGE1_PERFECT_PATTERN_SCORE
    STAGE1_STRONG_PATTERN_SCORE = STAGE1_STRONG_PATTERN_SCORE
    STAGE1_BASE_CONFIDENCE = STAGE1_BASE_CONFIDENCE
    STAGE1_MAX_CONFIDENCE = STAGE1_MAX_CONFIDENCE

    # Order blocks thresholds
    OB_LOOKBACK = OB_LOOKBACK
    OB_MIN_IMPULSE_PCT = OB_MIN_IMPULSE_PCT
    OB_MIN_IMBALANCE_BARS = OB_MIN_IMBALANCE_BARS
    OB_MAX_AGE_CANDLES = OB_MAX_AGE_CANDLES
    OB_SWING_WINDOW = OB_SWING_WINDOW
    OB_CLEAN_IMPULSE_RATIO = OB_CLEAN_IMPULSE_RATIO
    OB_MITIGATION_TOLERANCE = OB_MITIGATION_TOLERANCE
    OB_BASE_ADJUSTMENT = OB_BASE_ADJUSTMENT
    OB_STRENGTH_BONUS_THRESHOLD = OB_STRENGTH_BONUS_THRESHOLD
    OB_STRENGTH_BONUS = OB_STRENGTH_BONUS
    OB_FRESH_BONUS = OB_FRESH_BONUS
    OB_AGE_VERY_FRESH = OB_AGE_VERY_FRESH
    OB_AGE_FRESH = OB_AGE_FRESH
    OB_AGE_MEDIUM = OB_AGE_MEDIUM
    OB_AGE_OLD = OB_AGE_OLD
    OB_AGE_VERY_FRESH_BONUS = OB_AGE_VERY_FRESH_BONUS
    OB_AGE_FRESH_BONUS = OB_AGE_FRESH_BONUS
    OB_AGE_MEDIUM_BONUS = OB_AGE_MEDIUM_BONUS
    OB_AGE_OLD_PENALTY = OB_AGE_OLD_PENALTY
    OB_DISTANCE_FAR_PCT = OB_DISTANCE_FAR_PCT
    OB_DISTANCE_CLOSE_PCT = OB_DISTANCE_CLOSE_PCT
    OB_DISTANCE_FAR_PENALTY = OB_DISTANCE_FAR_PENALTY
    OB_DISTANCE_CLOSE_BONUS = OB_DISTANCE_CLOSE_BONUS

    # Imbalance thresholds
    IMB_LOOKBACK = IMB_LOOKBACK
    IMB_MIN_GAP_SIZE_PCT = IMB_MIN_GAP_SIZE_PCT
    IMB_FILL_THRESHOLD_PCT = IMB_FILL_THRESHOLD_PCT
    IMB_FILL_TOTAL_THRESHOLD = IMB_FILL_TOTAL_THRESHOLD
    IMB_FILL_TOUCH_COUNT = IMB_FILL_TOUCH_COUNT
    IMB_PARTIAL_FILL_30_PCT = IMB_PARTIAL_FILL_30_PCT
    IMB_PARTIAL_FILL_50_PCT = IMB_PARTIAL_FILL_50_PCT
    IMB_BASE_ADJUSTMENT = IMB_BASE_ADJUSTMENT
    IMB_UNFILLED_BONUS = IMB_UNFILLED_BONUS
    IMB_PARTIAL_30_BONUS = IMB_PARTIAL_30_BONUS
    IMB_PARTIAL_50_BONUS = IMB_PARTIAL_50_BONUS
    IMB_DISTANCE_FAR_PCT = IMB_DISTANCE_FAR_PCT
    IMB_DISTANCE_CLOSE_PCT = IMB_DISTANCE_CLOSE_PCT
    IMB_DISTANCE_FAR_PENALTY = IMB_DISTANCE_FAR_PENALTY
    IMB_DISTANCE_CLOSE_BONUS = IMB_DISTANCE_CLOSE_BONUS

    # Liquidity sweep thresholds
    SWEEP_LOOKBACK = SWEEP_LOOKBACK
    SWEEP_THRESHOLD_PCT = SWEEP_THRESHOLD_PCT
    SWEEP_MIN_PCT = SWEEP_MIN_PCT
    SWEEP_REVERSAL_BARS = SWEEP_REVERSAL_BARS
    SWEEP_REVERSION_MIN_PCT = SWEEP_REVERSION_MIN_PCT
    SWEEP_VOLUME_SPIKE_MULTIPLIER = SWEEP_VOLUME_SPIKE_MULTIPLIER
    SWEEP_ALIGNED_ADJUSTMENT = SWEEP_ALIGNED_ADJUSTMENT
    SWEEP_VOLUME_CONFIRMATION_BONUS = SWEEP_VOLUME_CONFIRMATION_BONUS
    SWEEP_MISMATCH_PENALTY = SWEEP_MISMATCH_PENALTY

    # Volume profile thresholds
    VP_NUM_BINS = VP_NUM_BINS
    VP_VALUE_AREA_PCT = VP_VALUE_AREA_PCT
    VP_HVN_MULTIPLIER = VP_HVN_MULTIPLIER
    VP_LVN_MULTIPLIER = VP_LVN_MULTIPLIER
    VP_POC_STRONG_DISTANCE_PCT = VP_POC_STRONG_DISTANCE_PCT
    VP_POC_MODERATE_DISTANCE_PCT = VP_POC_MODERATE_DISTANCE_PCT
    VP_POC_WEAK_DISTANCE_PCT = VP_POC_WEAK_DISTANCE_PCT
    VP_POC_STRONG_ADJUSTMENT = VP_POC_STRONG_ADJUSTMENT
    VP_POC_MODERATE_ADJUSTMENT = VP_POC_MODERATE_ADJUSTMENT
    VP_VA_OVEREXTENDED_PCT = VP_VA_OVEREXTENDED_PCT
    VP_VA_OVEREXTENDED_PENALTY = VP_VA_OVEREXTENDED_PENALTY
    VP_VA_STRONG_BONUS = VP_VA_STRONG_BONUS
    VP_HVN_BONUS = VP_HVN_BONUS
    VP_LVN_PENALTY = VP_LVN_PENALTY

    # Correlation thresholds
    CORR_WINDOW = CORR_WINDOW
    CORR_STRONG_THRESHOLD = CORR_STRONG_THRESHOLD
    CORR_MODERATE_THRESHOLD = CORR_MODERATE_THRESHOLD
    CORR_BLOCK_THRESHOLD = CORR_BLOCK_THRESHOLD
    CORR_SIGNIFICANT_THRESHOLD = CORR_SIGNIFICANT_THRESHOLD
    CORR_ALIGNED_BONUS = CORR_ALIGNED_BONUS
    CORR_MISALIGNED_PENALTY = CORR_MISALIGNED_PENALTY
    CORR_ANOMALY_DECOUPLING_MULTIPLIER = CORR_ANOMALY_DECOUPLING_MULTIPLIER
    CORR_ANOMALY_STRENGTH_BONUS = CORR_ANOMALY_STRENGTH_BONUS
    CORR_ANOMALY_WEAKNESS_PENALTY = CORR_ANOMALY_WEAKNESS_PENALTY
    CORR_BTC_TREND_WINDOW = CORR_BTC_TREND_WINDOW
    CORR_BTC_TREND_THRESHOLD_PCT = CORR_BTC_TREND_THRESHOLD_PCT

    # ATR thresholds
    ATR_STOP_LOSS_MULTIPLIER = ATR_STOP_LOSS_MULTIPLIER
    WAVE_SWING_WINDOW = WAVE_SWING_WINDOW

    # EMA thresholds
    EMA_DISTANCE_OPTIMAL_PCT = EMA_DISTANCE_OPTIMAL_PCT
    EMA_DISTANCE_OPTIMAL_BONUS = EMA_DISTANCE_OPTIMAL_BONUS
    EMA_DISTANCE_FAR_PCT = EMA_DISTANCE_FAR_PCT
    EMA_DISTANCE_FAR_PENALTY = EMA_DISTANCE_FAR_PENALTY
    EMA_SLOPE_FLAT_THRESHOLD = EMA_SLOPE_FLAT_THRESHOLD
    EMA_SLOPE_FLAT_PENALTY = EMA_SLOPE_FLAT_PENALTY
    EMA_CROSSES_CHOPPY_THRESHOLD = EMA_CROSSES_CHOPPY_THRESHOLD
    EMA_CROSSES_CHOPPY_PENALTY = EMA_CROSSES_CHOPPY_PENALTY
    EMA_VOLUME_LOW_THRESHOLD = EMA_VOLUME_LOW_THRESHOLD
    EMA_VOLUME_LOW_PENALTY = EMA_VOLUME_LOW_PENALTY

    # Stage 3 S/R validation
    STAGE3_SR_LOOKBACK = STAGE3_SR_LOOKBACK
    STAGE3_SR_NEAR_DISTANCE_PCT = STAGE3_SR_NEAR_DISTANCE_PCT

    # Bybit API settings
    BYBIT_MAX_CONCURRENT_REQUESTS = BYBIT_MAX_CONCURRENT_REQUESTS
    BYBIT_REQUEST_TIMEOUT = BYBIT_REQUEST_TIMEOUT
    BYBIT_CONNECT_TIMEOUT = BYBIT_CONNECT_TIMEOUT
    BYBIT_LIMIT_PER_HOST = BYBIT_LIMIT_PER_HOST
    BYBIT_KEEPALIVE_TIMEOUT = BYBIT_KEEPALIVE_TIMEOUT
    BYBIT_DEFAULT_CANDLES_LIMIT = BYBIT_DEFAULT_CANDLES_LIMIT

    # Backtesting settings
    BACKTEST_CANDLES_LIMIT = BACKTEST_CANDLES_LIMIT
    BACKTEST_DEBUG_CANDLES = BACKTEST_DEBUG_CANDLES
    BACKTEST_TIME_DIFF_THRESHOLD_MIN = BACKTEST_TIME_DIFF_THRESHOLD_MIN

    # Backtesting quality scoring thresholds
    BACKTEST_QUALITY_CONFIDENCE_MAX = BACKTEST_QUALITY_CONFIDENCE_MAX
    BACKTEST_QUALITY_CONFIDENCE_BASE = BACKTEST_QUALITY_CONFIDENCE_BASE
    BACKTEST_QUALITY_CONFIDENCE_MULTIPLIER = BACKTEST_QUALITY_CONFIDENCE_MULTIPLIER
    BACKTEST_QUALITY_RR_3_0_SCORE = BACKTEST_QUALITY_RR_3_0_SCORE
    BACKTEST_QUALITY_RR_2_5_SCORE = BACKTEST_QUALITY_RR_2_5_SCORE
    BACKTEST_QUALITY_RR_2_0_SCORE = BACKTEST_QUALITY_RR_2_0_SCORE
    BACKTEST_QUALITY_RR_1_5_SCORE = BACKTEST_QUALITY_RR_1_5_SCORE
    BACKTEST_QUALITY_RR_3_0_THRESHOLD = BACKTEST_QUALITY_RR_3_0_THRESHOLD
    BACKTEST_QUALITY_RR_2_5_THRESHOLD = BACKTEST_QUALITY_RR_2_5_THRESHOLD
    BACKTEST_QUALITY_RR_2_0_THRESHOLD = BACKTEST_QUALITY_RR_2_0_THRESHOLD
    BACKTEST_QUALITY_RR_1_5_THRESHOLD = BACKTEST_QUALITY_RR_1_5_THRESHOLD
    BACKTEST_QUALITY_SMC_MAX = BACKTEST_QUALITY_SMC_MAX
    BACKTEST_QUALITY_MARKET_MAX = BACKTEST_QUALITY_MARKET_MAX
    BACKTEST_QUALITY_FUNDING_RATE_THRESHOLD = BACKTEST_QUALITY_FUNDING_RATE_THRESHOLD
    BACKTEST_QUALITY_FUNDING_RATE_SCORE = BACKTEST_QUALITY_FUNDING_RATE_SCORE
    BACKTEST_QUALITY_OI_CHANGE_SCORE = BACKTEST_QUALITY_OI_CHANGE_SCORE
    BACKTEST_QUALITY_SPREAD_THRESHOLD = BACKTEST_QUALITY_SPREAD_THRESHOLD
    BACKTEST_QUALITY_SPREAD_SCORE = BACKTEST_QUALITY_SPREAD_SCORE
    BACKTEST_QUALITY_INDICATORS_MAX = BACKTEST_QUALITY_INDICATORS_MAX
    BACKTEST_QUALITY_RSI_LONG_MIN = BACKTEST_QUALITY_RSI_LONG_MIN
    BACKTEST_QUALITY_RSI_LONG_MAX = BACKTEST_QUALITY_RSI_LONG_MAX
    BACKTEST_QUALITY_RSI_SHORT_MIN = BACKTEST_QUALITY_RSI_SHORT_MIN
    BACKTEST_QUALITY_RSI_SHORT_MAX = BACKTEST_QUALITY_RSI_SHORT_MAX
    BACKTEST_QUALITY_RSI_SCORE = BACKTEST_QUALITY_RSI_SCORE
    BACKTEST_QUALITY_VOLUME_RATIO_THRESHOLD = BACKTEST_QUALITY_VOLUME_RATIO_THRESHOLD
    BACKTEST_QUALITY_VOLUME_RATIO_SCORE = BACKTEST_QUALITY_VOLUME_RATIO_SCORE
    BACKTEST_QUALITY_TP3_THRESHOLD = BACKTEST_QUALITY_TP3_THRESHOLD
    BACKTEST_QUALITY_TP2_THRESHOLD = BACKTEST_QUALITY_TP2_THRESHOLD
    BACKTEST_QUALITY_TP1_THRESHOLD = BACKTEST_QUALITY_TP1_THRESHOLD
    BACKTEST_QUALITY_MIN_THRESHOLD = BACKTEST_QUALITY_MIN_THRESHOLD
    BACKTEST_QUALITY_OB_DISTANCE_THRESHOLD = BACKTEST_QUALITY_OB_DISTANCE_THRESHOLD
    BACKTEST_QUALITY_OB_AGE_FRESH = BACKTEST_QUALITY_OB_AGE_FRESH
    BACKTEST_QUALITY_OB_MAX_SCORE = BACKTEST_QUALITY_OB_MAX_SCORE
    BACKTEST_QUALITY_IMB_FILL_THRESHOLD = BACKTEST_QUALITY_IMB_FILL_THRESHOLD


config = Config()


# ============================================================================
# VALIDATION
# ============================================================================
def validate_config():
    errors = []

    if not TELEGRAM_BOT_TOKEN:
        errors.append("TELEGRAM_BOT_TOKEN not set in .env")

    # ✅ ИЗМЕНЕНО: Проверяем список пользователей
    if not TELEGRAM_USER_IDS:
        errors.append("TELEGRAM_USER_IDS not set in .env (or TELEGRAM_USER_ID for single user)")

    if TELEGRAM_GROUP_ID == 0:
        errors.append("TELEGRAM_GROUP_ID not set in .env")

    if not DEEPSEEK_API_KEY and not ANTHROPIC_API_KEY:
        errors.append("At least one AI API key required (DEEPSEEK or ANTHROPIC)")

    if errors:
        raise ValueError(
            "Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors)
        )


validate_config()