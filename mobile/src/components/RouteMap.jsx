import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";

// OpenStreetMap tiles dimmed for night use. Without internet the tiles don't load,
// but routes and markers still draw, and the plan is also shown as text below.
const STYLE = {
  version: 8,
  sources: {
    osm: {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors",
    },
  },
  layers: [
    { id: "bg", type: "background", paint: { "background-color": "#221F38" } },
    { id: "osm", type: "raster", source: "osm",
      paint: { "raster-brightness-max": 0.5, "raster-saturation": -0.7, "raster-contrast": 0.15 } },
  ],
};

// Nagpur city centre, used until a point is known
const CITY_CENTER = [79.0882, 21.1458];

const KIND_COLOR = { pharmacy: "#5E9E6B", hospital: "#5E9E6B", police: "#7C93D6", cctv: "#B9AE98" };

export default function RouteMap({ routes = [], selected = 0, origin, destination, stops = [], onPick, picking = false, height = 260 }) {
  const el = useRef(null);
  const map = useRef(null);
  const markers = useRef([]);
  const pickRef = useRef(onPick);
  pickRef.current = onPick;

  useEffect(() => {
    map.current = new maplibregl.Map({
      container: el.current,
      style: STYLE,
      center: origin ? [origin.lon, origin.lat] : CITY_CENTER,
      zoom: 13,
      attributionControl: { compact: true },
    });
    map.current.on("click", (e) => pickRef.current && pickRef.current({ lat: e.lngLat.lat, lon: e.lngLat.lng }));
    return () => map.current.remove();
  }, []);

  useEffect(() => {
    const m = map.current;
    const draw = () => {
      markers.current.forEach((mk) => mk.remove());
      markers.current = [];
      (m.getStyle().layers || []).filter((l) => l.id.startsWith("route-")).forEach((l) => m.removeLayer(l.id));
      Object.keys(m.getStyle().sources).filter((s) => s.startsWith("route-")).forEach((s) => m.removeSource(s));

      const order = routes.map((_, i) => i).filter((i) => i !== selected).concat(routes.length ? [selected] : []);
      order.forEach((i) => {
        const r = routes[i];
        m.addSource(`route-${i}`, { type: "geojson", data: { type: "Feature",
          geometry: { type: "LineString", coordinates: r.coords.map(([la, lo]) => [lo, la]) } } });
        const sel = i === selected;
        if (sel) m.addLayer({ id: `route-${i}-casing`, type: "line", source: `route-${i}`,
          paint: { "line-color": "#1B1830", "line-width": 9 }, layout: { "line-cap": "round", "line-join": "round" } });
        m.addLayer({ id: `route-${i}`, type: "line", source: `route-${i}`,
          paint: { "line-color": sel ? "#E9B23C" : "#8A8499", "line-width": sel ? 5 : 3,
            "line-dasharray": sel ? [1] : [2, 2] },
          layout: { "line-cap": "round", "line-join": "round" } });
      });

      const sel = routes[selected];
      if (sel) {
        sel.places.filter((p) => p.open_when_passing || p.kind === "cctv" || p.kind === "police").forEach((p) => {
          const d = document.createElement("div");
          d.className = "poi-dot";
          d.style.background = KIND_COLOR[p.kind] || "#E9B23C";
          markers.current.push(new maplibregl.Marker({ element: d }).setLngLat([p.lon, p.lat]).addTo(m));
        });
      }
      const pin = (pt, cls) => {
        if (!pt) return;
        const d = document.createElement("div");
        d.className = cls;
        markers.current.push(new maplibregl.Marker({ element: d }).setLngLat([pt.lon, pt.lat]).addTo(m));
      };
      pin(origin, "pin-start");
      stops.forEach((s, i) => {
        if (!s) return;
        const d = document.createElement("div");
        d.className = "pin-stop";
        d.textContent = i + 1;
        markers.current.push(new maplibregl.Marker({ element: d }).setLngLat([s.lon, s.lat]).addTo(m));
      });
      pin(destination, "pin-end");

      const pts = sel ? sel.coords : [origin, ...stops, destination].filter(Boolean).map((p) => [p.lat, p.lon]);
      if (pts.length > 1) {
        const b = new maplibregl.LngLatBounds();
        pts.forEach(([la, lo]) => b.extend([lo, la]));
        m.fitBounds(b, { padding: 36, duration: 0, maxZoom: 16 });
      } else if (pts.length === 1) {
        m.jumpTo({ center: [pts[0][1], pts[0][0]] });
      }
    };
    if (m.isStyleLoaded()) draw();
    else m.once("load", draw);
  }, [routes, selected, origin, destination, stops]);

  return <div ref={el} className={`map${picking ? " map-picking" : ""}`} style={{ height }} />;
}
