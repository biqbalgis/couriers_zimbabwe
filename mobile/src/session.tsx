import React, { createContext, useContext, useEffect, useState } from "react";
import { AppState } from "react-native";
import * as Network from "expo-network";
import {
  read,
  restoreSession,
  clearSession,
  syncQueue,
  networkError,
} from "./api";
import type { Account } from "./domain";
interface Session {
  user: Account | null;
  ready: boolean;
  connected: boolean;
  setUser: (value: Account | null) => void;
  logout: () => Promise<void>;
  error: string;
  clearError: () => void;
}
const Context = createContext<Session | null>(null);
export function SessionProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<Account | null>(null),
    [ready, setReady] = useState(false),
    [connected, setConnected] = useState(true),
    [error, setError] = useState("");
  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const saved = await restoreSession();
        if (saved) {
          try {
            const fresh = await read<Account>("/users/me/");
            if (active) setUser(fresh);
          } catch (e) {
            if (networkError(e)) {
              if (active) setUser(saved);
            } else {
              await clearSession();
              if (active) setError("Your session expired. Sign in again.");
            }
          }
        }
      } catch (e) {
        if (active) setError(String(e));
      } finally {
        if (active) setReady(true);
      }
    })();
    return () => {
      active = false;
    };
  }, []);
  useEffect(() => {
    const update = async () => {
      try {
        const status = await Network.getNetworkStateAsync();
        setConnected(
          status.isConnected !== false && status.isInternetReachable !== false,
        );
        await syncQueue();
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      }
    };
    void update();
    const listener = Network.addNetworkStateListener(() => void update());
    const foreground = AppState.addEventListener("change", (state) => {
      if (state === "active") void update();
    });
    return () => {
      listener.remove();
      foreground.remove();
    };
  }, [user]);
  return (
    <Context.Provider
      value={{
        user,
        ready,
        connected,
        setUser,
        error,
        clearError: () => setError(""),
        logout: async () => {
          await clearSession();
          setUser(null);
        },
      }}
    >
      {children}
    </Context.Provider>
  );
}
export const useSession = () => {
  const context = useContext(Context);
  if (!context) throw new Error("Session provider is missing");
  return context;
};
