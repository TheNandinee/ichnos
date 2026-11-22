const KEY = import.meta.env.VITE_MAPTILER_KEY;
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { computeGeoBounds } from './data.js';

const BASEMAPS = {
  dark: {
    version: 8,
    sources: {
      carto: {
        type: 'raster',
        tiles: [
          `https://api.maptiler.com/maps/dataviz-dark/256/{z}/{x}/{y}@2x.png?key=${KEY}`,
          
          
        ],
        tileSize: 256,
        attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
      },
    },
    layers: [{ id: 'carto-base', type: 'raster', source: 'carto' }],
  },
  light: {
    version: 8,
    sources: {
      carto: {
        type: 'raster',
        tiles: [
          `https://api.maptiler.com/maps/dataviz/256/{z}/{x}/{y}@2x.png?key=${KEY}`,
          
          
        ],
        tileSize: 256,
        attribution: '&copy; OpenStreetMap contributors &copy; CARTO',
      },
    },
    layers: [{ id: 'carto-base', type: 'raster', source: 'carto' }],
  },
};

const INDIA_BOUNDS = [
  [67.5, 6.5],
  [97.8, 36.2],
];

export class IchnosMap {
  constructor(containerId, datasets, callbacks) {
    this.datasets = datasets;
    this.callbacks = callbacks;
    this.basemap = 'dark';
    this.state = {
      mode: 'ichnos',
      allHours: true,
      selectedHour: null,
      selectedEventId: null,
      layers: {
        jamming: true,
        spoofing: true,
        events: true,
        regions: true,
        coverage: false,
      },
    };

    this.map = new maplibregl.Map({
      container: containerId,
      style: BASEMAPS.dark,
      bounds: INDIA_BOUNDS,
      fitBoundsOptions: { padding: 28 },
      attributionControl: true,
    });

    this.map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');
    this.map.addControl(new maplibregl.ScaleControl({ unit: 'metric' }), 'bottom-right');

    this.map.on('style.load', () => {
      this._installDataLayers();
      this.applyState(this.state);
    });
  }

  setBasemap(theme) {
    if (theme !== 'dark' && theme !== 'light') return;
    if (this.basemap === theme) return;
    this.basemap = theme;
    this.map.setStyle(BASEMAPS[theme]);
  }

  _installDataLayers() {
    const { hexes, anomalies, events, regions, coverage } = this.datasets;

    if (!this.map.getSource('src-coverage')) {
      this.map.addSource('src-coverage', { type: 'geojson', data: coverage });
      this.map.addSource('src-hexes', { type: 'geojson', data: hexes });
      this.map.addSource('src-regions', { type: 'geojson', data: regions });
      this.map.addSource('src-anomalies', { type: 'geojson', data: anomalies });
      this.map.addSource('src-events', { type: 'geojson', data: events });
    }

    // 1. Receiver coverage
    this.map.addLayer({
      id: 'layer-coverage-fill',
      type: 'fill',
      source: 'src-coverage',
      paint: {
        'fill-color': '#00B3C7',
        'fill-opacity': [
          'interpolate',
          ['linear'],
          ['coalesce', ['get', 'reports_per_hour'], 0],
          0,
          0.02,
          50,
          0.12,
          500,
          0.26,
        ],
      },
    });

    // 2. Jamming hexes (Amber fill, opacity scaled by share)
    this.map.addLayer({
      id: 'layer-hexes-fill',
      type: 'fill',
      source: 'src-hexes',
      paint: {
        'fill-color': '#F5A524',
        'fill-opacity': [
          'interpolate',
          ['linear'],
          ['coalesce', ['get', 'share'], 0.1],
          0,
          0.12,
          0.5,
          0.48,
          1,
          0.78,
        ],
      },
    });

    this.map.addLayer({
      id: 'layer-hexes-outline',
      type: 'line',
      source: 'src-hexes',
      paint: {
        'line-color': '#F5A524',
        'line-width': 0.8,
        'line-opacity': 0.55,
      },
    });

    // 3. Feasible regions (Saffron dashed outline with light fill)
    this.map.addLayer({
      id: 'layer-regions-fill',
      type: 'fill',
      source: 'src-regions',
      paint: {
        'fill-color': '#FF9933',
        'fill-opacity': 0.1,
      },
    });

    this.map.addLayer({
      id: 'layer-regions-outline',
      type: 'line',
      source: 'src-regions',
      paint: {
        'line-color': '#FF9933',
        'line-width': 1.75,
        'line-dasharray': [3, 2],
        'line-opacity': 0.9,
      },
    });

    // 4. Spoofing points (Alert Red, radius 3)
    this.map.addLayer({
      id: 'layer-anomalies-pts',
      type: 'circle',
      source: 'src-anomalies',
      paint: {
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 4, 3, 7, 6, 10, 10],
        'circle-color': '#E5484D',
        'circle-opacity': 0.95,
        'circle-stroke-color': '#FFFFFF',
        'circle-stroke-width': 1,
      },
    });

    // 5. Clustered Events (Outlined circles sized by n_aircraft, coloured by type)
    this.map.addLayer({
      id: 'layer-events-circles',
      type: 'circle',
      source: 'src-events',
      paint: {
        'circle-radius': [
          'interpolate',
          ['linear'],
          ['coalesce', ['get', 'n_aircraft'], 1],
          1,
          6,
          10,
          11,
          40,
          18,
        ],
        'circle-color': [
          'match',
          ['get', 'type'],
          'jam',
          'rgba(245, 165, 36, 0.22)',
          'spoof',
          'rgba(229, 72, 77, 0.22)',
          'rgba(0, 179, 199, 0.22)',
        ],
        'circle-stroke-width': 2.2,
        'circle-stroke-color': [
          'match',
          ['get', 'type'],
          'jam',
          '#F5A524',
          'spoof',
          '#E5484D',
          '#00B3C7',
        ],
        'circle-opacity': 1,
        'circle-stroke-opacity': 1,
      },
    });

    this._bindInteractions();
  }

  _bindInteractions() {
    this.map.on('mouseenter', 'layer-events-circles', () => {
      this.map.getCanvas().style.cursor = 'pointer';
    });

    this.map.on('mousemove', 'layer-events-circles', (e) => {
      const feature = e.features && e.features[0];
      if (!feature) return;
      this.callbacks.onHoverEvent?.(feature.properties, e.point);
    });

    this.map.on('mouseleave', 'layer-events-circles', () => {
      this.map.getCanvas().style.cursor = '';
      this.callbacks.onLeaveEvent?.();
    });

    this.map.on('click', 'layer-events-circles', (e) => {
      const feature = e.features && e.features[0];
      if (!feature) return;
      this.callbacks.onSelectEvent?.(feature.properties.event_id);
    });

    this.map.on('click', (e) => {
      const hits = this.map.queryRenderedFeatures(e.point, {
        layers: ['layer-events-circles'],
      });
      if (!hits.length && this.state.selectedEventId) {
        this.callbacks.onClearSelection?.();
      }
    });
  }

  applyState(nextState) {
    this.state = { ...this.state, ...nextState };
    if (!this.map.isStyleLoaded() || !this.map.getLayer('layer-events-circles')) return;

    const { mode, allHours, selectedHour, selectedEventId, layers } = this.state;
    const isIchnos = mode === 'ichnos';
    const dimFactor = selectedEventId ? 0.3 : 1;

    // Layer visibilities
    this._setVisible('layer-coverage-fill', layers.coverage);
    this._setVisible('layer-hexes-fill', layers.jamming);
    this._setVisible('layer-hexes-outline', layers.jamming);
    this._setVisible('layer-anomalies-pts', isIchnos && layers.spoofing);
    this._setVisible('layer-regions-fill', isIchnos && layers.regions);
    this._setVisible('layer-regions-outline', isIchnos && layers.regions);
    this._setVisible('layer-events-circles', layers.events);

    // Hour filters
    const hexFilter = allHours
      ? ['==', ['get', 'hour'], -1]
      : ['==', ['get', 'hour'], selectedHour];
    this.map.setFilter('layer-hexes-fill', hexFilter);
    this.map.setFilter('layer-hexes-outline', hexFilter);

    const anomalyFilter = allHours ? null : ['==', ['get', 'hour'], selectedHour];
    this.map.setFilter('layer-anomalies-pts', anomalyFilter);

    const hourStartMs = typeof selectedHour === 'number' ? selectedHour * 3600 * 1000 : 0;
    const hourEndMs = hourStartMs + 3600 * 1000;

    const eventFilters = ['all'];
    if (!isIchnos) {
      eventFilters.push(['==', ['get', 'type'], 'jam']);
    }
    if (!allHours && typeof selectedHour === 'number') {
      eventFilters.push(['<', ['get', 't_start_ms'], hourEndMs]);
      eventFilters.push(['>=', ['get', 't_end_ms'], hourStartMs]);
    }
    this.map.setFilter('layer-events-circles', eventFilters.length > 1 ? eventFilters : null);

    // Feasible regions filter (visible events + selected event isolation)
    const visibleEventIds = this._getVisibleEventIds();
    const regionFilter = selectedEventId
      ? ['==', ['get', 'event_id'], selectedEventId]
      : visibleEventIds.length
        ? ['in', ['get', 'event_id'], ['literal', visibleEventIds]]
        : ['==', ['get', 'event_id'], '__none__'];
    this.map.setFilter('layer-regions-fill', regionFilter);
    this.map.setFilter('layer-regions-outline', regionFilter);

    // Dimming everything else to 30% opacity when an event is selected
    this.map.setPaintProperty('layer-coverage-fill', 'fill-opacity', 0.14 * dimFactor);

    this.map.setPaintProperty('layer-hexes-fill', 'fill-opacity', [
      '*',
      dimFactor,
      [
        'interpolate',
        ['linear'],
        ['coalesce', ['get', 'share'], 0.1],
        0,
        0.12,
        0.5,
        0.48,
        1,
        0.78,
      ],
    ]);
    this.map.setPaintProperty('layer-hexes-outline', 'line-opacity', 0.55 * dimFactor);
    this.map.setPaintProperty('layer-anomalies-pts', 'circle-opacity', 0.88 * dimFactor);

    this.map.setPaintProperty(
      'layer-regions-fill',
      'fill-opacity',
      selectedEventId ? 0.16 : 0.1 * dimFactor
    );
    this.map.setPaintProperty(
      'layer-regions-outline',
      'line-opacity',
      selectedEventId ? 1.0 : 0.9 * dimFactor
    );

    if (selectedEventId) {
      this.map.setPaintProperty('layer-events-circles', 'circle-opacity', [
        'case',
        ['==', ['get', 'event_id'], selectedEventId],
        1.0,
        0.3,
      ]);
      this.map.setPaintProperty('layer-events-circles', 'circle-stroke-opacity', [
        'case',
        ['==', ['get', 'event_id'], selectedEventId],
        1.0,
        0.3,
      ]);
      this.map.setPaintProperty('layer-events-circles', 'circle-stroke-color', [
        'case',
        ['==', ['get', 'event_id'], selectedEventId],
        '#FF9933',
        [
          'match',
          ['get', 'type'],
          'jam',
          '#F5A524',
          'spoof',
          '#E5484D',
          '#00B3C7',
        ],
      ]);
    } else {
      this.map.setPaintProperty('layer-events-circles', 'circle-opacity', 1.0);
      this.map.setPaintProperty('layer-events-circles', 'circle-stroke-opacity', 1.0);
      this.map.setPaintProperty('layer-events-circles', 'circle-stroke-color', [
        'match',
        ['get', 'type'],
        'jam',
        '#F5A524',
        'spoof',
        '#E5484D',
        '#00B3C7',
      ]);
    }
  }

  _getVisibleEventIds() {
    const { mode, allHours, selectedHour } = this.state;
    const isIchnos = mode === 'ichnos';
    const h0 = typeof selectedHour === 'number' ? selectedHour * 3600 * 1000 : 0;
    const h1 = h0 + 3600 * 1000;

    return this.datasets.events.features
      .filter((f) => {
        const p = f.properties || {};
        if (!isIchnos && p.type !== 'jam') return false;
        if (!allHours && typeof selectedHour === 'number') {
          if (!(Number(p.t_start_ms) < h1 && Number(p.t_end_ms) >= h0)) return false;
        }
        return true;
      })
      .map((f) => f.properties.event_id);
  }

  _setVisible(layerId, visible) {
    if (!this.map.getLayer(layerId)) return;
    this.map.setLayoutProperty(layerId, 'visibility', visible ? 'visible' : 'none');
  }

  flyToEvent(eventId) {
    const eventFeature = this.datasets.events.features.find(
      (f) => f.properties?.event_id === eventId
    );
    const regionFeature = this.datasets.regions.features.find(
      (f) => f.properties?.event_id === eventId
    );
    const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (regionFeature && this.state.mode === 'ichnos') {
      const bounds = computeGeoBounds(regionFeature);
      if (bounds) {
        this.map.fitBounds(bounds, {
          padding: { top: 80, bottom: 110, left: 60, right: 400 },
          maxZoom: 8.5,
          duration: prefersReduced ? 0 : 750,
        });
        return;
      }
    }

    if (eventFeature?.geometry?.type === 'Point') {
      this.map.flyTo({
        center: eventFeature.geometry.coordinates,
        zoom: 7.2,
        padding: { right: 340 },
        duration: prefersReduced ? 0 : 750,
      });
    }
  }
}