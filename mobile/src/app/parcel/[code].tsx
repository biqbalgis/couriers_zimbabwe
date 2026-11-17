import React from "react";
import { useLocalSearchParams } from "expo-router";
import Guard from "../../components/Guard";
import { ParcelDetail } from "../../screens/Journeys";
export default function Route() {
  const { code } = useLocalSearchParams<{ code: string }>();
  return (
    <Guard>
      <ParcelDetail code={code} />
    </Guard>
  );
}
