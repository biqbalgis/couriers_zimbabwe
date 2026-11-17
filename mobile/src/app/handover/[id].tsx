import React from "react";
import { useLocalSearchParams } from "expo-router";
import Guard from "../../components/Guard";
import { Handover } from "../../screens/Journeys";
export default function Route() {
  const { id } = useLocalSearchParams<{ id: string }>();
  return (
    <Guard>
      <Handover id={id} />
    </Guard>
  );
}
