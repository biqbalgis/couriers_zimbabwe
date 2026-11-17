import React from "react";
import { useLocalSearchParams } from "expo-router";
import Guard from "../../components/Guard";
import { StationDetail } from "../../screens/Journeys";
export default function Route() {
  const { id } = useLocalSearchParams<{ id: string }>();
  return (
    <Guard>
      <StationDetail id={id} />
    </Guard>
  );
}
