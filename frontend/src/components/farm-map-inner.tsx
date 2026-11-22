"use client";

import "leaflet/dist/leaflet.css";
import { useEffect } from "react";
import { MapContainer, Polygon, TileLayer, Tooltip, useMap } from "react-leaflet";
import type { Zone } from "@/lib/api";

const ACTION_COLOR: Record<string, string> = {
  irrigate: "#2f6f9f",
  accept_deficit: "#b5651d",
  hold_zone: "#a63a2b",
  no_action: "#3f7d4e",
};

function MapLifecycle() {
  const map = useMap();
  useEffect(() => {
    map.invalidateSize();
  }, [map]);
  return null;
}

export default function FarmMapInner({
  center,
  zones,
  actions,
}: {
  center: [number, number];
  zones: Zone[];
  actions: Record<string, string>;
}) {
  const mapKey = `${center[0]}:${center[1]}:${zones.map((z) => z.zone_id).join(",")}`;
  return (
    <MapContainer
      key={mapKey}
      center={center}
      zoom={16}
      scrollWheelZoom={false}
      className="h-80 w-full rounded-lg"
    >
      <MapLifecycle />
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url="https://tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {zones.map((z) => {
        const color = ACTION_COLOR[actions[z.zone_id]] ?? "#5f6b63";
        return (
          <Polygon key={z.zone_id} positions={z.polygon} pathOptions={{ color, weight: 2, fillOpacity: 0.35 }}>
            <Tooltip sticky>
              {z.name} · {z.area_ha} ha · {actions[z.zone_id]?.replace("_", " ") ?? "no decision"}
            </Tooltip>
          </Polygon>
        );
      })}
    </MapContainer>
  );
}
