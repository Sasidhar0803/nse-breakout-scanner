# ──────────────────────────────────────────────────────────────
#  NSE BREAKOUT SCANNER
#  Scans NSE stocks for your breakout strategy conditions
#  Runs daily via GitHub Actions at 4 PM IST (weekdays only)
# ──────────────────────────────────────────────────────────────

import yfinance as yf
import pandas as pd
import requests
from datetime import datetime
import time
import os

# ──────────────────────────────────────────────────────────────
#  CREDENTIALS — stored safely in GitHub Secrets (not here)
# ──────────────────────────────────────────────────────────────

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "")

# ──────────────────────────────────────────────────────────────
#  STRATEGY SETTINGS
# ──────────────────────────────────────────────────────────────

VOL_MULTIPLIER  = 1.5    # volume must be 1.5x the 30-day average
VOL_MA_PERIOD   = 30     # 30-day average volume
LOOKBACK_DAYS   = 252    # 52-week high lookback
EMA_PERIOD      = 21     # 21 EMA

# ──────────────────────────────────────────────────────────────
#  NSE STOCK LIST — Nifty 500 components
# ──────────────────────────────────────────────────────────────

NSE_STOCKS = [
    "RELIANCE.NS","TCS.NS","HDFCBANK.NS","BHARTIARTL.NS","ICICIBANK.NS",
    "SBIN.NS","INFY.NS","HINDUNILVR.NS","ITC.NS","KOTAKBANK.NS",
    "LT.NS","HCLTECH.NS","BAJFINANCE.NS","MARUTI.NS","SUNPHARMA.NS",
    "ONGC.NS","NTPC.NS","TITAN.NS","AXISBANK.NS","ADANIENT.NS",
    "ADANIPORTS.NS","BAJAJFINSV.NS","WIPRO.NS","ULTRACEMCO.NS","POWERGRID.NS",
    "NESTLEIND.NS","ASIANPAINT.NS","JSWSTEEL.NS","M&M.NS","TATAMOTORS.NS",
    "COALINDIA.NS","TATASTEEL.NS","INDUSINDBK.NS","TECHM.NS","HINDALCO.NS",
    "DRREDDY.NS","BPCL.NS","DIVISLAB.NS","BAJAJ-AUTO.NS","GRASIM.NS",
    "CIPLA.NS","EICHERMOT.NS","TATACONSUM.NS","APOLLOHOSP.NS","HEROMOTOCO.NS",
    "BRITANNIA.NS","SBILIFE.NS","SHRIRAMFIN.NS","HDFCLIFE.NS","ICICIGI.NS",
    "PIDILITIND.NS","HAVELLS.NS","DABUR.NS","SIEMENS.NS","MARICO.NS",
    "GODREJCP.NS","TORNTPHARM.NS","COLPAL.NS","BERGEPAINT.NS","MUTHOOTFIN.NS",
    "UNIONBANK.NS","BANKBARODA.NS","CANBK.NS","PNB.NS","SAIL.NS",
    "NMDC.NS","NATIONALUM.NS","JINDALSTEL.NS","JSPL.NS","VEDL.NS",
    "HINDZINC.NS","APLAPOLLO.NS","ASHOKLEY.NS","TVSMOTOR.NS","BALKRISIND.NS",
    "MRF.NS","CEAT.NS","APOLLOTYRE.NS","BOSCHLTD.NS","MOTHERSON.NS",
    "BHARATFORG.NS","ESCORTS.NS","LTIM.NS","MPHASIS.NS","PERSISTENT.NS",
    "COFORGE.NS","LTTS.NS","OFSS.NS","KPITTECH.NS","TATAELXSI.NS",
    "ZOMATO.NS","IRCTC.NS","DMART.NS","TRENT.NS","PAGEIND.NS",
    "LALPATHLAB.NS","METROPOLIS.NS","MAXHEALTH.NS","FORTIS.NS","YESBANK.NS",
    "IDFCFIRSTB.NS","FEDERALBNK.NS","RBLBANK.NS","AUBANK.NS","CHOLAFIN.NS",
    "M&MFIN.NS","MANAPPURAM.NS","LICHSGFIN.NS","PNBHOUSING.NS","CANFINHOME.NS",
    "SBICARD.NS","BANDHANBNK.NS","ADANIPOWER.NS","TATAPOWER.NS","TORNTPOWER.NS",
    "CESC.NS","NHPC.NS","SJVN.NS","RECLTD.NS","PFC.NS",
    "IREDA.NS","ATGL.NS","IGL.NS","MGL.NS","GAIL.NS",
    "PETRONET.NS","HINDPETRO.NS","IOC.NS","AUROPHARMA.NS","LUPIN.NS",
    "BIOCON.NS","ALKEM.NS","IPCA.NS","LAURUSLABS.NS","GRANULES.NS",
    "NATCOPHARM.NS","MEDPLUS.NS","VOLTAS.NS","BLUESTARCO.NS","CROMPTON.NS",
    "VBL.NS","UNITDSPR.NS","RADICO.NS","MCDOWELL-N.NS","ZYDUSLIFE.NS",
    "GLENMARK.NS","OBEROIRLTY.NS","DLF.NS","GODREJPROP.NS","PRESTIGE.NS",
    "BRIGADE.NS","PHOENIXLTD.NS","SOBHA.NS","INDHOTEL.NS","EIHOTEL.NS",
    "LEMONTRE.NS","BEL.NS","HAL.NS","COCHINSHIP.NS","GRSE.NS",
    "MAZAGON.NS","BEML.NS","RVNL.NS","IRFC.NS","HUDCO.NS",
    "NBCC.NS","BHARATDYN.NS","DATAPATTNS.NS","DELHIVERY.NS","BLUEDART.NS",
    "POLYCAB.NS","KEI.NS","AMARARAJA.NS","EXIDEIND.NS","MINDA.NS",
    "ENDURANCE.NS","SUNDRMFAST.NS","AVANTIFEEDS.NS","SKFINDIA.NS","SCHAEFFLER.NS",
    "TIMKEN.NS","GRINDWELL.NS","CUMMINSIND.NS","THERMAX.NS","BHEL.NS",
    "ABB.NS","AIAENG.NS","ELGIEQUIP.NS","KIRLOSENG.NS","FINOLEX.NS",
    "HBLPOWER.NS","KARURVYSYA.NS","CUB.NS","EQUITASBNK.NS","UJJIVANSFB.NS",
    "CREDITACC.NS","SPANDANA.NS","HOMEFIRST.NS","AAVAS.NS","MANYAVAR.NS",
    "RAYMOND.NS","ABFRL.NS","TTKPRESTIG.NS","WHIRLPOOL.NS","ORIENTELEC.NS",
]

NSE_STOCKS = list(dict.fromkeys(NSE_STOCKS))  # remove duplicates


# ──────────────────────────────────────────────────────────────
#  TELEGRAM
# ──────────────────────────────────────────────────────────────

def send_telegram(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("❌ Telegram credentials missing.")
        return
    url     = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        r = requests.post(url, data=payload, timeout=10)
        if r.status_code == 200:
            print("✅ Telegram message sent.")
        else:
            print(f"❌ Telegram error: {r.text}")
    except Exception as e:
        print(f"❌ Telegram failed: {e}")


# ──────────────────────────────────────────────────────────────
#  SCANNER
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
        today_low    = float(today["Low"])
        today_volume = float(today["Volume"])

        week52_high  = float(prev_bars["High"].max())
        avg_volume   = float(df["Volume"].iloc[-VOL_MA_PERIOD - 1:-1].mean())
        ema21        = float(df["Close"].ewm(span=EMA_PERIOD, adjust=False).mean().iloc[-1])

        # ── CONDITIONS ──
        price_breakout = today_close > week52_high
        vol_ratio      = today_volume / avg_volume if avg_volume > 0 else 0
        vol_ok         = vol_ratio >= VOL_MULTIPLIER
        green_candle   = today_close > today_open
        above_ema      = today_close > ema21

        if price_breakout and vol_ok and green_candle and above_ema:
            all_time_high  = float(df["High"].max())
            breakout_type  = "ATH 🏆" if abs(week52_high - all_time_high) < 0.01 * week52_high else "52WH 📈"
            sl_price       = today_low
            sl_pct         = round((today_close - sl_price) / today_close * 100, 2)
            target_price   = round(today_close + 2 * (today_close - sl_price), 2)
            target_pct     = round(sl_pct * 2, 2)

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

    except Exception as e:
        print(f"  ⚠ {symbol}: {e}")
        return None


# ──────────────────────────────────────────────────────────────
#  MAIN
# ──────────────────────────────────────────────────────────────

def run_scanner():
    print(f"\n{'='*50}")
    print(f"  NSE Breakout Scanner — {datetime.now().strftime('%d %b %Y %H:%M')}")
    print(f"  Scanning {len(NSE_STOCKS)} stocks...")
    print(f"{'='*50}\n")

    results = []

    for i, symbol in enumerate(NSE_STOCKS, 1):
        print(f"  [{i:>3}/{len(NSE_STOCKS)}] {symbol:<25}", end="\r")
        result = check_stock(symbol)
        if result:
            results.append(result)
            print(f"  ✅ BREAKOUT: {symbol}")
        time.sleep(0.3)

    print(f"\n\n  Done. Found {len(results)} breakout(s).\n")

    today_str = datetime.now().strftime("%d %b %Y")

    if not results:
        message = (
            f"📊 <b>NSE Breakout Scanner — {today_str}</b>\n\n"
            f"No stocks found today.\n\n"
            f"<i>Conditions checked:\n"
            f"• Close above 52-Week High\n"
            f"• Volume ≥ {VOL_MULTIPLIER}x 30-day average\n"
            f"• Green candle (close &gt; open)\n"
            f"• Price above 21 EMA</i>"
        )
    else:
        lines = [
            f"🚀 <b>NSE Breakout Scanner — {today_str}</b>\n",
            f"<b>{len(results)} stock(s) found:</b>\n"
        ]
        for r in sorted(results, key=lambda x: x["vol_ratio"], reverse=True):
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
        lines.append("──────────────────")
        lines.append(
            f"\n⚠️ <i>Check chart before entry.\n"
            f"Enter next day only if price holds above breakout level.</i>"
        )
        message = "\n".join(lines)

    send_telegram(message)


if __name__ == "__main__":
    run_scanner()
