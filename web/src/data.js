const EMPTY_FC = Object.freeze({ type: 'FeatureCollection', features: [] });

async function fetchJsonSafe(url) {
  try {
    const res = await fetch(url, { cache: 'no-cache' });
    if (!res.ok) return null;
    const text = await res.text();
    if (!text || !text.trim()) return null;
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function normalizeFeatureCollection(raw) {
  if (raw && raw.type === 'FeatureCollection' && Array.isArray(raw.features)) {
    return raw;
  }
  return EMPTY_FC;
}

export async function loadAllDatasets() {
  const [metaRaw, metricsRaw, hexesRaw, anomaliesRaw, eventsRaw, regionsRaw, coverageRaw] =
    await Promise.all([
      fetchJsonSafe('/data/meta.json'),
      fetchJsonSafe('/data/metrics.json'),
      fetchJsonSafe('/data/hexes.geojson'),
      fetchJsonSafe('/data/anomalies.geojson'),
      fetchJsonSafe('/data/events.geojson'),
      fetchJsonSafe('/data/regions.geojson'),
      fetchJsonSafe('/data/coverage.geojson'),
    ]);

  const meta =
    metaRaw && typeof metaRaw === 'object'
      ? {
          days: Array.isArray(metaRaw.days) ? metaRaw.days : [],
          hours: Array.isArray(metaRaw.hours)
            ? [...metaRaw.hours].map(Number).filter(Number.isFinite).sort((a, b) => a - b)
            : [],
          release_tags: Array.isArray(metaRaw.release_tags) ? metaRaw.release_tags : [],
          n_reports: typeof metaRaw.n_reports === 'number' ? metaRaw.n_reports : null,
          n_aircraft: typeof metaRaw.n_aircraft === 'number' ? metaRaw.n_aircraft : null,
          n_events: typeof metaRaw.n_events === 'number' ? metaRaw.n_events : null,
          public_h3_res: metaRaw.public_h3_res ?? null,
          attribution: typeof metaRaw.attribution === 'string' ? metaRaw.attribution : null,
        }
      : null;

  const metrics =
    metricsRaw && typeof metricsRaw === 'object' && Array.isArray(metricsRaw.methods)
      ? {
          methods: metricsRaw.methods,
          windows: Array.isArray(metricsRaw.windows) ? metricsRaw.windows : [],
          performance: metricsRaw.performance || {},
          note: typeof metricsRaw.note === 'string' ? metricsRaw.note : '',
        }
      : null;

  return {
    meta,
    metrics,
    hexes: normalizeFeatureCollection(hexesRaw),
    anomalies: normalizeFeatureCollection(anomaliesRaw),
    events: normalizeFeatureCollection(eventsRaw),
    regions: normalizeFeatureCollection(regionsRaw),
    coverage: normalizeFeatureCollection(coverageRaw),
  };
}

export function formatInt(value) {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—';
  return new Intl.NumberFormat('en-US').format(Math.round(value));
}

export function formatPct(ratio) {
  if (typeof ratio !== 'number' || !Number.isFinite(ratio)) return '—';
  return `${(ratio * 100).toFixed(1)}%`;
}

export function formatEpochHourUtc(epochHour) {
  if (typeof epochHour !== 'number' || !Number.isFinite(epochHour)) return '—';
  const d = new Date(epochHour * 3600 * 1000);
  const iso = d.toISOString();
  return `${iso.slice(0, 10)} ${iso.slice(11, 13)}:00 UTC`;
}

export function formatMsRangeUtc(startMs, endMs) {
  if (typeof startMs !== 'number' || typeof endMs !== 'number') return '—';
  const s = new Date(startMs).toISOString();
  const e = new Date(endMs).toISOString();
  const sameDay = s.slice(0, 10) === e.slice(0, 10);
  if (sameDay) {
    return `${s.slice(0, 10)} ${s.slice(11, 16)}–${e.slice(11, 16)} UTC`;
  }
  return `${s.slice(0, 16).replace('T', ' ')} → ${e.slice(0, 16).replace('T', ' ')} UTC`;
}

export function formatDuration(startMs, endMs) {
  if (typeof startMs !== 'number' || typeof endMs !== 'number') return '—';
  const mins = Math.max(1, Math.round((endMs - startMs) / 60000));
  if (mins < 60) return `${mins}m`;
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
}

export function eventTouchesHour(props, epochHour) {
  if (!props || typeof epochHour !== 'number') return true;
  const hStart = epochHour * 3600 * 1000;
  const hEnd = hStart + 3600 * 1000;
  const t0 = Number(props.t_start_ms);
  const t1 = Number(props.t_end_ms);
  if (!Number.isFinite(t0) || !Number.isFinite(t1)) return true;
  return t0 < hEnd && t1 >= hStart;
}

export function computeGeoBounds(feature) {
  if (!feature || !feature.geometry) return null;
  let minLng = Infinity;
  let minLat = Infinity;
  let maxLng = -Infinity;
  let maxLat = -Infinity;

  function walk(coords) {
    if (!Array.isArray(coords)) return;
    if (typeof coords[0] === 'number' && typeof coords[1] === 'number') {
      minLng = Math.min(minLng, coords[0]);
      maxLng = Math.max(maxLng, coords[0]);
      minLat = Math.min(minLat, coords[1]);
      maxLat = Math.max(maxLat, coords[1]);
      return;
    }
    for (const child of coords) walk(child);
  }

  walk(feature.geometry.coordinates);
  if (!Number.isFinite(minLng)) return null;
  return [
    [minLng, minLat],
    [maxLng, maxLat],
  ];
}