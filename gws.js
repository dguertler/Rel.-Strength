// ── GWS-Analyse: zentrale Logik für alle Dashboards ─────────────────────────
//
// Ein Down-Retracement entsteht ERST wenn ein vorheriges Swing-Tief unterschritten wird.
// Das GWS ist dann das HÖCHSTE Hoch zwischen dem alten Tief und dem neuen tieferen Tief.
//
// Ablauf:
//   1. Sequenz von Swing-Hochs und Swing-Tiefs ermitteln
//   2. Suche tiefere Tiefs (jedes Swing-Tief, das ein vorheriges Swing-Tief unterschreitet)
//   3. Für jedes tiefere Tief: GWS = höchstes Hoch zwischen dem alten Tief und dem neuen Tief
//   4. Aktuelles GWS = letztes so ermitteltes Hoch
//   5. Bullish = Close über GWS Preis

// ── GWS-D Analyse (Daily, ±2 Bars) ──────────────────────────────────────────
function analyzeStructure(ohlcv) {
  if (!ohlcv || ohlcv.length < 10) return null;
  const n      = ohlcv.length;
  const highs  = ohlcv.map(d => d.h);
  const lows   = ohlcv.map(d => d.l);
  const closes = ohlcv.map(d => d.c);

  // Swing-Hochs (±2 Bars)
  const swingHighs = [];
  for (let i = 2; i < n - 2; i++) {
    if (highs[i] >= highs[i-1] && highs[i] >= highs[i-2] &&
        highs[i] >= highs[i+1] && highs[i] >= highs[i+2])
      swingHighs.push({ idx: i, date: ohlcv[i].d, price: highs[i] });
  }

  // Swing-Tiefs (±2 Bars)
  const swingLows = [];
  for (let i = 2; i < n - 2; i++) {
    if (lows[i] <= lows[i-1] && lows[i] <= lows[i-2] &&
        lows[i] <= lows[i+1] && lows[i] <= lows[i+2])
      swingLows.push({ idx: i, date: ohlcv[i].d, price: lows[i] });
  }

  // Kernlogik: tiefere Tiefs → GWS-D = höchstes Hoch dazwischen
  const gwsdCandidates = [];
  let lastGwsdDefLow = null;
  for (let j = 1; j < swingLows.length; j++) {
    const tiefNeu = swingLows[j];
    const tiefAlt = swingLows[j - 1];
    if (tiefNeu.price < tiefAlt.price &&
        (lastGwsdDefLow === null || tiefNeu.price < lastGwsdDefLow.price)) {
      const hochsDazwischen = swingHighs.filter(
        sh => sh.idx > tiefAlt.idx && sh.idx < tiefNeu.idx
      );
      if (hochsDazwischen.length > 0) {
        const gwsdHoch = hochsDazwischen.reduce((best, h) => h.price > best.price ? h : best);
        gwsdCandidates.push({
          idx:      gwsdHoch.idx,
          date:     gwsdHoch.date,
          price:    gwsdHoch.price,
          tiefAlt:  tiefAlt,
          tiefNeu:  tiefNeu,
        });
        lastGwsdDefLow = tiefNeu;
      }
    }
  }

  const gwsdHigh     = gwsdCandidates.length > 0 ? gwsdCandidates[gwsdCandidates.length - 1] : null;
  const prevGwsdHigh = gwsdCandidates.length > 1 ? gwsdCandidates[gwsdCandidates.length - 2] : null;

  const breakoutPrice = gwsdHigh ? gwsdHigh.price : null;

  let breakoutIdx = null;
  if (gwsdHigh) {
    for (let i = gwsdHigh.idx + 1; i < n; i++) {
      if (closes[i] > gwsdHigh.price) { breakoutIdx = i; break; }
    }
  }

  let prevBreakoutIdx = null;
  if (prevGwsdHigh) {
    for (let i = prevGwsdHigh.idx + 1; i < n; i++) {
      if (closes[i] > prevGwsdHigh.price) { prevBreakoutIdx = i; break; }
    }
  }

  let trend = "neutral";
  if (swingHighs.length >= 2) {
    const last = swingHighs[swingHighs.length - 1];
    const prev = swingHighs[swingHighs.length - 2];
    if (last.price > prev.price) trend = "bullish";
    else if (last.price < prev.price) trend = "bearish";
  }

  const broken       = gwsdHigh === null || breakoutIdx !== null;
  const currentClose = closes[n - 1];

  const recentBreakout = broken && (n - 1 - breakoutIdx <= 7);

  return {
    currentClose, gwsdHigh, breakoutIdx, breakoutPrice, broken, trend,
    prevGwsdHigh, prevBreakoutIdx,
    recentBreakout,
    swingHighs: swingHighs.slice(-6),
    swingLows:  swingLows.slice(-6),
    setup: broken && trend !== "bearish",
  };
}

// ── GWS-W Analyse (Weekly, ±1 Bar) ───────────────────────────────────────────
// ±1 Bar für Weekly (±2 ist zu streng, übersieht valide Swing-Hochs wie SNDK Feb 2)
function analyzeWeeklyStructure(ohlcvW) {
  if (!ohlcvW || ohlcvW.length < 8) return null;
  const n      = ohlcvW.length;
  const highs  = ohlcvW.map(d => d.h);
  const lows   = ohlcvW.map(d => d.l);
  const closes = ohlcvW.map(d => d.c);

  const swingHighs = [];
  for (let i = 1; i < n - 1; i++) {
    if (highs[i] >= highs[i-1] && highs[i] >= highs[i+1])
      swingHighs.push({ idx: i, date: ohlcvW[i].d, price: highs[i] });
  }

  const swingLows = [];
  for (let i = 1; i < n - 1; i++) {
    if (lows[i] <= lows[i-1] && lows[i] <= lows[i+1])
      swingLows.push({ idx: i, date: ohlcvW[i].d, price: lows[i] });
  }

  // Kernlogik: tiefere Tiefs → GWS-W = höchstes Hoch dazwischen
  const gwswCandidates = [];
  let lastGwswDefLow = null;
  for (let j = 1; j < swingLows.length; j++) {
    const tiefNeu = swingLows[j];
    const tiefAlt = swingLows[j - 1];
    if (tiefNeu.price < tiefAlt.price &&
        (lastGwswDefLow === null || tiefNeu.price < lastGwswDefLow.price)) {
      const hochsDazwischen = swingHighs.filter(
        sh => sh.idx > tiefAlt.idx && sh.idx < tiefNeu.idx
      );
      if (hochsDazwischen.length > 0) {
        const gwswHoch = hochsDazwischen.reduce((best, h) => h.price > best.price ? h : best);
        gwswCandidates.push({ idx: gwswHoch.idx, date: gwswHoch.date, price: gwswHoch.price });
        lastGwswDefLow = tiefNeu;
      }
    }
  }

  const gwswHigh     = gwswCandidates.length > 0 ? gwswCandidates[gwswCandidates.length - 1] : null;
  const prevGwswHigh = gwswCandidates.length > 1 ? gwswCandidates[gwswCandidates.length - 2] : null;

  let breakoutPrice = gwswHigh ? gwswHigh.price : null;
  let breakoutIdx = null;
  if (gwswHigh) {
    for (let i = gwswHigh.idx + 1; i < n; i++) {
      if (closes[i] > gwswHigh.price) { breakoutIdx = i; break; }
    }
  }

  let prevBreakoutIdx = null;
  if (prevGwswHigh) {
    for (let i = prevGwswHigh.idx + 1; i < n; i++) {
      if (closes[i] > prevGwswHigh.price) { prevBreakoutIdx = i; break; }
    }
  }

  let trend = "neutral";
  if (swingHighs.length >= 2) {
    const last = swingHighs[swingHighs.length - 1];
    const prev = swingHighs[swingHighs.length - 2];
    if (last.price > prev.price) trend = "bullish";
    else if (last.price < prev.price) trend = "bearish";
  }

  const broken = gwswHigh === null || breakoutIdx !== null;

  const recentBreakout = breakoutIdx !== null && (n - 1 - breakoutIdx <= 1);

  return {
    gwswHigh, breakoutIdx, breakoutPrice, broken,
    prevGwswHigh, prevBreakoutIdx,
    recentBreakout,
    swingHighs: swingHighs.slice(-6),
    swingLows:  swingLows.slice(-6),
  };
}

// ── GWS-4H Analyse (±2 Bars) ─────────────────────────────────────────────────
function analyze4HStructure(ohlcv4h) {
  if (!ohlcv4h || ohlcv4h.length < 8) return null;
  const n     = ohlcv4h.length;
  const highs = ohlcv4h.map(d => d.h);
  const lows  = ohlcv4h.map(d => d.l);
  const closes= ohlcv4h.map(d => d.c);

  const swingHighs = [];
  for (let i = 2; i < n - 2; i++) {
    if (highs[i] >= highs[i-1] && highs[i] >= highs[i-2] &&
        highs[i] >= highs[i+1] && highs[i] >= highs[i+2])
      swingHighs.push({ idx: i, date: ohlcv4h[i].d, price: highs[i] });
  }

  const swingLows = [];
  for (let i = 2; i < n - 2; i++) {
    if (lows[i] <= lows[i-1] && lows[i] <= lows[i-2] &&
        lows[i] <= lows[i+1] && lows[i] <= lows[i+2])
      swingLows.push({ idx: i, date: ohlcv4h[i].d, price: lows[i] });
  }

  // Kernlogik: tiefere Tiefs → GWS-4H = höchstes Hoch dazwischen
  const gws4hCandidates = [];
  let lastGws4hDefLow = null;
  for (let j = 1; j < swingLows.length; j++) {
    const tiefNeu = swingLows[j];
    const tiefAlt = swingLows[j - 1];
    if (tiefNeu.price < tiefAlt.price &&
        (lastGws4hDefLow === null || tiefNeu.price < lastGws4hDefLow.price)) {
      const hochsDazwischen = swingHighs.filter(
        sh => sh.idx > tiefAlt.idx && sh.idx < tiefNeu.idx
      );
      if (hochsDazwischen.length > 0) {
        const gws4hHoch = hochsDazwischen.reduce((best, h) => h.price > best.price ? h : best);
        gws4hCandidates.push({ idx: gws4hHoch.idx, date: gws4hHoch.date, price: gws4hHoch.price });
        lastGws4hDefLow = tiefNeu;
      }
    }
  }

  const gws4hHigh     = gws4hCandidates.length > 0 ? gws4hCandidates[gws4hCandidates.length - 1] : null;
  const prevGws4hHigh = gws4hCandidates.length > 1 ? gws4hCandidates[gws4hCandidates.length - 2] : null;

  let breakout4hIdx = null;
  if (gws4hHigh) {
    for (let i = gws4hHigh.idx + 1; i < n; i++) {
      if (closes[i] > gws4hHigh.price) { breakout4hIdx = i; break; }
    }
  }

  let prevBreakout4hIdx = null;
  if (prevGws4hHigh) {
    for (let i = prevGws4hHigh.idx + 1; i < n; i++) {
      if (closes[i] > prevGws4hHigh.price) { prevBreakout4hIdx = i; break; }
    }
  }

  let trend4h = "neutral";
  if (swingHighs.length >= 2) {
    const last4h = swingHighs[swingHighs.length - 1];
    const prev4h = swingHighs[swingHighs.length - 2];
    if (last4h.price > prev4h.price) trend4h = "bullish";
    else if (last4h.price < prev4h.price) trend4h = "bearish";
  }

  const recentBreakout = breakout4hIdx !== null && (() => {
    const breakoutDate = new Date(ohlcv4h[breakout4hIdx].d.replace(' ', 'T'));
    const lastDate     = new Date(ohlcv4h[n - 1].d.replace(' ', 'T'));
    return (lastDate - breakoutDate) / (1000 * 60 * 60 * 24) <= 7;
  })();
  return {
    gws4hHigh, breakout4hIdx, broken4h: gws4hHigh === null || breakout4hIdx !== null,
    prevGws4hHigh, prevBreakout4hIdx,
    recentBreakout,
    swingHighs: swingHighs.slice(-8),
    swingLows:  swingLows.slice(-8),
  };
}
