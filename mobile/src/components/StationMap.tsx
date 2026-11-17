import React from "react";
import { Linking } from "react-native";
import { Button, Text } from "react-native-paper";
import type { Station } from "../domain";
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
    Number.isFinite(longitude);
  return (
    <>
      <Text>
        {valid
          ? `Station location: ${latitude}, ${longitude} (EPSG:4326)`
          : "Station coordinates are unavailable."}
      </Text>
      <Button
        onPress={() =>
          void Linking.openURL(
            `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(valid ? `${latitude},${longitude}` : station.address)}`,
          )
        }
      >
        Open map & directions
      </Button>
    </>
  );
}
