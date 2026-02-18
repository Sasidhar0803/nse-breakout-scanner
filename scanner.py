# ──────────────────────────────────────────────────────────────
#  NSE BREAKOUT SCANNER — FULL MARKET (~1800 NSE Stocks)
#  Runs daily via GitHub Actions at 4 PM IST (weekdays only)
# ──────────────────────────────────────────────────────────────

import yfinance as yf
import pandas as pd
import requests
import time
import os
import io
from datetime import datetime

# ──────────────────────────────────────────────────────────────
#  CREDENTIALS — stored in GitHub Secrets
# ──────────────────────────────────────────────────────────────

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

# ──────────────────────────────────────────────────────────────
#  STRATEGY SETTINGS
# ──────────────────────────────────────────────────────────────

VOL_MULTIPLIER  = 1.5    # (not enforced - kept for reference in messages)
VOL_MA_PERIOD   = 30
LOOKBACK_DAYS   = 252
EMA_PERIOD      = 21
MIN_PRICE       = 100.0
MAX_PRICE       = 2000.0
MIN_VOLUME      = 50000

# ──────────────────────────────────────────────────────────────
#  STOCK LIST — ~1800 NSE stocks across all segments
# ──────────────────────────────────────────────────────────────

def get_nse_stocks():
    """Use curated Nifty 500 list - reliable, fast, no rate limiting."""
    print("  📋 Using curated Nifty 500 stock list...")
    return get_full_stock_list()


def get_full_stock_list():
    """Nifty 500 stocks - liquid, tradeable, reliable data from Yahoo Finance"""
    raw = """RELIANCE,TCS,HDFCBANK,BHARTIARTL,ICICIBANK,SBIN,INFY,HINDUNILVR,ITC,KOTAKBANK,
LT,HCLTECH,BAJFINANCE,MARUTI,SUNPHARMA,ONGC,NTPC,TITAN,AXISBANK,ADANIENT,
ADANIPORTS,BAJAJFINSV,WIPRO,ULTRACEMCO,POWERGRID,NESTLEIND,ASIANPAINT,JSWSTEEL,
M&M,TATAMOTORS,COALINDIA,TATASTEEL,INDUSINDBK,TECHM,HINDALCO,DRREDDY,BPCL,
DIVISLAB,BAJAJ-AUTO,GRASIM,CIPLA,EICHERMOT,TATACONSUM,APOLLOHOSP,HEROMOTOCO,
BRITANNIA,SBILIFE,SHRIRAMFIN,HDFCLIFE,ICICIGI,PIDILITIND,HAVELLS,DABUR,SIEMENS,
MARICO,GODREJCP,TORNTPHARM,COLPAL,BERGEPAINT,MUTHOOTFIN,UNIONBANK,BANKBARODA,
CANBK,PNB,SAIL,NMDC,NATIONALUM,JINDALSTEL,JSPL,VEDL,HINDZINC,APLAPOLLO,
ASHOKLEY,TVSMOTOR,BALKRISIND,MRF,CEAT,APOLLOTYRE,BOSCHLTD,MOTHERSON,BHARATFORG,
ESCORTS,LTIM,MPHASIS,PERSISTENT,COFORGE,LTTS,OFSS,KPITTECH,TATAELXSI,ZOMATO,
IRCTC,DMART,TRENT,PAGEIND,ABFRL,RAYMOND,LALPATHLAB,METROPOLIS,
MAXHEALTH,FORTIS,YESBANK,IDFCFIRSTB,FEDERALBNK,RBLBANK,AUBANK,
CHOLAFIN,M&MFIN,MANAPPURAM,LICHSGFIN,PNBHOUSING,CANFINHOME,SBICARD,BANDHANBNK,
ADANIPOWER,TATAPOWER,TORNTPOWER,CESC,NHPC,RECLTD,PFC,IGL,MGL,GAIL,
PETRONET,HINDPETRO,IOC,AUROPHARMA,LUPIN,BIOCON,ALKEM,IPCA,LAURUSLABS,GRANULES,
GLENMARK,STRIDES,VOLTAS,BLUESTARCO,CROMPTON,DIXON,HAVELLS,VBL,UNITDSPR,RADICO,
JUBLFOOD,WESTLIFE,DEVYANI,NYKAA,POLICYBZR,IRCTC,DLF,GODREJPROP,PRESTIGE,BRIGADE,
PHOENIXLTD,SOBHA,RVNL,IRFC,HUDCO,NBCC,BEL,HAL,COCHINSHIP,GRSE,MAZAGON,BEML,
AARTI,DEEPAKNITRITE,NAVINFLUOR,ATUL,VINATI,TATACHEM,GNFC,COROMANDEL,UPL,
PIDILITIND,ASTRAL,JKLAKSHMI,AMBUJA,ACC,SHREECEM,RAMCOCEM,HEIDELBERG,JKCEMENT,
WELSPUN,ARVIND,ZEEL,SUNTV,PVRINOX,NETWORK18,BHARTIARTL,TATACOMM,HFCL,
AVANTIFEEDS,KRBL,GODREJAGRO,RALLIS,PI,JSWENERGY,TATAPOWER,KEC,KALPATPOWR,
TATAINVEST,VARROC,MOTHERSON,ENDURANCE,SUNDRMFAST,POLYCAB,KEI,AMARARAJA,EXIDEIND,
OBEROIRLTY,INDHOTEL,LEMONTRE,IPCALAB,AJANTPHARM,HONAUT,CUMMINSIND,THERMAX,BHEL,ABB,
CGPOWER,TIINDIA,SUPRAJIT,CERA,KAJARIACER,SOMANYCER,HSIL,CENTURYPLY,GREENPANEL,
PAGEIND,CAMPUS,BATA,RELAXO,VIP,SAFARI,LATENTVIEW,CYIENT,BIRLASOFT,HEXAWARE,
ECLERX,SONATSOFTW,JUSTDIAL,INFOEDGE,TEAMLEASE,QUESS,CRISIL,CDSL,BSE,MCX,
ANGELONE,MOTILALOFS,ICICIPRULI,HDFCAMC,NIPPONLIFE,360ONE,NUVAMA,EDELWEISS,
ABCAPITAL,SUNDARMFIN,APTUS,DELHIVERY,BLUEDART,CONCOR,VRL,GATEWAY,MASTEK,
COFORGE,PERSISTENT,MPHASIS,LTTS,LTIM,TATAELXSI,KPITTECH,OFSS,ROUTE,
DIXON,AMBER,VGUARD,CROMPTON,HAVELLS,ORIENTELEC,POLYCAB,KEI,FINOLEX,
NHIT,APTUS,HOMEFIRST,AAVAS,UJJIVANSFB,EQUITASBNK,ESAFSFB,CREDITACC,
MEDPLUS,METROPOLIS,LALPATHLAB,MAXHEALTH,FORTIS,ASTER,RAINBOW,KIMS,
ZOMATO,NYKAA,POLICYBZR,EASEMYTRIP,CARTRADE,PB,SWIGGY,PAYTM"""

    symbols = []
    for line in raw.strip().split("\n"):
        for sym in line.split(","):
            sym = sym.strip().upper()
            if sym and len(sym) > 0 and sym not in symbols:
                symbols.append(sym)

    yf_syms = [f"{s}.NS" for s in symbols if len(s) > 0]
    print(f"  ✅ Nifty 500 list: {len(yf_syms)} stocks")
    return yf_syms


# ──────────────────────────────────────────────────────────────
#  TELEGRAM
# ──────────────────────────────────────────────────────────────

def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Telegram credentials missing.")
        return
    url    = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
    for chunk in chunks:
        payload = {"chat_id": TELEGRAM_CHAT_ID, "text": chunk, "parse_mode": "HTML"}
        try:
            r = requests.post(url, data=payload, timeout=10)
            if r.status_code == 200:
                print("✅ Telegram sent.")
            else:
                print(f"❌ Telegram error: {r.text}")
        except Exception as e:
            print(f"❌ Telegram failed: {e}")
        time.sleep(0.5)


# ──────────────────────────────────────────────────────────────
#  CHECK SINGLE STOCK
# ──────────────────────────────────────────────────────────────

def check_stock(symbol):
    try:
        df = yf.download(symbol, period="14mo", interval="1d",
                         progress=False, auto_adjust=True)
        if df is None or len(df) < LOOKBACK_DAYS + 5:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.dropna()

        today        = df.iloc[-1]
        prev_bars    = df.iloc[-(LOOKBACK_DAYS + 1):-1]
        
        today_close  = float(today["Close"])
        today_open   = float(today["Open"])
        today_high   = float(today["High"])
        today_low    = float(today["Low"])
        today_volume = float(today["Volume"])

        # Debug logging for specific stocks
        debug_stocks = ["NHIT", "SBIN", "RELIANCE"]
        is_debug = any(d in symbol for d in debug_stocks)
        
        if is_debug:
            print(f"\n  🔍 DEBUG {symbol}:")
            print(f"     High: {today_high} | Close: {today_close} | Open: {today_open} | Vol: {today_volume}")

        if today_close < MIN_PRICE or today_close > MAX_PRICE:
            if is_debug:
                print(f"     ❌ FILTERED: Price {today_close} not in range ₹{MIN_PRICE}-₹{MAX_PRICE}")
            return None
        if today_volume < MIN_VOLUME:
            if is_debug:
                print(f"     ❌ FILTERED: Volume {today_volume} < {MIN_VOLUME}")
            return None

        week52_high = float(prev_bars["High"].max())
        avg_volume  = float(df["Volume"].iloc[-VOL_MA_PERIOD - 1:-1].mean())
        ema21       = float(df["Close"].ewm(span=EMA_PERIOD, adjust=False).mean().iloc[-1])

        if is_debug:
            print(f"     52WH: {week52_high} | 21EMA: {ema21} | AvgVol: {avg_volume}")

        # Breakout: today's high touched or crossed 52-week high
        price_breakout = today_high > week52_high
        vol_ratio      = today_volume / avg_volume if avg_volume > 0 else 0
        green_candle   = today_close > today_open
        above_ema      = today_close > ema21

        if is_debug:
            print(f"     Breakout check: High>{week52_high}? {price_breakout} ({today_high} vs {week52_high})")
            print(f"     Green candle: Close>{today_open}? {green_candle} ({today_close} vs {today_open})")
            print(f"     Above EMA: Close>{ema21}? {above_ema} ({today_close} vs {ema21})")
            if not (price_breakout and green_candle and above_ema):
                print(f"     ❌ FILTERED: Did not pass all conditions")
            else:
                print(f"     ✅ ALL CONDITIONS MET - should be in results")

        if price_breakout and green_candle and above_ema:
            all_time_high = float(df["High"].max())
            is_ath        = abs(week52_high - all_time_high) < 0.01 * week52_high
            breakout_type = "ATH 🏆" if is_ath else "52WH 📈"
            sl_price      = today_low
            sl_pct        = round((today_close - sl_price) / today_close * 100, 2)
            target_price  = round(today_close + 2 * (today_close - sl_price), 2)
            target_pct    = round(sl_pct * 2, 2)
            return {
                "symbol"       : symbol.replace(".NS", ""),
                "close"        : round(today_close, 2),
                "week52_high"  : round(week52_high, 2),
                "vol_ratio"    : round(vol_ratio, 2),
                "breakout_type": breakout_type,
                "sl_price"     : round(sl_price, 2),
                "sl_pct"       : sl_pct,
                "target_price" : target_price,
                "target_pct"   : target_pct,
                "ema21"        : round(ema21, 2),
            }
    except Exception:
        return None
    return None


# ──────────────────────────────────────────────────────────────
#  MAIN
# ──────────────────────────────────────────────────────────────

def run_scanner():
    start_time = time.time()
    today_str  = datetime.now().strftime("%d %b %Y")

    print(f"\n{'='*55}")
    print(f"  NSE FULL MARKET SCANNER — {today_str}")
    print(f"{'='*55}\n")

    stocks = get_nse_stocks()
    total  = len(stocks)
    print(f"  🔍 Scanning {total} stocks...\n")

    results = []

    for i, symbol in enumerate(stocks, 1):
        if i % 100 == 0 or i == 1:
            elapsed = round(time.time() - start_time)
            print(f"  Progress: {i}/{total} | Found: {len(results)} | Time: {elapsed}s")
        result = check_stock(symbol)
        if result:
            results.append(result)
            print(f"  ✅ BREAKOUT: {result['symbol']} | {result['breakout_type']} | Vol: {result['vol_ratio']}x")
        time.sleep(0.5)   # reasonable delay for ~500 stocks

    elapsed_total = round(time.time() - start_time)
    print(f"\n  Scan complete in {elapsed_total}s | Breakouts: {len(results)}\n")

    if not results:
        send_telegram(
            f"📊 <b>NSE Full Market Scanner — {today_str}</b>\n\n"
            f"No breakouts found today across {total} stocks.\n\n"
            f"<i>Filters: ₹{int(MIN_PRICE)}–₹{int(MAX_PRICE)} | "
            f"Green candle | Above 21 EMA | High above 52WH</i>"
        )
    else:
        results.sort(key=lambda x: x["vol_ratio"], reverse=True)
        send_telegram(
            f"🚀 <b>NSE Full Market Scanner — {today_str}</b>\n\n"
            f"<b>{len(results)} breakout(s) found</b> across {total} stocks\n"
            f"Sorted by volume strength ↓"
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
            f"⚠️ <i>Always check chart before entry.\n"
            f"Enter next day only if price holds above breakout level.\n"
            f"This is a scanner — not a buy recommendation.</i>"
        )


if __name__ == "__main__":
    run_scanner()
