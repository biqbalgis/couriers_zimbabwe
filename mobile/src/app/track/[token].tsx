import React from "react";
import { useLocalSearchParams } from "expo-router";
import { Recipient } from "../../screens/Journeys";
export default function Route() {
  const { token } = useLocalSearchParams<{ token: string }>();
  return <Recipient token={token} />;
}
