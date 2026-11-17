import * as SecureStore from "expo-secure-store";
import * as FS from "expo-file-system/legacy";
import * as Network from "expo-network";
import * as Crypto from "expo-crypto";
import * as Sharing from "expo-sharing";
import AsyncStorage from "@react-native-async-storage/async-storage";
import { Platform } from "react-native";
import {
  isAttachment,
  type Account,
  type Values,
  type Page,
  rows,
} from "./domain";
import { drainQueue } from "./offline.mjs";
export { rows } from "./domain";
export type { Account, Parcel, Task, Page, Role } from "./domain";
export const searchLocations=(address:string)=>read<import("./domain").LocationResult[]>("/locations/search/?address="+encodeURIComponent(address));
export const base = (
  process.env.EXPO_PUBLIC_API_URL ||
  (Platform.OS === "web"
    ? "http://localhost:8000/api"
    : "http://10.0.2.2:8000/api")
).replace(/\/$/, "");
let session: { access: string; refresh: string; user: Account } | null = null;
let refreshing: Promise<void> | null = null;
let syncing: Promise<void> | null = null;
let queueLock: Promise<unknown> = Promise.resolve();
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
export const networkError = (error: unknown) =>
  error instanceof ApiError && error.status === 0;
const listeners = new Set<() => void>();
export const subscribe = (callback: () => void) => {
  listeners.add(callback);
  return () => {
    listeners.delete(callback);
  };
};
const changed = () => listeners.forEach((callback) => callback());
const storage = {
  get: async () =>
    Platform.OS === "web"
      ? sessionStorage.getItem("pano.session")
      : SecureStore.getItemAsync("pano.session"),
  set: async (value: string) => {
    if (Platform.OS === "web") sessionStorage.setItem("pano.session", value);
    else await SecureStore.setItemAsync("pano.session", value);
  },
  remove: async () => {
    if (Platform.OS === "web") sessionStorage.removeItem("pano.session");
    else await SecureStore.deleteItemAsync("pano.session");
  },
};
export const currentAccount = () => session?.user.id;
export async function restoreSession() {
  const saved = await storage.get();
  session = saved ? JSON.parse(saved) : null;
  return session?.user || null;
}
export async function clearSession() {
  session = null;
  await storage.remove();
  changed();
}
export async function saveSession(
  tokens: { access: string; refresh: string },
  user: Account,
) {
  session = { ...tokens, user };
  await storage.set(JSON.stringify(session));
  changed();
  return user;
}
export async function online() {
  const state = await Network.getNetworkStateAsync();
  return state.isConnected !== false && state.isInternetReachable !== false;
}
function safePath(path: string) {
  if (!path.startsWith("/") || path.startsWith("//") || path.includes("://"))
    throw new Error("Invalid API path");
  return path;
}
async function bodyFor(data: unknown, multipart: boolean) {
  if (!multipart) return data === undefined ? undefined : JSON.stringify(data);
  const form = new FormData();
  for (const [key, value] of Object.entries(data as Values)) {
    if (value === undefined || value === "") continue;
    if (isAttachment(value)) {
      if (Platform.OS === "web") {
        const blob = await (await fetch(value.uri)).blob();
        form.append(key, blob, value.name);
      } else form.append(key, value as unknown as Blob);
    } else form.append(key, String(value));
  }
  return form;
}
interface RequestOptions {
  multipart?: boolean;
  public?: boolean;
  key?: string;
  retry?: boolean;
}
export async function api<T>(
  path: string,
  method = "GET",
  data?: unknown,
  options: RequestOptions = {},
): Promise<T> {
  safePath(path);
  const started = session;
  const headers: Record<string, string> = {};
  if (!options.multipart) headers["Content-Type"] = "application/json";
  if (!options.public && started)
    headers.Authorization = `Bearer ${started.access}`;
  if (options.key) headers["Idempotency-Key"] = options.key;
  let response: Response;
  try {
    response = await fetch(`${base}${path}`, {
      method,
      headers,
      body: await bodyFor(data, !!options.multipart),
      signal: AbortSignal.timeout(30000),
    });
  } catch (e) {
    throw new ApiError(
      e instanceof Error ? e.message : "Network unavailable",
      0,
    );
  }
  if (
    response.status === 401 &&
    !options.public &&
    started &&
    options.retry !== false
  ) {
    if (currentAccount() !== started.user.id)
      throw new ApiError("Account changed. Try again.", 401);
    // Another concurrent request may already have refreshed these credentials.
    if (session && session.access !== started.access)
      return api<T>(path, method, data, { ...options, retry: false });
    if (!refreshing)
      refreshing = (async () => {
        const tokens = await api<{ access: string; refresh?: string }>(
          "/auth/token/refresh/",
          "POST",
          { refresh: started.refresh },
          { public: true, retry: false },
        );
        if (session !== started)
          throw new ApiError("Account changed. Try again.", 401);
        session = { ...started, ...tokens };
        await storage.set(JSON.stringify(session));
      })().finally(() => {
        refreshing = null;
      });
    await refreshing;
    if (currentAccount() !== started.user.id)
      throw new ApiError("Account changed. Try again.", 401);
    return api<T>(path, method, data, { ...options, retry: false });
  }
  const body = await response
    .json()
    .catch(() => ({ detail: "Unexpected server response" }));
  if (!response.ok)
    throw new ApiError(
      typeof body === "string"
        ? body
        : Array.isArray(body)
          ? body.join("\n")
          : Object.entries(body)
              .map(
                ([key, value]) =>
                  `${key === "detail" ? "" : `${key}: `}${Array.isArray(value) ? value.join(", ") : typeof value === "object" ? JSON.stringify(value) : String(value)}`,
              )
              .join("\n"),
      response.status,
    );
  if (!options.public && started && currentAccount() !== started.user.id)
    throw new ApiError("Account changed. Reload this screen.", 401);
  return body as T;
}
export async function login(username: string, password: string) {
  const tokens = await api<{ access: string; refresh: string }>(
    "/auth/token/",
    "POST",
    { username, password },
    { public: true },
  );
  // Read the profile before persisting a session; failed profile retrieval cannot leave a partial login.
  const response = await fetch(`${base}/users/me/`, {
    headers: { Authorization: `Bearer ${tokens.access}` },
    signal: AbortSignal.timeout(30000),
  });
  if (!response.ok)
    throw new ApiError("Unable to retrieve your account", response.status);
  return saveSession(tokens, await response.json());
}
export async function phoneVerify(challenge_id: number, code: string) {
  const result = await api<{ access: string; refresh: string; user: Account }>(
    "/auth/phone/verify/",
    "POST",
    { challenge_id, code },
    { public: true },
  );
  return saveSession(result, result.user);
}
export async function read<T>(path: string, publicRead = false): Promise<T> {
  const account = currentAccount();
  const cacheKey = `pano.cache:${base}:${publicRead ? "guest" : account}:${path}`;
  try {
    const data = await api<T>(path, "GET", undefined, { public: publicRead });
    if (!publicRead && account !== undefined)
      await AsyncStorage.setItem(cacheKey, JSON.stringify(data));
    return data;
  } catch (e) {
    if (!networkError(e) || publicRead || account === undefined) throw e;
    const saved = await AsyncStorage.getItem(cacheKey);
    if (!saved)
      throw new ApiError(
        "Open this screen while connected before using it offline.",
        0,
      );
    return JSON.parse(saved);
  }
}
export async function all<T>(path: string): Promise<T[]> {
  let pagePath = path;
  const result: T[] = [];
  do {
    const data = await read<Page<T> | T[]>(pagePath);
    result.push(...rows(data));
    if (Array.isArray(data) || !data.next) break;
    const next = new URL(data.next, base);
    if (
      next.origin !== new URL(base).origin ||
      !next.pathname.startsWith(new URL(base).pathname + "/")
    )
      throw new Error("Unexpected pagination URL");
    pagePath = next.pathname.slice(new URL(base).pathname.length) + next.search;
  } while (true);
  return result;
}
export interface Queued {
  id: string;
  account: number;
  path: string;
  data: Values;
  createdAt: string;
  error: string;
}
const queueKey = () => `pano.queue:${base}`;
async function locked<T>(operation: () => Promise<T>): Promise<T> {
  const result = queueLock.then(operation, operation);
  queueLock = result.catch(() => undefined);
  return result;
}
const loadQueue = async (): Promise<Queued[]> =>
  JSON.parse((await AsyncStorage.getItem(queueKey())) || "[]");
export async function queue() {
  return (await loadQueue()).filter(
    (item) => item.account === currentAccount(),
  );
}
async function updateQueue(update: (items: Queued[]) => Queued[]) {
  await locked(async () => {
    await AsyncStorage.setItem(
      queueKey(),
      JSON.stringify(update(await loadQueue())),
    );
  });
  changed();
}
const fileDir = (account: number, id: string) =>
  `${FS.documentDirectory}pano-queue/${account}/${id}/`;
async function persistFiles(
  values: Values,
  account: number,
  id: string,
): Promise<Values> {
  const result = { ...values };
  if (Platform.OS === "web")
    throw new Error(
      "Offline file capture requires the native Android or iOS app.",
    );
  const dir = fileDir(account, id);
  await FS.makeDirectoryAsync(dir, { intermediates: true });
  for (const [key, value] of Object.entries(result))
    if (isAttachment(value)) {
      const uri = dir + key + "-" + value.name.replace(/[^a-zA-Z0-9._-]/g, "_");
      await FS.copyAsync({ from: value.uri, to: uri });
      result[key] = { ...value, uri };
    }
  return result;
}
async function removeItem(item: Queued) {
  await updateQueue((items) => items.filter((value) => value.id !== item.id));
  if (Platform.OS !== "web")
    await FS.deleteAsync(fileDir(item.account, item.id), {
      idempotent: true,
    }).catch(() => undefined);
}
export async function discardQueued(id: string) {
  const item = (await queue()).find((value) => value.id === id);
  if (item) await removeItem(item);
}
export async function retryQueued(id: string) {
  await updateQueue((items) =>
    items.map((item) =>
      item.id === id && item.account === currentAccount()
        ? { ...item, error: "" }
        : item,
    ),
  );
  await syncQueue();
}
export async function handover(path: string, values: Values) {
  const account = currentAccount();
  if (account === undefined)
    throw new ApiError("Sign in before recording handovers.", 401);
  const id = Crypto.randomUUID();
  if (Platform.OS === "web")
    return api(path, "POST", values, { multipart: true, key: id });
  const data = await persistFiles(values, account, id);
  const item: Queued = {
    id,
    account,
    path,
    data,
    createdAt: new Date().toISOString(),
    error: "",
  };
  // Persist BEFORE sending so a process restart/lost response always reuses this exact request key and file bytes.
  await updateQueue((items) => [...items, item]);
  if (!(await online())) return { queued: true };
  try {
    const result = await api(path, "POST", data, { multipart: true, key: id });
    await removeItem(item);
    return result;
  } catch (error) {
    if (networkError(error)) return { queued: true };
    await updateQueue((items) =>
      items.map((value) =>
        value.id === id
          ? {
              ...value,
              error: error instanceof Error ? error.message : String(error),
            }
          : value,
      ),
    );
    throw error;
  }
}
export async function syncQueue() {
  if (syncing) return syncing;
  const account = currentAccount();
  if (account === undefined || !(await online())) return;
  syncing = (async () => {
    await drainQueue({
      items: await loadQueue(),
      account,
      isCurrent: () => currentAccount() === account,
      send: (item) =>
        api(item.path, "POST", item.data, { multipart: true, key: item.id }),
      remove: removeItem,
      fail: async (item, error) =>
        updateQueue((items) =>
          items.map((value) =>
            value.id === item.id
              ? {
                  ...value,
                  error: error instanceof Error ? error.message : String(error),
                }
              : value,
          ),
        ),
      isNetworkError: networkError,
    });
  })().finally(() => {
    syncing = null;
  });
  return syncing;
}
export function privatePath(value: string) {
  const url = new URL(value, base + "/");
  if (url.origin !== new URL(base).origin)
    throw new Error("File must belong to the configured API server.");
  const raw = url.pathname.replace(/^\/media\//, "");
  if (url.pathname.startsWith("/media/")) return `/files/${raw}`;
  const prefix = new URL(base).pathname;
  if (!url.pathname.startsWith(prefix + "/files/"))
    throw new Error("Unsupported file URL");
  return url.pathname.slice(prefix.length) + url.search;
}
export async function download(path: string, name: string) {
  safePath(path);
  const filename = name.replace(/[^a-zA-Z0-9._-]/g, "_");
  const request = async () => {
    const headers: Record<string, string> = session
      ? { Authorization: `Bearer ${session.access}` }
      : {};
    return fetch(base + path, { headers, signal: AbortSignal.timeout(30000) });
  };
  let response = await request();
  if (response.status === 401 && session) {
    await api("/users/me/");
    response = await request();
  }
  if (!response.ok)
    throw new ApiError("Unable to download this file.", response.status);
  if (Platform.OS === "web") {
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = url;
    link.download = filename;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 10000);
    return;
  }
  const blob = await response.blob();
  const buffer = await blob.arrayBuffer();
  let binary = "";
  for (const byte of new Uint8Array(buffer))
    binary += String.fromCharCode(byte);
  const uri = FS.cacheDirectory + Crypto.randomUUID() + "-" + filename;
  await FS.writeAsStringAsync(uri, btoa(binary), {
    encoding: FS.EncodingType.Base64,
  });
  if (await Sharing.isAvailableAsync()) await Sharing.shareAsync(uri);
  else throw new Error("File sharing is unavailable on this device.");
}
export async function openFile(value: string) {
  return download(
    privatePath(value),
    value.split("/").pop()?.split("?")[0] || "document",
  );
}
