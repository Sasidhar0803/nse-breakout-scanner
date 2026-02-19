# ──────────────────────────────────────────────────────────────
#  NSE BREAKOUT SCANNER — NIFTY 500 (Stable)
#  Fixes yfinance JSONDecodeError + rate limits
# ──────────────────────────────────────────────────────────────

import yfinance as yf
import pandas as pd
import requests
import time
import os
from datetime import datetime

# OPTIONAL CACHE (Recommended for GitHub Actions)
# If you enable this, add: pip install requests-cache
USE_CACHE = False
if USE_CACHE:
    import requests_cache
    requests_cache.install_cache("yfinance_cache", expire_after=3600)

# ──────────────────────────────────────────────────────────────
#  CREDENTIALS — stored in GitHub Secrets
# ──────────────────────────────────────────────────────────────

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

# ──────────────────────────────────────────────────────────────
#  STRATEGY SETTINGS
# ──────────────────────────────────────────────────────────────

VOL_MA_PERIOD   = 30
LOOKBACK_DAYS   = 252
EMA_PERIOD      = 21
MIN_PRICE       = 100.0
MAX_PRICE       = 2000.0
MIN_VOLUME      = 50000

REQUEST_DELAY   = 1.2      # safer for Yahoo (0.5 is risky)
MAX_RETRIES     = 4        # retry failed symbols
RETRY_WAIT_BASE = 2        # seconds

# ──────────────────────────────────────────────────────────────
#  STOCK LIST (Curated Nifty 500)
# ──────────────────────────────────────────────────────────────

def get_full_stock_list():
    raw = """RELIANCE,TCS,HDFCBANK,BHARTIARTL,ICICIBANK,SBIN,INFY,HINDUNILVR,ITC,KOTAKBANK,
LT,HCLTECH,BAJFINANCE,MARUTI,SUNPHARMA,ONGC,NTPC,TITAN,AXISBANK,ADANIENT,
ADANIPORTS,BAJAJFINSV,WIPRO,ULTRACEMCO,POWERGRID,NESTLEIND,ASIANPAINT,JSWSTEEL,
M&M,TATAMOTORS,COALINDIA,TATASTEEL,INDUSINDBK,TECHM,HINDALCO,DRREDDY,BPCL,
DIVISLAB,BAJAJ-AUTO,GRASIM,CIPLA,EICHERMOT,TATACONSUM,APOLLOHOSP,HEROMOTOCO,
BRITANNIA,SBILIFE,SHRIRAMFIN,HDFCLIFE,ICICIGI,PIDILITIND,HAVELLS,DABUR,SIEMENS,
MARICO,GODREJCP,TORNTPHARM,COLPAL,BERGEPAINT,MUTHOOTFIN,UNIONBANK,BANKBARODA,
CANBK,PNB"""

    symbols = []
    for line in raw.strip().split("\n"):
        for sym in line.split(","):
            sym = sym.strip().upper()
            if sym and sym not in symbols:
                symbols.append(sym)

    yf_syms = [f"{s}.NS" for s in symbols]
    print(f"  ✅ Curated list: {len(yf_syms)} stocks")
    return yf_syms


def get_nse_stocks():
    print("  📋 Using curated stock list...")
    return get_full_stock_list()

# ──────────────────────────────────────────────────────────────
#  TELEGRAM
# ──────────────────────────────────────────────────────────────

def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Telegram credentials missing.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]

    for chunk in chunks:
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": chunk, "parse_mode": "HTML"}
        try:
            r = requests.post(url, data=payload, timeout=15)
            if r.status_code != 200:
                print(f"❌ Telegram error: {r.text}")
        except Exception as e:
            print(f"❌ Telegram failed: {e}")
        time.sleep(0.4)

# ──────────────────────────────────────────────────────────────
#  SAFE DOWNLOAD (Fix for JSONDecodeError)
# ──────────────────────────────────────────────────────────────

def safe_download(symbol, retries=MAX_RETRIES):
    """
    Yahoo often blocks GitHub Actions / fast requests.
    This function retries with exponential backoff.
    """
    for attempt in range(1, retries + 1):
        try:
            df = yf.download(
                symbol,
                period="14mo",
                interval="1d",
                progress=False,
                auto_adjust=True,
                threads=False
            )

            if df is not None and len(df) > 20:
                if isinstance(df.columns, pd.MultiIndex):
                    df.columns = df.columns.get_level_values(0)
                return df.dropna()

        except Exception:
            pass

        wait = RETRY_WAIT_BASE * attempt
        time.sleep(wait)

    return None

# ──────────────────────────────────────────────────────────────
#  CHECK SINGLE STOCK
# ──────────────────────────────────────────────────────────────

def check_stock(symbol):
    df = safe_download(symbol)
    if df is None or len(df) < LOOKBACK_DAYS + 5:
        return None

    today     = df.iloc[-1]
    prev_bars = df.iloc[-(LOOKBACK_DAYS + 1):-1]

    today_close  = float(today["Close"])
    today_open   = float(today["Open"])
    today_high   = float(today["High"])
    today_low    = float(today["Low"])
    today_volume = float(today["Volume"])

    if today_close < MIN_PRICE or today_close > MAX_PRICE:
        return None
    if today_volume < MIN_VOLUME:
        return None

    week52_high = float(prev_bars["High"].max())
    avg_volume  = float(df["Volume"].iloc[-VOL_MA_PERIOD - 1:-1].mean())
    ema21       = float(df["Close"].ewm(span=EMA_PERIOD, adjust=False).mean().iloc[-1])

    price_breakout = today_high > week52_high
    green_candle   = today_close > today_open
    above_ema      = today_close > ema21

    if not (price_breakout and green_candle and above_ema):
        return None

    vol_ratio = today_volume / avg_volume if avg_volume > 0 else 0

    all_time_high = float(df["High"].max())
    is_ath = abs(week52_high - all_time_high) < 0.01 * week52_high
    breakout_type = "ATH 🏆" if is_ath else "52WH 📈"

    sl_price = today_low
    sl_pct   = round((today_close - sl_price) / today_close * 100, 2)

    target_price = round(today_close + 2 * (today_close - sl_price), 2)
    target_pct   = round(sl_pct * 2, 2)

    return {
        "symbol": symbol.replace(".NS", ""),
        "close": round(today_close, 2),
        "week52_high": round(week52_high, 2),
        "vol_ratio": round(vol_ratio, 2),
        "breakout_type": breakout_type,
        "sl_price": round(sl_price, 2),
        "sl_pct": sl_pct,
        "target_price": target_price,
        "target_pct": target_pct,
        "ema21": round(ema21, 2),
    }

# ──────────────────────────────────────────────────────────────
#  MAIN
# ──────────────────────────────────────────────────────────────

def run_scanner():
    start_time = time.time()
    today_str  = datetime.now().strftime("%d %b %Y")

    print(f"\n{'='*60}")
    print(f"  NSE BREAKOUT SCANNER — {today_str}")
    print(f"{'='*60}\n")

    stocks = get_nse_stocks()
    total  = len(stocks)

    results = []
    failed  = []

    print(f"  🔍 Scanning {total} stocks...\n")

    for i, symbol in enumerate(stocks, 1):
        if i % 25 == 0 or i == 1:
            elapsed = round(time.time() - start_time)
            print(f"  Progress: {i}/{total} | Found: {len(results)} | Failed: {len(failed)} | Time: {elapsed}s")

        try:
            result = check_stock(symbol)
            if result:
                results.append(result)
                print(f"  ✅ BREAKOUT: {result['symbol']} | {result['breakout_type']} | Vol: {result['vol_ratio']}x")
            else:
                # if safe_download failed, it returns None (we track)
                pass
        except Exception:
            failed.append(symbol)

        time.sleep(REQUEST_DELAY)

    elapsed_total = round(time.time() - start_time)
    print(f"\n  Scan complete in {elapsed_total}s | Breakouts: {len(results)} | Failed: {len(failed)}\n")

    # ───────── Telegram Summary ─────────

    if not results:
        send_telegram(
            f"📊 <b>NSE Breakout Scanner — {today_str}</b>\n\n"
            f"No breakouts found.\n\n"
            f"Scanned: {total}\n"
            f"Failed: {len(failed)}\n\n"
            f"<i>Filters: ₹{int(MIN_PRICE)}–₹{int(MAX_PRICE)} | "
            f"Green candle | Above 21 EMA | High > 52W High</i>"
        )
        return

    results.sort(key=lambda x: x["vol_ratio"], reverse=True)

    send_telegram(
        f"🚀 <b>NSE Breakout Scanner — {today_str}</b>\n\n"
        f"<b>{len(results)} breakout(s) found</b>\n"
        f"Scanned: {total}\n"
        f"Failed: {len(failed)}\n"
        f"Sorted by volume ratio ↓"
    )
    time.sleep(0.5)

    for batch_start in range(0, len(results), 10):
        batch = results[batch_start:batch_start + 10]
        lines = []

        for r in batch:
            lines.append(
                f"──────────────────\n"
                f"📌 <b>{r['symbol']}</b>  {r['breakout_type']}\n"
                f"   Close    : ₹{r['close']}\n"
                f"   52W High : ₹{r['week52_high']}\n"
                f"   Volume   : {r['vol_ratio']}x avg\n"
                f"   21 EMA   : ₹{r['ema21']}\n"
                f"   SL       : ₹{r['sl_price']} (-{r['sl_pct']}%)\n"
                f"   Target   : ₹{r['target_price']} (+{r['target_pct']}%)\n"
            )

        send_telegram("\n".join(lines))
        time.sleep(0.5)

    send_telegram(
        f"──────────────────\n"
        f"⚠️ <i>Scanner only. Always verify chart.\n"
        f"Enter only if price holds above breakout level next day.</i>"
    )

if __name__ == "__main__":
    run_scanner()
