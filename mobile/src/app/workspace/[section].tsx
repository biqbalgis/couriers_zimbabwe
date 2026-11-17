import React from "react";
import { ScrollView, View } from "react-native";
import { router, useLocalSearchParams } from "expo-router";
import { SafeAreaView } from "react-native-safe-area-context";
import { Button, Chip, Text } from "react-native-paper";
import Guard from "../../components/Guard";
import { useSession } from "../../session";
import {Operations} from "../../screens/Operations";
import { menus } from "../../domain";
import { theme } from "../../theme";
import { Booking } from "../../screens/Booking";
import { Parcels, Tasks } from "../../screens/Journeys";
import {
  ResourceScreen,
  Earnings,
  Reports,
  Settings,
} from "../../screens/Resources";
import {
  Dashboard,
  Onboarding,
  Profile,
  OfflineQueue,
} from "../../screens/Account";
export default function WorkspaceRoute() {
  return (
    <Guard>
      <Workspace />
    </Guard>
  );
}
function Workspace() {
  const { section: screen } = useLocalSearchParams<{ section: string }>();
  const { user, connected, logout } = useSession();
  if (!user) return null;
  const items = menus.filter((item) => item.roles.includes(user.role)),
    allowed = items.some((item) => item.key === screen);
  return (
    <SafeAreaView style={{ flex: 1 }}>
      <View style={{ padding: 16, backgroundColor: theme.colors.surface }}>
        <Text variant="titleLarge">Pano Logistics</Text>
        <Text>
          {user.name} · {connected ? "Connected" : "Offline — saved data"}
        </Text>
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          contentContainerStyle={{ gap: 8, paddingTop: 12 }}
        >
          {items.map((item) => (
            <Chip
              key={item.key}
              selected={item.key === screen}
              onPress={() => router.replace(`/workspace/${item.key}`)}
            >
              {item.title}
            </Chip>
          ))}
        </ScrollView>
        <Button
          onPress={async () => {
            await logout();
            router.replace("/login");
          }}
        >
          Sign out
        </Button>
      </View>
      {!allowed ? (
        <Text>This workspace is unavailable for your role.</Text>
      ) : screen === "dashboard" ? (
        <Dashboard />
      ) : screen === "book" ? (
        <Booking />
      ) : screen === "parcels" ? (
        <Parcels />
      ) : screen === "tasks" ? (
        <Tasks />
      ) : screen === "onboarding" ? (
        <Onboarding />
      ) : screen === "earnings" ? (
        <Earnings />
      ) : screen === "reports" ? (
        <Reports />
      ) : screen === "operations" ? (
        <Operations />
      ) : screen === "settings" ? (
        <Settings />
      ) : screen === "profile" ? (
        <Profile />
      ) : screen === "queue" ? (
        <OfflineQueue />
      ) : (
        <ResourceScreen key={screen} screen={screen} />
      )}
    </SafeAreaView>
  );
}
