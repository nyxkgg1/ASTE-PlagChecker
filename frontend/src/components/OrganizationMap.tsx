
import {
  MapContainer,
  TileLayer,
  CircleMarker,
  Popup,
} from "react-leaflet";
import "leaflet/dist/leaflet.css";

type Location = {
  id: string;
  name: string;
  latitude: number;
  longitude: number;
  documents_scanned: number;
};

export default function OrganizationMap({
  locations,
}: {
  locations: Location[];
}) {
  if (!locations.length) {
    return (
      <div className="muted" style={{ padding: 35, textAlign: "center" }}>
        No authorized location data configured.
      </div>
    );
  }

  return (
    <div style={{ overflow: "hidden", borderRadius: 12 }}>
      <MapContainer
        center={[locations[0].latitude, locations[0].longitude]}
        zoom={6}
        scrollWheelZoom={false}
        style={{ height: 380, width: "100%" }}
      >
        <TileLayer
          attribution="Locally hosted map tiles"
          url="/map-tiles/{z}/{x}/{y}.png"
        />

        {locations.map((location) => (
          <CircleMarker
            key={location.id}
            center={[location.latitude, location.longitude]}
            radius={Math.max(
              7,
              Math.min(20, 6 + Math.sqrt(location.documents_scanned))
            )}
            pathOptions={{
              color: "#0369a1",
              fillColor: "#38bdf8",
              fillOpacity: 0.8,
            }}
          >
            <Popup>
              <strong>{location.name}</strong>
              <br />
              Documents scanned: {location.documents_scanned}
            </Popup>
          </CircleMarker>
        ))}
      </MapContainer>
    </div>
  );
}
