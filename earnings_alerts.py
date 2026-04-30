import subprocess
subprocess.run(["pip", "install", "yfinance", "pandas", "matplotlib", "requests", "-q"])

import json, os, sys, io, base64, smtplib, requests
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

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

# ── GWS-Analyse (identisch zu check_alerts.py) ────────────────────────────────

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

    if earnings_date:
        for i, c in enumerate(candles):
            if c['d'][:10] == str(earnings_date):
                ax.axvline(i, color='#f97316', linewidth=1.5, linestyle=':',
                           alpha=0.9, label='Earnings', zorder=4)
                break

    all_h = [c['h'] for c in candles]
    all_l = [c['l'] for c in candles]
    pad   = (max(all_h) - min(all_l)) * 0.06
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


# ── Finnhub Earnings-Kalender ─────────────────────────────────────────────────

def get_finnhub_earnings(target_date, api_key):
    """
    Holt alle Earnings-Ergebnisse von Finnhub für target_date.
    Gibt Liste von Dicts zurück (symbol, epsActual, epsEstimate, revenue, hour, ...).
    """
    try:
        resp = requests.get(
            'https://finnhub.io/api/v1/calendar/earnings',
            params={'from': str(target_date), 'to': str(target_date), 'token': api_key},
            timeout=30,
        )
        resp.raise_for_status()
        items = resp.json().get('earningsCalendar', [])
        print(f'Finnhub: {len(items)} Earnings-Einträge für {target_date}')
        return items
    except Exception as e:
        print(f'Finnhub-Fehler: {e}')
        return []


def build_highlights(finnhub_items, ticker_map, min_surprise_pct=5.0, max_results=15):
    """
    Filtert Finnhub-Ergebnisse:
    - Nur Ticker die in unserem Universum (rs_sp500/rs_full) sind
    - EPS-Surprise >= min_surprise_pct
    Sortiert nach Surprise% absteigend.
    """
    highlights = []

    for item in finnhub_items:
        symbol  = item.get('symbol', '')
        if symbol not in ticker_map:
            continue

        eps_act = item.get('epsActual')
        eps_est = item.get('epsEstimate')

        if eps_act is None:
            continue  # noch nicht gemeldet

        # Surprise%: (Actual - Estimate) / |Estimate|
        surprise_pct = None
        if eps_est is not None and eps_est != 0:
            surprise_pct = (eps_act - eps_est) / abs(eps_est) * 100

        if surprise_pct is None or surprise_pct < min_surprise_pct:
            continue

        rev_act = item.get('revenueActual')
        rev_est = item.get('revenueEstimate')
        hour    = item.get('hour', '')   # 'bmo' = before market open, 'amc' = after market close

        print(f'  HIGHLIGHT: {symbol}  EPS {surprise_pct:+.1f}%'
              f'  ({hour if hour else "?"})')

        highlights.append((symbol, ticker_map[symbol], {
            'eps_actual':        eps_act,
            'eps_estimate':      eps_est,
            'surprise_pct':      surprise_pct,
            'revenue':           rev_act,
            'revenue_estimate':  rev_est,
            'hour':              hour,
        }))

    highlights.sort(key=lambda x: x[2]['surprise_pct'], reverse=True)
    return highlights[:max_results]


# ── E-Mail ────────────────────────────────────────────────────────────────────

def _hour_label(hour):
    if hour == 'bmo':
        return 'vor Börseneröffnung'
    if hour == 'amc':
        return 'nach Börsenschluss'
    return ''


def _earnings_summary_html(ed):
    parts = []

    eps_act  = ed.get('eps_actual')
    eps_est  = ed.get('eps_estimate')
    surprise = ed.get('surprise_pct')
    rev_act  = ed.get('revenue')
    rev_est  = ed.get('revenue_estimate')

    if eps_act is not None:
        s = f'EPS: <strong>${eps_act:.2f}</strong>'
        if eps_est is not None:
            s += f' (est. ${eps_est:.2f})'
        if surprise is not None:
            clr  = '#4ade80' if surprise >= 0 else '#f87171'
            sign = '+' if surprise >= 0 else ''
            s += f'&nbsp;<span style="color:{clr}">{sign}{surprise:.1f}%</span>'
        parts.append(s)

    if rev_act is not None:
        rev_bn = rev_act / 1e9
        s = f'Revenue: <strong>${rev_bn:.1f}bn</strong>'
        if rev_est is not None:
            rev_est_bn = rev_est / 1e9
            rev_beat = (rev_act / rev_est - 1) * 100
            clr  = '#4ade80' if rev_beat >= 0 else '#f87171'
            sign = '+' if rev_beat >= 0 else ''
            s += f' (est. ${rev_est_bn:.1f}bn&nbsp;<span style="color:{clr}">{sign}{rev_beat:.1f}%</span>)'
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
    Folgende Aktien haben gestern ({target_date}) Quartalszahlen gemeldet
    und die Erwartungen deutlich &uuml;bertroffen:
  </p>
"""]

    cid_counter = 0
    inline_imgs = []

    for ticker_symbol, entry, ed in highlights:
        display = ticker_symbol.replace('.DE', '') if ticker_symbol.endswith('.DE') else ticker_symbol
        score   = entry.get('score', 0)
        source  = entry.get('_source', 'SPX')
        hour    = ed.get('hour', '')

        if source == 'DAX':
            dash_url, dash_lbl = 'https://dguertler.github.io/Rel.-Strength/dax.html', 'DAX-Dashboard'
        elif source == 'QQQ':
            dash_url, dash_lbl = 'https://dguertler.github.io/Rel.-Strength/', 'Nasdaq-Dashboard'
        else:
            dash_url, dash_lbl = 'https://dguertler.github.io/Rel.-Strength/sp500.html', 'S&amp;P 500-Dashboard'

        sp   = ed.get('surprise_pct', 0)
        clr  = '#4ade80' if sp >= 0 else '#f87171'
        sign = '+' if sp >= 0 else ''
        surprise_badge = (
            f'<span style="font-size:10px;font-weight:bold;color:#0f172a;'
            f'background:{clr};border-radius:4px;padding:1px 6px;'
            f'letter-spacing:0.5px">{sign}{sp:.1f}%</span>'
        )

        hour_badge = ''
        if hour:
            hl = _hour_label(hour)
            hour_badge = (
                f'<span style="font-size:10px;color:#94a3b8;'
                f'border:1px solid #334155;border-radius:4px;padding:1px 6px">'
                f'{hl}</span>'
            )

        html_parts.append(f"""
  <div style="margin:0 0 28px;padding:16px;
              background:#12100a;border:1px solid #f97316;
              border-left:4px solid #f97316;border-radius:8px">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;flex-wrap:wrap">
      <span style="font-size:18px">&#128202;</span>
      <span style="font-size:16px;font-weight:bold;color:#fb923c">{display}</span>
      <span style="font-size:10px;font-weight:bold;color:#0f172a;
             background:#f97316;border-radius:4px;padding:1px 6px;
             letter-spacing:0.5px">NEWS!</span>
      {surprise_badge}
      {hour_badge}
      <span style="font-size:11px;color:#64748b">({source})</span>
      <span style="margin-left:auto;font-size:11px;color:#94a3b8">
        RS-Score:&nbsp;<strong style="color:#f1f5f9">{score:.1f}</strong>
      </span>
    </div>
    <div style="font-size:12px;margin-bottom:8px">
      <a href="{dash_url}" style="color:#3b82f6;font-size:11px;
         text-decoration:none">&rarr; {dash_lbl}</a>
    </div>
""")

        gws_w  = _get_gws_price(entry.get('ohlcv_w',  []), window=1)
        gws_d  = _get_gws_price(entry.get('ohlcv',    []), window=2)
        gws_4h = _get_gws_price(entry.get('ohlcv_4h', []), window=2)

        for ohlcv_data, tf_label, gws_price, n_c in [
            (entry.get('ohlcv_w',  []), 'Weekly (letzten 30 Kerzen)',  gws_w,  30),
            (entry.get('ohlcv',    []), 'Daily (letzten 40 Kerzen)',   gws_d,  40),
            (entry.get('ohlcv_4h', []), '4H (letzten 60 Kerzen)',      gws_4h, 60),
        ]:
            b64 = render_chart(ohlcv_data, display, tf_label,
                               gws_price=gws_price, n_candles=n_c,
                               earnings_date=target_date)
            if b64:
                cid = f'chart_{cid_counter}'
                cid_counter += 1
                inline_imgs.append((cid, b64))
                html_parts.append(
                    f'    <img src="cid:{cid}" style="width:100%;max-width:720px;'
                    f'display:block;margin:6px 0;border-radius:6px">\n'
                )

        summary = _earnings_summary_html(ed)
        if summary:
            html_parts.append(f"""
    <div style="margin-top:10px;padding:8px 12px;background:#1a1a0f;
                border-radius:6px;font-size:12px;color:#94a3b8;line-height:1.8">
      <span style="color:#f97316;font-weight:bold">&#9650; Earnings:&nbsp;</span>
      {summary}
    </div>
""")

        html_parts.append('  </div>\n')

    html_parts.append("""
  <p style="font-size:10px;color:#334155;margin-top:24px">
    Generiert von RS-Dashboard &middot; earnings_alerts.py &middot; Daten: Finnhub
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
    smtp_host   = os.environ.get('SMTP_HOST', '')
    smtp_port   = os.environ.get('SMTP_PORT', '587')
    smtp_user   = os.environ.get('SMTP_USER', '')
    smtp_pass   = os.environ.get('SMTP_PASS', '')
    to_addr     = os.environ.get('ALERT_EMAIL_TO', '')
    finnhub_key = os.environ.get('FINNHUB_API_KEY', '')

    if not all([smtp_host, smtp_user, smtp_pass, to_addr, finnhub_key]):
        print('FEHLER: SMTP_HOST, SMTP_USER, SMTP_PASS, ALERT_EMAIL_TO '
              'und FINNHUB_API_KEY müssen gesetzt sein.')
        sys.exit(1)

    yesterday = (datetime.utcnow() - timedelta(days=1)).date()

    if yesterday.weekday() >= 5:
        print(f'Kein Handelstag: {yesterday} ist Wochenende. Abbruch.')
        return

    print(f'earnings_alerts.py  –  Earnings-Check für {yesterday}')

    # Ticker-Universum laden (SPX hat Vorrang bei Duplikaten)
    ticker_map = {}
    for json_path, source_label in [('rs_sp500.json', 'SPX'), ('rs_full.json', 'QQQ')]:
        if not os.path.exists(json_path):
            print(f'Datei nicht gefunden: {json_path}')
            continue
        with open(json_path) as f:
            data = json.load(f)
        for entry in data.get('data', []):
            t = entry['ticker']
            if t not in ticker_map:
                entry['_source'] = source_label
                ticker_map[t] = entry

    print(f'{len(ticker_map)} Ticker geladen.')

    # Finnhub: Earnings für gestern
    finnhub_items = get_finnhub_earnings(yesterday, finnhub_key)

    min_surprise  = float(os.environ.get('MIN_SURPRISE_PCT', '5.0'))
    max_highlights = int(os.environ.get('MAX_HIGHLIGHTS', '15'))

    highlights = build_highlights(
        finnhub_items, ticker_map,
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
