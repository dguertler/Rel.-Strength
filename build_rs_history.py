"""
Berechnet täglich die Top-20-Rankings für QQQ, SPX und DAX
aus tatsächlichen Kursdaten (yfinance, maximale Verlaufstiefe).

Score-Formel (identisch zu rs_colab.py / dax_colab.py):
  RS_W = (Ticker-Return über W Tage in %) − (Benchmark-Return über W Tage in %)
  Windows: 5T, 10T, 20T, 50T, 6M(126T), 12M(252T)
  score = Summe aller verfügbaren RS_W-Werte

Ergebnis: rs_top20_history.json mit einem Eintrag pro Handelstag
  {"QQQ": [{"date": "YYYY-MM-DD", "top20": [...]}, ...], "SPX": [...], "DAX": [...]}
"""
import subprocess
subprocess.run(["pip", "install", "yfinance", "pandas", "-q"])

import yfinance as yf
import pandas as pd
import json
import os
import time
from datetime import datetime

CONFIG_FILE = "tickers_config.json"
OUT_FILE    = "rs_top20_history.json"

RS_WINDOWS = {"5T": 5, "10T": 10, "20T": 20, "50T": 50, "6M": 126, "12M": 252}
MIN_WINDOW = max(RS_WINDOWS.values())  # 252 Tage – Minimum für vollständige Bewertung
CHUNK_SIZE = 100                        # Ticker pro yfinance-Batch


# ── Daten laden ───────────────────────────────────────────────────────────────

def download_closes(tickers, benchmark):
    """
    Lädt Close-Preise für alle Ticker + Benchmark (maximaler Verlauf, täglich).
    Download in Chunks um Rate-Limits zu vermeiden.
    """
    all_tickers = sorted(set(tickers) | {benchmark})
    frames = []

    for i in range(0, len(all_tickers), CHUNK_SIZE):
        chunk = all_tickers[i : i + CHUNK_SIZE]
        print(f"  Chunk {i // CHUNK_SIZE + 1}/{(len(all_tickers) - 1) // CHUNK_SIZE + 1}"
              f"  ({len(chunk)} Ticker)...")
        for attempt in range(3):
            try:
                raw = yf.download(
                    chunk, period="max", interval="1d",
                    auto_adjust=True, progress=False
                )
                break
            except Exception as e:
                print(f"    Fehler (Versuch {attempt+1}): {e}")
                time.sleep(10 * (attempt + 1))
        else:
            print("    Übersprungen nach 3 Fehlversuchen")
            continue

        if raw.empty:
            continue

        if isinstance(raw.columns, pd.MultiIndex):
            closes = raw["Close"]
        else:
            # Einzelner Ticker
            closes = raw[["Close"]].rename(columns={"Close": chunk[0]})

        frames.append(closes)
        time.sleep(1)  # kurze Pause zwischen Chunks

    if not frames:
        return pd.DataFrame()

    result = pd.concat(frames, axis=1)
    result = result.loc[:, ~result.columns.duplicated()]
    return result


# ── Score-Berechnung ──────────────────────────────────────────────────────────

def compute_daily_top20(closes, tickers, benchmark):
    """
    Vektorisierte Berechnung der täglichen Top-20-Listen.

    Für jeden Handelstag t und jedes Ticker-Fenster W:
      RS_W(t) = (close[t] / close[t-W] - 1)*100 - (bench[t] / bench[t-W] - 1)*100
    score(t) = Σ RS_W(t) über alle W, bei denen close[t-W] verfügbar ist

    Nur Ticker mit vollständiger 252T-History werden gerankt.
    Nur Tage, an denen ≥ 20 Ticker einen gültigen Score haben, werden gespeichert.
    """
    if benchmark not in closes.columns:
        print(f"  FEHLER: Benchmark {benchmark} nicht in den Daten")
        return []

    bench     = closes[benchmark]
    available = [t for t in tickers if t in closes.columns and t != benchmark]

    if len(available) < 20:
        print(f"  FEHLER: nur {len(available)} Ticker verfügbar (Minimum: 20)")
        return []

    print(f"  {len(available)} von {len(tickers)} Tickern mit Kursdaten")

    close = closes[available].copy()

    # ── Score-Matrix aufbauen (vektorisiert) ────────────────────────────────
    # Ergebnis: DataFrame [Datum × Ticker] → RS-Score (Summe aller Fenster)
    score_df = pd.DataFrame(
        0.0, index=closes.index, columns=available, dtype="float64"
    )

    for label, days in RS_WINDOWS.items():
        t_ret = close.pct_change(days) * 100                         # [Datum × Ticker]
        b_ret = bench.pct_change(days) * 100                         # [Datum]
        rs    = t_ret.subtract(b_ret, axis=0)                        # [Datum × Ticker]
        # NaN-bewusstes Aufsummieren: NaN-Fenster werden nicht addiert (≈ current code)
        score_df = score_df.add(rs, fill_value=0)

    # Ticker ohne vollständige 252T-History auf NaN setzen
    has_full_history = close.pct_change(MIN_WINDOW).notna()
    score_df = score_df.where(has_full_history)

    # Nur Tage mit ≥ 20 bewertbaren Tickern
    valid_count = score_df.notna().sum(axis=1)
    valid_dates = score_df.index[valid_count >= 20]

    print(f"  {len(valid_dates)} Handelstage mit ≥ 20 bewertbaren Tickern")
    if valid_dates.empty:
        return []

    print(f"  Erster Tag: {valid_dates[0].date()}  |  Letzter Tag: {valid_dates[-1].date()}")
    print("  Berechne Top-20 pro Tag...")

    daily_top20 = []
    for date in valid_dates:
        row = score_df.loc[date].dropna()
        if len(row) < 20:
            continue
        top20 = row.nlargest(20).index.tolist()
        daily_top20.append({
            "date":  date.strftime("%Y-%m-%d"),
            "top20": top20,
        })

    return daily_top20


# ── Hauptprogramm ─────────────────────────────────────────────────────────────

def main():
    if not os.path.exists(CONFIG_FILE):
        print(f"FEHLER: {CONFIG_FILE} nicht gefunden – zuerst update_tickers.py ausführen")
        return

    with open(CONFIG_FILE) as f:
        config = json.load(f)

    INDICES = {
        "QQQ": {"tickers": config.get("QQQ", []), "benchmark": "QQQ"},
        "SPX": {"tickers": config.get("SPX", []), "benchmark": "^GSPC"},
        "DAX": {"tickers": config.get("DAX", []), "benchmark": "^GDAXI"},
    }

    history = {}

    for index_key, cfg in INDICES.items():
        tickers   = cfg["tickers"]
        benchmark = cfg["benchmark"]

        print(f"\n{'=' * 60}")
        print(f"  {index_key}  |  {len(tickers)} Ticker  |  Benchmark: {benchmark}")
        print(f"{'=' * 60}")

        if not tickers:
            print("  Keine Ticker konfiguriert – übersprungen")
            history[index_key] = []
            continue

        closes = download_closes(tickers, benchmark)

        if closes.empty:
            print("  Keine Kursdaten erhalten")
            history[index_key] = []
            continue

        print(f"  Datenverfügbar: {closes.index[0].date()} – {closes.index[-1].date()}"
              f"  ({len(closes)} Handelstage gesamt)")

        daily_top20 = compute_daily_top20(closes, tickers, benchmark)
        history[index_key] = daily_top20

        if daily_top20:
            print(f"  ✓ {len(daily_top20)} Tage gespeichert")
        else:
            print("  Keine Daten gespeichert")

    # Ohne Einrückung speichern (Dateigröße)
    with open(OUT_FILE, "w") as f:
        json.dump(history, f, separators=(",", ":"))

    size_kb = os.path.getsize(OUT_FILE) / 1024
    print(f"\n{'=' * 60}")
    print(f"✅  Gespeichert: {OUT_FILE}  ({size_kb:.0f} KB)")
    for key in INDICES:
        entries = history.get(key, [])
        if entries:
            print(f"  {key}: {len(entries)} Tage  "
                  f"({entries[0]['date']} – {entries[-1]['date']})")
        else:
            print(f"  {key}: keine Daten")


if __name__ == "__main__":
    main()
