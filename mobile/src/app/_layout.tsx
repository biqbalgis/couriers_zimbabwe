import React from "react";
import { Stack } from "expo-router";
import { PaperProvider, Snackbar } from "react-native-paper";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { StatusBar } from "expo-status-bar";
import { theme } from "../theme";
import { SessionProvider, useSession } from "../session";
export default function Root() {
  return (
    <PaperProvider theme={theme}>
      <SafeAreaProvider>
        <SessionProvider>
          <StatusBar style="dark" />
          <Stack
            screenOptions={{
              headerStyle: { backgroundColor: theme.colors.surface },
              headerTintColor: theme.colors.primary,
              contentStyle: { backgroundColor: theme.colors.background },
            }}
          >
            <Stack.Screen name="index" options={{ title: "Pano Logistics" }} />
            <Stack.Screen name="login" options={{ title: "Sign in" }} />
            <Stack.Screen
              name="workspace/[section]"
              options={{ headerShown: false }}
            />
            <Stack.Screen
              name="parcel/[code]"
              options={{ title: "Parcel journey" }}
            />
            <Stack.Screen
              name="handover/[id]"
              options={{ title: "Handover" }}
            />
            <Stack.Screen
              name="station/[id]"
              options={{ title: "Partner station" }}
            />
            <Stack.Screen
              name="track/[token]"
              options={{ title: "Your delivery" }}
            />
          </Stack>
          <SessionError />
        </SessionProvider>
      </SafeAreaProvider>
    </PaperProvider>
  );
}
function SessionError() {
  const { error, clearError } = useSession();
  if (!error) return null;
  return (
    <Snackbar visible={!!error} onDismiss={clearError}>
      {error}
    </Snackbar>
  );
}
