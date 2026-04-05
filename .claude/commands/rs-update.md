# RS QQQ Update

Führe das folgende Python-Skript aus, um die RS-Daten für alle QQQ-Aktien zu berechnen und `rs_full.json` zu aktualisieren. Danach committe und pushe die Datei nach GitHub auf den aktuellen Branch.

```python
import yfinance as yf
import pandas as pd
import json
from datetime import datetime, timedelta

tickers = [
    "AAPL", "MSFT", "NVDA", "AMZN", "META", "GOOGL", "GOOG", "TSLA", "AVGO", "COST",
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

benchmark = "QQQ"
rs_windows = {"5T": 5, "10T": 10, "20T": 20, "50T": 50, "6M": 126, "12M": 252}

# ── Schritt 1: RS-Score für alle Ticker ───────────────────────────────────
print(f"Schritt 1: RS-Berechnung für alle {len(tickers)} Aktien...")
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

# ── Schritt 2: Weekly OHLCV für ALLE Ticker (letzte 60 Wochen = ~15 Monate)
print(f"\nSchritt 2: Weekly OHLCV für alle {len(tickers)} Ticker (60 Wochen)...")
end_date = datetime.now()
start_weekly = end_date - timedelta(days=450)

all_tickers_list = [r["ticker"] for r in all_results]
raw_weekly = yf.download(
    all_tickers_list + [benchmark],
    start=start_weekly.strftime("%Y-%m-%d"),
    end=end_date.strftime("%Y-%m-%d"),
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

# ── Schritt 3: Daily OHLCV für ALLE Ticker (letzte 60 Kerzen ≈ 3 Monate)
print(f"\nSchritt 3: Daily OHLCV für alle {len(tickers)} Ticker (60 Kerzen)...")
start_daily = end_date - timedelta(days=100)

raw_daily = yf.download(
    all_tickers_list + [benchmark],
    start=start_daily.strftime("%Y-%m-%d"),
    end=end_date.strftime("%Y-%m-%d"),
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

# ── Schritt 4: 4H OHLCV für ALLE Ticker (letzte 60 Kerzen ≈ 30 Handelstage)
print(f"\nSchritt 4: 4H OHLCV für alle {len(tickers)} Ticker (60 Kerzen ≈ 30 Tage)...")
start_4h = end_date - timedelta(days=45)

def extract_ohlcv_4h(ticker, n_candles=60):
    try:
        df = yf.download(
            ticker,
            start=start_4h.strftime("%Y-%m-%d"),
            end=end_date.strftime("%Y-%m-%d"),
            interval="1h",
            auto_adjust=True,
            progress=False
        )
        if df.empty:
            return []
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df[["Open", "High", "Low", "Close"]].dropna()
        df.index = pd.to_datetime(df.index)
        df_4h = df.resample("4h", offset="1h30min").agg({
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

# ── Schritt 5: Ausgabe zusammenbauen ──────────────────────────────────────
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

with open("rs_full.json", "w") as f:
    json.dump(data, f)

output_size = len(json.dumps(data)) / 1024
print(f"\n✅ Fertig! Dateigröße: {output_size:.0f} KB")
print(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
print(f"Ticker gesamt: {len(data)}")
print("Top 5:")
for i, r in enumerate(data[:5]):
    print(f"  {i+1}. {r['ticker']}: Score={r['score']}, Weekly={len(r['ohlcv_w'])} Kerzen, Daily={len(r['ohlcv'])} Kerzen, 4H={len(r['ohlcv_4h'])} Kerzen")
```

Führe anschließend diese Schritte aus:

1. Schreibe den obigen Python-Code in eine temporäre Datei `/tmp/rs_run.py`
2. Führe aus: `python3 /tmp/rs_run.py`
3. Committe und pushe `rs_full.json` nach GitHub:
   ```
   git add rs_full.json
   git commit -m "RS Daten aktualisiert"
   git push
   ```
4. Lösche die temporäre Datei: `rm /tmp/rs_run.py`
