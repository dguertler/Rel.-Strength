"""
Berechnet täglich die Top-20-Rankings für QQQ, SPX und DAX
aus tatsächlichen Kursdaten (yfinance).

Aufruf:
  python build_rs_history.py           → alle 3 Indizes
  python build_rs_history.py QQQ       → nur QQQ
  python build_rs_history.py SPX       → nur SPX
  python build_rs_history.py DAX       → nur DAX

Score-Formel (identisch zu rs_colab.py):
  RS_W = (Ticker-Return über W Tage in %) − (Benchmark-Return über W Tage in %)
  Windows: 5T, 10T, 20T, 50T, 6M(126T), 12M(252T)
  score = Summe aller verfügbaren RS_W-Werte
"""
import sys
import json
import os
import time
from datetime import datetime, date

import yfinance as yf
import pandas as pd

CONFIG_FILE   = "tickers_config.json"
OUT_FILE      = "rs_top20_history.json"

RS_WINDOWS    = {"5T": 5, "10T": 10, "20T": 20, "50T": 50, "6M": 126, "12M": 252}
MIN_WINDOW    = max(RS_WINDOWS.values())   # 252
HISTORY_START = "2018-01-01"              # ~7 Jahre – deckt alle RS-Fenster ab
CHUNK_SIZE    = 50                         # kleine Chunks gegen Rate-Limits


# ── Download ──────────────────────────────────────────────────────────────────

def download_closes(tickers, benchmark, start=HISTORY_START):
    all_tickers = sorted(set(tickers) | {benchmark})
    print(f"  {len(all_tickers)} Ticker, Chunks à {CHUNK_SIZE}, ab {start}")
    frames = []
    n_ok, n_fail, n_empty = 0, 0, 0

    for i in range(0, len(all_tickers), CHUNK_SIZE):
        chunk = all_tickers[i : i + CHUNK_SIZE]
        ci = i // CHUNK_SIZE + 1
        ct = (len(all_tickers) - 1) // CHUNK_SIZE + 1
        print(f"  Chunk {ci}/{ct}  ({len(chunk)} Ticker)...", flush=True)

        raw = None
        for attempt in range(3):
            try:
                r = yf.download(
                    chunk, start=start, interval="1d",
                    auto_adjust=True, progress=False,
                    timeout=60
                )
                if not r.empty:
                    raw = r
                    break
                # Leeres Ergebnis → retry
                wait = 20 * (attempt + 1)
                print(f"    Versuch {attempt+1}: leer → warte {wait}s", flush=True)
                time.sleep(wait)
            except Exception as e:
                wait = 20 * (attempt + 1)
                print(f"    Fehler Versuch {attempt+1}: {e}  → warte {wait}s", flush=True)
                time.sleep(wait)

        if raw is None or raw.empty:
            print(f"    → nach 3 Versuchen fehlgeschlagen", flush=True)
            n_fail += 1
            continue

        if isinstance(raw.columns, pd.MultiIndex):
            closes = raw["Close"]
        else:
            # Einzelner Ticker: Spalten heißen Open/High/Low/Close/Volume
            closes = raw[["Close"]].rename(columns={"Close": chunk[0]})

        # Nur Spalten mit ausreichend Daten behalten
        keeps = [c for c in closes.columns if closes[c].notna().sum() >= MIN_WINDOW]
        if keeps:
            frames.append(closes[keeps])
            n_ok += 1
        else:
            n_empty += 1
            print(f"    → alle Spalten ohne ausreichend Daten")

        time.sleep(2)   # Pause zwischen Chunks

    print(f"  Download: {n_ok} Chunks ok, {n_fail} fehlgeschlagen, {n_empty} leer")

    if not frames:
        return pd.DataFrame()

    result = pd.concat(frames, axis=1)
    result = result.loc[:, ~result.columns.duplicated()]
    print(f"  DataFrame: {len(result)} Handelstage × {len(result.columns)} Ticker")
    return result


# ── Score-Berechnung ──────────────────────────────────────────────────────────

def compute_daily_top20(closes, tickers, benchmark):
    if benchmark not in closes.columns:
        print(f"  FEHLER: Benchmark {benchmark} nicht in Daten")
        return []

    bench     = closes[benchmark]
    available = [t for t in tickers if t in closes.columns and t != benchmark]

    if len(available) < 20:
        print(f"  FEHLER: nur {len(available)} Ticker verfügbar (min. 20)")
        return []

    print(f"  {len(available)}/{len(tickers)} Ticker mit Daten")
    close = closes[available].copy()

    # Vektorisierter RS-Score über alle Fenster
    score_df = pd.DataFrame(0.0, index=closes.index, columns=available)
    for label, days in RS_WINDOWS.items():
        t_ret = close.pct_change(days) * 100
        b_ret = bench.pct_change(days) * 100
        rs    = t_ret.subtract(b_ret, axis=0)
        score_df = score_df.add(rs, fill_value=0)

    # Nur Ticker mit vollständiger 252T-History einbeziehen
    has_history = close.pct_change(MIN_WINDOW).notna()
    score_df    = score_df.where(has_history)

    valid_count = score_df.notna().sum(axis=1)
    valid_dates = score_df.index[valid_count >= 20]

    if valid_dates.empty:
        print("  Keine Tage mit ≥ 20 bewertbaren Tickern")
        return []

    print(f"  {len(valid_dates)} Handelstage  ({valid_dates[0].date()} – {valid_dates[-1].date()})")

    daily_top20 = []
    for dt in valid_dates:
        row = score_df.loc[dt].dropna()
        if len(row) < 20:
            continue
        top20 = row.nlargest(20).index.tolist()
        daily_top20.append({"date": dt.strftime("%Y-%m-%d"), "top20": top20})

    return daily_top20


# ── Hilfsfunktionen ───────────────────────────────────────────────────────────

def load_history():
    if os.path.exists(OUT_FILE):
        try:
            with open(OUT_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def save_history(history):
    with open(OUT_FILE, "w") as f:
        json.dump(history, f, separators=(",", ":"))
    kb = os.path.getsize(OUT_FILE) / 1024
    print(f"  Gespeichert: {OUT_FILE}  ({kb:.0f} KB)")


# ── Hauptprogramm ─────────────────────────────────────────────────────────────

def main():
    if not os.path.exists(CONFIG_FILE):
        print(f"FEHLER: {CONFIG_FILE} nicht gefunden")
        sys.exit(1)

    with open(CONFIG_FILE) as f:
        config = json.load(f)

    # Welche Indizes sollen berechnet werden?
    requested = [a.upper() for a in sys.argv[1:]] if len(sys.argv) > 1 else ["QQQ", "SPX", "DAX"]

    INDICES = {
        "QQQ": {"tickers": config.get("QQQ", []), "benchmark": "QQQ"},
        "SPX": {"tickers": config.get("SPX", []), "benchmark": "^GSPC"},
        "DAX": {"tickers": config.get("DAX", []), "benchmark": "^GDAXI"},
    }

    history = load_history()

    for index_key in requested:
        if index_key not in INDICES:
            print(f"Unbekannter Index: {index_key}  (QQQ / SPX / DAX)")
            continue

        cfg       = INDICES[index_key]
        tickers   = cfg["tickers"]
        benchmark = cfg["benchmark"]

        print(f"\n{'='*60}")
        print(f"  {index_key}  |  {len(tickers)} Ticker  |  Benchmark: {benchmark}")
        print(f"{'='*60}")

        if not tickers:
            print("  Keine Ticker – übersprungen")
            history[index_key] = []
            continue

        closes = download_closes(tickers, benchmark)

        if closes.empty:
            print("  Keine Kursdaten – Index übersprungen")
            # Bestehende History NICHT überschreiben bei Fehlschlag
            continue

        print(f"  Zeitraum gesamt: {closes.index[0].date()} – {closes.index[-1].date()}")

        daily_top20 = compute_daily_top20(closes, tickers, benchmark)
        history[index_key] = daily_top20

        # Sofort nach jedem Index speichern
        save_history(history)

        if daily_top20:
            print(f"  ✓ {len(daily_top20)} Tage berechnet")
        else:
            print("  Keine Ergebnisse")

    print(f"\n{'='*60}")
    print("Zusammenfassung:")
    for key in ["QQQ", "SPX", "DAX"]:
        entries = history.get(key, [])
        if entries:
            print(f"  {key}: {len(entries)} Tage  ({entries[0]['date']} – {entries[-1]['date']})")
        else:
            print(f"  {key}: keine Daten")


if __name__ == "__main__":
    main()
