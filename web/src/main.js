import './style.css';
import {
  loadAllDatasets,
  formatInt,
  formatPct,
  formatEpochHourUtc,
  formatMsRangeUtc,
  formatDuration,
  eventTouchesHour,
} from './data.js';
import { IchnosMap } from './map.js';

const state = {
  mode: 'ichnos',
  allHours: true,
  hourIndex: 0,
  selectedEventId: null,
  playing: false,
  playTimer: null,
  layers: {
    jamming: true,
    spoofing: true,
    events: true,
    regions: true,
    coverage: false,
  },
};

let datasets = null;
let mapController = null;

function $(id) {
  return document.getElementById(id);
}

function getSelectedEpochHour() {
  const hours = datasets?.meta?.hours || [];
  if (!hours.length) return null;
  const idx = Math.min(Math.max(0, state.hourIndex), hours.length - 1);
  return hours[idx];
}

function getFilteredEvents() {
  const features = datasets?.events?.features || [];
  const selectedHour = getSelectedEpochHour();
  return features.filter((f) => {
    const p = f.properties || {};
    if (state.mode === 'standard' && p.type !== 'jam') return false;
    if (!state.allHours && typeof selectedHour === 'number') {
      if (!eventTouchesHour(p, selectedHour)) return false;
    }
    return true;
  });
}

function renderHeroStats() {
  const meta = datasets.meta;
  const metrics = datasets.metrics;

  if (meta) {
    $('stat-reports').textContent = formatInt(meta.n_reports);
    $('stat-days').textContent = meta.days.length
      ? `${meta.days.length} day${meta.days.length === 1 ? '' : 's'} · H3 res ${meta.public_h3_res ?? '—'}`
      : 'Run the pipeline to populate this panel';

    $('stat-aircraft').textContent = formatInt(meta.n_aircraft);
    $('stat-events').textContent =
      typeof meta.n_events === 'number'
        ? `${formatInt(meta.n_events)} clustered events`
        : 'Run the pipeline to populate this panel';

    if (meta.attribution) {
      $('footer-attribution').textContent = meta.attribution;
    }
    $('footer-version').textContent = meta.release_tags.length
      ? `release: ${meta.release_tags[meta.release_tags.length - 1]}`
      : 'release: dev';
  } else {
    $('stat-reports').textContent = '—';
    $('stat-days').textContent = 'Run the pipeline to populate this panel';
    $('stat-aircraft').textContent = '—';
    $('stat-events').textContent = 'Run the pipeline to populate this panel';
  }

  const ichnosMethod = metrics?.methods?.find((m) => m.method === 'ichnos');
  if (ichnosMethod && typeof ichnosMethod.recall === 'number') {
    $('stat-recall').textContent = formatPct(ichnosMethod.recall);
    $('stat-recall-ci').textContent = `95% CI [${formatPct(ichnosMethod.ci_lo)}, ${formatPct(
      ichnosMethod.ci_hi
    )}]`;
  } else {
    $('stat-recall').textContent = '—';
    $('stat-recall-ci').textContent = 'Run the pipeline to populate this panel';
  }
}

function renderScrubber() {
  const hours = datasets?.meta?.hours || [];
  const range = $('scrubber-range');
  const playBtn = $('btn-play-pause');
  const ticksEl = $('scrubber-ticks');
  const timestampEl = $('scrubber-timestamp');
  const railReadout = $('rail-time-readout');

  if (!hours.length) {
    range.disabled = true;
    playBtn.disabled = true;
    timestampEl.textContent = 'Run the pipeline to populate this panel';
    railReadout.textContent = 'NO HOURS LOADED';
    ticksEl.innerHTML = '';
    return;
  }

  range.disabled = false;
  playBtn.disabled = false;
  range.min = '0';
  range.max = String(hours.length - 1);
  range.value = String(state.hourIndex);

  const currentHour = getSelectedEpochHour();
  const formattedHour = formatEpochHourUtc(currentHour);
  timestampEl.textContent = state.allHours
    ? `All hours (${hours.length}h window)`
    : formattedHour;
  railReadout.textContent = state.allHours ? `ALL HOURS (${hours.length}h)` : formattedHour;

  // Render tick marks where events exist
  const events = datasets?.events?.features || [];
  ticksEl.innerHTML = '';
  if (hours.length > 1 && events.length) {
    const denom = hours.length - 1;
    hours.forEach((h, idx) => {
      const hasEvent = events.some((ev) => {
        const p = ev.properties || {};
        if (state.mode === 'standard' && p.type !== 'jam') return false;
        return eventTouchesHour(p, h);
      });
      if (hasEvent) {
        const tick = document.createElement('span');
        tick.className = 'scrubber__tick';
        tick.style.left = `${(idx / denom) * 100}%`;
        ticksEl.appendChild(tick);
      }
    });
  }
}

function renderEventList() {
  const listEl = $('event-list');
  const emptyEl = $('event-list-empty');
  const badgeEl = $('event-count-badge');
  const hasAnyData =
    datasets.events.features.length > 0 ||
    datasets.hexes.features.length > 0 ||
    datasets.meta !== null;

  $('map-empty-banner').hidden = hasAnyData;

  const filtered = getFilteredEvents();
  badgeEl.textContent = formatInt(filtered.length);

  if (!filtered.length) {
    listEl.hidden = true;
    listEl.innerHTML = '';
    emptyEl.hidden = false;
    emptyEl.textContent = hasAnyData
      ? 'No events match the active mode and hour window.'
      : 'Run the pipeline to populate this panel';
    return;
  }

  emptyEl.hidden = true;
  listEl.hidden = false;
  listEl.innerHTML = '';

  const sorted = [...filtered].sort(
    (a, b) => Number(b.properties?.t_start_ms || 0) - Number(a.properties?.t_start_ms || 0)
  );

  for (const feature of sorted) {
    const p = feature.properties || {};
    const li = document.createElement('li');
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'event-card';
    if (p.event_id === state.selectedEventId) {
      btn.classList.add('is-selected');
    }

    const typeKey = p.type === 'jam' || p.type === 'spoof' ? p.type : 'mixed';
    const typeLabel =
      typeKey === 'jam' ? 'JAMMING' : typeKey === 'spoof' ? 'SPOOFING' : 'MIXED';

    btn.innerHTML = `
      <div class="event-card__top">
        <span class="event-card__id mono">${escapeHtml(p.event_id || 'unknown')}</span>
        <span class="type-pill type-pill--${typeKey}">${typeLabel}</span>
      </div>
      <div class="event-card__bottom mono">
        <span>${formatMsRangeUtc(p.t_start_ms, p.t_end_ms)}</span>
        <span>${formatInt(p.n_aircraft)} ac</span>
      </div>
    `;

    btn.addEventListener('click', () => selectEvent(p.event_id, true));
    li.appendChild(btn);
    listEl.appendChild(li);
  }
}

function renderDrawer() {
  const drawer = $('event-drawer');
  const resetBtn = $('btn-reset-view');

  if (!state.selectedEventId) {
    drawer.classList.remove('is-open');
    drawer.setAttribute('aria-hidden', 'true');
    resetBtn.hidden = true;
    return;
  }

  const feature = datasets.events.features.find(
    (f) => f.properties?.event_id === state.selectedEventId
  );
  if (!feature) {
    state.selectedEventId = null;
    drawer.classList.remove('is-open');
    drawer.setAttribute('aria-hidden', 'true');
    resetBtn.hidden = true;
    return;
  }

  const p = feature.properties || {};
  const typeKey = p.type === 'jam' || p.type === 'spoof' ? p.type : 'mixed';
  const typeLabel =
    typeKey === 'jam' ? 'JAMMING' : typeKey === 'spoof' ? 'SPOOFING' : 'MIXED';

  $('drawer-event-id').textContent = p.event_id || '—';
  const badge = $('drawer-type-badge');
  badge.className = `type-pill type-pill--${typeKey}`;
  badge.textContent = typeLabel;

  $('drawer-day').textContent = p.day || '—';
  $('drawer-window').textContent = formatMsRangeUtc(p.t_start_ms, p.t_end_ms);
  $('drawer-duration').textContent = formatDuration(p.t_start_ms, p.t_end_ms);
  $('drawer-aircraft').textContent = formatInt(p.n_aircraft);
  $('drawer-anomalies').textContent = formatInt(p.n_anomalies);
  $('drawer-minpts').textContent =
    typeof p.minpts === 'number' ? formatInt(p.minpts) : '—';

  const area = Number(p.region_area_km2);
  $('drawer-area').textContent =
    state.mode === 'standard'
      ? 'ICHNOS mode only'
      : Number.isFinite(area) && area > 0
        ? `${formatInt(area)} km²`
        : '—';

  let borderText = 'Unknown';
  if (p.border_feasible === true) borderText = 'Feasible (cross-border LoS)';
  else if (p.border_feasible === false) borderText = 'Domestic LoS envelope';
  $('drawer-border').textContent = state.mode === 'standard' ? 'ICHNOS mode only' : borderText;

  // Timeline bar position across total dataset hours
  const hours = datasets?.meta?.hours || [];
  const fillEl = $('drawer-timeline-fill');
  $('drawer-span-label').textContent = formatDuration(p.t_start_ms, p.t_end_ms);
  if (hours.length >= 1 && typeof p.t_start_ms === 'number' && typeof p.t_end_ms === 'number') {
    const spanStart = hours[0] * 3600 * 1000;
    const spanEnd = (hours[hours.length - 1] + 1) * 3600 * 1000;
    const total = Math.max(1, spanEnd - spanStart);
    const leftPct = Math.max(0, Math.min(100, ((p.t_start_ms - spanStart) / total) * 100));
    const widthPct = Math.max(2, Math.min(100 - leftPct, ((p.t_end_ms - p.t_start_ms) / total) * 100));
    fillEl.style.left = `${leftPct}%`;
    fillEl.style.width = `${widthPct}%`;
  } else {
    fillEl.style.left = '0%';
    fillEl.style.width = '100%';
  }

  drawer.classList.add('is-open');
  drawer.setAttribute('aria-hidden', 'false');
  resetBtn.hidden = false;
}

function renderBenchmarks() {
  const methods = datasets?.metrics?.methods || [];
  const emptyEl = $('benchmark-empty');
  const rowsEl = $('benchmark-rows');
  const noteEl = $('benchmark-note');

  noteEl.textContent = datasets?.metrics?.note || '';

  if (!methods.length) {
    emptyEl.hidden = false;
    rowsEl.hidden = true;
    return;
  }

  emptyEl.hidden = true;
  rowsEl.hidden = false;
  rowsEl.innerHTML = '';

  const ordered = [...methods].sort((a, b) => (a.method === 'ichnos' ? 1 : -1));

  for (const m of ordered) {
    const isIchnos = m.method === 'ichnos';
    const label = isIchnos ? 'ICHNOS (Lane 1 + Lane 2)' : 'Integrity-only baseline';
    const recallPct = Math.max(0, Math.min(100, (Number(m.recall) || 0) * 100));
    const ciLoPct = Math.max(0, Math.min(100, (Number(m.ci_lo) || 0) * 100));
    const ciHiPct = Math.max(ciLoPct, Math.min(100, (Number(m.ci_hi) || 0) * 100));

    const row = document.createElement('div');
    row.className = 'bench-row';
    row.innerHTML = `
      <div class="bench-row__head">
        <span class="bench-row__name">${label}</span>
        <span class="bench-row__metrics mono">
          Recall: <strong>${formatPct(m.recall)}</strong>
          (95% CI ${formatPct(m.ci_lo)}–${formatPct(m.ci_hi)})
        </span>
      </div>
      <div class="bench-bar-track" role="img" aria-label="${label} recall ${formatPct(
        m.recall
      )}, 95% confidence interval ${formatPct(m.ci_lo)} to ${formatPct(m.ci_hi)}">
        <div class="bench-bar-fill ${isIchnos ? 'bench-bar-fill--ichnos' : ''}" style="width: ${recallPct}%"></div>
        <div class="bench-ci-whisker" style="left: ${ciLoPct}%; width: ${Math.max(
          0.5,
          ciHiPct - ciLoPct
        )}%"></div>
      </div>
      <div class="bench-row__sub mono">
        <span>Windows detected: ${formatInt(m.detected)} / ${formatInt(m.n_windows)}</span>
        <span>False events: ${formatInt(m.fa_events)} / ${formatInt(
          m.control_hours
        )} control hrs (UB95: ${
          typeof m.fa_rate_ub95_per_h === 'number' ? m.fa_rate_ub95_per_h.toFixed(4) : '—'
        }/h)</span>
      </div>
    `;
    rowsEl.appendChild(row);
  }
}

function syncAll() {
  const isIchnos = state.mode === 'ichnos';

  $('mode-standard').classList.toggle('is-active', !isIchnos);
  $('mode-standard').setAttribute('aria-pressed', String(!isIchnos));
  $('mode-ichnos').classList.toggle('is-active', isIchnos);
  $('mode-ichnos').setAttribute('aria-pressed', String(isIchnos));

  document.querySelectorAll('[data-ichnos-only]').forEach((el) => {
    el.classList.toggle('is-hidden-mode', !isIchnos);
  });

  const hudDot = document.querySelector('#hud-mode-status .hud-dot');
  hudDot.className = `hud-dot ${isIchnos ? 'hud-dot--cyan' : 'hud-dot--amber'}`;
  $('hud-mode-label').textContent = isIchnos
    ? 'ICHNOS LANE 1 + LANE 2 ACTIVE'
    : 'STANDARD MAP · LANE 1 JAMMING ONLY';

  if (!isIchnos && state.selectedEventId) {
    const ev = datasets.events.features.find(
      (f) => f.properties?.event_id === state.selectedEventId
    );
    if (ev && ev.properties?.type !== 'jam') {
      state.selectedEventId = null;
    }
  }

  renderScrubber();
  renderEventList();
  renderDrawer();

  mapController?.applyState({
    mode: state.mode,
    allHours: state.allHours,
    selectedHour: getSelectedEpochHour(),
    selectedEventId: state.selectedEventId,
    layers: state.layers,
  });
}

function selectEvent(eventId, fly = true) {
  state.selectedEventId = eventId;
  syncAll();
  if (fly && eventId) {
    mapController?.flyToEvent(eventId);
  }
}

function stopPlayback() {
  state.playing = false;
  if (state.playTimer) {
    clearInterval(state.playTimer);
    state.playTimer = null;
  }
  $('play-icon').textContent = '▶';
  $('btn-play-pause').setAttribute('aria-label', 'Play timeline');
}

function togglePlayback() {
  const hours = datasets?.meta?.hours || [];
  if (!hours.length) return;

  if (state.playing) {
    stopPlayback();
    return;
  }

  const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  state.playing = true;
  state.allHours = false;
  $('chk-all-hours').checked = false;
  $('play-icon').textContent = '❚❚';
  $('btn-play-pause').setAttribute('aria-label', 'Pause timeline');
  syncAll();

  const stepMs = prefersReduced ? 2000 : 1000; // 1 hour per second; slower if reduced motion
  state.playTimer = setInterval(() => {
    state.hourIndex = (state.hourIndex + 1) % hours.length;
    syncAll();
  }, stepMs);
}

function escapeHtml(str) {
  return String(str)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;');
}

function wireEvents() {
  // Mode toggle
  $('mode-standard').addEventListener('click', () => {
    state.mode = 'standard';
    syncAll();
  });
  $('mode-ichnos').addEventListener('click', () => {
    state.mode = 'ichnos';
    syncAll();
  });

  // Hero strip collapse
  $('btn-toggle-hero').addEventListener('click', () => {
    const strip = $('hero-strip');
    const collapsed = strip.classList.toggle('is-collapsed');
    const btn = $('btn-toggle-hero');
    btn.setAttribute('aria-expanded', String(!collapsed));
    btn.querySelector('.hero-strip__toggle-text').textContent = collapsed ? 'Expand' : 'Collapse';
    btn.querySelector('.hero-strip__toggle-icon').textContent = collapsed ? '▼' : '▲';
    mapController?.map?.resize();
  });

  // Basemap switcher
  $('basemap-dark').addEventListener('click', () => {
    $('basemap-dark').classList.add('is-active');
    $('basemap-dark').setAttribute('aria-pressed', 'true');
    $('basemap-light').classList.remove('is-active');
    $('basemap-light').setAttribute('aria-pressed', 'false');
    mapController?.setBasemap('dark');
  });
  $('basemap-light').addEventListener('click', () => {
    $('basemap-light').classList.add('is-active');
    $('basemap-light').setAttribute('aria-pressed', 'true');
    $('basemap-dark').classList.remove('is-active');
    $('basemap-dark').setAttribute('aria-pressed', 'false');
    mapController?.setBasemap('light');
  });

  // Layer checkboxes
  const layerMap = {
    'layer-jamming': 'jamming',
    'layer-spoofing': 'spoofing',
    'layer-events': 'events',
    'layer-regions': 'regions',
    'layer-coverage': 'coverage',
  };
  Object.entries(layerMap).forEach(([elId, key]) => {
    $(elId).addEventListener('change', (e) => {
      state.layers[key] = e.target.checked;
      syncAll();
    });
  });

  // Time controls
  $('chk-all-hours').addEventListener('change', (e) => {
    state.allHours = e.target.checked;
    if (state.allHours) stopPlayback();
    syncAll();
  });

  $('scrubber-range').addEventListener('input', (e) => {
    stopPlayback();
    state.allHours = false;
    $('chk-all-hours').checked = false;
    state.hourIndex = Number(e.target.value) || 0;
    syncAll();
  });

  $('btn-play-pause').addEventListener('click', togglePlayback);

  // Drawer actions
  $('btn-close-drawer').addEventListener('click', () => selectEvent(null, false));
  $('btn-reset-view').addEventListener('click', () => selectEvent(null, false));
  $('btn-zoom-event').addEventListener('click', () => {
    if (state.selectedEventId) mapController?.flyToEvent(state.selectedEventId);
  });

  $('btn-copy-id').addEventListener('click', async () => {
    if (!state.selectedEventId) return;
    const btn = $('btn-copy-id');
    try {
      await navigator.clipboard.writeText(state.selectedEventId);
      btn.textContent = 'Copied';
      setTimeout(() => {
        btn.textContent = 'Copy event ID';
      }, 1500);
    } catch {
      btn.textContent = state.selectedEventId;
    }
  });

  // Method dialog
  const dialog = $('method-dialog');
  $('btn-open-method').addEventListener('click', () => dialog.showModal());
  $('btn-close-method').addEventListener('click', () => dialog.close());
  $('btn-dismiss-method').addEventListener('click', () => dialog.close());
  dialog.addEventListener('click', (e) => {
    if (e.target === dialog) dialog.close();
  });

  // Escape key clears event selection
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !dialog.open && state.selectedEventId) {
      selectEvent(null, false);
    }
  });
}

async function init() {
  datasets = await loadAllDatasets();

  renderHeroStats();
  renderBenchmarks();

  const tooltip = $('map-tooltip');
  mapController = new IchnosMap('map', datasets, {
    onHoverEvent(props, point) {
      const typeKey = props.type === 'jam' || props.type === 'spoof' ? props.type : 'mixed';
      const label =
        typeKey === 'jam' ? 'JAMMING' : typeKey === 'spoof' ? 'SPOOFING' : 'MIXED';
      tooltip.innerHTML = `
        <div class="map-tooltip__row">
          <span class="type-pill type-pill--${typeKey}">${label}</span>
          <span class="mono">${formatInt(props.n_aircraft)} aircraft</span>
        </div>
        <div class="map-tooltip__time mono">${formatMsRangeUtc(
          Number(props.t_start_ms),
          Number(props.t_end_ms)
        )}</div>
      `;
      tooltip.style.left = `${Math.min(point.x + 14, window.innerWidth - 260)}px`;
      tooltip.style.top = `${Math.max(12, point.y - 12)}px`;
      tooltip.hidden = false;
    },
    onLeaveEvent() {
      tooltip.hidden = true;
    },
    onSelectEvent(eventId) {
      tooltip.hidden = true;
      selectEvent(eventId, true);
    },
    onClearSelection() {
      selectEvent(null, false);
    },
  });

  wireEvents();
  syncAll();
}

init();