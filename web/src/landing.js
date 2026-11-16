import './landing.css';

const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];
const rand = (a, b) => a + Math.random() * (b - a);

/* ---------------- animated sky ---------------- */
const canvas = $('#sky');
const ctx = canvas.getContext('2d');
const grid = document.createElement('canvas');
let W = 0, H = 0, tracks = [], pings = [], frameNo = 0, running = true, looping = false;

class Track {
  constructor(spoofable) { this.spoofable = spoofable; this.reset(true); }
  reset(initial) {
    const fromLeft = Math.random() < 0.5;
    this.x0 = fromLeft ? -60 : W + 60; this.y0 = rand(0.08, 0.92) * H;
    this.x1 = fromLeft ? W + 60 : -60; this.y1 = rand(0.08, 0.92) * H;
    this.t = initial ? Math.random() : 0;
    this.speed = rand(0.0007, 0.0015);
    this.trail = [];
    this.spoofAt = this.spoofable ? rand(0.3, 0.6) : 9;
    this.off = { x: rand(-110, 110), y: rand(60, 140) * (Math.random() < 0.5 ? -1 : 1) };
    this.spoofed = false;
  }
  pos(t) { return { x: this.x0 + (this.x1 - this.x0) * t, y: this.y0 + (this.y1 - this.y0) * t }; }
  step() {
    this.t += this.speed;
    if (this.t > 1.05) { this.reset(false); return; }
    const p = this.pos(this.t);
    if (this.t > this.spoofAt) { this.spoofed = true; p.x += this.off.x; p.y += this.off.y; }
    this.trail.push({ x: p.x, y: p.y, s: this.spoofed });
    if (this.trail.length > 110) this.trail.shift();
  }
  draw() {
    const n = this.trail.length;
    for (let i = 1; i < n; i++) {
      const a = this.trail[i - 1], b = this.trail[i];
      ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y);
      if (a.s !== b.s) { ctx.strokeStyle = 'rgba(229,72,77,0.95)'; ctx.lineWidth = 1.6; }
      else {
        const alpha = (i / n) * 0.75;
        ctx.strokeStyle = b.s ? `rgba(229,72,77,${alpha})` : `rgba(0,179,199,${alpha})`;
        ctx.lineWidth = 1.2;
      }
      ctx.stroke();
    }
    const head = this.trail[n - 1];
    if (!head) return;
    if (this.spoofed) {
      const from = this.pos(this.spoofAt), to = this.pos(this.t);
      ctx.setLineDash([4, 5]); ctx.strokeStyle = 'rgba(255,153,51,0.75)'; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(from.x, from.y); ctx.lineTo(to.x, to.y); ctx.stroke(); ctx.setLineDash([]);
      ctx.fillStyle = 'rgba(255,153,51,0.9)'; ctx.beginPath(); ctx.arc(to.x, to.y, 1.8, 0, Math.PI * 2); ctx.fill();
    }
    ctx.fillStyle = this.spoofed ? '#E5484D' : '#F5F7FA';
    ctx.beginPath(); ctx.arc(head.x, head.y, this.spoofed ? 2.8 : 1.9, 0, Math.PI * 2); ctx.fill();
  }
}

function resize() {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  W = canvas.clientWidth; H = canvas.clientHeight;
  canvas.width = Math.floor(W * dpr); canvas.height = Math.floor(H * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  grid.width = canvas.width; grid.height = canvas.height;
  const g = grid.getContext('2d');
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.fillStyle = 'rgba(138,148,166,0.22)';
  for (let x = 0; x < W; x += 32) for (let y = 0; y < H; y += 32) g.fillRect(x, y, 1, 1);
  const count = Math.max(14, Math.min(44, Math.round(W / 36)));
  tracks = Array.from({ length: count }, (_, i) => new Track(i % 6 === 0));
}

function drawFrame() {
  ctx.clearRect(0, 0, W, H);
  ctx.drawImage(grid, 0, 0, W, H);
  if (frameNo % 80 === 0) pings.push({ x: rand(0.05, 0.95) * W, y: rand(0.1, 0.9) * H, r: 0, life: 1 });
  for (const p of pings) {
    p.r += 0.7; p.life -= 0.006;
    ctx.strokeStyle = `rgba(0,179,199,${Math.max(p.life, 0) * 0.3})`; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2); ctx.stroke();
  }
  pings = pings.filter((p) => p.life > 0);
  for (const t of tracks) { t.step(); t.draw(); }
  frameNo++;
}

function loop() {
  if (!running) { looping = false; return; }
  looping = true;
  drawFrame();
  requestAnimationFrame(loop);
}

resize();
window.addEventListener('resize', resize);
if (reduce) {
  for (let i = 0; i < 400; i++) tracks.forEach((t) => t.step());
  drawFrame();
} else {
  new IntersectionObserver(([e]) => {
    running = e.isIntersecting;
    if (running && !looping) loop();
  }).observe($('#hero'));
  document.addEventListener('visibilitychange', () => {
    running = !document.hidden;
    if (running && !looping) loop();
  });
  loop();
}

/* ---------------- nav + scroll reveal ---------------- */
const nav = $('#nav');
const onScroll = () => nav.classList.toggle('scrolled', window.scrollY > 24);
window.addEventListener('scroll', onScroll, { passive: true });
onScroll();

const revealObs = new IntersectionObserver((entries) => {
  for (const e of entries) if (e.isIntersecting) { e.target.classList.add('in'); revealObs.unobserve(e.target); }
}, { threshold: 0.15 });
$$('.reveal').forEach((el) => (reduce ? el.classList.add('in') : revealObs.observe(el)));

/* ---------------- count-up numbers ---------------- */
function countUp(el, target, decimals = 0, suffix = '') {
  const fmt = (v) => v.toLocaleString('en-IN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals }) + suffix;
  if (reduce) { el.textContent = fmt(target); return; }
  const t0 = performance.now(), dur = 1600;
  const tick = (now) => {
    const k = Math.min(1, (now - t0) / dur);
    el.textContent = fmt(target * (1 - Math.pow(1 - k, 3)));
    if (k < 1) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}
const countObs = new IntersectionObserver((entries) => {
  for (const e of entries) {
    if (!e.isIntersecting) continue;
    const el = e.target;
    countObs.unobserve(el);
    countUp(el, parseFloat(el.dataset.count), Number(el.dataset.decimals || 0), el.dataset.suffix || '');
  }
}, { threshold: 0.4 });
const armCount = (el, value, decimals = 0, suffix = '') => {
  if (value == null || Number.isNaN(Number(value))) { el.textContent = '—'; return; }
  el.dataset.count = value; el.dataset.decimals = decimals; el.dataset.suffix = suffix;
  countObs.observe(el);
};
$$('.stat .num[data-count]').forEach((el) => countObs.observe(el));

/* ---------------- live pipeline numbers ---------------- */
async function getJSON(path) {
  try { const r = await fetch(path); if (!r.ok) throw new Error(path); return await r.json(); }
  catch { return null; }
}
const [meta, metrics] = await Promise.all([getJSON('/data/meta.json'), getJSON('/data/metrics.json')]);

if (meta) {
  armCount($('#p-reports'), meta.n_reports);
  armCount($('#p-aircraft'), meta.n_aircraft);
  armCount($('#p-events'), meta.n_events);
  armCount($('#p-days'), meta.days?.length ?? null);
  $('#ticker-main').textContent =
    `${meta.n_reports.toLocaleString('en-IN')} reports · ${meta.n_aircraft.toLocaleString('en-IN')} aircraft · ${meta.days.length} days replayed`;
} else {
  $('#ticker-main').textContent = 'Replay dataset not found. Run the pipeline export.';
  $('#proof-note').textContent = 'Run the ICHNOS pipeline to populate these figures.';
}

const ich = metrics?.methods?.find((m) => m.method === 'ichnos');
if (ich && ich.recall != null) {
  armCount($('#p-recall'), ich.recall * 100, 1, '%');
  const pct = (x) => (x == null ? 'n/a' : `${(x * 100).toFixed(1)}%`);
  $('#p-recall-ci').textContent =
    `95% CI ${pct(ich.ci_lo)} – ${pct(ich.ci_hi)} · ${ich.detected}/${ich.n_windows} labelled windows · ${ich.fa_events} false events in ${ich.control_hours} control hours`;
  requestAnimationFrame(() => {
    const lo = (ich.ci_lo ?? 0) * 100, hi = (ich.ci_hi ?? 0) * 100;
    $('#ci-band').style.left = `${lo}%`;
    $('#ci-band').style.width = `${hi - lo}%`;
    $('#ci-pt').style.left = `${ich.recall * 100}%`;
  });
}
