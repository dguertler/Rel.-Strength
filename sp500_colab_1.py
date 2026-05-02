import subprocess
subprocess.run(["pip", "install", "yfinance", "pandas", "-q"])

import yfinance as yf
import pandas as pd
import json
import math
from datetime import datetime, timedelta

# S&P 500 – Teil 1: Financials, Healthcare, Consumer, Energy, Industrials
# Alle Werte die NICHT schon im QQQ-Dashboard abgedeckt sind.
tickers = [
    # Financials
    "JPM", "BAC", "WFC", "GS",  "MS",   "BLK", "C",   "AXP", "SCHW", "USB",
    "PNC", "TFC", "COF", "SPGI","ICE",  "MCO", "CME", "CB",  "MMC",  "PGR",
    "TRV", "AFL", "MET", "PRU", "ALL",  "AIG", "HIG", "BK",  "STT",  "NTRS",
    "GPN", "FIS", "FI",  "V",   "MA",   "AMP", "SYF", "DFS", "ALLY", "CBOE",
    "NDAQ","RJF", "WRB", "L",   "CINF", "TROW","AON",
    # Healthcare
    "UNH", "LLY", "JNJ", "ABBV","MRK",  "TMO", "ABT", "DHR", "PFE",  "SYK",
    "BSX", "HCA", "ELV", "CI",  "CVS",  "MCK", "CAH", "CNC", "MOH",  "HUM",
    "A",   "BDX", "BAX", "EW",  "RMD",  "IQV", "ZBH", "BMY", "HOLX", "VTRS",
    "HSIC","ALGN","TFX", "COO", "DGX",  "LH",  "BIO",
    # Consumer Discretionary
    "HD",  "MCD", "NKE", "TGT", "LOW",  "CMG", "TJX", "AZO", "GM",   "F",
    "BBY", "DRI", "YUM", "EXPE","POOL", "NVR", "PHM", "DHI", "LEN",  "TOL",
    "TPR", "RL",  "APTV","MGM", "WYNN", "LVS", "MAR", "HLT", "H",    "RCL",
    "CCL", "NCLH","CZR",
    # Consumer Staples
    "WMT", "PG",  "KO",  "PM",  "MO",   "CL",  "KR",  "GIS", "K",    "SJM",
    "CPB", "CAG", "TSN", "HRL", "MKC",  "CHD", "CLX", "EL",  "SYY",  "WBA",
    # Energy
    "XOM", "CVX", "COP", "SLB", "OXY",  "EOG", "PSX", "MPC", "VLO",  "HAL",
    "DVN", "BKR", "APA", "HES", "MRO",  "CTRA","EQT", "RRC", "SM",   "OVV",
    # Industrials
    "CAT", "GE",  "UNP", "BA",  "RTX",  "LMT", "NOC", "GD",  "MMM",  "DE",
    "EMR", "ETN", "ITW", "PH",  "CSX",  "NSC", "UPS", "FDX", "ROK",  "CMI",
    "WM",  "RSG", "FTV", "CARR","OTIS", "JCI", "TT",  "IR",  "ROP",  "SWK",
    "HII", "HWM", "XYL", "MAS", "AME",
]
tickers = list(set(tickers))

benchmark   = "^GSPC"
rs_windows  = {"5T": 5, "10T": 10, "20T": 20, "50T": 50, "6M": 126, "12M": 252}
OUTPUT_FILE = "rs_sp500_1.json"

def sanitize_nan(obj):
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: sanitize_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_nan(v) for v in obj]
    return obj

print(f"Teil 1: RS-Berechnung für {len(tickers)} S&P 500-Aktien (ohne QQQ-Werte)...")
all_tickers = tickers + [benchmark]
raw   = yf.download(all_tickers, period="1y", auto_adjust=True, progress=False)
close = raw["Close"]
spx   = close[benchmark]

all_results = []
for ticker in tickers:
    if ticker not in close.columns:
        continue
    s = close[ticker].dropna()
    if len(s) < 50:
        continue
    windows_result = {}
    for label, days in rs_windows.items():
        try:
            windows_result[label] = round(
                float((s.iloc[-1]/s.iloc[-days]-1)*100 - (spx.iloc[-1]/spx.iloc[-days]-1)*100), 2)
        except:
            windows_result[label] = None
    score = round(sum(v for v in windows_result.values() if v is not None), 2)
    all_results.append({"ticker": ticker, "score": score, "windows": windows_result})

all_results.sort(key=lambda x: x["score"], reverse=True)
print(f"Top 5: {', '.join(r['ticker'] for r in all_results[:5])}")

end_date     = datetime.now()
end_str      = (end_date + timedelta(days=1)).strftime("%Y-%m-%d")
start_weekly = end_date - timedelta(days=450)
start_daily  = end_date - timedelta(days=100)
start_4h     = end_date - timedelta(days=60)

all_tickers_list = [r["ticker"] for r in all_results]

print(f"\nWeekly OHLCV ({len(all_tickers_list)} Ticker)...")
raw_weekly = yf.download(
    all_tickers_list + [benchmark],
    start=start_weekly.strftime("%Y-%m-%d"), end=end_str,
    interval="1wk", auto_adjust=True, progress=False)

print(f"Daily OHLCV ({len(all_tickers_list)} Ticker)...")
raw_daily = yf.download(
    all_tickers_list + [benchmark],
    start=start_daily.strftime("%Y-%m-%d"), end=end_str,
    interval="1d", auto_adjust=True, progress=False)

def extract_ohlcv(ticker, raw_data, n_candles, date_fmt="%Y-%m-%d"):
    try:
        if isinstance(raw_data.columns, pd.MultiIndex):
            c = raw_data["Close"][ticker].dropna()
            o = raw_data["Open"][ticker].reindex(c.index)
            h = raw_data["High"][ticker].reindex(c.index)
            l = raw_data["Low"][ticker].reindex(c.index)
        else:
            c = raw_data["Close"].dropna()
            o = raw_data["Open"].reindex(c.index)
            h = raw_data["High"].reindex(c.index)
            l = raw_data["Low"].reindex(c.index)
        result = []
        for date, ov, hv, lv, cv in zip(c.index, o, h, l, c):
            if pd.isna(cv): continue
            result.append({"d": date.strftime(date_fmt),
                           "o": round(float(ov), 2), "h": round(float(hv), 2),
                           "l": round(float(lv), 2), "c": round(float(cv), 2)})
        return result[-n_candles:]
    except:
        return []

def extract_ohlcv_4h(ticker, n_candles=90):
    try:
        df = yf.download(ticker, start=start_4h.strftime("%Y-%m-%d"), end=end_str,
                         interval="1h", prepost=True, auto_adjust=True, progress=False)
        if df.empty: return []
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df[["Open","High","Low","Close"]].dropna()
        df.index = pd.to_datetime(df.index)
        df_4h = df.resample("4h", offset="1h30min").agg(
            {"Open":"first","High":"max","Low":"min","Close":"last"}).dropna()
        result = []
        for dt, row in df_4h.iterrows():
            if pd.isna(row["Close"]): continue
            result.append({"d": dt.strftime("%Y-%m-%d %H:%M"),
                           "o": round(float(row["Open"]),  2),
                           "h": round(float(row["High"]),  2),
                           "l": round(float(row["Low"]),   2),
                           "c": round(float(row["Close"]), 2)})
        return result[-n_candles:]
    except Exception as e:
        print(f"  4H Fehler {ticker}: {e}")
        return []

print(f"\n4H OHLCV ({len(all_tickers_list)} Ticker)...")
ohlcv_4h_map = {}
for i, ticker in enumerate(all_tickers_list):
    print(f"  4H [{i+1}/{len(all_tickers_list)}] {ticker}...", end=" ", flush=True)
    ohlcv_4h_map[ticker] = extract_ohlcv_4h(ticker)
    print(f"{len(ohlcv_4h_map[ticker])} Kerzen")

print("\nJSON zusammenbauen...")
data = []
for r in all_results:
    t = r["ticker"]
    data.append({"ticker": t, "score": r["score"], "windows": r["windows"],
                 "ohlcv_w":  extract_ohlcv(t, raw_weekly, 60),
                 "ohlcv":    extract_ohlcv(t, raw_daily, 60),
                 "ohlcv_4h": ohlcv_4h_map.get(t, [])})

output = {
    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
    "benchmark": "SPX",
    "data": data,
    "benchmark_ohlcv_w": extract_ohlcv(benchmark, raw_weekly, 60),
    "benchmark_ohlcv":   extract_ohlcv(benchmark, raw_daily, 60),
}
MIN_TICKERS = 50
if len(data) < MIN_TICKERS:
    print(f"\n⚠️  Nur {len(data)} Aktien geladen (Minimum {MIN_TICKERS}). {OUTPUT_FILE} wird NICHT überschrieben.")
    import sys; sys.exit(1)
with open(OUTPUT_FILE, "w") as f:
    json.dump(sanitize_nan(output), f)
print(f"✅ Teil 1 fertig – {len(data)} Ticker → {OUTPUT_FILE}")
