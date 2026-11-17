import React from "react";
import { Redirect } from "expo-router";
import { ActivityIndicator } from "react-native-paper";
import { useSession } from "../session";
export default function Index() {
  const { user, ready } = useSession();
  return ready ? (
    <Redirect href={user ? "/workspace/dashboard" : "/login"} />
  ) : (
    <ActivityIndicator />
  );
}
