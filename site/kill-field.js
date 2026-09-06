/* The kill field.
   Two handlers on two timelines. A red line is the SIGKILL; everything left of it is durable,
   everything right of it is what a fresh worker does with the same event. Move the pointer to
   move the kill. The misleading-green patch only fails when the kill lands between its two
   commits, which is why CrashCheck kills after every commit instead of once. */
(function () {
  'use strict';
  var canvas = document.querySelector('[data-kill-field]');
  if (!canvas) return;
  var ctx = canvas.getContext('2d', { alpha: false });
  var hero = canvas.parentElement;
  var legend = document.querySelector('[data-legend-line]');
  if (!ctx || !hero) return;

  var css = getComputedStyle(document.documentElement);
  function token(name, fallback) { return (css.getPropertyValue(name) || fallback).trim(); }
  var BG = token('--bg', '#0d1117'), INK = token('--ink', '#ecebe6');
  var MUTED = token('--muted', '#9aa0aa'), RED = token('--red', '#e6392d');
  var reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  var FONT = '11px ui-monospace, "SF Mono", Menlo, monospace';

  /* The story, in normalized time along the stage. */
  var LANES = [
    { name: 'misleading-green', commits: [{ u: .30, what: 'credit' }, { u: .48, what: 'mark' }] },
    { name: 'atomic fix', commits: [{ u: .39, what: 'credit_and_mark' }] }
  ];
  var REPLAY_GAP = .09, REVEAL_MS = 1400, DWELL_MS = 4200, SWEEP_MS = 14000;
  var WAKE = [], WAKE_MAX = 32, WAKE_MS = 800, WAKE_RADIUS = 120;

  var W = 0, H = 0, dpr = 1, ticks = [], stage = null, narrow = false;
  var kill = .40, target = .40, pointerU = null, pointerAt = -1e9;
  var mounted = performance.now(), raf = 0, running = false, lastLegend = '';

  function clamp(v, lo, hi) { return v < lo ? lo : v > hi ? hi : v; }
  function smooth(t) { t = clamp(t, 0, 1); return t * t * (3 - 2 * t); }
  function easeOut(t) { t = clamp(t, 0, 1); return 1 - Math.pow(1 - t, 3); }

  /* What a lane does when killed at u. */
  function outcome(lane, u) {
    var durable = lane.commits.filter(function (c) { return c.u <= u; });
    var replay = [];
    if (lane.commits.length === 2) {
      var credited = durable.length >= 1, marked = durable.length === 2;
      if (marked) replay.push({ kind: 'nothing' });
      else {
        replay.push({ kind: credited ? 'duplicate' : 'write', what: 'credit' });
        replay.push({ kind: 'write', what: 'mark' });
      }
      return { durable: durable, replay: replay, total: credited && !marked ? 5000 : 2500, duplicate: credited && !marked };
    }
    replay.push(durable.length ? { kind: 'nothing' } : { kind: 'write', what: 'credit_and_mark' });
    return { durable: durable, replay: replay, total: 2500, duplicate: false };
  }
  function money(cents) { return '$' + (cents / 100).toFixed(2); }

  function layout() {
    W = canvas.clientWidth; H = canvas.clientHeight;
    if (!W || !H) return;
    var ratio = Math.min(window.devicePixelRatio || 1, 2);
    dpr = ratio;
    var bw = Math.round(W * dpr), bh = Math.round(H * dpr);
    if (canvas.width !== bw) canvas.width = bw;
    if (canvas.height !== bh) canvas.height = bh;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    narrow = W < 900;
    stage = narrow
      ? { x0: W * .08, x1: W * .92, lanes: [H - 215, H - 140], top: H - 310, bottom: H - 62 }
      : { x0: W * .52, x1: W * .95, lanes: [H * .42, H * .60], top: 0, bottom: H };

    /* The tick field: a ruler over the whole hero, denser near the story. */
    var step = narrow ? 30 : 26;
    var cap = 1500, estimate = Math.ceil(W / step) * Math.ceil(H / step);
    if (estimate > cap) step *= Math.sqrt(estimate / cap);
    ticks = [];
    var ox = ((W % step) + step) / 2, oy = ((H % step) + step) / 2;
    var yMin = narrow ? stage.top : 0, yMax = narrow ? stage.bottom : H;
    for (var y = oy; y < H; y += step) {
      if (y < yMin || y > yMax) continue;
      for (var x = ox; x < W; x += step) ticks.push({ x: x, y: y });
    }
  }

  function killX() { return stage.x0 + (stage.x1 - stage.x0) * kill; }
  function toX(u) { return stage.x0 + (stage.x1 - stage.x0) * u; }

  function drawTicks(now, kx) {
    var reveal = easeOut((now - mounted) / REVEAL_MS);
    var buckets = [[], [], [], [], [], [], [], []];
    /* The pointer's wake: recent samples lift the ticks they passed, then fade. */
    var live = [];
    for (var wi = 0; wi < WAKE.length; wi++) {
      var age = now - WAKE[wi].t;
      if (age < WAKE_MS) live.push({ x: WAKE[wi].x, y: WAKE[wi].y, e: 1 - age / WAKE_MS });
    }
    var mid = narrow ? (stage.top + stage.bottom) / 2 : H / 2;
    for (var i = 0; i < ticks.length; i++) {
      var t = ticks[i], d = Math.abs(t.x - kx);
      var near = 1 - smooth(d / 150), wake = 0;
      for (var li = 0; li < live.length; li++) {
        var dx = t.x - live[li].x, dy = t.y - live[li].y, dd = Math.sqrt(dx * dx + dy * dy);
        if (dd < WAKE_RADIUS) wake = Math.max(wake, (1 - smooth(dd / WAKE_RADIUS)) * live[li].e);
      }
      var angle = near * Math.PI / 2 * (t.y < mid ? 1 : -1) * .92;
      var len = 3.5 + near * 3 + wake * 4, alpha = (.10 + near * .42 + wake * .55) * reveal;
      var c = Math.cos(angle) * len, s = Math.sin(angle) * len;
      var b = Math.min(7, Math.floor(alpha * 14));
      buckets[b].push(t.x - c, t.y - s, t.x + c, t.y + s);
    }
    ctx.lineWidth = 1; ctx.strokeStyle = INK;
    for (var k = 0; k < buckets.length; k++) {
      var lines = buckets[k]; if (!lines.length) continue;
      ctx.globalAlpha = (k + .5) / 14;
      ctx.beginPath();
      for (var j = 0; j < lines.length; j += 4) { ctx.moveTo(lines[j], lines[j + 1]); ctx.lineTo(lines[j + 2], lines[j + 3]); }
      ctx.stroke();
    }
    ctx.globalAlpha = 1;
  }

  function square(x, y, size, style) {
    var h = size / 2;
    if (style === 'hollow') { ctx.strokeStyle = RED; ctx.lineWidth = 1.5; ctx.strokeRect(x - h + .5, y - h + .5, size - 1, size - 1); return; }
    ctx.fillStyle = style === 'duplicate' ? RED : INK;
    ctx.fillRect(x - h, y - h, size, size);
  }

  function drawStory(now, kx) {
    var reveal = (now - mounted) / REVEAL_MS;
    var gap = 12, size = 9;
    ctx.font = FONT; ctx.textBaseline = 'middle';
    for (var li = 0; li < LANES.length; li++) {
      var lane = LANES[li], y = stage.lanes[li], o = outcome(lane, kill);
      /* Rails, split at the kill like the banner. */
      ctx.globalAlpha = .55 * easeOut(reveal); ctx.strokeStyle = INK; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(stage.x0, y + .5); ctx.lineTo(Math.max(stage.x0, kx - gap), y + .5); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(Math.min(stage.x1, kx + gap), y + .5); ctx.lineTo(stage.x1, y + .5); ctx.stroke();
      ctx.globalAlpha = 1;
      /* Durable commits: one by one during the reveal. */
      for (var ci = 0; ci < lane.commits.length; ci++) {
        var c = lane.commits[ci], appear = easeOut(reveal * 1.6 - c.u);
        if (appear <= 0) continue;
        /* A commit the kill precedes never happened in this world: it fades out as the
           line arrives and stays gone. */
        var x = toX(c.u), on = c.u <= kill;
        var ghost = on ? 1 : 1 - easeOut((now - mounted - REVEAL_MS * .8) / 500);
        if (ghost <= 0) continue;
        ctx.globalAlpha = appear * ghost;
        square(x, y, size * (.6 + .4 * appear), 'solid');
        ctx.globalAlpha = .75 * ghost; ctx.fillStyle = MUTED; ctx.textAlign = 'center';
        ctx.fillText(c.what, x, y - 16);
      }
      /* What the fresh worker does after the kill. */
      if (reveal > 1) {
        for (var ri = 0; ri < o.replay.length; ri++) {
          var r = o.replay[ri], rx = kx + (stage.x1 - stage.x0) * REPLAY_GAP * (ri + 1);
          if (rx > stage.x1 - 4) continue;
          ctx.globalAlpha = 1;
          if (r.kind === 'nothing') { square(rx, y, size, 'hollow'); }
          else {
            square(rx, y, size, r.kind === 'duplicate' ? 'duplicate' : 'solid');
            /* First replay label above the rail, the second below it, clear of the amount. */
            var below = ri === 1, labelY = below ? y + 18 : y - 16;
            if (!below || rx < stage.x1 - 150) {
              ctx.globalAlpha = .8; ctx.fillStyle = r.kind === 'duplicate' ? RED : MUTED; ctx.textAlign = 'center';
              ctx.fillText(r.kind === 'duplicate' ? (narrow ? 'again' : 'credit again') : r.what, rx, labelY);
            }
          }
        }
      }
      /* Lane name and its balance at this kill. */
      ctx.globalAlpha = .9 * easeOut(reveal); ctx.fillStyle = MUTED; ctx.textAlign = 'left';
      ctx.fillText(lane.name, stage.x0, y + 18);
      if (reveal > 1) {
        ctx.textAlign = 'right'; ctx.fillStyle = o.duplicate ? RED : INK;
        ctx.fillText(money(o.total) + (o.duplicate ? '  DUPLICATE' : '  exactly once'), stage.x1, y + 18);
      }
      ctx.globalAlpha = 1;
    }
    /* The kill line, with the banner's ticks, and its name. */
    var lineAlpha = easeOut((now - mounted - REVEAL_MS * .8) / 500);
    if (lineAlpha > 0) {
      ctx.globalAlpha = lineAlpha; ctx.strokeStyle = RED; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(kx + .5, stage.top); ctx.lineTo(kx + .5, stage.bottom); ctx.stroke();
      ctx.beginPath();
      for (var ty = stage.top + 24; ty < stage.bottom; ty += 48) { ctx.moveTo(kx - 5, ty + .5); ctx.lineTo(kx + 6, ty + .5); }
      ctx.stroke();
      ctx.fillStyle = RED; ctx.textAlign = 'left'; ctx.textBaseline = 'top';
      ctx.fillText('SIGKILL', kx + 9, stage.top + 10);
      ctx.globalAlpha = 1;
    }
  }

  function updateLegend() {
    if (!legend) return;
    var a = outcome(LANES[0], kill), b = outcome(LANES[1], kill);
    var text = 'kill at t=' + kill.toFixed(2) + ' · misleading-green: ' + money(a.total) + (a.duplicate ? ' duplicate' : ' once') +
      ' · atomic: ' + money(b.total) + ' once' + (pointerU == null ? ' · move the kill' : '');
    if (text !== lastLegend) { legend.textContent = text; lastLegend = text; }
  }

  function frame(now) {
    raf = 0;
    if (!stage) layout();
    if (!stage) return;
    var idle = now - pointerAt > 4000, since = now - mounted;
    if (pointerU != null && !idle) target = pointerU;
    else if (!reduce) {
      /* Dwell inside the duplicate window first, then sweep across the whole timeline. */
      target = since < DWELL_MS ? .40 : .41 + .21 * Math.sin((since - DWELL_MS) / SWEEP_MS * Math.PI * 2);
    }
    kill += (target - kill) * (reduce ? 1 : .07);
    var kx = killX();
    ctx.fillStyle = BG; ctx.fillRect(0, 0, W, H);
    drawTicks(now, kx);
    drawStory(now, kx);
    updateLegend();
    var settled = reduce && Math.abs(target - kill) < .0005 && now - mounted > REVEAL_MS * 1.5 && !WAKE.length;
    if (WAKE.length && now - WAKE[WAKE.length - 1].t > WAKE_MS) WAKE.length = 0;
    if (running && !settled) raf = requestAnimationFrame(frame);
  }
  function start() { if (!running) { running = true; } if (!raf) raf = requestAnimationFrame(frame); }
  function stop() { running = false; if (raf) { cancelAnimationFrame(raf); raf = 0; } }

  function setPointer(clientX, clientY) {
    var rect = canvas.getBoundingClientRect();
    if (clientY < rect.top || clientY > rect.bottom) return;
    var x = (clientX - rect.left) * (W / rect.width), y = (clientY - rect.top) * (H / rect.height);
    pointerU = clamp((x - stage.x0) / (stage.x1 - stage.x0), 0, 1);
    pointerAt = performance.now();
    var last = WAKE[WAKE.length - 1];
    if (!last || Math.abs(last.x - x) + Math.abs(last.y - y) > 8) {
      WAKE.push({ x: x, y: y, t: pointerAt });
      if (WAKE.length > WAKE_MAX) WAKE.shift();
    }
    start();
  }
  hero.addEventListener('pointermove', function (e) { if (stage) setPointer(e.clientX, e.clientY); }, { passive: true });
  hero.addEventListener('pointerdown', function (e) { if (stage) setPointer(e.clientX, e.clientY); }, { passive: true });
  hero.addEventListener('pointerleave', function () { pointerAt = performance.now() - 3000; });

  var resize = window.ResizeObserver ? new ResizeObserver(function () { layout(); start(); }) : null;
  if (resize) resize.observe(hero); else window.addEventListener('resize', function () { layout(); start(); });
  if (window.IntersectionObserver) {
    new IntersectionObserver(function (entries) { entries[0].isIntersecting ? start() : stop(); }, { threshold: .02 }).observe(hero);
  }
  document.addEventListener('visibilitychange', function () { document.hidden ? stop() : start(); });
  layout(); start();
})();
