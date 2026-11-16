import './landing.css';

/* Findings from the pipeline run (14 Oct, 4 Nov, 5 Nov 2025). Update these if you re-run. */
const FINDINGS = {
  spoofNearDelhi: 47,
  spoofTotal: 48,
  rateRatio: 8.3,
  eventAircraft: 108,
  regionKm2: 12371,
};

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
    this.x0 = fromLeft ? -60 : W + 60; this.y0 = rand(0.05, 0.95) * H;
    this.x1 = fromLeft ? W + 60 : -60; this.y1 = rand(0.05, 0.95) * H;
    this.t = initial ? Math.random() : 0;
    this.speed = rand(0.0006, 0.0013);
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
    if (this.trail.length > 120) this.trail.shift();
  }
  draw() {
    const n = this.trail.length;
    for (let i = 1; i < n; i++) {
      const a = this.trail[i - 1], b = this.trail[i];
      ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y);
      if (a.s !== b.s) { ctx.strokeStyle = 'rgba(229,72,77,0.95)'; ctx.lineWidth = 1.6; }
      else {
        const alpha = (i / n) * 0.7;
        ctx.strokeStyle = b.s ? `rgba(229,72,77,${alpha})` : `rgba(0,179,199,${alpha})`;
        ctx.lineWidth = 1.1;
      }
      ctx.stroke();
    }
    const head = this.trail[n - 1];
    if (!head) return;
    if (this.spoofed) {
      const from = this.pos(this.spoofAt), to = this.pos(this.t);
      ctx.setLineDash([4, 5]); ctx.strokeStyle = 'rgba(255,153,51,0.7)'; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(from.x, from.y); ctx.lineTo(to.x, to.y); ctx.stroke(); ctx.setLineDash([]);
    }
    ctx.fillStyle = this.spoofed ? '#E5484D' : '#F5F7FA';
    ctx.beginPath(); ctx.arc(head.x, head.y, this.spoofed ? 2.7 : 1.8, 0, Math.PI * 2); ctx.fill();
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
  g.fillStyle = 'rgba(138,148,166,0.2)';
  for (let x = 0; x < W; x += 32) for (let y = 0; y < H; y += 32) g.fillRect(x, y, 1, 1);
  const count = Math.max(14, Math.min(46, Math.round(W / 34)));
  tracks = Array.from({ length: count }, (_, i) => new Track(i % 6 === 0));
}

function drawFrame() {
  ctx.clearRect(0, 0, W, H);
  ctx.drawImage(grid, 0, 0, W, H);
  if (frameNo % 80 === 0) pings.push({ x: rand(0.05, 0.95) * W, y: rand(0.1, 0.9) * H, r: 0, life: 1 });
  for (const p of pings) {
    p.r += 0.7; p.life -= 0.006;
    ctx.strokeStyle = `rgba(0,179,199,${Math.max(p.life, 0) * 0.28})`; ctx.lineWidth = 1;
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
  new IntersectionObserver(([e]) => { running = e.isIntersecting; if (running && !looping) loop(); }).observe($('#hero'));
  document.addEventListener('visibilitychange', () => { running = !document.hidden; if (running && !looping) loop(); });
  loop();
}

/* ---------------- nav, frame tilt, reveals ---------------- */
const nav = $('#nav');
const frame = $('#frame');
function onScroll() {
  nav.classList.toggle('scrolled', window.scrollY > 24);
  if (!reduce && frame) {
    const r = frame.getBoundingClientRect();
    const k = Math.min(1, Math.max(0, (window.innerHeight - r.top) / (window.innerHeight * 0.85)));
    frame.style.setProperty('--tilt', `${(1 - k) * 14}deg`);
  }
}
window.addEventListener('scroll', onScroll, { passive: true });
onScroll();

const revealObs = new IntersectionObserver((entries) => {
  for (const e of entries) if (e.isIntersecting) { e.target.classList.add('in'); revealObs.unobserve(e.target); }
}, { threshold: 0.12 });
$$('.reveal').forEach((el) => (reduce ? el.classList.add('in') : revealObs.observe(el)));

$$('.spot').forEach((el) => el.addEventListener('pointermove', (e) => {
  const r = el.getBoundingClientRect();
  el.style.setProperty('--mx', `${e.clientX - r.left}px`);
  el.style.setProperty('--my', `${e.clientY - r.top}px`);
}));

/* ---------------- compare slider ---------------- */
const cmp = $('#compare');
if (cmp) {
  const range = cmp.querySelector('.compare__range');
  const set = (v) => cmp.style.setProperty('--pos', `${v}%`);
  range.addEventListener('input', (e) => set(e.target.value));
  if (!reduce) {
    new IntersectionObserver(([en], obs) => {
      if (!en.isIntersecting) return;
      obs.disconnect();
      const t0 = performance.now();
      const sweep = (now) => {
        const k = Math.min(1, (now - t0) / 2000);
        const v = 50 + 32 * Math.sin(k * Math.PI * 2) * (1 - k);
        range.value = v; set(v);
        if (k < 1) requestAnimationFrame(sweep);
      };
      requestAnimationFrame(sweep);
    }, { threshold: 0.5 }).observe(cmp);
  }
}

/* ---------------- scroll story ---------------- */
const steps = $$('.how__step');
const svgs = $$('.how__svg');
const stepObs = new IntersectionObserver((entries) => {
  for (const e of entries) {
    if (!e.isIntersecting) continue;
    const i = e.target.dataset.step;
    steps.forEach((s) => s.classList.toggle('is-on', s.dataset.step === i));
    svgs.forEach((s) => s.classList.toggle('is-on', s.dataset.step === i));
  }
}, { rootMargin: '-45% 0px -45% 0px' });
steps.forEach((s) => stepObs.observe(s));

/* ---------------- count-ups ---------------- */
function countUp(el, target, decimals = 0, prefix = '', suffix = '') {
  const fmt = (v) => prefix + v.toLocaleString('en-IN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals }) + suffix;
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
    countUp(el, parseFloat(el.dataset.count), Number(el.dataset.decimals || 0), el.dataset.prefix || '', el.dataset.suffix || '');
  }
}, { threshold: 0.4 });
function arm(el, value, { decimals = 0, prefix = '', suffix = '' } = {}) {
  if (!el) return;
  if (value == null || Number.isNaN(Number(value))) { el.textContent = '—'; return; }
  Object.assign(el.dataset, { count: value, decimals, prefix, suffix });
  countObs.observe(el);
}
$$('[data-count]').forEach((el) => countObs.observe(el));

arm($('#f-near'), FINDINGS.spoofNearDelhi);
$('#f-total').textContent = String(FINDINGS.spoofTotal);
arm($('#f-ratio'), FINDINGS.rateRatio, { decimals: 1, prefix: '≈', suffix: '×' });
arm($('#f-aircraft'), FINDINGS.eventAircraft);
arm($('#f-area'), FINDINGS.regionKm2);

/* ---------------- live pipeline numbers ---------------- */
async function getJSON(path) {
  try { const r = await fetch(path); if (!r.ok) throw new Error(path); return await r.json(); }
  catch { return null; }
}
const [meta, metrics] = await Promise.all([getJSON('/data/meta.json'), getJSON('/data/metrics.json')]);

if (meta) {
  arm($('#p-reports'), meta.n_reports);
  arm($('#p-aircraft'), meta.n_aircraft);
  arm($('#p-events'), meta.n_events);
  $('#hero-chip').textContent = `${meta.n_reports.toLocaleString('en-IN')} real ADS-B reports replayed`;
} else {
  $('#bench-note').textContent = 'Run the ICHNOS pipeline export to populate these figures.';
}

const ich = metrics?.methods?.find((m) => m.method === 'ichnos');
if (ich && ich.recall != null) {
  const pct = (x) => (x == null ? 'n/a' : `${(x * 100).toFixed(1)}%`);
  $('#p-recall').textContent = `${ich.detected}/${ich.n_windows} windows`;
  $('#p-recall-ci').textContent =
    `95% CI ${pct(ich.ci_lo)}–${pct(ich.ci_hi)} · ${ich.fa_events} events in ${ich.control_hours} h of control data`;
  requestAnimationFrame(() => {
    const lo = (ich.ci_lo ?? 0) * 100, hi = (ich.ci_hi ?? 0) * 100;
    $('#ci-band').style.left = `${lo}%`;
    $('#ci-band').style.width = `${hi - lo}%`;
    $('#ci-pt').style.left = `${ich.recall * 100}%`;
  });
}
