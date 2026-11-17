import React from "react";
import { Linking } from "react-native";
import MapView, { Marker } from "react-native-maps";
import { Button, Text } from "react-native-paper";
import type { Station } from "../domain";
import { theme } from "../theme";
export default function StationMap({
  station,
}: {
  station: Pick<Station, "name" | "address" | "latitude" | "longitude">;
}) {
  const latitude = Number(station.latitude),
    longitude = Number(station.longitude);
  const valid =
    station.latitude !== null &&
    station.longitude !== null &&
    Number.isFinite(latitude) &&
    Number.isFinite(longitude) &&
    Math.abs(latitude) <= 90 &&
    Math.abs(longitude) <= 180;
  return (
    <>
      {valid ? (
        <MapView
          style={{ height: 240, borderRadius: theme.roundness * 3 }}
          initialRegion={{
            latitude,
            longitude,
            latitudeDelta: 0.02,
            longitudeDelta: 0.02,
          }}
        >
          <Marker
            coordinate={{ latitude, longitude }}
            title={station.name}
            description={station.address}
            pinColor={theme.colors.primary}
          />
        </MapView>
      ) : (
        <Text>Station coordinates are unavailable.</Text>
      )}
      <Text>Station coordinates use EPSG:4326.</Text>
      <Button
        onPress={() =>
          void Linking.openURL(
            `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(valid ? `${latitude},${longitude}` : station.address)}`,
          )
        }
      >
        Open directions
      </Button>
    </>
  );
}
