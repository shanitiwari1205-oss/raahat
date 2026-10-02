import { useMemo } from "react";
import DeckGL from "@deck.gl/react";
import { ArcLayer, LineLayer, ScatterplotLayer } from "@deck.gl/layers";
import { HeatmapLayer } from "@deck.gl/aggregation-layers";
import { Map as MapLibreMap } from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";
import type { FlowItem, RoadState, WorldSnapshot } from "../store";

const MUMBAI_VIEW = {
  longitude: 72.88,
  latitude: 19.1,
  zoom: 10.3,
  pitch: 45,
  bearing: -10,
};

// No API key needed -- CARTO's free vector basemap.
const BASEMAP_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

const FLOW_TTL_MS = 5000;

function urgencyColor(urgency: number): [number, number, number] {
  // relief green -> caution amber -> alert red, matching the design system tokens
  if (urgency < 0.4) return [31, 122, 77];
  if (urgency < 0.7) return [255, 184, 0];
  return [255, 59, 31];
}

export function ReliefMap({
  world,
  activeFlows,
  onRoadClick,
}: {
  world: WorldSnapshot | null;
  activeFlows: FlowItem[];
  onRoadClick?: (road: RoadState) => void;
}) {
  const nodeCoords = useMemo(() => {
    const m: Record<string, [number, number]> = {};
    if (!world) return m;
    for (const z of world.zones) m[z.id] = [z.lon, z.lat];
    for (const d of world.depots) m[d.id] = [d.lon, d.lat];
    for (const h of world.hospitals) m[h.id] = [h.lon, h.lat];
    return m;
  }, [world]);

  const heatmapLayer = useMemo(() => {
    if (!world || world.zones.length === 0) return null;
    return new HeatmapLayer({
      id: "urgency-heat",
      data: world.zones,
      getPosition: (z) => [z.lon, z.lat],
      getWeight: (z) => Math.max(0.05, z.urgency),
      radiusPixels: 90,
      intensity: 1.4,
      threshold: 0.03,
      colorRange: [
        [31, 122, 77, 0],
        [31, 122, 77, 140],
        [255, 184, 0, 170],
        [255, 100, 40, 200],
        [255, 59, 31, 230],
        [255, 59, 31, 255],
      ],
    });
  }, [world]);

  const zoneLayer = useMemo(() => {
    if (!world) return null;
    return new ScatterplotLayer({
      id: "zones",
      data: world.zones,
      getPosition: (z) => [z.lon, z.lat],
      getFillColor: (z) => urgencyColor(z.urgency),
      getRadius: (z) => 500 + z.population / 40,
      radiusUnits: "meters",
      stroked: true,
      getLineColor: [11, 13, 10],
      getLineWidth: 2,
      lineWidthUnits: "pixels",
      pickable: true,
    });
  }, [world]);

  const hospitalLayer = useMemo(() => {
    if (!world) return null;
    return new ScatterplotLayer({
      id: "hospitals",
      data: world.hospitals,
      getPosition: (h) => [h.lon, h.lat],
      getFillColor: [29, 78, 216],
      getRadius: 420,
      radiusUnits: "meters",
      stroked: true,
      getLineColor: [244, 241, 232],
      getLineWidth: 2,
      lineWidthUnits: "pixels",
      pickable: true,
    });
  }, [world]);

  const depotLayer = useMemo(() => {
    if (!world) return null;
    return new ScatterplotLayer({
      id: "depots",
      data: world.depots,
      getPosition: (d) => [d.lon, d.lat],
      getFillColor: [244, 241, 232],
      getRadius: 380,
      radiusUnits: "meters",
      stroked: true,
      getLineColor: [11, 13, 10],
      getLineWidth: 3,
      lineWidthUnits: "pixels",
      pickable: true,
    });
  }, [world]);

  const roadLayer = useMemo(() => {
    if (!world) return null;
    return new LineLayer({
      id: "roads",
      data: world.roads,
      getSourcePosition: (r) => [r.u_coords.lon, r.u_coords.lat],
      getTargetPosition: (r) => [r.v_coords.lon, r.v_coords.lat],
      getColor: (r) => (r.blocked ? [255, 59, 31, 220] : [120, 120, 110, 140]),
      getWidth: (r) => (r.blocked ? 4 : 2),
      widthUnits: "pixels",
      pickable: !!onRoadClick,
    });
  }, [world, onRoadClick]);

  // Animated depot->zone resource flow arcs -- driven entirely by REAL
  // allocation events broadcast from the Supervisor (see store.ts's
  // activeFlows), fading out over FLOW_TTL_MS. Nothing here is decorative
  // or hardcoded: no flows exist on the map until a real allocation happens.
  const arcLayer = useMemo(() => {
    const data = activeFlows.filter((f) => nodeCoords[f.depot_id] && nodeCoords[f.zone_id]);
    if (data.length === 0) return null;
    const now = Date.now();
    return new ArcLayer({
      id: "flows",
      data,
      getSourcePosition: (f) => nodeCoords[f.depot_id],
      getTargetPosition: (f) => nodeCoords[f.zone_id],
      getSourceColor: (f: FlowItem) => {
        const age = now - f.t;
        const alpha = Math.max(0, 255 * (1 - age / FLOW_TTL_MS));
        return [29, 78, 216, alpha];
      },
      getTargetColor: (f: FlowItem) => {
        const age = now - f.t;
        const alpha = Math.max(0, 255 * (1 - age / FLOW_TTL_MS));
        return [255, 184, 0, alpha];
      },
      getWidth: (f) => Math.min(10, 2 + f.amount / 12),
      widthUnits: "pixels",
      greatCircle: false,
    });
  }, [activeFlows, nodeCoords]);

  const layers = [heatmapLayer, roadLayer, arcLayer, depotLayer, hospitalLayer, zoneLayer].filter(Boolean);

  return (
    <DeckGL
      initialViewState={MUMBAI_VIEW}
      controller={true}
      layers={layers}
      getCursor={({ isHovering }) => (isHovering && onRoadClick ? "pointer" : "grab")}
      onClick={(info) => {
        if (info.layer?.id === "roads" && info.object && onRoadClick) {
          onRoadClick(info.object as RoadState);
        }
      }}
      getTooltip={({ object, layer }) => {
        if (!object) return null;
        if (layer?.id === "zones") {
          return {
            html: `<b>${object.id}</b><br/>Urgency: ${(object.urgency * 100).toFixed(0)}%<br/>Population: ${object.population.toLocaleString()}`,
          };
        }
        if (layer?.id === "hospitals") {
          return { html: `<b>${object.id}</b><br/>Beds: ${object.beds_used}/${object.bed_capacity}` };
        }
        if (layer?.id === "depots") {
          const budget = Math.round(object.budget_inr).toLocaleString("en-IN");
          return { html: `<b>${object.id}</b><br/>Budget: ₹${budget}` };
        }
        if (layer?.id === "roads") {
          const r = object as RoadState;
          return {
            html: `<b>${r.u} → ${r.v}</b><br/>${r.blocked ? "BLOCKED" : `${r.travel_time} min`}${onRoadClick ? "<br/><i>click to block</i>" : ""}`,
          };
        }
        return null;
      }}
    >
      <MapLibreMap mapStyle={BASEMAP_STYLE} reuseMaps />
    </DeckGL>
  );
}
