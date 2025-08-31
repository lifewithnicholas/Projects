#!/usr/bin/env python3
"""
Crypto Volatility Paper-Trading Bot (Reddit-informed)
====================================================

What this does
--------------
- Listens to a subreddit for mentions of crypto **exchanges** (e.g., Binance, Coinbase, Kraken)
  and **tickers** (BTC, ETH, SOL...) in posts/comments.
- Builds a rolling watchlist of (exchange, symbol) pairs from those mentions.
- Pulls market data from the mentioned exchanges using `ccxt` and estimates volatility.
- Runs a simple **volatility/momentum** paper-trading strategy and logs simulated trades.
- Can also run an **offline backtest** for a given (exchange, symbol, timeframe, window).

Key ideas
---------
- *Signal:* realized volatility (stdev of log returns) + short-term momentum vs. moving average.
- *Execution:* market fills at next candle's open (for simplicity) with position sizing based on volatility (lower vol → larger size).
- *Risk:* stop-loss by volatility multiple; take-profit by R-multiple; max 1 position per symbol.

Dependencies
------------
- ccxt        (exchange market data)
- praw        (Reddit API; optional if running in backtest-only mode)
- pandas, numpy, pydantic, pytz

Install:
    pip install ccxt praw pandas numpy pydantic pytz

Environment (for Reddit live mode):
    export REDDIT_CLIENT_ID=...
    export REDDIT_CLIENT_SECRET=...
    export REDDIT_USER_AGENT="volbot/1.0 by <yourname>"

Quick start
-----------
Backtest:
    python bot.py backtest --exchange binance --symbol BTC/USDT --timeframe 5m --days 14

Live (paper):
    python bot.py live --subreddit CryptoCurrency --poll-seconds 60 --timeframe 5m

Notes
-----
- Symbols differ by exchange. Use quote assets that exist (e.g., BTC/USDT on Binance, BTC/USD on Coinbase).
- This is educational code. It is **not** investment advice.
"""
from __future__ import annotations

import os
import re
import time
import math
import json
import queue
import signal
import random
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple, Iterable, Set

import numpy as np
import pandas as pd
from pydantic import BaseModel, Field, validator

try:
    import ccxt  # type: ignore
except Exception as e:
    raise SystemExit("ccxt is required: pip install ccxt")

# --- Optional PRAW import (only needed for live Reddit mode) ---
try:
    import praw  # type: ignore
except Exception:
    praw = None

# ----------------------------- Logging -----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-7s | %(message)s",
)
logger = logging.getLogger("volbot")

# ----------------------------- Utils -------------------------------
EXCHANGE_ALIASES = {
    # canonical_name: [aliases]
    "binance": ["binance", "binanceus", "binnance"],
    "coinbase": ["coinbase", "cb", "coinbasepro", "advanced trade"],
    "kraken": ["kraken"],
    "kucoin": ["kucoin"],
    "bybit": ["bybit"],
    "okx": ["okx", "okex"],
}

DEFAULT_EXCHANGE_CLASS = {
    "binance": ccxt.binance,
    "coinbase": ccxt.coinbase,
    "kraken": ccxt.kraken,
    "kucoin": ccxt.kucoin,
    "bybit": ccxt.bybit,
    "okx": ccxt.okx,
}

TICKER_PATTERN = re.compile(r"\b([A-Z]{2,6})(?:/(USD|USDT|USDC))?\b")

# Common quote assets by exchange
DEFAULT_QUOTES = {
    "binance": "USDT",
    "coinbase": "USD",
    "kraken": "USD",
    "kucoin": "USDT",
    "bybit": "USDT",
    "okx": "USDT",
}

SUPPORTED_TIMEFRAMES = ["1m", "3m", "5m", "15m", "30m", "1h"]

# --------------------------- Config Models -------------------------
class BacktestArgs(BaseModel):
    exchange: str
    symbol: str
    timeframe: str = Field("5m")
    days: int = Field(7, ge=1, le=365)

    @validator("timeframe")
    def _tf(cls, v):
        if v not in SUPPORTED_TIMEFRAMES:
            raise ValueError(f"timeframe must be one of {SUPPORTED_TIMEFRAMES}")
        return v

class LiveArgs(BaseModel):
    subreddit: str = Field("CryptoCurrency")
    poll_seconds: int = Field(60, ge=15, le=600)
    timeframe: str = Field("5m")
    watch_ttl_minutes: int = Field(180, ge=10, le=1440)
    max_pairs: int = Field(20, ge=1, le=200)

    @validator("timeframe")
    def _tf(cls, v):
        if v not in SUPPORTED_TIMEFRAMES:
            raise ValueError(f"timeframe must be one of {SUPPORTED_TIMEFRAMES}")
        return v

# ----------------------- Reddit Watchlist Builder ------------------
@dataclass
class WatchItem:
    exchange: str
    symbol: str  # e.g., "BTC/USDT"
    last_seen: datetime

class RedditWatcher:
    def __init__(self, subreddit: str, ttl_minutes: int = 180, max_pairs: int = 50):
        if praw is None:
            raise RuntimeError("praw is not installed; install it or run in backtest mode")
        client_id = os.getenv("REDDIT_CLIENT_ID")
        client_secret = os.getenv("REDDIT_CLIENT_SECRET")
        user_agent = os.getenv("REDDIT_USER_AGENT", "volbot/1.0")
        if not (client_id and client_secret and user_agent):
            raise RuntimeError("Missing Reddit API env vars: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USER_AGENT")
        self.reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
        )
        self.subreddit_name = subreddit
        self.ttl = timedelta(minutes=ttl_minutes)
        self.max_pairs = max_pairs
        self.watch: Dict[Tuple[str, str], WatchItem] = {}

    @staticmethod
    def _normalize_exchange(text: str) -> Optional[str]:
        low = text.lower()
        for canon, aliases in EXCHANGE_ALIASES.items():
            for a in aliases:
                if a in low:
                    return canon
        return None

    @staticmethod
    def _extract_tickers(text: str) -> Set[str]:
        syms = set()
        for m in TICKER_PATTERN.finditer(text):
            base = m.group(1)
            quote = m.group(2)
            if base in {"USD", "USDT", "USDC"}:  # ignore pure quotes
                continue
            if quote:
                syms.add(f"{base}/{quote}")
            else:
                syms.add(base)
        return syms

    def _to_symbol(self, exchange: str, token_or_pair: str) -> Optional[str]:
        # If already a pair, return if plausible; else add default quote
        if "/" in token_or_pair:
            return token_or_pair
        quote = DEFAULT_QUOTES.get(exchange, "USDT")
        return f"{token_or_pair}/{quote}"

    def _prune(self):
        now = datetime.now(timezone.utc)
        expired = [k for k, v in self.watch.items() if now - v.last_seen > self.ttl]
        for k in expired:
            self.watch.pop(k, None)

    def _cap(self):
        if len(self.watch) <= self.max_pairs:
            return
        # Keep the most recent N
        items = sorted(self.watch.values(), key=lambda w: w.last_seen, reverse=True)[: self.max_pairs]
        self.watch = {(w.exchange, w.symbol): w for w in items}

    def poll_once(self) -> List[WatchItem]:
        self._prune()
        sub = self.reddit.subreddit(self.subreddit_name)
        texts = []
        for s in sub.new(limit=25):
            texts.append(s.title + "\n\n" + (s.selftext or ""))
        for c in sub.comments(limit=100):
            texts.append(c.body)
        now = datetime.now(timezone.utc)
        for t in texts:
            ex = self._normalize_exchange(t)
            if not ex:
                continue
            for tok in self._extract_tickers(t):
                pair = self._to_symbol(ex, tok)
                if not pair:
                    continue
                key = (ex, pair)
                self.watch[key] = WatchItem(exchange=ex, symbol=pair, last_seen=now)
        self._cap()
        return list(self.watch.values())

# --------------------------- Market Data ---------------------------
class MarketData:
    def __init__(self, exchange_name: str):
        exchange_name = exchange_name.lower()
        if exchange_name not in DEFAULT_EXCHANGE_CLASS:
            raise ValueError(f"Unsupported exchange: {exchange_name}")
        self.exchange_name = exchange_name
        self.ex = DEFAULT_EXCHANGE_CLASS[exchange_name]({"enableRateLimit": True})
        self.ex.load_markets()

    def ensure_symbol(self, symbol: str) -> Optional[str]:
        # Try exact, else try to switch quote if needed
        if symbol in self.ex.markets:
            return symbol
        base, quote = symbol.split("/")
        # Try common quotes
        for q in [quote, "USDT", "USD", "USDC", "BUSD"]:
            candidate = f"{base}/{q}"
            if candidate in self.ex.markets:
                return candidate
        return None

    def fetch_ohlcv_df(self, symbol: str, timeframe: str, since_ms: Optional[int] = None, limit: int = 500) -> pd.DataFrame:
        market_symbol = self.ensure_symbol(symbol)
        if not market_symbol:
            raise ValueError(f"Symbol not found on {self.exchange_name}: {symbol}")
        raw = self.ex.fetch_ohlcv(market_symbol, timeframe=timeframe, since=since_ms, limit=limit)
        df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
        df.set_index("timestamp", inplace=True)
        return df

# --------------------------- Strategy ------------------------------
def realized_vol(returns: pd.Series) -> float:
    # annualized realized volatility using sqrt(365*24*60/period_minutes)
    if len(returns) < 2:
        return 0.0
    return float(np.sqrt(returns.var(ddof=1)) * np.sqrt(252*24*60/5))  # assume 5-minute default scaling

@dataclass
class Position:
    side: str  # "long" or "short"
    qty: float
    entry: float
    stop: float
    take: float
    opened_at: datetime

@dataclass
class Trade:
    symbol: str
    exchange: str
    side: str
    entry: float
    exit: float
    pnl: float
    opened_at: datetime
    closed_at: datetime

@dataclass
class Portfolio:
    cash: float = 10000.0
    positions: Dict[str, Position] = field(default_factory=dict)  # key: exchange:symbol
    history: List[Trade] = field(default_factory=list)

    def value(self, prices: Dict[str, float]) -> float:
        v = self.cash
        for key, pos in self.positions.items():
            price = prices.get(key)
            if price is None:
                continue
            sign = 1 if pos.side == "long" else -1
            v += sign * pos.qty * (price - pos.entry)
        return v

# Simple vol+momentum strategy
class VolMomentumStrategy:
    def __init__(self, vol_window: int = 48, ma_window: int = 20, vol_z: float = 1.0, risk_per_trade: float = 0.01,
                 stop_k: float = 2.0, take_k: float = 3.0):
        self.vol_window = vol_window
        self.ma_window = ma_window
        self.vol_z = vol_z
        self.risk_per_trade = risk_per_trade
        self.stop_k = stop_k
        self.take_k = take_k

    def generate_signal(self, df: pd.DataFrame) -> str:
        # compute log returns, rolling vol, moving average, momentum
        closes = df["close"].astype(float)
        rets = np.log(closes).diff()
        vol = rets.rolling(self.vol_window).std()
        vol_z = (vol - vol.rolling(self.vol_window).mean()) / (vol.rolling(self.vol_window).std() + 1e-9)
        ma = closes.rolling(self.ma_window).mean()
        mom = closes.pct_change(self.ma_window)
        if len(closes) < max(self.vol_window * 2, self.ma_window) + 2:
            return "hold"
        if vol_z.iloc[-2] > self.vol_z and mom.iloc[-2] > 0 and closes.iloc[-2] > ma.iloc[-2]:
            return "buy"
        if vol_z.iloc[-2] > self.vol_z and mom.iloc[-2] < 0 and closes.iloc[-2] < ma.iloc[-2]:
            return "sell"
        return "hold"

    def position_size(self, portfolio: Portfolio, price: float, atr_like: float) -> float:
        # Risk sizing: risk_per_trade * equity / (stop distance)
        equity = portfolio.cash
        stop_dist = max(atr_like, price * 0.005)
        dollar_risk = equity * self.risk_per_trade
        qty = dollar_risk / stop_dist
        return max(0.0, qty)

# ------------------------- Backtest Engine -------------------------
class Backtester:
    def __init__(self, md: MarketData, strategy: VolMomentumStrategy):
        self.md = md
        self.strategy = strategy

    def run(self, symbol: str, timeframe: str, days: int = 7) -> Portfolio:
        # Fetch a few extra candles for indicator warmup
        limit = min(2000, int(days * (24*60 / 5) * 1.2) if timeframe == "5m" else 1000)
        df = self.md.fetch_ohlcv_df(symbol, timeframe=timeframe, limit=limit)
        df = df.dropna()
        pf = Portfolio(cash=10000.0)
        key = f"{self.md.exchange_name}:{symbol}"
        rets = np.log(df["close"]).diff()
        atr_like = (df["high"] - df["low"]).rolling(14).mean()

        for i in range(60, len(df)-1):  # iterate candle by candle; next open is fill
            window = df.iloc[: i+1]
            price = window["close"].iloc[-1]
            next_open = df["open"].iloc[i+1]
            sig = self.strategy.generate_signal(window)
            atr = float(atr_like.iloc[i]) if not math.isnan(atr_like.iloc[i]) else price * 0.01
            # Manage existing position
            if key in pf.positions:
                pos = pf.positions[key]
                # Check stop/take at next open
                exit_price = None
                if pos.side == "long":
                    if next_open <= pos.stop or next_open >= pos.take:
                        exit_price = next_open
                else:
                    if next_open >= pos.stop or next_open <= pos.take:
                        exit_price = next_open
                if exit_price is not None:
                    sign = 1 if pos.side == "long" else -1
                    pnl = sign * pos.qty * (exit_price - pos.entry)
                    pf.cash += pnl
                    pf.history.append(Trade(
                        symbol=symbol,
                        exchange=self.md.exchange_name,
                        side=pos.side,
                        entry=pos.entry,
                        exit=exit_price,
                        pnl=pnl,
                        opened_at=pos.opened_at,
                        closed_at=df.index[i+1].to_pydatetime(),
                    ))
                    del pf.positions[key]
            # Entry logic if flat
            if key not in pf.positions and sig in ("buy", "sell"):
                qty = self.strategy.position_size(pf, price, atr)
                if qty <= 0:
                    continue
                side = "long" if sig == "buy" else "short"
                stop = price - self.strategy.stop_k * atr if side == "long" else price + self.strategy.stop_k * atr
                take = price + self.strategy.take_k * atr if side == "long" else price - self.strategy.take_k * atr
                pf.positions[key] = Position(
                    side=side, qty=qty, entry=next_open, stop=stop, take=take, opened_at=df.index[i+1].to_pydatetime()
                )
        return pf

# ---------------------------- Live Loop ----------------------------
class LiveRunner:
    def __init__(self, args: LiveArgs, strategy: VolMomentumStrategy):
        self.args = args
        self.strategy = strategy
        self.watcher = RedditWatcher(args.subreddit, ttl_minutes=args.watch_ttl_minutes, max_pairs=args.max_pairs)
        self.portfolios: Dict[str, Portfolio] = {}
        self.last_prices: Dict[str, float] = {}

    def _get_pf(self, exchange: str) -> Portfolio:
        return self.portfolios.setdefault(exchange, Portfolio(cash=10000.0))

    def step(self):
        items = self.watcher.poll_once()
        logger.info("Watchlist: %s", ", ".join(f"{w.exchange}:{w.symbol}" for w in items) or "<empty>")
        grouped: Dict[str, List[WatchItem]] = {}
        for w in items:
            grouped.setdefault(w.exchange, []).append(w)
        for ex_name, ws in grouped.items():
            md = MarketData(ex_name)
            pf = self._get_pf(ex_name)
            for w in ws:
                try:
                    df = md.fetch_ohlcv_df(w.symbol, timeframe=self.args.timeframe, limit=500)
                except Exception as e:
                    logger.warning("%s:%s fetch error: %s", ex_name, w.symbol, e)
                    continue
                if len(df) < 60:
                    continue
                price = float(df["close"].iloc[-1])
                key = f"{ex_name}:{w.symbol}"
                self.last_prices[key] = price
                sig = self.strategy.generate_signal(df)
                atr_like = float((df["high"] - df["low"]).rolling(14).mean().iloc[-1])
                # Manage existing positions
                if key in pf.positions:
                    pos = pf.positions[key]
                    exit_price = None
                    if pos.side == "long":
                        if price <= pos.stop or price >= pos.take:
                            exit_price = price
                    else:
                        if price >= pos.stop or price <= pos.take:
                            exit_price = price
                    if exit_price is not None:
                        sign = 1 if pos.side == "long" else -1
                        pnl = sign * pos.qty * (exit_price - pos.entry)
                        pf.cash += pnl
                        pf.history.append(Trade(
                            symbol=w.symbol,
                            exchange=ex_name,
                            side=pos.side,
                            entry=pos.entry,
                            exit=exit_price,
                            pnl=pnl,
                            opened_at=pos.opened_at,
                            closed_at=datetime.now(timezone.utc),
                        ))
                        del pf.positions[key]
                # Entry if flat
                if key not in pf.positions and sig in ("buy", "sell"):
                    qty = self.strategy.position_size(pf, price, atr_like)
                    if qty <= 0:
                        continue
                    side = "long" if sig == "buy" else "short"
                    stop = price - self.strategy.stop_k * atr_like if side == "long" else price + self.strategy.stop_k * atr_like
                    take = price + self.strategy.take_k * atr_like if side == "long" else price - self.strategy.take_k * atr_like
                    pf.positions[key] = Position(
                        side=side, qty=qty, entry=price, stop=stop, take=take, opened_at=datetime.now(timezone.utc)
                    )
                    logger.info("%s entry %s %s qty=%.6f @ %.4f (stop=%.4f, take=%.4f)", ex_name, w.symbol, side, qty, price, stop, take)

        # Report PnL snapshot
        total = 0.0
        for ex_name, pf in self.portfolios.items():
            eq = pf.value(self.last_prices)
            total += eq
            logger.info("Equity %s: $%.2f (cash $%.2f, pos %d, trades %d)", ex_name, eq, pf.cash, len(pf.positions), len(pf.history))
        logger.info("Total equity across exchanges: $%.2f", total)

    def run(self):
        logger.info("Starting live runner: subreddit=%s, timeframe=%s", self.args.subreddit, self.args.timeframe)
        try:
            while True:
                self.step()
                time.sleep(self.args.poll_seconds)
        except KeyboardInterrupt:
            logger.info("Interrupted. Finalizing...")

# ------------------------------ CLI --------------------------------
import argparse

def cli():
    parser = argparse.ArgumentParser(description="Reddit-informed crypto volatility paper-trading bot")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_back = sub.add_parser("backtest", help="Run a historical backtest")
    p_back.add_argument("--exchange", required=True, type=str)
    p_back.add_argument("--symbol", required=True, type=str, help="e.g., BTC/USDT")
    p_back.add_argument("--timeframe", default="5m", choices=SUPPORTED_TIMEFRAMES)
    p_back.add_argument("--days", default=7, type=int)

    p_live = sub.add_parser("live", help="Run live Reddit-informed paper trading")
    p_live.add_argument("--subreddit", default="CryptoCurrency")
    p_live.add_argument("--poll-seconds", default=60, type=int)
    p_live.add_argument("--timeframe", default="5m", choices=SUPPORTED_TIMEFRAMES)
    p_live.add_argument("--watch-ttl-minutes", default=180, type=int)
    p_live.add_argument("--max-pairs", default=20, type=int)

    args = parser.parse_args()

    if args.cmd == "backtest":
        bargs = BacktestArgs(exchange=args.exchange.lower(), symbol=args.symbol, timeframe=args.timeframe, days=args.days)
        md = MarketData(bargs.exchange)
        strat = VolMomentumStrategy()
        bt = Backtester(md, strat)
        pf = bt.run(bargs.symbol, bargs.timeframe, days=bargs.days)
        # Print summary
        total_pnl = sum(t.pnl for t in pf.history)
        wins = sum(1 for t in pf.history if t.pnl > 0)
        losses = sum(1 for t in pf.history if t.pnl <= 0)
        winrate = (wins / max(1, wins + losses)) * 100
        print(f"Backtest {bargs.exchange}:{bargs.symbol} {bargs.timeframe} over {bargs.days}d")
        print(f"Trades: {len(pf.history)}, Winrate: {winrate:.1f}%")
        if pf.history:
            avg_win = np.mean([t.pnl for t in pf.history if t.pnl > 0]) if wins else 0.0
            avg_loss = np.mean([t.pnl for t in pf.history if t.pnl <= 0]) if losses else 0.0
            print(f"P&L: ${total_pnl:.2f} | Avg win ${avg_win:.2f} | Avg loss ${avg_loss:.2f}")
        # Export trades
        rows = [t.__dict__ for t in pf.history]
        out = f"trades_{bargs.exchange}_{bargs.symbol.replace('/', '-')}_{bargs.timeframe}.json"
        with open(out, "w") as f:
            json.dump(rows, f, default=str, indent=2)
        print(f"Saved trades to {out}")

    elif args.cmd == "live":
        largs = LiveArgs(
            subreddit=args.subreddit,
            poll_seconds=args.poll_seconds,
            timeframe=args.timeframe,
            watch_ttl_minutes=args.watch_ttl_minutes,
            max_pairs=args.max_pairs,
        )
        strat = VolMomentumStrategy()
        runner = LiveRunner(largs, strat)
        runner.run()

if __name__ == "__main__":
    cli()
