// GET /api/live?lat=28.5665&lon=77.1031&dist=150  ->  coarse GNSS-health snapshot from api.adsb.lol (ODbL)
const median = (a) => { const s = [...a].sort((x, y) => x - y); const m = s.length >> 1; return s.length % 2 ? s[m] : (s[m - 1] + s[m]) / 2; };
const r2 = (x) => Math.round(x * 100) / 100;

export default async function handler(req, res) {
  const q = req.query || {};
  const lat = Number(q.lat ?? 28.5665), lon = Number(q.lon ?? 77.1031);
  const dist = Math.min(Math.max(Number(q.dist ?? 150), 10), 250);
  if (!Number.isFinite(lat) || !Number.isFinite(lon)) return res.status(400).json({ error: 'bad lat/lon' });
  let j;
  try {
    const r = await fetch(`https://api.adsb.lol/v2/lat/${lat}/lon/${lon}/dist/${dist}`, { headers: { 'User-Agent': 'ichnos-research' } });
    if (!r.ok) return res.status(502).json({ error: `adsb.lol returned ${r.status}` });
    j = await r.json();
  } catch { return res.status(502).json({ error: 'adsb.lol unreachable' }); }

  const air = (j.ac || []).filter((a) => typeof a.lat === 'number' && typeof a.alt_baro === 'number' && a.alt_baro > 1000);
  const withNic = air.filter((a) => typeof a.nic === 'number' && (a.version ?? 2) >= 2); // skip ADS-B v0/v1 integrity
  const low = withNic.filter((a) => a.nic <= 6);
  const bands = {};
  for (const a of air) if (typeof a.alt_geom === 'number' && a.alt_baro >= 5000) (bands[Math.floor(a.alt_baro / 2000)] ||= []).push(a);
  const altOut = [];
  for (const list of Object.values(bands)) {
    if (list.length < 4) continue;
    const med = median(list.map((a) => a.alt_geom - a.alt_baro));
    for (const a of list) {
      const resid = a.alt_geom - a.alt_baro - med;
      if (Math.abs(resid) > 800) altOut.push({ lat: r2(a.lat), lon: r2(a.lon), alt_ft: a.alt_baro, resid_ft: Math.round(resid) });
    }
  }
  res.setHeader('Cache-Control', 's-maxage=30, stale-while-revalidate=60');
  res.status(200).json({
    generated_at: new Date().toISOString(), center: { lat, lon, dist_nm: dist },
    aircraft: air.length, with_nic: withNic.length, low_nic: low.length,
    low_nic_share: withNic.length ? low.length / withNic.length : null,
    low_nic_points: low.map((a) => ({ lat: r2(a.lat), lon: r2(a.lon), nic: a.nic })),
    alt_outliers: altOut,
    note: 'Single snapshot; no per-aircraft baseline. Source: api.adsb.lol contributors, ODbL 1.0',
  });
}