import subprocess
subprocess.run(["pip", "install", "yfinance", "pandas", "-q"])

import math
import yfinance as yf
import pandas as pd
import json
from datetime import datetime, timedelta

tickers = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "TSLA", "AVGO", "COST",
    "NFLX", "AMD", "ADBE", "QCOM", "PEP", "INTU", "CSCO", "AMAT", "TXN", "HON",
    "AMGN", "SBUX", "BKNG", "ISRG", "GILD", "ADI", "LRCX", "REGN", "MU", "VRTX",
    "PANW", "KLAC", "SNPS", "CDNS", "MRVL", "ORLY", "CTAS", "ASML", "FTNT", "MDLZ",
    "ABNB", "MNST", "PYPL", "MELI", "NXPI", "WDAY", "CPRT", "ROST", "KDP", "AEP",
    "PCAR", "DDOG", "IDXX", "ODFL", "FAST", "BIIB", "TEAM", "EA", "ZS", "SIRI",
    "VRSK", "GEHC", "ON", "ANSS", "CTSH", "DLTR", "XEL", "FANG", "CRWD", "TTWO",
    "ILMN", "MRNA", "SMCI", "ARM", "MCHP", "ADSK", "CHTR", "PAYX", "DXCM", "CEG",
    "CCEP", "COIN", "APP", "AXON", "WELL", "HUBS", "TTD", "OKTA", "SNDK", "MSTR",
    "PLTR", "RXRX", "GFS", "LULU", "EBAY", "CSGP", "FSLR", "DASH"
]
tickers = list(set(tickers))

benchmark  = "QQQ"
rs_windows = {"5T": 5, "10T": 10, "20T": 20, "50T": 50, "6M": 126, "12M": 252}

# Lookback periods for data download
WEEKS_LOOKBACK = 450   # covers ~60 weekly candles
DAYS_LOOKBACK  = 100   # covers ~60 daily trading days
H4_LOOKBACK    =  60   # covers ~90 4H candles


def sanitize_nan(obj):
    """Ersetzt NaN/Infinity durch None, damit gültiges JSON entsteht."""
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: sanitize_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_nan(v) for v in obj]
    return obj


def extract_ohlcv(ticker, raw_data, timeframe_label, n_candles=60):
    """Extrahiert OHLCV-Daten für einen Ticker aus einem bulk-Download DataFrame."""
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
            if pd.isna(cv):
                continue
            result.append({
                "d": date.strftime("%Y-%m-%d"),
                "o": round(float(ov), 2),
                "h": round(float(hv), 2),
                "l": round(float(lv), 2),
                "c": round(float(cv), 2)
            })
        return result[-n_candles:]
    except Exception as e:
        print(f"  Fehler {timeframe_label} OHLCV {ticker}: {e}")
        return []


# ── Schritt 1: RS-Score für alle Ticker ─────────────────────────────────────────
print(f"Schritt 1: RS-Berechnung für alle {len(tickers)} Aktien...")
all_tickers = tickers + [benchmark]
raw = yf.download(all_tickers, period="1y", auto_adjust=True, progress=False)
close = raw["Close"]
qqq   = close[benchmark]

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
                float((s.iloc[-1] / s.iloc[-days] - 1) * 100
                      - (qqq.iloc[-1] / qqq.iloc[-days] - 1) * 100), 2
            )
        except (IndexError, ZeroDivisionError, ValueError):
            windows_result[label] = None
    score = round(sum(v for v in windows_result.values() if v is not None), 2)
    all_results.append({"ticker": ticker, "score": score, "windows": windows_result})

all_results.sort(key=lambda x: x["score"], reverse=True)
top20 = [r["ticker"] for r in all_results[:20]]
print(f"Top 20: {', '.join(top20)}")

# ── Schritt 2: Weekly OHLCV für ALLE Ticker (letzte 60 Wochen = ~15 Monate)
print(f"\nSchritt 2: Weekly OHLCV für alle {len(tickers)} Ticker (60 Wochen)...")
end_date     = datetime.now()
end_str      = (end_date + timedelta(days=1)).strftime("%Y-%m-%d")
start_weekly = end_date - timedelta(days=WEEKS_LOOKBACK)

all_tickers_list = [r["ticker"] for r in all_results]
raw_weekly = yf.download(
    all_tickers_list + [benchmark],
    start=start_weekly.strftime("%Y-%m-%d"),
    end=end_str,
    interval="1wk",
    auto_adjust=True,
    progress=False
)

# ── Schritt 3: Daily OHLCV für ALLE Ticker (letzte 60 Kerzen ≈ 3 Monate)
print(f"\nSchritt 3: Daily OHLCV für alle {len(tickers)} Ticker (60 Kerzen)...")
start_daily = end_date - timedelta(days=DAYS_LOOKBACK)

raw_daily = yf.download(
    all_tickers_list + [benchmark],
    start=start_daily.strftime("%Y-%m-%d"),
    end=end_str,
    interval="1d",
    auto_adjust=True,
    progress=False
)

# ── Schritt 4: 4H OHLCV für ALLE Ticker (letzte 90 Kerzen inkl. Extended Hours)
print(f"\nSchritt 4: 4H OHLCV für alle {len(tickers)} Ticker (90 Kerzen, inkl. Pre-/Post-Market)...")
start_4h = end_date - timedelta(days=H4_LOOKBACK)


def extract_ohlcv_4h(ticker, n_candles=90):
    """Lädt 4H-Daten inkl. Extended Hours (Pre-Market 04:00-09:30 ET ≈ London-Session,
    After-Hours 16:00-20:00 ET) via yfinance (1H → 4H aggregiert), letzte n_candles."""
    try:
        df = yf.download(
            ticker,
            start=start_4h.strftime("%Y-%m-%d"),
            end=end_str,
            interval="1h",
            prepost=True,
            auto_adjust=True,
            progress=False
        )
        if df.empty:
            return []

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df = df[["Open", "High", "Low", "Close"]].dropna()
        df.index = pd.to_datetime(df.index)

        # offset="1h30min" aligns 4H bars to NYSE open (09:30 ET)
        df_4h = df.resample("4h", offset="1h30min").agg({
            "Open":  "first",
            "High":  "max",
            "Low":   "min",
            "Close": "last"
        }).dropna()

        result = []
        for dt, row in df_4h.iterrows():
            if pd.isna(row["Close"]):
                continue
            result.append({
                "d": dt.strftime("%Y-%m-%d %H:%M"),
                "o": round(float(row["Open"]),  2),
                "h": round(float(row["High"]),  2),
                "l": round(float(row["Low"]),   2),
                "c": round(float(row["Close"]), 2)
            })
        return result[-n_candles:]
    except Exception as e:
        print(f"  Fehler 4H {ticker}: {e}")
        return []


ohlcv_4h_map = {}
for i, ticker in enumerate(all_tickers_list):
    print(f"  4H [{i+1}/{len(all_tickers_list)}] {ticker}...", end=" ")
    data_4h = extract_ohlcv_4h(ticker)
    ohlcv_4h_map[ticker] = data_4h
    print(f"{len(data_4h)} Kerzen")

# ── Schritt 5: Ausgabe zusammenbauen ──────────────────────────────────────────
print("\nSchritt 5: JSON zusammenbauen...")
data = []
for r in all_results:
    ticker  = r["ticker"]
    ohlcv_w = extract_ohlcv(ticker, raw_weekly, "Weekly")
    ohlcv_d = extract_ohlcv(ticker, raw_daily,  "Daily")
    ohlcv4h = ohlcv_4h_map.get(ticker, [])
    data.append({
        "ticker":   ticker,
        "score":    r["score"],
        "windows":  r["windows"],
        "ohlcv_w":  ohlcv_w,
        "ohlcv":    ohlcv_d,
        "ohlcv_4h": ohlcv4h
    })

# Benchmark (QQQ) OHLCV für Index-Overlay in Charts
benchmark_ohlcv_w = extract_ohlcv(benchmark, raw_weekly, "Weekly")
benchmark_ohlcv_d = extract_ohlcv(benchmark, raw_daily,  "Daily")
print(f"Benchmark {benchmark}: Weekly={len(benchmark_ohlcv_w)} Kerzen, Daily={len(benchmark_ohlcv_d)} Kerzen")

output = {
    "timestamp":        datetime.now().strftime("%Y-%m-%d %H:%M"),
    "benchmark":        "QQQ",
    "top20":            top20,
    "data":             data,
    "benchmark_ohlcv_w": benchmark_ohlcv_w,
    "benchmark_ohlcv":  benchmark_ohlcv_d,
}

MIN_TICKERS = 50  # Mindestanzahl Aktien – bei weniger liegt ein yfinance-Fehler vor
if len(data) < MIN_TICKERS:
    print(f"\n⚠️  Nur {len(data)} Aktien geladen (Minimum {MIN_TICKERS}). rs_full.json wird NICHT überschrieben.")
    raise SystemExit(1)

sanitized = sanitize_nan(output)
with open("rs_full.json", "w") as f:
    json.dump(sanitized, f)

size_kb = len(json.dumps(sanitized)) / 1024
print(f"\n✅ Fertig! Dateigröße: {size_kb:.0f} KB")
print(f"Timestamp: {output['timestamp']}")
print(f"Ticker gesamt: {len(data)}")
print("Top 5:")
for i, r in enumerate(data[:5]):
    print(f"  {i+1}. {r['ticker']}: Score={r['score']}, Weekly={len(r['ohlcv_w'])} Kerzen, Daily={len(r['ohlcv'])} Kerzen, 4H={len(r['ohlcv_4h'])} Kerzen")
print("\nDatei gespeichert: rs_full.json")

# ── Top-20-Historie fortschreiben ────────────────────────────────────────────
_hist_file = "rs_top20_history.json"
_date_key  = output["timestamp"][:10]
try:
    with open(_hist_file) as _f:
        _hist = json.load(_f)
except FileNotFoundError:
    _hist = {}
_entries = _hist.setdefault("QQQ", [])
_known   = {e["date"] for e in _entries}
if _date_key not in _known:
    _entries.append({"date": _date_key, "top20": top20})
else:
    for _e in _entries:
        if _e["date"] == _date_key:
            _e["top20"] = top20
            break
_entries.sort(key=lambda x: x["date"])
with open(_hist_file, "w") as _f:
    json.dump(_hist, _f, indent=2)
print(f"Top-20-Historie aktualisiert: QQQ {_date_key} → {_hist_file}")
