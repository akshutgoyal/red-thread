import { useEffect } from "react";
import L from "leaflet";
import { CircleMarker, MapContainer, Popup, TileLayer, useMap } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { formatDateTime } from "@/lib/format";
import type { SpatialObservation } from "@/types";

const TILE_URL =
  import.meta.env.VITE_MAP_TILE_URL ??
  "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png";

function FitBounds({ observations }: { observations: SpatialObservation[] }) {
  const map = useMap();

  useEffect(() => {
    if (observations.length === 0) return;
    const bounds = L.latLngBounds(
      observations.map((item) => [item.latitude, item.longitude] as [number, number]),
    );
    map.fitBounds(bounds, { padding: [30, 30], maxZoom: 15 });
  }, [map, observations]);

  return null;
}

export function SpatialMap({
  observations,
  selectedId,
  onSelect,
}: {
  observations: SpatialObservation[];
  selectedId: string | null;
  onSelect: (eventId: string) => void;
}) {
  const center: [number, number] = observations[0]
    ? [observations[0].latitude, observations[0].longitude]
    : [12.9716, 77.5946];

  return (
    <MapContainer
      center={center}
      zoom={13}
      scrollWheelZoom
      className="h-[480px] w-full overflow-hidden rounded-xl"
      style={{ minHeight: 480 }}
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
        url={TILE_URL}
      />
      <FitBounds observations={observations} />
      {observations.map((observation) => {
        const selected = observation.event_id === selectedId;
        return (
          <CircleMarker
            key={observation.event_id}
            center={[observation.latitude, observation.longitude]}
            radius={selected ? 10 : 7}
            pathOptions={{
              color: selected ? "#06b6d4" : "#2563eb",
              fillColor: selected ? "#06b6d4" : "#3b82f6",
              fillOpacity: 0.72,
              weight: 2,
            }}
            eventHandlers={{ click: () => onSelect(observation.event_id) }}
          >
            <Popup>
              <div className="space-y-1 text-xs">
                <p className="font-semibold">
                  {observation.label || observation.entity_values[0] || observation.event_type}
                </p>
                <p>{formatDateTime(observation.timestamp_normalized)}</p>
                <p>
                  {observation.source_filename} · {observation.source_locator}
                </p>
              </div>
            </Popup>
          </CircleMarker>
        );
      })}
    </MapContainer>
  );
}
