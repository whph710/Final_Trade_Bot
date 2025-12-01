# 🏗️ ARCHITECTURE & SCALING GUIDE

> **Trading Bot - Complete Architecture & Scaling Documentation**
> 
> **Last Updated:** 2025-01-01  
> **Version:** 3.0 - Production Ready

---

## 📋 Table of Contents

1. [System Overview](#system-overview)
2. [Core Architectural Principles](#core-architectural-principles)
3. [Directory Structure & Responsibilities](#directory-structure--responsibilities)
4. [Data Flow Pipeline](#data-flow-pipeline)
5. [Adding New Components - Step by Step](#adding-new-components---step-by-step)
6. [Design Patterns Used](#design-patterns-used)
7. [Critical Rules & Constraints](#critical-rules--constraints)
8. [Testing & Validation](#testing--validation)
9. [Performance Considerations](#performance-considerations)
10. [Common Pitfalls & Solutions](#common-pitfalls--solutions)

---

## System Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         TELEGRAM BOT                            │
│                    (User Interface Layer)                       │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      ORCHESTRATION                              │
│                 (stages/ - Pipeline Logic)                      │
│                                                                 │
│  ┌──────────┐    ┌──────────┐    ┌──────────────┐            │
│  │ Stage 1  │───▶│ Stage 2  │───▶│   Stage 3    │            │
│  │ Filter   │    │AI Select │    │AI Analysis   │            │
│  │ (SMC)    │    │          │    │(Comprehensive)│            │
│  └──────────┘    └──────────┘    └──────────────┘            │
└────────┬────────────────┬────────────────┬─────────────────────┘
         │                │                │
         ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BUSINESS LOGIC LAYER                         │
│                                                                 │
│  ┌──────────────┐  ┌────────────┐  ┌──────────────┐          │
│  │  Indicators  │  │ AI Router  │  │Market Data   │          │
│  │  (Technical) │  │(Multi-LLM) │  │ Collector    │          │
│  └──────────────┘  └────────────┘  └──────────────┘          │
└────────┬────────────────┬────────────────┬─────────────────────┘
         │                │                │
         ▼                ▼                ▼
┌─────────────────────────────────────────────────────────────────┐
│                       DATA LAYER                                │
│                                                                 │
│  ┌──────────────┐  ┌────────────┐  ┌──────────────┐          │
│  │ Bybit Client │  │ Normalizer │  │Signal Storage│          │
│  │  (async)     │  │  (unified) │  │ (JSON/Files) │          │
│  └──────────────┘  └────────────┘  └──────────────┘          │
└─────────────────────────────────────────────────────────────────┘
```

### Tech Stack

```yaml
Language: Python 3.11+
Async Framework: asyncio + aiohttp
AI Providers: DeepSeek (OpenAI SDK), Anthropic Claude
Telegram: aiogram 3.4+
Data Processing: numpy
Storage: JSON files (signals/, logs/)
```

---

## Core Architectural Principles

### 1. **Single Source of Truth: `NormalizedCandles`**

**WHY:** Every data provider returns different formats. We normalize once, use everywhere.

```python
# ✅ CORRECT - All modules consume this
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

**Flow:**
```
Raw Data (Bybit/Binance/etc) → normalize_candles() → NormalizedCandles → indicators/stages
```

**Adding New Data Source:**
```python
# 1. Fetch raw data
raw_data = await fetch_from_new_source()

# 2. MANDATORY: Normalize
candles = normalize_candles(raw_data, symbol, interval)

# 3. Validate
if not candles or not candles.is_valid:
    return None

# 4. Now ALL existing indicators work!
ema_result = analyze_triple_ema(candles)
rsi_result = analyze_rsi(candles)
```

---

### 2. **Separation of Concerns (Strict Layer Isolation)**

```
data_providers/  → ONLY data fetching & normalization
indicators/      → ONLY technical calculations
stages/          → ONLY pipeline orchestration
ai/              → ONLY AI provider interfaces
telegram/        → ONLY user interface
utils/           → ONLY helper functions
```

**❌ FORBIDDEN:**
```python
# indicators/ema.py
async def analyze_ema(candles):
    result = calculate_ema(...)
    await telegram_bot.send_message("EMA signal!")  # ❌ NEVER!
    return result
```

**✅ CORRECT:**
```python
# indicators/ema.py
def analyze_ema(candles: NormalizedCandles) -> EMAAnalysis:
    # Pure calculation
    return EMAAnalysis(...)

# stages/stage1_filter.py
ema_result = analyze_ema(candles)
if ema_result.confidence > 80:
    # Business logic here
    candidates.append(...)
```

---

### 3. **Async for I/O, Sync for Compute**

**RULE:** I/O operations MUST be async. Calculations MUST be sync.

```python
# ✅ I/O = async
async def fetch_candles(symbol: str) -> List:
    async with session.get(url) as response:
        return await response.json()

# ✅ Compute = sync
def calculate_ema(prices: np.ndarray, period: int) -> np.ndarray:
    # CPU-bound math - sync
    return ema_array
```

**Batch Operations:**
```python
# ❌ Sequential (slow)
for symbol in pairs:
    candles = await fetch_candles(symbol)  # N requests

# ✅ Parallel (fast)
tasks = [fetch_candles(sym) for sym in pairs]
results = await asyncio.gather(*tasks)  # 1 batch
```

---

### 4. **Type Safety & Explicit Contracts**

**Every function MUST have:**
- Type hints for ALL parameters
- Return type annotation
- Docstring with Args/Returns

```python
# ✅ TEMPLATE
def analyze_indicator(
    candles: NormalizedCandles,
    period: int = 14,
    threshold: float = 70.0
) -> Optional[IndicatorAnalysis]:
    """
    Brief description
    
    Args:
        candles: Normalized candle data
        period: Calculation period (default: 14)
        threshold: Signal threshold (default: 70.0)
        
    Returns:
        IndicatorAnalysis object or None on error
    """
    if not candles or not candles.is_valid:
        return None
    
    try:
        # Your logic
        return IndicatorAnalysis(...)
    except Exception as e:
        logger.error(f"Indicator error: {e}")
        return None
```

---

### 5. **Dataclasses for Structured Results**

**ALWAYS use `@dataclass` for complex return values.**

```python
# ✅ Type-safe, auto-completion, easy to refactor
@dataclass
class EMAAnalysis:
    ema9_current: float
    ema21_current: float
    ema50_current: float
    alignment: str
    confidence_score: int
    details: str

# ❌ No type safety, error-prone
def analyze_ema(...) -> Dict:
    return {
        'ema9': 42.5,
        'trend': 'UP',
        # Easy to typo, no IDE help
    }
```

---

## Directory Structure & Responsibilities

```
trading_bot/
│
├── config.py                 # ✅ ALL configuration (env vars, constants)
├── main.py                   # ✅ Entry point (telegram or once mode)
│
├── data_providers/           # ✅ Data fetching & normalization ONLY
│   ├── __init__.py
│   ├── bybit_client.py       # Async Bybit API client
│   ├── data_normalizer.py    # normalize_candles() - CRITICAL
│   └── market_data.py        # Funding, OI, Orderbook
│
├── indicators/               # ✅ Pure technical calculations ONLY
│   ├── __init__.py
│   ├── ema.py                # Triple EMA (9/21/50)
│   ├── rsi.py                # RSI indicator
│   ├── macd.py               # MACD
│   ├── volume.py             # Volume analysis
│   ├── atr.py                # ATR & stop-loss
│   ├── correlation.py        # BTC correlation
│   ├── volume_profile.py     # POC, Value Area, HVN/LVN
│   ├── order_blocks.py       # SMC: Order Blocks detection
│   ├── imbalance.py          # SMC: Fair Value Gaps (FVG)
│   └── liquidity_sweep.py    # SMC: Liquidity Sweeps
│
├── stages/                   # ✅ Pipeline orchestration ONLY
│   ├── __init__.py
│   ├── stage1_filter.py      # SMC-based filtering (OB/FVG/Sweeps)
│   ├── stage2_selection.py   # AI pair selection (multi-TF)
│   └── stage3_analysis.py    # AI comprehensive analysis
│
├── ai/                       # ✅ AI provider interfaces ONLY
│   ├── __init__.py
│   ├── deepseek_client.py    # DeepSeek API wrapper
│   ├── anthropic_client.py   # Claude API wrapper
│   ├── ai_router.py          # Multi-provider routing logic
│   └── prompts/
│       ├── prompt_select.txt # Stage 2 selection prompt
│       └── prompt_analyze.txt# Stage 3 analysis prompt
│
├── telegram/                 # ✅ User interface ONLY
│   ├── __init__.py
│   ├── bot_main.py           # Telegram bot (commands, handlers)
│   ├── formatters.py         # Message formatting templates
│   └── scheduler.py          # Scheduling logic
│
├── utils/                    # ✅ Helper functions ONLY
│   ├── __init__.py
│   ├── logger.py             # Logging setup (red console + files)
│   ├── validators.py         # Data validation helpers
│   ├── signal_storage.py     # Save/load signals to JSON
│   └── backtesting.py        # Backtest historical signals
│
├── logs/                     # ✅ Auto-created, gitignored
│   ├── bot_YYYYMMDD.log
│   ├── bot_errors_YYYYMMDD.log
│   └── bot_statistics.json
│
├── signals/                  # ✅ Auto-created, gitignored
│   ├── signal_YYYYMMDD_HHMMSS_SYMBOL.json
│   └── backtest_results/
│       └── backtest_YYYYMMDD_HHMMSS.json
│
├── .env                      # ✅ Secrets (API keys, tokens)
├── requirements.txt          # ✅ Python dependencies
├── ARCHITECTURE.md           # ✅ THIS FILE
└── README.md                 # ✅ User-facing documentation
```

---

## Data Flow Pipeline

### Full Pipeline Flow

```
User triggers analysis (Telegram or scheduled)
    │
    ▼
┌─────────────────────────────────────────────────────────────┐
│ STAGE 1: SMC-Based Filtering (stages/stage1_filter.py)     │
│                                                             │
│ 1. Fetch all trading pairs (~400)                          │
│ 2. Batch load 4H candles (100 bars each)                   │
│ 3. For each pair:                                           │
│    • Detect Order Blocks (find_order_blocks)               │
│    • Detect Imbalances/FVG (find_imbalances)               │
│    • Detect Liquidity Sweeps (detect_liquidity_sweep)      │
│    • Calculate EMA50 (trend context)                        │
│    • Volume + RSI basic filter                             │
│    • Score LONG/SHORT based on SMC patterns                │
│ 4. Return 30-50 candidates (PERFECT/STRONG/MODERATE SMC)   │
│                                                             │
│ Output: List[SignalCandidate] with SMC metadata            │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ STAGE 2: AI Pair Selection (stages/stage2_selection.py)    │
│                                                             │
│ 1. Load 1H + 4H candles for candidates                     │
│ 2. Calculate compact indicators (EMA/RSI/MACD/Volume)      │
│ 3. Prepare SMC data for AI:                                │
│    • OB analysis (nearest OB, direction, distance)         │
│    • Imbalance analysis (FVG count, unfilled)              │
│    • Sweep analysis (detected, direction, confirmed)       │
│ 4. Send to AI (DeepSeek/Claude via ai_router)              │
│ 5. AI selects 3-5 best pairs                               │
│                                                             │
│ Output: List[str] of selected symbols                      │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ STAGE 3: Comprehensive Analysis (stages/stage3_analysis.py)│
│                                                             │
│ For each selected pair:                                    │
│ 1. Load 1H + 4H candles (100 + 60 bars)                    │
│ 2. Load BTC candles for correlation                        │
│ 3. Calculate FULL indicators (30-bar history)              │
│ 4. Gather market data:                                     │
│    • Funding rate                                          │
│    • Open Interest                                         │
│    • Orderbook spread                                      │
│ 5. Calculate correlation with BTC                          │
│ 6. Calculate Volume Profile (POC, Value Area)              │
│ 7. Re-detect SMC patterns on current timeframes:           │
│    • Order Blocks (50-bar lookback)                        │
│    • Imbalances (50-bar lookback)                          │
│    • Liquidity Sweeps (20-bar lookback)                    │
│ 8. Package comprehensive_data                              │
│ 9. Send to AI for final decision:                          │
│    • Entry, Stop Loss, Take Profit levels                  │
│    • Confidence score                                      │
│    • Detailed analysis text                                │
│                                                             │
│ Output: List[TradingSignal] approved signals               │
└─────────────────────┬───────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────┐
│ POST-PROCESSING                                             │
│                                                             │
│ • Save approved signals → signals/signal_*.json             │
│ • Send to Telegram group (formatted messages)              │
│ • Send rejected signals to user (private messages)         │
│ • Update statistics → logs/bot_statistics.json             │
└─────────────────────────────────────────────────────────────┘
```

---

## Adding New Components - Step by Step

### ✅ Adding a New Indicator

**Example: Adding Bollinger Bands**

#### Step 1: Create indicator file

```python
# indicators/bollinger_bands.py
"""
Bollinger Bands Indicator
Файл: indicators/bollinger_bands.py
"""

import numpy as np
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class BollingerAnalysis:
    """Bollinger Bands analysis result"""
    upper_band: float
    middle_band: float
    lower_band: float
    position: str  # 'ABOVE_UPPER' | 'IN_MIDDLE' | 'BELOW_LOWER'
    bandwidth_pct: float
    confidence_adjustment: int
    details: str


def calculate_bollinger_bands(
    prices: np.ndarray,
    period: int = 20,
    std_dev: float = 2.0
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Calculate Bollinger Bands
    
    Args:
        prices: Price array
        period: SMA period (default: 20)
        std_dev: Standard deviation multiplier (default: 2.0)
        
    Returns:
        (upper_band, middle_band, lower_band) arrays
    """
    if len(prices) < period:
        zero = np.zeros_like(prices)
        return zero, zero, zero
    
    try:
        # SMA as middle band
        middle_band = np.convolve(
            prices, 
            np.ones(period) / period, 
            mode='same'
        )
        
        # Rolling std
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
    candles: 'NormalizedCandles',
    period: int = 20,
    std_dev: float = 2.0
) -> Optional[BollingerAnalysis]:
    """
    Analyze Bollinger Bands
    
    Args:
        candles: NormalizedCandles object
        period: SMA period
        std_dev: Standard deviation multiplier
        
    Returns:
        BollingerAnalysis or None on error
    """
    # ✅ MANDATORY: Validate input
    if not candles or not candles.is_valid:
        return None
    
    if len(candles.closes) < period + 10:
        return None
    
    try:
        # Calculate bands
        upper, middle, lower = calculate_bollinger_bands(
            candles.closes, period, std_dev
        )
        
        current_price = float(candles.closes[-1])
        current_upper = float(upper[-1])
        current_middle = float(middle[-1])
        current_lower = float(lower[-1])
        
        # ✅ MANDATORY: NaN/Inf check
        if any(np.isnan(v) or np.isinf(v) for v in [
            current_upper, current_middle, current_lower
        ]):
            return None
        
        # Determine position
        if current_price > current_upper:
            position = 'ABOVE_UPPER'
            adjustment = -10  # Overbought
        elif current_price < current_lower:
            position = 'BELOW_LOWER'
            adjustment = -10  # Oversold
        else:
            position = 'IN_MIDDLE'
            adjustment = 0
        
        bandwidth_pct = ((current_upper - current_lower) / current_middle) * 100
        
        # Narrow bands = potential breakout
        if bandwidth_pct < 5.0:
            adjustment += 8
        
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
```

#### Step 2: Export from package

```python
# indicators/__init__.py

from .bollinger_bands import (
    calculate_bollinger_bands,
    analyze_bollinger_bands,
    BollingerAnalysis
)

__all__ = [
    # ... existing exports
    'calculate_bollinger_bands',
    'analyze_bollinger_bands',
    'BollingerAnalysis',
]
```

#### Step 3: Use in stages

```python
# stages/stage3_analysis.py

from indicators import analyze_bollinger_bands

# In _calculate_full_indicators()
bb_result = analyze_bollinger_bands(candles, period=20)

if bb_result:
    indicators['bollinger'] = {
        'position': bb_result.position,
        'bandwidth': bb_result.bandwidth_pct
    }
```

#### Step 4: Checklist

- [x] Consumes `NormalizedCandles`
- [x] Returns `@dataclass` or `Optional[dataclass]`
- [x] Type hints everywhere
- [x] Docstrings with Args/Returns
- [x] NaN/Inf validation
- [x] Try-except with logging
- [x] Exported via `__init__.py`
- [x] No external dependencies (stays in module)

---

### ✅ Adding a New Data Provider

**Example: Adding Binance as data source**

#### Step 1: Create client module

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
    Fetch candles from Binance
    
    Args:
        symbol: Trading pair (e.g., 'BTCUSDT')
        interval: Timeframe ('1h', '4h', '1d')
        limit: Number of candles
        
    Returns:
        Raw Binance klines data
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

#### Step 2: Use with normalizer

```python
# Usage anywhere
from data_providers import normalize_candles
from data_providers.binance_client import fetch_candles_binance

# 1. Fetch raw data
raw_candles = await fetch_candles_binance('BTCUSDT', '1h', 100)

# 2. ✅ MANDATORY: Normalize to unified format
candles = normalize_candles(
    raw_candles,
    symbol='BTCUSDT',
    interval='1h'
)

# 3. Now ALL existing indicators work!
if candles and candles.is_valid:
    ema_result = analyze_triple_ema(candles)
    rsi_result = analyze_rsi(candles)
    # ... all other indicators
```

#### Step 3: Checklist

- [x] Async function (I/O operation)
- [x] Returns raw data (List[List] format)
- [x] Error handling (try-except)
- [x] Logging on errors
- [x] **MUST** be normalized via `normalize_candles()` before use
- [x] No direct usage without normalization

---

### ✅ Adding a New AI Provider

**Example: Adding Google Gemini**

#### Step 1: Create AI client

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
    """Client for Google Gemini API"""
    
    def __init__(self, api_key: str, model: str = "gemini-pro"):
        self.api_key = api_key
        self.model = model
        logger.info(f"Gemini client initialized: {model}")
    
    async def select_pairs(
        self,
        pairs_data: List[Dict],
        max_pairs: Optional[int] = None,
        temperature: float = 0.3,
        max_tokens: int = 2000
    ) -> List[str]:
        """
        Stage 2: Pair selection via Gemini
        
        ⚠️ CRITICAL: MUST have same signature as DeepSeek/Claude!
        
        Args:
            pairs_data: Candidate pairs with indicators
            max_pairs: Maximum pairs to select
            temperature: Temperature
            max_tokens: Max tokens
            
        Returns:
            List of selected symbols
        """
        # Your Gemini API logic
        pass
    
    async def analyze_comprehensive(
        self,
        symbol: str,
        comprehensive_data: Dict,
        temperature: float = 0.7,
        max_tokens: int = 4000
    ) -> Dict:
        """
        Stage 3: Comprehensive analysis via Gemini
        
        ⚠️ CRITICAL: MUST have same signature as DeepSeek/Claude!
        
        Args:
            symbol: Trading pair
            comprehensive_data: Full analysis data
            temperature: Temperature
            max_tokens: Max tokens
            
        Returns:
            Analysis result dict with signal/confidence/levels
        """
        # Your Gemini API logic
        pass
```

#### Step 2: Register in AI Router

```python
# ai/ai_router.py

class AIRouter:
    async def _get_gemini_client(self) -> Optional['GeminiClient']:
        """Get Gemini client instance"""
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
        
        if provider == 'gemini':  # ✅ Add new provider
            client = await self._get_gemini_client()
            return 'gemini', client
        
        # ... existing providers (deepseek, claude)
```

#### Step 3: Add config

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

#### Step 4: Checklist

- [x] **SAME** method signatures as existing providers
- [x] `select_pairs()` for Stage 2
- [x] `analyze_comprehensive()` for Stage 3
- [x] Returns SAME format (List[str] and Dict respectively)
- [x] Registered in `ai_router.py`
- [x] Config in `config.py` and `.env`
- [x] Easy switching via `STAGE2_PROVIDER`/`STAGE3_PROVIDER`

---

### ✅ Adding a New Telegram Command

**Example: Adding `/status` command**

#### Step 1: Add handler in bot_main.py

```python
# telegram/bot_main.py

class TradingBotTelegram:
    def _register_handlers(self):
        # ... existing handlers
        
        # ✅ New command
        self.dp.message.register(
            self.show_system_status,
            F.text == "📊 System Status"
        )
    
    async def show_system_status(self, message: Message):
        """Show detailed system status"""
        user_id = message.from_user.id
        
        if user_id != self.user_id:
            return
        
        try:
            # Gather system info
            from config import config
            import psutil  # If you want process stats
            
            status_text = [
                "📊 <b>SYSTEM STATUS</b>",
                "━━━━━━━━━━━━━━━━━━━━━━\n",
                f"<b>⏰ Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                f"<b>👤 User ID:</b> {self.user_id}",
                f"<b>👥 Group ID:</b> {self.group_id}",
                f"\n<b>🤖 AI Providers:</b>",
                f"  • Stage 2: {config.STAGE2_PROVIDER.upper()}",
                f"  • Stage 3: {config.STAGE3_PROVIDER.upper()}",
                f"\n<b>📁 Storage:</b>",
                f"  • Signals: {len(list(config.SIGNALS_DIR.glob('signal_*.json')))}",
                f"  • Logs: {len(list(config.LOGS_DIR.glob('*.log')))}"
            ]
            
            await message.answer("\n".join(status_text), parse_mode="HTML")
            
        except Exception as e:
            logger.exception("Error in system status")
            await message.answer(
                f"❌ <b>Error:</b> {str(e)[:200]}",
                parse_mode="HTML"
            )
```

#### Step 2: Add keyboard button (if needed)

```python# 
telegram/bot_main.py

async def start_command(self, message: Message):
    """Handler for /start"""
    keyboard = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="▶️ Запустить сейчас")],
            [KeyboardButton(text="🔍 Анализ пары")],
            [
                KeyboardButton(text="📊 Статус"),
                KeyboardButton(text="📈 Статистика")
            ],
            [KeyboardButton(text="📊 System Status")],  # ✅ New button
            [KeyboardButton(text="🛑 Остановить")]
        ],
        resize_keyboard=True
    )
    # ...
```

#### Step 3: Checklist

- [x] Handler registered in `_register_handlers()`
- [x] User ID validation (security)
- [x] Error handling (try-except)
- [x] Logging on errors
- [x] HTML formatting for Telegram
- [x] Optional keyboard button

---

### ✅ Adding a New Stage

**Example: Adding Stage 4 - Risk Management**

#### Step 1: Create stage module

```python
# stages/stage4_risk_check.py
"""
Stage 4: Risk Management Check
Файл: stages/stage4_risk_check.py
"""

import logging
from typing import List, Dict
from datetime import datetime

logger = logging.getLogger(__name__)


async def run_stage4(
    signals: List['TradingSignal']
) -> tuple[List['TradingSignal'], List[Dict]]:
    """
    Stage 4: Final risk checks
    
    Args:
        signals: Approved signals from Stage 3
        
    Returns:
        (approved, rejected) - Final signals and rejects
    """
    logger.info(f"Stage 4: Risk check for {len(signals)} signals")
    
    approved = []
    rejected = []
    
    for signal in signals:
        try:
            # Check 1: R/R ratio minimum
            if signal.risk_reward_ratio < 2.0:
                rejected.append({
                    'symbol': signal.symbol,
                    'signal': signal.signal,
                    'rejection_reason': f'Low R/R: {signal.risk_reward_ratio:.2f} < 2.0'
                })
                logger.info(f"Stage 4: {signal.symbol} rejected - low R/R")
                continue
            
            # Check 2: Stop loss not > 5%
            risk_pct = abs((signal.entry_price - signal.stop_loss) / signal.entry_price * 100)
            if risk_pct > 5.0:
                rejected.append({
                    'symbol': signal.symbol,
                    'signal': signal.signal,
                    'rejection_reason': f'Risk too high: {risk_pct:.2f}% > 5%'
                })
                logger.info(f"Stage 4: {signal.symbol} rejected - high risk")
                continue
            
            # Check 3: Trading hours (8-22)
            hour = datetime.now().hour
            if hour < 8 or hour > 22:
                rejected.append({
                    'symbol': signal.symbol,
                    'signal': signal.signal,
                    'rejection_reason': f'Outside trading hours: {hour}:00'
                })
                logger.info(f"Stage 4: {signal.symbol} rejected - off hours")
                continue
            
            # Approved
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

#### Step 2: Export from package

```python
# stages/__init__.py

from .stage4_risk_check import run_stage4

__all__ = [
    # ... existing
    'run_stage4',
]
```

#### Step 3: Integrate in pipeline

```python
# telegram/bot_main.py or scheduler callback

# ... existing Stage 1, 2, 3

approved_signals, rejected_stage3 = await run_stage3(selected_pairs)

if approved_signals:
    # ✅ Add Stage 4
    final_approved, rejected_stage4 = await run_stage4(approved_signals)
    
    # Merge rejected
    all_rejected = rejected_stage3 + rejected_stage4
    
    logger.info(
        f"Pipeline complete: {len(final_approved)} final signals, "
        f"{len(all_rejected)} total rejected"
    )
    
    # Send final signals
    if final_approved:
        self.signal_storage.save_signals_batch(final_approved)
        await self._send_signals_to_group(final_approved)
```

#### Step 4: Checklist

- [x] Async function (consistent with other stages)
- [x] Clear input/output types
- [x] Detailed logging (INFO for decisions, ERROR for failures)
- [x] Returns tuple (approved, rejected)
- [x] Exported via `__init__.py`
- [x] Easy to enable/disable (just comment out in pipeline)

---

## Design Patterns Used

### 1. **Dependency Injection (via Parameters)**

```python
# ❌ Hard dependency
class Stage3:
    def __init__(self):
        self.ai_client = DeepSeekClient(api_key="...")  # Tight coupling

# ✅ Dependency Injection
class AIRouter:
    async def _get_deepseek_client(self) -> DeepSeekClient:
        # Client created on-demand
        from config import config
        return DeepSeekClient(api_key=config.DEEPSEEK_API_KEY)
    
# Usage in stages - no direct dependency
ai_router = AIRouter()
result = await ai_router.analyze_pair_comprehensive(symbol, data)
```

### 2. **Factory Pattern (Data Normalization)**

```python
# Factory function: normalize_candles()
def normalize_candles(
    raw_candles: List,
    symbol: str,
    interval: str
) -> Optional[NormalizedCandles]:
    """
    Factory: Convert ANY raw format → NormalizedCandles
    """
    # Validation + transformation
    return NormalizedCandles(...)

# Usage
bybit_candles = await fetch_candles_bybit(...)
binance_candles = await fetch_candles_binance(...)

# Both return NormalizedCandles - same interface
norm_bybit = normalize_candles(bybit_candles, ...)
norm_binance = normalize_candles(binance_candles, ...)
```

### 3. **Strategy Pattern (AI Providers)**

```python
# AIRouter implements Strategy pattern
class AIRouter:
    async def _get_provider_client(self, stage: str):
        provider = self.stage_providers[stage]
        
        # Different strategy based on config
        if provider == 'deepseek':
            return await self._get_deepseek_client()
        elif provider == 'claude':
            return await self._get_claude_client()
        # ... extensible for new providers
```

### 4. **Singleton Pattern (Storage Managers)**

```python
# utils/signal_storage.py
_signal_storage = None

def get_signal_storage() -> SignalStorage:
    """Singleton instance"""
    global _signal_storage
    if _signal_storage is None:
        _signal_storage = SignalStorage()
    return _signal_storage
```

### 5. **Pipeline Pattern (Stages)**

```python
# Each stage is a transformation step
data → Stage1 → candidates → Stage2 → selected → Stage3 → signals

# Stages are composable and independent
async def run_full_pipeline():
    pairs = await get_all_pairs()
    
    candidates = await run_stage1(pairs)
    if not candidates:
        return
    
    selected = await run_stage2(candidates)
    if not selected:
        return
    
    signals = await run_stage3(selected)
    return signals
```

---

## Critical Rules & Constraints

### 🔴 NEVER DO THIS

```python
# ❌ 1. Circular imports
# indicators/ema.py
from stages.stage1_filter import determine_direction  # FORBIDDEN

# ❌ 2. Mixing sync and async
def blocking_request(url):
    response = requests.get(url)  # Blocks event loop!
    return response.json()

# ❌ 3. Mutating input data
def process_prices(prices: np.ndarray):
    prices[prices < 0] = 0  # Mutates original!
    return prices

# ❌ 4. Hardcoded values
def analyze_signal(candles):
    if confidence > 70:  # Magic number
        return 'STRONG'

# ❌ 5. No type hints
def calculate_something(data, period):  # What types?
    return result

# ❌ 6. Ignoring Optional
result = analyze_indicator(candles)
confidence = result.confidence  # May be None!

# ❌ 7. Global state
current_signals = []  # Global mutable state

def add_signal(signal):
    current_signals.append(signal)  # Dangerous
```

### ✅ ALWAYS DO THIS

```python
# ✅ 1. Respect layer boundaries
# indicators/ema.py - stays in own module
def analyze_ema(candles: NormalizedCandles) -> EMAAnalysis:
    return EMAAnalysis(...)

# stages/stage1_filter.py - uses indicators
from indicators import analyze_ema
ema_result = analyze_ema(candles)

# ✅ 2. Async for I/O
async def fetch_data(url):
    async with session.get(url) as response:
        return await response.json()

# ✅ 3. Copy before mutating
def process_prices(prices: np.ndarray) -> np.ndarray:
    result = prices.copy()
    result[result < 0] = 0
    return result

# ✅ 4. Config from config.py
from config import config

def analyze_signal(candles):
    if confidence > config.MIN_CONFIDENCE:
        return 'STRONG'

# ✅ 5. Type hints everywhere
def calculate_ema(
    prices: np.ndarray,
    period: int
) -> np.ndarray:
    return ema_array

# ✅ 6. Handle Optional
result = analyze_indicator(candles)
if result is None:
    logger.warning("Analysis failed")
    return

confidence = result.confidence  # Safe now

# ✅ 7. Explicit state management
async def run_stage3(selected_pairs: List[str]) -> List[TradingSignal]:
    signals = []  # Local state
    
    for symbol in selected_pairs:
        signal = await analyze(symbol)
        if signal:
            signals.append(signal)
    
    return signals  # Explicit return
```

---

## Testing & Validation

### Manual Testing Checklist

```bash
# 1. Test single run
python main.py once

# 2. Test manual pair analysis (Telegram)
/start → 🔍 Анализ пары → BTCUSDT → LONG

# 3. Test backtest
/start → 📊 Backtest

# 4. Check logs
ls logs/
cat logs/bot_$(date +%Y%m%d).log

# 5. Check signals
ls signals/
cat signals/signal_*.json | head -n 50

# 6. Test with different AI providers
# .env
STAGE2_PROVIDER=deepseek
STAGE3_PROVIDER=claude
```

### Validation Functions

```python
# Use validators from utils/
from utils import (
    validate_candles,
    safe_float,
    validate_rr_ratio,
    validate_prices_in_range
)

# Example
if not validate_candles(raw_candles, min_length=50):
    logger.error("Invalid candles")
    return None

# Safe conversions
price = safe_float(data.get('price'), default=0.0)

# R/R validation
if not validate_rr_ratio(entry, stop, tp1, min_rr=1.5):
    logger.warning("R/R too low")
    return None
```

---

## Performance Considerations

### 1. **Batch Operations**

```python
# ❌ Sequential (slow)
for symbol in pairs:
    candles = await fetch_candles(symbol)

# ✅ Parallel (fast)
tasks = [fetch_candles(sym) for sym in pairs]
results = await asyncio.gather(*tasks)

# ✅ Even better: fetch_multiple_candles with semaphore
requests = [{'symbol': s, 'interval': '60', 'limit': 100} for s in pairs]
results = await fetch_multiple_candles(requests)
```

### 2. **Semaphore for Rate Limiting**

```python
# data_providers/bybit_client.py
_semaphore = asyncio.Semaphore(50)  # Max 50 concurrent

async def fetch_candles(symbol: str) -> List:
    async with _semaphore:
        # Rate-limited request
        return await _fetch(symbol)
```

### 3. **Caching Strategies**

```python
# Prompt caching (already implemented)
_prompt_cache: Dict[str, str] = {}

def load_prompt_cached(filename: str) -> str:
    if filename in _prompt_cache:
        return _prompt_cache[filename]
    
    content = Path(filename).read_text()
    _prompt_cache[filename] = content
    return content
```

### 4. **Memory Management**

```python
# Use numpy views, not copies (when safe)
recent_prices = prices[-100:]  # View, not copy

# Only copy when mutating
def normalize_prices(prices: np.ndarray) -> np.ndarray:
    result = prices.copy()  # Now safe to mutate
    result[result < 0] = 0
    return result
```

---

## Common Pitfalls & Solutions

### Pitfall 1: Forgetting to validate `is_valid`

```python
# ❌ Missing validation
candles = normalize_candles(raw_data, symbol, interval)
ema = calculate_ema(candles.closes, 21)  # May crash!

# ✅ Always validate
candles = normalize_candles(raw_data, symbol, interval)
if not candles or not candles.is_valid:
    logger.warning(f"{symbol} - invalid candles")
    return None

ema = calculate_ema(candles.closes, 21)  # Safe
```

### Pitfall 2: NaN/Inf in calculations

```python
# ✅ Always check after calculations
def calculate_indicator(candles):
    result = some_math(candles.closes)
    
    # CRITICAL: Check for NaN/Inf
    if np.isnan(result) or np.isinf(result):
        logger.warning("NaN/Inf detected")
        return None
    
    return float(result)
```

### Pitfall 3: Incorrect take_profit_levels handling

```python
# ❌ Assuming length
tp1 = signal.take_profit_levels[0]  # May crash if empty

# ✅ Safe access
tp_levels = signal.take_profit_levels
if len(tp_levels) < 3:
    tp_levels = tp_levels + [0] * (3 - len(tp_levels))

tp1, tp2, tp3 = tp_levels[0], tp_levels[1], tp_levels[2]
```

### Pitfall 4: Session cleanup

```python
# ✅ Always cleanup sessions
from data_providers import cleanup_session

try:
    # Your async operations
    result = await some_operation()
finally:
    # CRITICAL: Close aiohttp session
    await cleanup_session()
```

### Pitfall 5: Timezone issues

```python
# ✅ Use timezone-aware datetime
from datetime import datetime
import pytz

# Correct
perm_tz = pytz.timezone('Asia/Yekaterinburg')
now = datetime.now(perm_tz)

# Incorrect
now = datetime.now()  # Naive datetime
```

---

## Final Checklist for ANY New Feature

```markdown
## Pre-Implementation
- [ ] Feature aligns with existing architecture layers
- [ ] No circular dependencies introduced
- [ ] Async/sync correctly chosen (I/O vs compute)

## Implementation
- [ ] Type hints on ALL parameters and return
- [ ] Docstring with Args/Returns
- [ ] Uses `NormalizedCandles` if working with candle data
- [ ] Returns `Optional[T]` or `@dataclass`
- [ ] Try-except with logging
- [ ] Early validation, early return
- [ ] NaN/Inf checks for numerical results
- [ ] Config values from `config.py`, not hardcoded

## Integration
- [ ] Exported via `__init__.py`
- [ ] No global mutable state
- [ ] Doesn't mutate input data
- [ ] Session cleanup if creating new async clients

## Testing
- [ ] Tested with `python main.py once`
- [ ] Tested via Telegram commands
- [ ] Checked logs in `logs/`
- [ ] Verified output format matches expected

## Documentation
- [ ] Updated ARCHITECTURE.md if changing patterns
- [ ] Updated README.md if user-facing
- [ ] Added example usage in docstring
```

---

## 🎯 Quick Reference

### Key Files to Remember

```
config.py              → ALL configuration (API keys, thresholds)
data_providers/        → Data fetching + normalize_candles()
indicators/            → Pure technical calculations
stages/                → Pipeline orchestration (3-4 stages)
ai/ai_router.py        → Multi-provider AI routing
telegram/bot_main.py   → User commands & handlers
utils/signal_storage.py→ Save/load signals for backtest
```

### Most Important Functions

```python
# Data
normalize_candles(raw, symbol, interval) → NormalizedCandles
fetch_multiple_candles(requests) → batch results

# Indicators (ALL use NormalizedCandles)
analyze_triple_ema(candles) → EMAAnalysis
analyze_order_blocks(candles, price, direction) → OrderBlockAnalysis
analyze_imbalances(candles, price, direction) → ImbalanceAnalysis

# Stages
await run_stage1(pairs) → List[SignalCandidate]
await run_stage2(candidates) → List[str]
await run_stage3(selected_pairs) → (approved, rejected)

# AI
ai_router.select_pairs(pairs_data, max_pairs) → List[str]
ai_router.analyze_pair_comprehensive(symbol, data) → Dict

# Storage
signal_storage.save_signal(signal) → Path
signal_storage.load_signals() → List[Dict]
```

### Common Patterns

```python
# Pattern 1: Adding indicator
def analyze_my_indicator(candles: NormalizedCandles) -> Optional[MyAnalysis]:
    if not candles or not candles.is_valid:
        return None
    
    try:
        result = calculate(candles.closes)
        return MyAnalysis(...)
    except Exception as e:
        logger.error(f"Error: {e}")
        return None

# Pattern 2: Batch async operation
requests = [{'symbol': s, 'interval': i} for s in symbols]
results = await fetch_multiple_candles(requests)

# Pattern 3: Safe result handling
result = analyze_something(candles)
if result is None:
    logger.warning("Analysis failed")
    return

# Use result safely
confidence = result.confidence
```

---

## 📚 Related Documentation

- `README.md` - User-facing setup & usage guide
- `config.py` - All configuration variables with comments
- `indicators/*.py` - Each indicator has detailed docstrings
- `ai/prompts/*.txt` - AI prompts for Stage 2/3

---

**Remember:**
1. **Every new component must respect layer boundaries**
2. **Always use `NormalizedCandles` for candle data**
3. **Type hints, docstrings, error handling are MANDATORY**
4. **Test incrementally - don't break existing functionality**
5. **When in doubt, look at existing similar components**

**Last Updated:** 2025-01-01  
**Maintained By:** @your_name  
**Questions?** Open an issue or refer to this document first.