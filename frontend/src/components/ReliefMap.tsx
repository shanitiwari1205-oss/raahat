import { useMemo } from "react";
import DeckGL from "@deck.gl/react";
import { ScatterplotLayer, LineLayer } from "@deck.gl/layers";
import { Map as MapLibreMap } from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";
import type { WorldSnapshot } from "../store";

const MUMBAI_VIEW = {
  longitude: 72.88,
  latitude: 19.1,
  zoom: 10.3,
  pitch: 45,
  bearing: -10,
};

// No API key needed -- CARTO's free vector basemap.
const BASEMAP_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json";

function urgencyColor(urgency: number): [number, number, number] {
  // relief green -> caution amber -> alert red, matching the design system tokens
  if (urgency < 0.4) return [31, 122, 77];
  if (urgency < 0.7) return [255, 184, 0];
  return [255, 59, 31];
}

export function ReliefMap({ world }: { world: WorldSnapshot | null }) {
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
      getColor: (r) => (r.blocked ? [255, 59, 31, 220] : [120, 120, 110, 120]),
      getWidth: (r) => (r.blocked ? 4 : 1.5),
      widthUnits: "pixels",
    });
  }, [world]);

  const layers = [roadLayer, depotLayer, hospitalLayer, zoneLayer].filter(Boolean);

  return (
    <DeckGL
      initialViewState={MUMBAI_VIEW}
      controller={true}
      layers={layers}
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
        return null;
      }}
    >
      <MapLibreMap mapStyle={BASEMAP_STYLE} reuseMaps />
    </DeckGL>
  );
}
