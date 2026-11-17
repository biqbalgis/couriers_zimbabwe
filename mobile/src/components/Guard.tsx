import React from "react";
import { Redirect } from "expo-router";
import { ActivityIndicator } from "react-native-paper";
import { useSession } from "../session";
export default function Guard({ children }: { children: React.ReactNode }) {
  const { ready, user } = useSession();
  if (!ready) return <ActivityIndicator />;
  return user ? <>{children}</> : <Redirect href="/login" />;
}
