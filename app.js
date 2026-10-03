import * as maplibregl from "https://cdn.jsdelivr.net/npm/maplibre-gl@6.11.2/dist/maplibre-gl.mjs";
import proj4 from "https://cdn.jsdelivr.net/npm/proj4@2.22.0/+esm";
import { search } from "./js/search.js";
import { pointInFeature } from "./js/lookup.js";
import { toChomeQuery } from "./js/address.js";

// Regions (one per prefecture) are listed in regions.json. The wide view (below DETAIL_ZOOM) shows one light
// overview of all regions; a region's detailed data are loaded when it comes into view closer in, or on a click.
const MANIFEST = new URLSearchParams(location.search).get("manifest") || "data/regions.json";
const STYLE = "https://tiles.openfreemap.org/styles/liberty";
const PHOTO = "https://cyberjapandata.gsi.go.jp/xyz/seamlessphoto/{z}/{x}/{y}.jpg";
const PALETTE = ["#8dd3c7", "#fdb462", "#bebada", "#80b1d3", "#b3de69", "#fccde5"];
const OWN = "#c2410c";
const OTHER = "#1d4ed8";
const EMPTY = { type: "FeatureCollection", features: [] };
const DETAIL_ZOOM = 12;

const state = {
  manifest: null,
  regions: new Map(), // name -> { info, loading, meta, stations, territories, aoi, far, band, chunks, iso }
  byKey: new Map(), // station key -> [{ R, s }] across loaded regions
  points: new Map(), // station key -> { key, name, lon, lat, regions } (overview: every station)
  overview: null,
  detailZoom: 0, // DETAIL_ZOOM when the manifest has an overview
  mPerMin: 80,
  limitM: 1200,
  marker: null,
  isoReq: 0,
  places: null,
};
const $ = (id) => document.getElementById(id);
const minutes = (m) => Math.max(1, Math.ceil(m / state.mPerMin - 1e-9));
const approx = (m) => `約${(Math.round(m / 10) * 10).toLocaleString()}m`;

async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`${url}: ${r.status}`);
  return r.json();
}

function el(tag, attrs = {}, ...children) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v);
  }
  for (const c of children) e.append(c);
  return e;
}

// --- regions ---
const inBox = (b, lng, lat) => lng >= b[0] && lng <= b[2] && lat >= b[1] && lat <= b[3];
const boxesMeet = (a, b) => a[0] <= b[2] && b[0] <= a[2] && a[1] <= b[3] && b[1] <= a[3];

function loadRegion(name) {
  const R = state.regions.get(name);
  if (!R.loading) {
    R.loading = (async () => {
      const base = R.info.path;
      const files = ["meta.json", "stations.json", "territories.geojson", "aoi.geojson", "far.geojson", "band.geojson", "lines.geojson"];
      const [meta, stations, territories, aoi, far, band, lines] = await Promise.all(files.map((f) => getJSON(base + f)));
      for (const f of territories.features) f.properties.r = name;
      Object.assign(R, { meta, stations, territories, aoi, far, band, lines });
      state.mPerMin = meta.m_per_min;
      state.limitM = meta.limit_m;
      for (const s of stations) {
        if (!state.byKey.has(s.key)) state.byKey.set(s.key, []);
        state.byKey.get(s.key).push({ R, s });
      }
      if (!state.metaShown) {
        state.metaShown = true;
        fillMeta(meta);
      }
      refreshSources();
      return R;
    })();
  }
  return R.loading;
}

const loaded = () => [...state.regions.values()].filter((R) => R.meta);

function refreshSources() {
  if (!map.getSource("t")) return;
  const all = (k) => ({ type: "FeatureCollection", features: loaded().flatMap((R) => R[k].features) });
  map.getSource("t").setData(all("territories"));
  map.getSource("far").setData(all("far"));
  map.getSource("band").setData(all("band"));
  map.getSource("lines").setData(all("lines"));
  if (!state.overview) {
    for (const R of loaded()) for (const s of R.stations) addPoint(s.key, s.name, s.lon, s.lat, [R.info.name]);
    refreshPoints();
  }
}

function addPoint(key, name, lon, lat, regions) {
  if (!state.points.has(key)) state.points.set(key, { key, name, lon, lat, regions });
}

function refreshPoints() {
  const features = [...state.points.values()].map((p) => ({
    type: "Feature", properties: { k: p.key, name: p.name }, geometry: { type: "Point", coordinates: [p.lon, p.lat] },
  }));
  map.getSource("st").setData({ type: "FeatureCollection", features });
}

function loadVisible() {
  if (map.getZoom() < state.detailZoom) return Promise.resolve([]);
  const b = map.getBounds();
  const view = [b.getWest(), b.getSouth(), b.getEast(), b.getNorth()];
  return Promise.all(state.manifest.regions.filter((r) => boxesMeet(view, r.bbox)).map((r) => loadRegion(r.name)));
}

async function regionAt(lng, lat) {
  for (const info of state.manifest.regions.filter((r) => inBox(r.bbox, lng, lat))) {
    const R = await loadRegion(info.name);
    if (R.aoi.features.some((f) => pointInFeature([lng, lat], f))) return R;
  }
  return null;
}

// --- data lookups ---
function loadChunk(R, cx, cy) {
  const key = `${cx}_${cy}`;
  if (!R.chunks.has(key)) {
    R.chunks.set(key, fetch(`${R.info.path}cells/${key}.json`).then((r) => (r.ok ? r.json() : null)));
  }
  return R.chunks.get(key);
}

async function cellValues(R, lng, lat) {
  const g = R.meta.grid;
  const [x, y] = proj4("EPSG:4326", g.proj4, [lng, lat]);
  const c = Math.floor((x - g.x0) / g.cell);
  const r = Math.floor((y - g.y0) / g.cell);
  if (c < 0 || r < 0 || c >= g.nx || r >= g.ny) return null;
  const arr = await loadChunk(R, Math.floor(c / g.chunk), Math.floor(r / g.chunk));
  const v = arr?.[(r % g.chunk) * g.chunk + (c % g.chunk)];
  if (!v) return null;
  const out = [];
  for (let i = 0; i < v.length; i += 2) out.push({ g: v[i], d: v[i + 1] });
  return out;
}

function ownerAt(R, lng, lat) {
  const f = R.territories.features.find((f) => pointInFeature([lng, lat], f));
  return f ? f.properties.g : null;
}

async function lookup(lng, lat) {
  const R = await regionAt(lng, lat);
  if (!R) return { status: "outside" };
  const vals = await cellValues(R, lng, lat);
  if (!vals) return { status: "blank", R, owner: ownerAt(R, lng, lat) };
  // the drawn territory decides the owner; if its station is not in this cell's data, trust the data
  const drawn = ownerAt(R, lng, lat);
  const own = vals.find((x) => x.g === drawn) ?? vals[0];
  const others = vals.filter((x) => x.g !== own.g && x.d <= state.limitM).sort((a, b) => a.d - b.d);
  return { status: "ok", R, owner: own.g, ownD: own.d, others };
}

function loadIso(R, id) {
  if (!R.iso.has(id)) R.iso.set(id, fetch(`${R.info.path}iso/${id}.json`).then((r) => (r.ok ? r.json() : null)));
  return R.iso.get(id);
}

// Outlines of a station come from every loaded region that has it.
async function highlight(ownKey, otherKeys) {
  const req = ++state.isoReq;
  map.setFilter("sel-line", ["any", ["==", ["get", "a"], ownKey ?? "-"], ["==", ["get", "b"], ownKey ?? "-"]]);
  map.setFilter("st-sel", ["==", ["get", "k"], ownKey ?? ""]);
  const keys = ownKey == null ? [] : [ownKey, ...otherKeys];
  const jobs = keys.flatMap((k) =>
    (state.byKey.get(k) || []).filter(({ s }) => s.iso).map(({ R, s }) => loadIso(R, s.id).then((f) => f && { f, k })),
  );
  const found = (await Promise.all(jobs)).filter(Boolean);
  if (req !== state.isoReq) return;
  map.getSource("iso").setData({
    type: "FeatureCollection",
    features: found.map(({ f, k }) => ({ ...f, properties: { k, own: k === ownKey } })),
  });
}

// --- panels ---
const lineText = (s) => s.lines.map((l) => l.line).join("・");

// One station across regions: area summed, farthest point the maximum, share within 15 minutes weighted by area.
function stationSummary(key) {
  const parts = (state.byKey.get(key) || []).map((x) => x.s);
  const inside = parts.filter((s) => s.area_km2 != null);
  const area = inside.reduce((a, s) => a + s.area_km2, 0);
  return {
    ...parts[0],
    area_km2: inside.length ? Math.round(area * 100) / 100 : null,
    far_m: inside.length ? Math.max(...inside.map((s) => s.far_m)) : null,
    within: inside.length && area > 0 ? inside.reduce((a, s) => a + s.within * s.area_km2, 0) / area : null,
  };
}

function showPanel(...children) {
  $("result").replaceChildren(...children);
  $("panel").hidden = false;
  $("hint").hidden = true;
}

function renderPoint(res) {
  if (res.status === "outside") {
    const names = state.manifest.regions.map((r) => r.label).join("・");
    showPanel(el("p", { class: "status" }, `対象範囲の外です (${names})。`));
    highlight(null, []);
    return;
  }
  const st = (g) => res.R.stations[g];
  if (res.status === "blank") {
    if (res.owner != null) {
      showPanel(
        el("h2", {}, `${st(res.owner).name}駅の縄張りの中です`),
        el("p", {}, "ただし、川・池などの水面や道から遠い所なので、道のりは出していません (地図では色を薄くしています)。"),
      );
      highlight(st(res.owner).key, []);
    } else {
      showPanel(el("p", { class: "status" }, "この地点は計算していません (海・川・池や、道から遠い所です)。"));
      highlight(null, []);
    }
    return;
  }
  const own = st(res.owner);
  const head = el("h2", {}, "ここは ", el("b", {}, `${own.name}駅`), ` の勢力圏 (徒歩 ${minutes(res.ownD)} 分)`);
  // small islands are drawn as part of the surrounding territory; say so when another station is nearer
  const nearer = res.others.find((o) => o.d < res.ownD);
  const note = nearer
    ? el("p", { class: "sub" }, `地図では小さな飛び地をまわりの縄張りに含めています。いちばん近いのは ${st(nearer.g).name}駅 (${minutes(nearer.d)} 分) です。`)
    : "";
  const sub =
    res.others.length > 0
      ? el("p", {}, `${res.others.map((o) => `${st(o.g).name}駅 (${minutes(o.d)} 分)`).join("・")} の 15 分圏とも重なります。`)
      : res.ownD > state.limitM
        ? el("p", {}, "徒歩 15 分以内に行ける駅はありません。")
        : el("p", {}, "ほかの駅の 15 分圏とは重なりません。");
  const rows = [{ g: res.owner, d: res.ownD, own: true }, ...res.others].map((o) =>
    el(
      "tr",
      { class: o.own ? "own" : "" },
      el("td", {}, el("button", { type: "button", class: "link", onclick: () => selectStation(st(o.g).key, false) }, st(o.g).name)),
      el("td", { class: "sub" }, lineText(st(o.g))),
      el("td", { class: "r" }, el("b", {}, `${minutes(o.d)} 分`), ` ${approx(o.d)}`),
    ),
  );
  showPanel(head, note, sub, el("table", {}, ...rows), el("p", { class: "sub" }, "太線 = 勢力圏の駅の縄張り / 破線 = 15 分圏 (橙: 勢力圏の駅、青: 重なる駅)"));
  highlight(own.key, res.others.map((o) => st(o.g).key));
}

function renderStation(key) {
  const s = stationSummary(key);
  const stats =
    s.area_km2 == null
      ? [el("tr", {}, el("td", {}, "縄張り"), el("td", { class: "r" }, "対象範囲の外"))]
      : [
          el("tr", {}, el("td", {}, "縄張りの広さ"), el("td", { class: "r" }, el("b", {}, `${s.area_km2} km²`))),
          el("tr", {}, el("td", {}, "縄張りでいちばん遠い所"), el("td", { class: "r" }, el("b", {}, `徒歩 ${minutes(s.far_m)} 分`), ` (${approx(s.far_m)})`)),
          el("tr", {}, el("td", {}, "縄張りのうち 15 分以内"), el("td", { class: "r" }, el("b", {}, `${Math.round(s.within * 100)}%`))),
        ];
  showPanel(
    el("h2", {}, `${s.name}駅の縄張り`),
    el("p", { class: "sub" }, lineText(s)),
    el("table", {}, ...stats),
    el("p", { class: "sub" }, "太線 = 縄張り / 破線 = 15 分圏 (縄張りの外にもはみ出します)"),
  );
  highlight(key, []);
}

async function showPoint(lng, lat) {
  if (!state.marker) state.marker = new maplibregl.Marker({ color: OWN });
  state.marker.setLngLat([lng, lat]).addTo(map);
  await ready;
  renderPoint(await lookup(lng, lat));
}

async function selectStation(key, fly = true) {
  await ready;
  state.marker?.remove();
  const p = state.points.get(key) ?? stationSummary(key);
  if (fly) map.flyTo({ center: [p.lon, p.lat], zoom: 14 });
  // every region that lists the station (one near a border may have territory in several)
  const names = new Set(p.regions ?? []);
  for (const r of state.manifest.regions) if (inBox(r.bbox, p.lon, p.lat)) names.add(r.name);
  await Promise.all([...names].map((n) => loadRegion(n)));
  renderStation(key);
}

// --- map ---
const hadHash = Boolean(location.hash); // the map writes its own hash right away
const map = new maplibregl.Map({
  container: "map",
  style: STYLE,
  center: [139.6, 35.69],
  zoom: 10,
  hash: true,
  attributionControl: {
    compact: true,
    customAttribution: [
      "道路: © OpenStreetMap contributors (ODbL)",
      '駅・行政区域: <a href="https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N02-2025.html">国土数値情報（鉄道データ）</a>・<a href="https://nlftp.mlit.go.jp/ksj/gml/datalist/KsjTmplt-N03-2026.html">（行政区域データ）</a>（国土交通省）を加工',
      '町丁目: <a href="https://www.digital.go.jp/policies/base_registry_address">アドレス・ベース・レジストリ</a>（デジタル庁）を加工',
    ],
  },
});
map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");

const manifestReady = getJSON(MANIFEST).then((manifest) => {
  state.manifest = manifest;
  for (const info of manifest.regions) state.regions.set(info.name, { info, chunks: new Map(), iso: new Map() });
  if (manifest.overview) state.detailZoom = DETAIL_ZOOM; // before jumpTo: its moveend loads what is in view
  if (!hadHash && manifest.home) map.jumpTo({ center: manifest.home.center, zoom: manifest.home.zoom + 1 });
  $("legend").replaceChildren(...legend());
  if (manifest.overview) {
    return getJSON(manifest.overview).then((ov) => {
      state.overview = ov;
      for (const [key, name, lon, lat, regions] of ov.st) addPoint(key, name, lon, lat, regions);
    });
  }
});

function japaneseLabels() {
  for (const layer of map.getStyle().layers) {
    const tf = layer.layout?.["text-field"];
    if (tf && JSON.stringify(tf).includes("name")) {
      map.setLayoutProperty(layer.id, "text-field", ["coalesce", ["get", "name:ja"], ["get", "name"]]);
    }
    // points of interest and road numbers (route shields such as E14 or 127) are hidden
    if (layer.id.startsWith("poi_") || layer.id.includes("shield")) map.setLayoutProperty(layer.id, "visibility", "none");
  }
}

// Our fills go above every basemap fill (buildings included) and below the labels that follow them.
function overlayAnchor() {
  const layers = map.getStyle().layers;
  let last = -1;
  layers.forEach((l, i) => {
    if (l.type === "fill" || l.type === "fill-extrusion") last = i;
  });
  return layers.slice(last + 1).find((l) => l.type === "symbol")?.id;
}

function hatch() {
  const cv = document.createElement("canvas");
  cv.width = cv.height = 12;
  const cx = cv.getContext("2d");
  cx.strokeStyle = "rgba(40,40,40,0.55)";
  cx.lineWidth = 1.4;
  for (const o of [-12, 0, 12]) {
    cx.beginPath();
    cx.moveTo(o, 12);
    cx.lineTo(o + 12, 0);
    cx.stroke();
  }
  return cx.getImageData(0, 0, 12, 12);
}

function addOverlays() {
  const below = overlayAnchor();
  map.addImage("hatch", hatch());
  map.addSource("photo", {
    type: "raster", tiles: [PHOTO], tileSize: 256, maxzoom: 18,
    attribution:
      '<a href="https://maps.gsi.go.jp/development/ichiran.html">地理院タイル</a> (全国最新写真 (シームレス)。データソース：Landsat8画像（GSI,TSIC,GEO Grid/AIST）, Landsat8画像（courtesy of the U.S. Geological Survey）, 海底地形（GEBCO）)',
  });
  map.addLayer({ id: "photo", type: "raster", source: "photo", layout: { visibility: "none" } }, below);
  const colorExpr = ["match", ["get", "c"], 0, PALETTE[0], 1, PALETTE[1], 2, PALETTE[2], 3, PALETTE[3], 4, PALETTE[4], PALETTE[5]];
  const fills = {
    t: { "fill-color": colorExpr, "fill-opacity": 0.55, "fill-antialias": false },
    far: { "fill-color": "#fff", "fill-opacity": 0.55, "fill-antialias": false },
    band: { "fill-pattern": "hatch", "fill-opacity": 0.6, "fill-antialias": false },
  };
  const linePaint = { "line-color": "#3a3f45", "line-width": ["interpolate", ["linear"], ["zoom"], 10, 0.4, 13, 0.9, 16, 1.8] };
  // wide view: the overview (territories already joined across prefecture borders, so their outlines are the lines)
  const ov = state.overview;
  if (ov) {
    for (const k of ["t", "far", "band"]) {
      map.addSource(`ov-${k}`, { type: "geojson", data: ov[k] });
      map.addLayer({ id: `ov-${k}`, type: "fill", source: `ov-${k}`, maxzoom: state.detailZoom, paint: fills[k] }, below);
    }
    map.addLayer({ id: "ov-line", type: "line", source: "ov-t", maxzoom: state.detailZoom, paint: linePaint }, below);
  }
  // closer in: the regions' detailed data
  const zoom = ov ? { minzoom: state.detailZoom } : {};
  map.addSource("t", { type: "geojson", data: EMPTY });
  map.addLayer({ id: "t-fill", type: "fill", source: "t", ...zoom, paint: fills.t }, below);
  map.addSource("far", { type: "geojson", data: EMPTY });
  map.addLayer({ id: "far", type: "fill", source: "far", ...zoom, paint: fills.far }, below);
  map.addSource("band", { type: "geojson", data: EMPTY });
  map.addLayer({ id: "band", type: "fill", source: "band", ...zoom, paint: fills.band }, below);
  // borders between different stations only (lines.geojson from combine): a territory that spans two
  // prefectures has no line at the border, and no dashed region outline is drawn
  map.addSource("lines", { type: "geojson", data: EMPTY });
  map.addLayer({ id: "t-line", type: "line", source: "lines", ...zoom, paint: linePaint }, below);
  map.addSource("iso", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
  map.addLayer({ id: "sel-line", type: "line", source: "lines", filter: ["==", ["get", "a"], "-"], paint: { "line-color": OWN, "line-width": 4 } });
  map.addLayer({ id: "iso-own", type: "line", source: "iso", filter: ["==", ["get", "own"], true], paint: { "line-color": OWN, "line-width": 2, "line-dasharray": [3, 2] } });
  map.addLayer({ id: "iso-other", type: "line", source: "iso", filter: ["==", ["get", "own"], false], paint: { "line-color": OTHER, "line-width": 1.6, "line-dasharray": [3, 2] } });
  map.addSource("st", { type: "geojson", data: EMPTY });
  map.addLayer({ id: "st-dot", type: "circle", source: "st", minzoom: 11, paint: { "circle-radius": 4, "circle-color": "#fff", "circle-stroke-color": "#1f2328", "circle-stroke-width": 2 } });
  map.addLayer({ id: "st-sel", type: "circle", source: "st", filter: ["==", ["get", "k"], ""], paint: { "circle-radius": 7, "circle-color": OWN, "circle-stroke-color": "#fff", "circle-stroke-width": 2 } });
  map.addLayer({
    id: "st-name", type: "symbol", source: "st", minzoom: 11.5,
    layout: { "text-field": ["get", "name"], "text-font": ["Noto Sans Bold"], "text-size": 13, "text-offset": [0, 1.0], "text-anchor": "top" },
    paint: { "text-color": "#111", "text-halo-color": "#fff", "text-halo-width": 2 },
  });
}

const ready = new Promise((resolve) => {
  map.once("style.load", async () => {
    japaneseLabels();
    await manifestReady;
    addOverlays();
    refreshPoints();
    await loadVisible();
    resolve();
  });
});

map.on("moveend", () => {
  if (state.manifest) loadVisible();
});

map.on("click", async (e) => {
  await ready;
  const hit = map.queryRenderedFeatures(e.point, { layers: ["st-dot", "st-name"] })[0];
  if (hit) selectStation(hit.properties.k, false);
  else showPoint(e.lngLat.lng, e.lngLat.lat);
});
for (const id of ["st-dot", "st-name"]) {
  map.on("mouseenter", id, () => (map.getCanvas().style.cursor = "pointer"));
  map.on("mouseleave", id, () => (map.getCanvas().style.cursor = ""));
}

// --- controls ---
function legend() {
  return [
    el("div", {}, ...PALETTE.slice(0, 4).map((c) => el("i", { class: "sw", style: `background:${c}` })), " 駅ごとの縄張り"),
    el("div", {}, el("i", { class: "sw hatch" }), " 2 駅とも 15 分以内で、差が 3 分以内"),
    el("div", {}, el("i", { class: "sw pale" }), " 15 分超、または水面など (道のりなし)"),
  ];
}

for (const b of document.querySelectorAll("[data-base]")) {
  b.addEventListener("click", async () => {
    await ready;
    map.setLayoutProperty("photo", "visibility", b.dataset.base === "photo" ? "visible" : "none");
    for (const x of document.querySelectorAll("[data-base]")) x.setAttribute("aria-pressed", String(x === b));
  });
}

$("locate").addEventListener("click", () => {
  if (!navigator.geolocation) return alert("このブラウザでは現在地を使えません。");
  navigator.geolocation.getCurrentPosition(
    (p) => {
      const { longitude: lng, latitude: lat } = p.coords;
      map.flyTo({ center: [lng, lat], zoom: 16 });
      showPoint(lng, lat);
    },
    () => alert("現在地を取得できませんでした。"),
    { enableHighAccuracy: true, timeout: 10000 },
  );
});

$("panel-close").addEventListener("click", () => {
  $("panel").hidden = true;
  state.marker?.remove();
  highlight(null, []);
});

const about = $("about");
for (const b of document.querySelectorAll("#about-open, [data-open-about]")) b.addEventListener("click", () => about.showModal());

function fillMeta(meta) {
  const s = meta.sources;
  const date = (k) => s[k]?.file ?? "";
  document.querySelector('[data-meta="osm"]').textContent = `(${date("osm-kanto")})`;
  document.querySelector('[data-meta="ksj"]').textContent = `(${date("n02")}, N03 2026)`;
  document.querySelector('[data-meta="ekiwalk"]').textContent = `(${meta.ekiwalk.commit.slice(0, 7)})`;
  document.querySelector('[data-meta="built"]').textContent = ` 計算日: ${meta.built_at_utc.slice(0, 10)}`;
}

// --- search (places.json is loaded on first use) ---
// Search rows of every region; a station listed by several regions is kept once.
async function places() {
  if (!state.places) {
    state.places = (async () => {
      const lists = await Promise.all(state.manifest.regions.map((r) => getJSON(r.path + "places.json").catch(() => [])));
      const seen = new Set();
      return lists.flat().filter((row) => {
        const id = row[4] === "s" ? `${row[0]}@${row[2].toFixed(3)},${row[3].toFixed(3)}` : `${row[0]}@${row[4]}`;
        if (seen.has(id)) return false;
        seen.add(id);
        return true;
      });
    })();
  }
  return state.places;
}

async function stationKeyForPlace(row) {
  const name = row[0].replace(/駅$/, "");
  await Promise.all(state.manifest.regions.filter((r) => inBox(r.bbox, row[2], row[3])).map((r) => loadRegion(r.name)));
  const all = loaded().flatMap((R) => R.stations);
  const cands = all.filter((s) => s.name === name);
  const pool = cands.length ? cands : all;
  return pool.reduce((best, s) => {
    const d = (s.lon - row[2]) ** 2 + (s.lat - row[3]) ** 2;
    return !best || d < best.d ? { s, d } : best;
  }, null).s.key;
}

async function choose(row) {
  $("hits").hidden = true;
  $("q").value = row[0];
  if (row[4] === "s") {
    selectStation(await stationKeyForPlace(row), true);
  } else {
    map.flyTo({ center: [row[2], row[3]], zoom: 16 });
    showPoint(row[2], row[3]);
  }
}

// Addresses down to the block or house number are searched at chome level (places.json has 町丁目 only).
async function findPlaces(q, limit) {
  const all = await places();
  let hits = search(all, q, limit);
  let note = "";
  const chome = toChomeQuery(q);
  if (hits.length === 0 && chome && chome !== q) {
    hits = search(all, chome, limit);
    if (hits.length) note = `番地までは探せないため、「${chome}」で探しています`;
  }
  return { hits, note };
}

let timer = 0;
$("q").addEventListener("input", () => {
  clearTimeout(timer);
  timer = setTimeout(async () => {
    const q = $("q").value.trim();
    if (!q) {
      $("hits").hidden = true;
      return;
    }
    const { hits, note } = await findPlaces(q, 8);
    const items = hits.map((row) =>
      el("li", {}, el("button", { type: "button", onclick: () => choose(row) }, row[0], el("span", { class: "kind" }, row[4] === "s" ? "駅" : "町丁目"))),
    );
    if (note) items.unshift(el("li", { class: "msg" }, note));
    if (!hits.length) items.push(el("li", { class: "msg" }, "見つかりません。駅名か、住所の「○丁目」までを入れてください。"));
    $("hits").replaceChildren(...items);
    $("hits").hidden = false;
  }, 150);
});
$("search").addEventListener("submit", async (e) => {
  e.preventDefault();
  const { hits } = await findPlaces($("q").value.trim(), 1);
  if (hits[0]) choose(hits[0]);
});

// the legacy walk15 hash (#zoom/lat/lng) keeps working; ?point=lat,lng opens a point
const pt = new URLSearchParams(location.search).get("point");
if (pt) {
  const [lat, lng] = pt.split(",").map(Number);
  if (Number.isFinite(lat) && Number.isFinite(lng)) showPoint(lng, lat);
}
