import subprocess
subprocess.run(["pip", "install", "yfinance", "pandas", "matplotlib", "-q"])

import json, os, sys, io, base64, smtplib, time
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from concurrent.futures import ThreadPoolExecutor, as_completed

import yfinance as yf
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# ── Charting Constants ────────────────────────────────────────────────────────
BG_DARK  = '#07090f'
BG_PANEL = '#0a0f1e'
BULL_CLR = '#4ade80'
BEAR_CLR = '#f87171'
GWS_CLR  = '#f59e0b'
TICK_CLR = '#475569'
GRID_CLR = '#1e293b'
TEXT_CLR = '#e2e8f0'

# ── GWS-Analyse (Port aus index.html, identisch zu check_alerts.py) ───────────

def _find_swing_points(highs, lows, n, window=2):
    swing_highs, swing_lows = [], []
    for i in range(window, n - window):
        if all(highs[i] >= highs[i-k] and highs[i] >= highs[i+k] for k in range(1, window+1)):
            swing_highs.append({'idx': i, 'price': highs[i]})
        if all(lows[i] <= lows[i-k] and lows[i] <= lows[i+k] for k in range(1, window+1)):
            swing_lows.append({'idx': i, 'price': lows[i]})
    return swing_highs, swing_lows


def _gws_core(swing_highs, swing_lows, closes, n):
    candidates = []
    for j in range(1, len(swing_lows)):
        tief_neu = swing_lows[j]
        tief_alt = swing_lows[j - 1]
        if tief_neu['price'] < tief_alt['price']:
            hochs = [h for h in swing_highs
                     if tief_alt['idx'] < h['idx'] < tief_neu['idx']]
            if hochs:
                candidates.append(max(hochs, key=lambda h: h['price']))
    gws_high = candidates[-1] if candidates else None
    breakout_idx = None
    if gws_high:
        for i in range(gws_high['idx'] + 1, n):
            if closes[i] > gws_high['price']:
                breakout_idx = i
                break
    return gws_high, breakout_idx


def _get_gws_price(ohlcv, window=2):
    """Gibt nur den GWS-Preis zurück (oder None), ohne Breakout-Analyse."""
    if not ohlcv or len(ohlcv) < 10:
        return None
    n      = len(ohlcv)
    highs  = [c['h'] for c in ohlcv]
    lows   = [c['l'] for c in ohlcv]
    closes = [c['c'] for c in ohlcv]
    sh, sl = _find_swing_points(highs, lows, n, window)
    gws, _ = _gws_core(sh, sl, closes, n)
    return gws['price'] if gws else None


# ── Chart-Rendering ───────────────────────────────────────────────────────────

def render_chart(ohlcv, ticker, timeframe, gws_price=None, n_candles=40, earnings_date=None):
    """Zeichnet Kerzenchart als base64-PNG; markiert optional den Earnings-Tag."""
    if not ohlcv:
        return None
    candles = ohlcv[-n_candles:]
    n = len(candles)

    fig, ax = plt.subplots(figsize=(9, 3.5))
    fig.patch.set_facecolor(BG_DARK)
    ax.set_facecolor(BG_DARK)

    for i, c in enumerate(candles):
        o, h, l, cl = c['o'], c['h'], c['l'], c['c']
        color = BULL_CLR if cl >= o else BEAR_CLR
        ax.plot([i, i], [l, h], color=color, linewidth=0.8, zorder=1)
        body_h = max(abs(cl - o), (h - l) * 0.01)
        rect = mpatches.Rectangle((i - 0.35, min(cl, o)), 0.7, body_h,
                                   facecolor=color, edgecolor=color, zorder=2)
        ax.add_patch(rect)

    if gws_price:
        ax.axhline(gws_price, color=GWS_CLR, linewidth=1.2, linestyle='--',
                   label=f'GWS  {gws_price:.2f}', zorder=3)

    # Earnings-Tag im Daily-Chart als vertikale Linie markieren
    if earnings_date:
        earnings_str = str(earnings_date)
        for i, c in enumerate(candles):
            if c['d'][:10] == earnings_str:
                ax.axvline(i, color='#f97316', linewidth=1.5, linestyle=':',
                           alpha=0.9, label='Earnings', zorder=4)
                break

    all_h = [c['h'] for c in candles]
    all_l = [c['l'] for c in candles]
    price_range = max(all_h) - min(all_l)
    pad = price_range * 0.06
    ax.set_xlim(-1, n)
    ax.set_ylim(min(all_l) - pad, max(all_h) + pad)

    step = max(1, n // 7)
    ax.set_xticks(range(0, n, step))
    ax.set_xticklabels([candles[i]['d'][:10] for i in range(0, n, step)],
                       rotation=25, fontsize=7, color=TICK_CLR, ha='right')
    ax.yaxis.tick_right()
    ax.tick_params(axis='y', colors=TICK_CLR, labelsize=7)
    ax.tick_params(axis='x', length=0)
    for spine in ax.spines.values():
        spine.set_edgecolor(GRID_CLR)
    ax.grid(axis='y', color=GRID_CLR, linewidth=0.5)

    ax.set_title(f'{ticker}  –  {timeframe}', color=TEXT_CLR, fontsize=10,
                 pad=6, loc='left', fontfamily='monospace')

    if gws_price or earnings_date:
        ax.legend(loc='upper left', facecolor=BG_PANEL, edgecolor=GRID_CLR,
                  labelcolor=TEXT_CLR, fontsize=8)

    buf = io.BytesIO()
    fig.tight_layout(pad=0.5)
    fig.savefig(buf, format='png', dpi=120, bbox_inches='tight', facecolor=BG_DARK)
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode('utf-8')


# ── yfinance Earnings-Daten ───────────────────────────────────────────────────

def _fetch_earnings_for_ticker(ticker_symbol, target_date):
    """
    Gibt Earnings-Daten zurück, wenn der Ticker am target_date berichtet hat.
    Sonst None.
    """
    try:
        t  = yf.Ticker(ticker_symbol)
        ed = t.earnings_dates
        if ed is None or ed.empty:
            return None

        for idx in ed.index:
            try:
                d = idx.date()
            except AttributeError:
                d = pd.Timestamp(idx).date()
            if d != target_date:
                continue

            row     = ed.loc[idx]
            eps_act = row.get('Reported EPS')
            if pd.isna(eps_act):
                return None

            eps_est  = row.get('EPS Estimate')
            surprise = row.get('Surprise(%)')

            result = {
                'eps_actual':   float(eps_act),
                'eps_estimate': float(eps_est)  if pd.notna(eps_est)  else None,
                'surprise_pct': float(surprise) if pd.notna(surprise) else None,
            }

            # Umsatz aus Quartalszahlen
            try:
                qf = t.quarterly_financials
                if qf is not None and not qf.empty:
                    for rev_key in ('Total Revenue', 'Revenue'):
                        if rev_key in qf.index:
                            rev_series = qf.loc[rev_key].dropna()
                            if len(rev_series) >= 1:
                                result['revenue'] = float(rev_series.iloc[0])
                            if len(rev_series) >= 5:
                                rev_yoy = float(rev_series.iloc[4])
                                if rev_yoy:
                                    result['revenue_yoy_pct'] = (result['revenue'] / rev_yoy - 1) * 100
                            break
            except Exception:
                pass

            return result
        return None
    except Exception:
        return None


def fetch_earnings_highlights(tickers_data, target_date,
                               min_surprise_pct=5.0, max_workers=6, max_results=15):
    """
    Prüft alle Ticker parallel auf Earnings am target_date.
    Gibt Liste von (ticker_symbol, entry, earnings_data) zurück – sortiert nach Surprise%.
    """
    print(f'Prüfe {len(tickers_data)} Ticker auf Earnings vom {target_date} '
          f'(min. Surprise: +{min_surprise_pct}%)...')
    highlights = []

    def check(item):
        ticker_symbol, entry = item
        data = _fetch_earnings_for_ticker(ticker_symbol, target_date)
        return ticker_symbol, entry, data

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(check, item): item for item in tickers_data}
        done = 0
        for future in as_completed(futures):
            ticker_symbol, entry, earnings_data = future.result()
            done += 1
            if done % 100 == 0:
                print(f'  {done}/{len(tickers_data)} geprüft...')
            if earnings_data is None:
                continue
            sp = earnings_data.get('surprise_pct')
            if sp is not None and sp >= min_surprise_pct:
                print(f'  HIGHLIGHT: {ticker_symbol}  EPS-Surprise {sp:+.1f}%')
                highlights.append((ticker_symbol, entry, earnings_data))

    highlights.sort(key=lambda x: x[2].get('surprise_pct', 0) or 0, reverse=True)
    return highlights[:max_results]


# ── E-Mail ────────────────────────────────────────────────────────────────────

def _earnings_summary_html(earnings_data):
    """Kurze HTML-Zeile mit den Key Facts der Earnings."""
    parts = []
    eps_act  = earnings_data.get('eps_actual')
    eps_est  = earnings_data.get('eps_estimate')
    surprise = earnings_data.get('surprise_pct')
    revenue  = earnings_data.get('revenue')
    rev_yoy  = earnings_data.get('revenue_yoy_pct')

    if eps_act is not None:
        s = f'EPS: <strong>${eps_act:.2f}</strong>'
        if eps_est is not None:
            s += f' (est. ${eps_est:.2f})'
        if surprise is not None:
            clr = '#4ade80' if surprise >= 0 else '#f87171'
            sign = '+' if surprise >= 0 else ''
            s += f'&nbsp;<span style="color:{clr}">{sign}{surprise:.1f}%</span>'
        parts.append(s)

    if revenue is not None:
        rev_bn = revenue / 1e9
        s = f'Revenue: <strong>${rev_bn:.1f}bn</strong>'
        if rev_yoy is not None:
            clr = '#4ade80' if rev_yoy >= 0 else '#f87171'
            sign = '+' if rev_yoy >= 0 else ''
            s += f'&nbsp;<span style="color:{clr}">{sign}{rev_yoy:.1f}% YoY</span>'
        parts.append(s)

    sep = '&nbsp;&nbsp;<span style="color:#475569">|</span>&nbsp;&nbsp;'
    return sep.join(parts)


def send_earnings_email(highlights, smtp_host, smtp_port, smtp_user, smtp_pass,
                        to_addr, target_date):
    today_str = datetime.now().strftime('%d.%m.%Y')
    subject   = (f'Earnings-Highlights {today_str}: '
                 f'{len(highlights)} Aktie(n) mit starken Quartalszahlen')

    msg = MIMEMultipart('related')
    msg['Subject'] = subject
    msg['From']    = smtp_user
    msg['To']      = to_addr

    html_parts = [f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="background:#060b14;color:#e2e8f0;font-family:monospace;
             padding:24px;max-width:780px;margin:0 auto">
  <h2 style="color:#fb923c;margin:0 0 4px">
    Earnings-Highlights &mdash; {today_str}
  </h2>
  <p style="color:#64748b;margin:0 0 24px;font-size:12px">
    Folgende Aktien haben gestern Quartalszahlen gemeldet und die Erwartungen
    deutlich &uuml;bertroffen &mdash; potenzielle Turnaround-Kandidaten:
  </p>
"""]

    cid_counter = 0
    inline_imgs = []

    for ticker_symbol, entry, earnings_data in highlights:
        display_ticker = ticker_symbol.replace('.DE', '') if ticker_symbol.endswith('.DE') else ticker_symbol
        score  = entry.get('score', 0)
        source = entry.get('_source', 'SPX')

        if source == 'DAX':
            dashboard_url   = 'https://dguertler.github.io/Rel.-Strength/dax.html'
            dashboard_label = 'DAX-Dashboard'
        elif source == 'QQQ':
            dashboard_url   = 'https://dguertler.github.io/Rel.-Strength/'
            dashboard_label = 'Nasdaq-Dashboard'
        else:
            dashboard_url   = 'https://dguertler.github.io/Rel.-Strength/sp500.html'
            dashboard_label = 'S&amp;P 500-Dashboard'

        sp = earnings_data.get('surprise_pct')
        surprise_badge = ''
        if sp is not None:
            clr  = '#4ade80' if sp >= 0 else '#f87171'
            sign = '+' if sp >= 0 else ''
            surprise_badge = (
                f'<span style="font-size:10px;font-weight:bold;color:#0f172a;'
                f'background:{clr};border-radius:4px;padding:1px 6px;'
                f'letter-spacing:0.5px">{sign}{sp:.1f}%</span>'
            )

        html_parts.append(f"""
  <div style="margin:0 0 28px;padding:16px;
              background:#12100a;border:1px solid #f97316;
              border-left:4px solid #f97316;border-radius:8px">
    <div style="display:flex;align-items:center;gap:12px;margin-bottom:10px;flex-wrap:wrap">
      <span style="font-size:18px">&#128202;</span>
      <span style="font-size:16px;font-weight:bold;color:#fb923c">{display_ticker}</span>
      <span style="font-size:10px;font-weight:bold;color:#0f172a;
             background:#f97316;border-radius:4px;padding:1px 6px;
             letter-spacing:0.5px">NEWS!</span>
      {surprise_badge}
      <span style="font-size:11px;color:#64748b">({source})</span>
      <span style="margin-left:auto;font-size:11px;color:#94a3b8">
        RS-Score:&nbsp;<strong style="color:#f1f5f9">{score:.1f}</strong>
      </span>
    </div>
    <div style="font-size:12px;margin-bottom:8px">
      <a href="{dashboard_url}" style="color:#3b82f6;font-size:11px;
         text-decoration:none">&rarr; {dashboard_label}</a>
    </div>
""")

        # Charts: Weekly (kein Earnings-Marker), Daily (mit Marker), 4H
        gws_w  = _get_gws_price(entry.get('ohlcv_w',  []), window=1)
        gws_d  = _get_gws_price(entry.get('ohlcv',    []), window=2)
        gws_4h = _get_gws_price(entry.get('ohlcv_4h', []), window=2)

        chart_specs = [
            (entry.get('ohlcv_w',  []), 'Weekly (letzten 30 Kerzen)',  gws_w,  30, None),
            (entry.get('ohlcv',    []), 'Daily (letzten 40 Kerzen)',   gws_d,  40, target_date),
            (entry.get('ohlcv_4h', []), '4H (letzten 60 Kerzen)',      gws_4h, 60, None),
        ]
        for ohlcv_data, tf_label, gws_price, n_c, earn_date in chart_specs:
            b64 = render_chart(ohlcv_data, display_ticker, tf_label,
                               gws_price=gws_price, n_candles=n_c,
                               earnings_date=earn_date)
            if b64:
                cid = f'chart_{cid_counter}'
                cid_counter += 1
                inline_imgs.append((cid, b64))
                html_parts.append(
                    f'    <img src="cid:{cid}" '
                    f'style="width:100%;max-width:720px;display:block;'
                    f'margin:6px 0;border-radius:6px">\n'
                )

        # Earnings-Summary unter den Charts
        summary_html = _earnings_summary_html(earnings_data)
        if summary_html:
            html_parts.append(f"""
    <div style="margin-top:10px;padding:8px 12px;background:#1a1a0f;
                border-radius:6px;font-size:12px;color:#94a3b8;line-height:1.8">
      <span style="color:#f97316;font-weight:bold">&#9650; Earnings Q-Zahlen:&nbsp;</span>
      {summary_html}
    </div>
""")

        html_parts.append('  </div>\n')

    html_parts.append("""
  <p style="font-size:10px;color:#334155;margin-top:24px">
    Generiert von RS-Dashboard &middot; earnings_alerts.py
  </p>
</body></html>""")

    html_body = ''.join(html_parts)
    msg_alt = MIMEMultipart('alternative')
    msg_alt.attach(MIMEText(html_body, 'html', 'utf-8'))
    msg.attach(msg_alt)

    for cid, b64_data in inline_imgs:
        img_data = base64.b64decode(b64_data)
        img = MIMEImage(img_data, 'png')
        img.add_header('Content-ID',          f'<{cid}>')
        img.add_header('Content-Disposition', 'inline', filename=f'{cid}.png')
        msg.attach(img)

    with smtplib.SMTP(smtp_host, int(smtp_port)) as server:
        server.ehlo()
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, to_addr, msg.as_bytes())

    print(f'Earnings-Mail gesendet an {to_addr}  ({len(highlights)} Aktien)')


# ── Hauptprogramm ─────────────────────────────────────────────────────────────

def main():
    smtp_host = os.environ.get('SMTP_HOST', '')
    smtp_port = os.environ.get('SMTP_PORT', '587')
    smtp_user = os.environ.get('SMTP_USER', '')
    smtp_pass = os.environ.get('SMTP_PASS', '')
    to_addr   = os.environ.get('ALERT_EMAIL_TO', '')

    if not all([smtp_host, smtp_user, smtp_pass, to_addr]):
        print('FEHLER: Bitte SMTP_HOST, SMTP_USER, SMTP_PASS und ALERT_EMAIL_TO setzen.')
        sys.exit(1)

    # "Gestern" im UTC-Kontext (Workflow läuft früh morgens UTC)
    yesterday = (datetime.utcnow() - timedelta(days=1)).date()

    # Wochenenden überspringen
    if yesterday.weekday() >= 5:
        print(f'Kein Handelstag: {yesterday} ist Wochenende. Abbruch.')
        return

    print(f'earnings_alerts.py  –  Earnings-Check für {yesterday}')

    # Ticker aus allen RS-JSON-Dateien laden (SPX hat Vorrang bei Duplikaten)
    seen        = {}
    tickers_data = []
    for json_path, source_label in [('rs_sp500.json', 'SPX'), ('rs_full.json', 'QQQ')]:
        if not os.path.exists(json_path):
            print(f'Datei nicht gefunden: {json_path}')
            continue
        with open(json_path) as f:
            data = json.load(f)
        for entry in data.get('data', []):
            t = entry['ticker']
            if t not in seen:
                entry['_source'] = source_label
                seen[t] = entry
                tickers_data.append((t, entry))

    print(f'{len(tickers_data)} Ticker geladen.')

    min_surprise  = float(os.environ.get('MIN_SURPRISE_PCT', '5.0'))
    max_highlights = int(os.environ.get('MAX_HIGHLIGHTS', '15'))

    highlights = fetch_earnings_highlights(
        tickers_data, yesterday,
        min_surprise_pct=min_surprise,
        max_results=max_highlights,
    )

    print(f'\n{len(highlights)} Earnings-Highlights gefunden.')

    if highlights:
        send_earnings_email(highlights, smtp_host, smtp_port,
                            smtp_user, smtp_pass, to_addr, yesterday)
    else:
        print('Keine relevanten Earnings-Highlights heute.')


if __name__ == '__main__':
    main()
