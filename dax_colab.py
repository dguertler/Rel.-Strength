import subprocess
subprocess.run(["pip", "install", "yfinance", "pandas", "-q"])

import yfinance as yf
import pandas as pd
import json
import math
from datetime import datetime, timedelta

# DAX 40 Mitglieder (yfinance Ticker mit .DE Suffix)
tickers = [
    "ADS.DE",   # Adidas
    "AIR.DE",   # Airbus
    "ALV.DE",   # Allianz
    "BAS.DE",   # BASF
    "BAYN.DE",  # Bayer
    "BEI.DE",   # Beiersdorf
    "BMW.DE",   # BMW
    "BNR.DE",   # Brenntag
    "CBK.DE",   # Commerzbank
    "CON.DE",   # Continental
    "1COV.DE",  # Covestro
    "DTG.DE",   # Daimler Truck
    "DBK.DE",   # Deutsche Bank
    "DB1.DE",   # Deutsche Börse
    "DHL.DE",   # Deutsche Post / DHL
    "DTE.DE",   # Deutsche Telekom
    "EOAN.DE",  # E.ON
    "FRE.DE",   # Fresenius
    "FME.DE",   # Fresenius Medical Care
    "HNR1.DE",  # Hannover Re
    "HEIG.DE",  # Heidelberg Materials
    "HEN3.DE",  # Henkel Vz
    "IFX.DE",   # Infineon
    "MRK.DE",   # Merck KGaA
    "MBG.DE",   # Mercedes-Benz
    "MTX.DE",   # MTU Aero Engines
    "MUV2.DE",  # Munich Re
    "P911.DE",  # Porsche AG
    "PAH3.DE",  # Porsche SE
    "QIA.DE",   # Qiagen
    "RHM.DE",   # Rheinmetall
    "RWE.DE",   # RWE
    "SAP.DE",   # SAP
    "SRT3.DE",  # Sartorius Vz
    "SIE.DE",   # Siemens
    "ENR.DE",   # Siemens Energy
    "SHL.DE",   # Siemens Healthineers
    "SY1.DE",   # Symrise
    "VOW3.DE",  # Volkswagen Vz
    "VNA.DE",   # Vonovia
]
tickers = list(set(tickers))

benchmark = "^GDAXI"  # DAX Performance Index
rs_windows = {"5T": 5, "10T": 10, "20T": 20, "50T": 50, "6M": 126, "12M": 252}

def sanitize_nan(obj):
    """Ersetzt NaN/Infinity durch None für gültiges JSON."""
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, dict):
        return {k: sanitize_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize_nan(v) for v in obj]
    return obj

# ── Schritt 1: RS-Score für alle Ticker ─────────────────────────────────────────
print(f"Schritt 1: RS-Berechnung für alle {len(tickers)} DAX-Aktien...")
all_tickers = tickers + [benchmark]
raw = yf.download(all_tickers, period="1y", auto_adjust=True, progress=False)
close = raw["Close"]
qqq = close[benchmark]

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
            windows_result[label] = round(float((s.iloc[-1]/s.iloc[-days]-1)*100 - (qqq.iloc[-1]/qqq.iloc[-days]-1)*100), 2)
        except:
            windows_result[label] = None
    score = round(sum(v for v in windows_result.values() if v is not None), 2)
    all_results.append({"ticker": ticker, "score": score, "windows": windows_result})

all_results.sort(key=lambda x: x["score"], reverse=True)
top20 = [r["ticker"] for r in all_results[:20]]
print(f"Top 20: {', '.join(top20)}")

# ── Schritt 2: Weekly OHLCV (letzte 60 Wochen)
print(f"\nSchritt 2: Weekly OHLCV für alle {len(tickers)} Ticker (60 Wochen)...")
end_date     = datetime.now()
end_str      = (end_date + timedelta(days=1)).strftime("%Y-%m-%d")
start_weekly = end_date - timedelta(days=450)

all_tickers_list = [r["ticker"] for r in all_results]
raw_weekly = yf.download(
    all_tickers_list + [benchmark],
    start=start_weekly.strftime("%Y-%m-%d"),
    end=end_str,
    interval="1wk",
    auto_adjust=True,
    progress=False
)

def extract_ohlcv_weekly(ticker, raw_data, n_candles=60):
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
            result.append({
                "d": date.strftime("%Y-%m-%d"),
                "o": round(float(ov), 2),
                "h": round(float(hv), 2),
                "l": round(float(lv), 2),
                "c": round(float(cv), 2)
            })
        return result[-n_candles:]
    except Exception as e:
        print(f"  Fehler Weekly OHLCV {ticker}: {e}")
        return []

# ── Schritt 3: Daily OHLCV (letzte 60 Kerzen)
print(f"\nSchritt 3: Daily OHLCV für alle {len(tickers)} Ticker (60 Kerzen)...")
start_daily = end_date - timedelta(days=100)

raw_daily = yf.download(
    all_tickers_list + [benchmark],
    start=start_daily.strftime("%Y-%m-%d"),
    end=end_str,
    interval="1d",
    auto_adjust=True,
    progress=False
)

def extract_ohlcv_daily(ticker, raw_data, n_candles=60):
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
            result.append({
                "d": date.strftime("%Y-%m-%d"),
                "o": round(float(ov), 2),
                "h": round(float(hv), 2),
                "l": round(float(lv), 2),
                "c": round(float(cv), 2)
            })
        return result[-n_candles:]
    except Exception as e:
        print(f"  Fehler Daily OHLCV {ticker}: {e}")
        return []

# ── Schritt 4: 4H OHLCV (letzte 90 Kerzen inkl. Extended Hours)
print(f"\nSchritt 4: 4H OHLCV für alle {len(tickers)} Ticker (90 Kerzen, inkl. Pre-/Post-Market)...")
start_4h = end_date - timedelta(days=60)

def extract_ohlcv_4h(ticker, n_candles=90):
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

        df_4h = df.resample("4h", offset="0h").agg({
            "Open":  "first",
            "High":  "max",
            "Low":   "min",
            "Close": "last"
        }).dropna()

        result = []
        for dt, row in df_4h.iterrows():
            if pd.isna(row["Close"]): continue
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

# ── Schritt 5: JSON zusammenbauen ─────────────────────────────────────────
print("\nSchritt 5: JSON zusammenbauen...")
data = []
for r in all_results:
    ticker  = r["ticker"]
    ohlcv_w = extract_ohlcv_weekly(ticker, raw_weekly)
    ohlcv_d = extract_ohlcv_daily(ticker, raw_daily)
    ohlcv4h = ohlcv_4h_map.get(ticker, [])
    data.append({
        "ticker":   ticker,
        "score":    r["score"],
        "windows":  r["windows"],
        "ohlcv_w":  ohlcv_w,
        "ohlcv":    ohlcv_d,
        "ohlcv_4h": ohlcv4h
    })

# Benchmark (^GDAXI) OHLCV für Index-Overlay in Charts
benchmark_ohlcv_w = extract_ohlcv_weekly(benchmark, raw_weekly)
benchmark_ohlcv_d = extract_ohlcv_daily(benchmark, raw_daily)
print(f"Benchmark {benchmark}: Weekly={len(benchmark_ohlcv_w)} Kerzen, Daily={len(benchmark_ohlcv_d)} Kerzen")

output = {
    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
    "benchmark": "DAX",
    "top20": top20,
    "data": data,
    "benchmark_ohlcv_w": benchmark_ohlcv_w,
    "benchmark_ohlcv":   benchmark_ohlcv_d,
}

with open("rs_dax.json", "w") as f:
    json.dump(sanitize_nan(output), f)

size_kb = len(json.dumps(sanitize_nan(output))) / 1024
print(f"\n✅ Fertig! Dateigröße: {size_kb:.0f} KB")
print(f"Timestamp: {output['timestamp']}")
print(f"Ticker gesamt: {len(data)}")
print("Top 5:")
for i, r in enumerate(data[:5]):
    print(f"  {i+1}. {r['ticker']}: Score={r['score']}, Weekly={len(r['ohlcv_w'])} Kerzen, Daily={len(r['ohlcv'])} Kerzen, 4H={len(r['ohlcv_4h'])} Kerzen")
print("\nDatei gespeichert: rs_dax.json")

# ── Top-20-Historie fortschreiben ────────────────────────────────────────────
_hist_file = "rs_top20_history.json"
_date_key  = output["timestamp"][:10]
try:
    with open(_hist_file) as _f:
        _hist = json.load(_f)
except FileNotFoundError:
    _hist = {}
_entries = _hist.setdefault("DAX", [])
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
print(f"Top-20-Historie aktualisiert: DAX {_date_key} → {_hist_file}")
