import subprocess
subprocess.run(["pip", "install", "yfinance", "pandas", "-q"])

import yfinance as yf
import pandas as pd
import json
from datetime import datetime

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

# ── Schritt 2: OHLCV nur für Top 20 laden ─────────────────────────────────
print("\nSchritt 2: OHLCV für Top 20...")
raw_top = yf.download(top20, period="3mo", auto_adjust=True, progress=False)

def extract_ohlcv(ticker, raw_data):
    """Extrahiert OHLCV-Daten für einen Ticker aus dem yfinance-Download."""
    try:
        c = raw_data["Close"][ticker].dropna()
        o = raw_data["Open"][ticker].reindex(c.index)
        h = raw_data["High"][ticker].reindex(c.index)
        l = raw_data["Low"][ticker].reindex(c.index)
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
        return result
    except Exception as e:
        print(f"  Fehler OHLCV {ticker}: {e}")
        return []

# ── Schritt 3: Ausgabe zusammenbauen ──────────────────────────────────────
data = []
for r in all_results:
    ticker = r["ticker"]
    ohlcv = extract_ohlcv(ticker, raw_top) if ticker in top20 else []
    data.append({
        "ticker": ticker,
        "score": r["score"],
        "windows": r["windows"],
        "ohlcv": ohlcv        # leer [] für alle Nicht-Top-20 Ticker
    })

output = {
    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
    "benchmark": "QQQ",
    "top20": top20,
    "data": data
}

with open("rs_full.json", "w") as f:
    json.dump(output, f)

size_kb = len(json.dumps(output)) / 1024
print(f"\n✅ Fertig! Dateigröße: {size_kb:.0f} KB")
print(f"Timestamp: {output['timestamp']}")
print(f"Ticker gesamt: {len(data)}")
print("Top 5:")
for i, r in enumerate(data[:5]):
    print(f"  {i+1}. {r['ticker']}: Score={r['score']}, OHLCV={len(r['ohlcv'])} Kerzen")
print("\nDatei gespeichert: rs_full.json")
