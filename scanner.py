import pandas as pd
import requests
import os
import time
from datetime import datetime, timedelta
from io import BytesIO
import zipfile

# ──────────────────────────────────────────────────────────────
# TELEGRAM (GitHub Secrets)
# ──────────────────────────────────────────────────────────────

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

# ──────────────────────────────────────────────────────────────
# SETTINGS
# ──────────────────────────────────────────────────────────────

LOOKBACK_DAYS = 252
EMA_PERIOD    = 21

MIN_PRICE     = 100.0
MAX_PRICE     = 2000.0
MIN_VOLUME    = 50000

DATA_DIR      = "data"
HISTORY_FILE  = os.path.join(DATA_DIR, "history.csv")

# ──────────────────────────────────────────────────────────────
# NSE BHAVCOPY DOWNLOAD
# ──────────────────────────────────────────────────────────────

def nse_bhavcopy_url(date_obj):
    """
    NSE Bhavcopy (Equities) ZIP
    Example:
    https://archives.nseindia.com/content/historical/EQUITIES/2025/FEB/cm18FEB2025bhav.csv.zip
    """
    dd  = date_obj.strftime("%d")
    mon = date_obj.strftime("%b").upper()
    yyyy = date_obj.strftime("%Y")

    return f"https://archives.nseindia.com/content/historical/EQUITIES/{yyyy}/{mon}/cm{dd}{mon}{yyyy}bhav.csv.zip"


def download_bhavcopy(date_obj):
    url = nse_bhavcopy_url(date_obj)
    print(f"📥 Downloading Bhavcopy: {url}")

    headers = {
        "User-Agent": "Mozilla/5.0",
        "Accept": "*/*",
        "Connection": "keep-alive"
    }

    r = requests.get(url, headers=headers, timeout=30)
    if r.status_code != 200:
        return None

    try:
        z = zipfile.ZipFile(BytesIO(r.content))
        name = z.namelist()[0]
        df = pd.read_csv(z.open(name))
        return df
    except Exception:
        return None


def get_latest_bhavcopy(max_back_days=10):
    """
    If today's file not available (holiday/weekend),
    it tries previous days up to max_back_days.
    """
    for i in range(max_back_days):
        d = datetime.now() - timedelta(days=i)
        df = download_bhavcopy(d)
        if df is not None and len(df) > 0:
            print(f"✅ Bhavcopy loaded for date: {d.strftime('%d %b %Y')}")
            return df, d
        time.sleep(1)

    return None, None

# ──────────────────────────────────────────────────────────────
# TELEGRAM
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
            r = requests.post(url, data=payload, timeout=20)
            if r.status_code != 200:
                print("❌ Telegram error:", r.text)
        except Exception as e:
            print("❌ Telegram failed:", e)
        time.sleep(0.5)

# ──────────────────────────────────────────────────────────────
# HISTORY STORAGE
# ──────────────────────────────────────────────────────────────

def normalize_bhavcopy(df, date_obj):
    """
    Bhavcopy columns typically:
    SYMBOL, SERIES, OPEN, HIGH, LOW, CLOSE, LAST, PREVCLOSE,
    TOTTRDQTY, TOTTRDVAL, TIMESTAMP, TOTALTRADES, ISIN
    """
    df = df.copy()

    df.columns = [c.strip().upper() for c in df.columns]

    # Keep only EQ series
    if "SERIES" in df.columns:
        df = df[df["SERIES"] == "EQ"]

    df["DATE"] = date_obj.strftime("%Y-%m-%d")

    out = df[["DATE", "SYMBOL", "OPEN", "HIGH", "LOW", "CLOSE", "TOTTRDQTY"]].copy()
    out.rename(columns={"TOTTRDQTY": "VOLUME"}, inplace=True)

    # Ensure numeric
    for col in ["OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"]:
        out[col] = pd.to_numeric(out[col], errors="coerce")

    out = out.dropna()
    out["SYMBOL"] = out["SYMBOL"].astype(str).str.strip().str.upper()

    return out


def load_history():
    if not os.path.exists(HISTORY_FILE):
        return pd.DataFrame(columns=["DATE", "SYMBOL", "OPEN", "HIGH", "LOW", "CLOSE", "VOLUME"])

    df = pd.read_csv(HISTORY_FILE)
    df["DATE"] = pd.to_datetime(df["DATE"])
    return df


def save_history(df):
    os.makedirs(DATA_DIR, exist_ok=True)
    df2 = df.copy()
    df2["DATE"] = pd.to_datetime(df2["DATE"]).dt.strftime("%Y-%m-%d")
    df2.to_csv(HISTORY_FILE, index=False)


def update_history(history, today_df):
    """
    Adds today's bhavcopy rows into history and removes duplicates.
    """
    today_df = today_df.copy()
    today_df["DATE"] = pd.to_datetime(today_df["DATE"])

    history = history.copy()
    history["DATE"] = pd.to_datetime(history["DATE"])

    combined = pd.concat([history, today_df], ignore_index=True)
    combined.drop_duplicates(subset=["DATE", "SYMBOL"], keep="last", inplace=True)

    combined.sort_values(["SYMBOL", "DATE"], inplace=True)
    return combined

# ──────────────────────────────────────────────────────────────
# INDICATORS
# ──────────────────────────────────────────────────────────────

def compute_ema(series, span):
    return series.ewm(span=span, adjust=False).mean()


def scan_breakouts(history, scan_date_str):
    """
    For each symbol:
    - Use last LOOKBACK_DAYS bars before today to compute 52WH
    - Use full bars to compute EMA21
    """
    results = []

    scan_date = pd.to_datetime(scan_date_str)

    # Only symbols that have today's data
    today_rows = history[history["DATE"] == scan_date]
    symbols_today = today_rows["SYMBOL"].unique().tolist()

    for sym in symbols_today:
        df = history[history["SYMBOL"] == sym].sort_values("DATE")

        if len(df) < LOOKBACK_DAYS + 30:
            continue

        # Today's row
        today = df[df["DATE"] == scan_date]
        if today.empty:
            continue
        today = today.iloc[0]

        today_close = float(today["CLOSE"])
        today_open  = float(today["OPEN"])
        today_high  = float(today["HIGH"])
        today_low   = float(today["LOW"])
        today_vol   = float(today["VOLUME"])

        if today_close < MIN_PRICE or today_close > MAX_PRICE:
            continue
        if today_vol < MIN_VOLUME:
            continue

        # previous LOOKBACK_DAYS bars excluding today
        prev = df[df["DATE"] < scan_date].tail(LOOKBACK_DAYS)
        if len(prev) < LOOKBACK_DAYS:
            continue

        week52_high = float(prev["HIGH"].max())

        # EMA21 from closes (including today)
        ema21 = float(compute_ema(df["CLOSE"], EMA_PERIOD).iloc[-1])

        price_breakout = today_high > week52_high
        green_candle   = today_close > today_open
        above_ema      = today_close > ema21

        if not (price_breakout and green_candle and above_ema):
            continue

        sl_price = today_low
        sl_pct = round((today_close - sl_price) / today_close * 100, 2)

        target_price = round(today_close + 2 * (today_close - sl_price), 2)
        target_pct   = round(sl_pct * 2, 2)

        results.append({
            "symbol": sym,
            "close": round(today_close, 2),
            "week52_high": round(week52_high, 2),
            "ema21": round(ema21, 2),
            "volume": int(today_vol),
            "sl_price": round(sl_price, 2),
            "sl_pct": sl_pct,
            "target_price": target_price,
            "target_pct": target_pct,
        })

    return results

# ──────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────

def run():
    print("\n" + "=" * 60)
    print("NSE Breakout Scanner (Bhavcopy Based)")
    print("=" * 60 + "\n")

    bhav, bhav_date = get_latest_bhavcopy()
    if bhav is None:
        print("❌ Could not download bhavcopy for last 10 days.")
        return

    today_df = normalize_bhavcopy(bhav, bhav_date)

    history = load_history()
    history = update_history(history, today_df)

    # Keep only last ~400 trading days for smaller file
    cutoff = pd.to_datetime(bhav_date) - timedelta(days=600)
    history = history[history["DATE"] >= cutoff]

    save_history(history)

    scan_date_str = bhav_date.strftime("%Y-%m-%d")
    results = scan_breakouts(history, scan_date_str)

    today_str = bhav_date.strftime("%d %b %Y")

    if not results:
        send_telegram(
            f"📊 <b>NSE Breakout Scanner — {today_str}</b>\n\n"
            f"No breakouts found today.\n\n"
            f"<i>Filters: ₹{int(MIN_PRICE)}–₹{int(MAX_PRICE)} | "
            f"Green candle | Close > 21 EMA | High > 52W High</i>"
        )
        print("No breakouts.")
        return

    # Sort by volume descending
    results.sort(key=lambda x: x["volume"], reverse=True)

    send_telegram(
        f"🚀 <b>NSE Breakout Scanner — {today_str}</b>\n\n"
        f"<b>{len(results)} breakout(s) found</b>\n"
        f"Sorted by volume ↓"
    )
    time.sleep(0.5)

    for batch_start in range(0, len(results), 10):
        batch = results[batch_start:batch_start + 10]
        lines = []
        for r in batch:
            lines.append(
                f"──────────────────\n"
                f"📌 <b>{r['symbol']}</b>\n"
                f"   Close    : ₹{r['close']}\n"
                f"   52W High : ₹{r['week52_high']}\n"
                f"   21 EMA   : ₹{r['ema21']}\n"
                f"   Volume   : {r['volume']}\n"
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
    run()
