import React, { useState } from "react";
import { router } from "expo-router";
import {
  Text,
  Button,
  Card,
  ActivityIndicator,
  TextInput,
} from "react-native-paper";
import { useSession } from "../session";
import {
  api,
  login,
  phoneVerify,
  queue,
  syncQueue,
  retryQueued,
  discardQueued,
  subscribe,
  type Queued,
} from "../api";
import {
  has,
  options,
  label,
  type Entity,
  type Action,
  type Page,
  type Account,
} from "../domain";
import { stationField, carrierFields } from "../workflows";
import {
  Screen,
  ErrorBox,
  Fields,
  ActionForm,
  useLoad,
} from "../components/UI";
export function Login() {
  const { setUser } = useSession();
  const [mode, setMode] = useState("credentials"),
    [values, setValues] = useState<Record<string, string>>({
      role: "customer",
      phone: "+263",
    }),
    [challenge, setChallenge] = useState<{
      challenge_id: number;
      development_code?: string;
    }>(),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [tracking, setTracking] = useState("");
  return (
    <Screen>
      <Text variant="displaySmall">Pano Logistics</Text>
      <Text>Mutare–Chipinge delivery network</Text>
      <Button
        onPress={() => {
          setMode(mode === "credentials" ? "phone" : "credentials");
          setChallenge(undefined);
          setError("");
        }}
      >
        {mode === "credentials"
          ? "Use phone sign-in"
          : "Use username & password"}
      </Button>
      <ErrorBox error={error} />
      {!!challenge?.development_code && (
        <Text>
          Local development only — code {challenge.development_code}. No SMS was
          sent.
        </Text>
      )}
      <Fields
        fields={
          mode === "credentials"
            ? [
                { name: "username", label: "Username", required: true },
                {
                  name: "password",
                  label: "Password",
                  type: "password",
                  required: true,
                },
              ]
            : challenge
              ? [
                  {
                    name: "code",
                    label: "Six-digit verification code",
                    required: true,
                  },
                ]
              : [
                  { name: "name", label: "Full name", required: true },
                  {
                    name: "phone",
                    label: "Zimbabwe phone (+263…)",
                    required: true,
                  },
                  {
                    name: "role",
                    label: "Joining as",
                    type: "select",
                    options: options(["customer", "rider", "carrier"]),
                    required: true,
                  },
                ]
        }
        values={values}
        onChange={(v) => setValues(v as Record<string, string>)}
      />
      <Button
        mode="contained"
        loading={busy}
        disabled={busy}
        onPress={async () => {
          setBusy(true);
          setError("");
          try {
            if (mode === "credentials") {
              if (!values.username || !values.password)
                throw new Error("Enter your username and password");
              setUser(await login(values.username.trim(), values.password));
              router.replace("/workspace/dashboard");
            } else if (challenge) {
              if (!/^\d{6}$/.test(values.code || ""))
                throw new Error("Enter the six-digit code");
              setUser(await phoneVerify(challenge.challenge_id, values.code));
              router.replace("/workspace/dashboard");
            } else {
              if (!values.name?.trim() || !/^\+263\d{9}$/.test(values.phone))
                throw new Error(
                  "Enter your name and a Zimbabwe phone (+263 followed by nine digits).",
                );
              setChallenge(
                await api("/auth/phone/request/", "POST", values, {
                  public: true,
                }),
              );
            }
          } catch (e) {
            setError(e instanceof Error ? e.message : String(e));
          } finally {
            setBusy(false);
          }
        }}
      >
        {mode === "credentials"
          ? "Sign in"
          : challenge
            ? "Verify and continue"
            : "Send verification code"}
      </Button>
      {challenge && (
        <Button onPress={() => setChallenge(undefined)}>
          Request another code
        </Button>
      )}
      <Text>
        Staff sign in with credentials. Rider and carrier applications need
        approval before assignment.
      </Text>
      <Text variant="titleLarge">Receiving a parcel?</Text>
      <TextInput
        mode="outlined"
        label="Private recipient link or token"
        value={tracking}
        onChangeText={setTracking}
        autoCapitalize="none"
      />
      <Button
        disabled={!tracking.trim()}
        onPress={() => {
          const token = tracking
            .trim()
            .split("/track/")
            .pop()!
            .split(/[?#]/)[0];
          router.push(`/track/${encodeURIComponent(token)}`);
        }}
      >
        Track my delivery
      </Button>
    </Screen>
  );
}
export function Dashboard() {
  const { user } = useSession();
  const q = useLoad<Record<string, unknown>>("/dashboard/");
  return (
    <Screen refreshing={q.loading} onRefresh={() => void q.reload()}>
      <Text variant="headlineMedium">Welcome, {user?.name}</Text>
      <ErrorBox error={q.error} retry={() => void q.reload()} />
      {q.loading && !q.data && <ActivityIndicator />}
      {q.data &&
        Object.entries(q.data)
          .filter(([key]) => key !== "pilot")
          .map(([key, value]) => (
            <Card key={key}>
              <Card.Content>
                <Text>{label(key)}</Text>
                <Text variant="headlineMedium">{String(value)}</Text>
              </Card.Content>
            </Card>
          ))}
      {has(user, "customer", "station_operator", "ops", "admin") && (
        <Button mode="contained" onPress={() => router.push("/workspace/book")}>
          Book a parcel
        </Button>
      )}
    </Screen>
  );
}
export function Onboarding() {
  const { user } = useSession();
  const resource = user?.role === "carrier" ? "carriers" : "riders";
  const q = useLoad<Page<Entity>>(`/${resource}/`);
  const profile = q.data?.results.find((item) => item.user === user?.id);
  const [action, setAction] = useState<Action>();
  const fields = [
    ...(user?.role === "carrier" ? carrierFields : [stationField]),
    {name:"document_expires_at",label:"Document expiry (YYYY-MM-DD)"},
    {
      name: "document",
      label: "Identity / operating document",
      type: "document" as const,
      required: true,
    },
  ];
  return (
    <Screen>
      <Text variant="headlineSmall">Your partner application</Text>
      <ErrorBox error={q.error} />
      {profile && (
        <>
          <Text variant="titleMedium">Application {label(profile.status)}</Text>
          <Text>{String(profile.review_note || "")}</Text>
        </>
      )}
      {!q.loading && !q.error && profile?.status !== "approved" && (
        <Button
          mode="contained"
          onPress={() =>
            setAction({
              title: profile ? "Resubmit application" : "Submit application",
              path: `/${resource}/${profile ? `${profile.id}/` : ""}`,
              method: profile ? "PATCH" : "POST",
              multipart: true,
              fields,
              initial: profile
                ? Object.fromEntries(
                    fields
                      .filter((field) => field.name !== "document")
                      .map((field) => [
                        field.name,
                        String(profile[field.name] || ""),
                      ]),
                  )
                : {},
            })
          }
        >
          {profile ? "Resubmit application" : "Apply for approval"}
        </Button>
      )}
      {profile?.status === "approved" && (
        <Text>
          Approved for matching. Contact operations for changes to licence or
          home station.
        </Text>
      )}
      {action && (
        <ActionForm
          action={action}
          onClose={() => setAction(undefined)}
          onDone={() => void q.reload()}
        />
      )}
    </Screen>
  );
}
export function Profile() {
  const { user, setUser } = useSession();
  const [action, setAction] = useState<Action>();
  return (
    <Screen>
      <Text variant="headlineSmall">My account</Text>
      <Text>{user?.name}</Text>
      <Text>
        {user?.username} · {user?.phone}
      </Text>
      <Text>
        {label(user?.role)} ·{" "}
        {user?.verified ? "Verified" : "Verification pending"}
      </Text>
      <Button
        onPress={() =>
          setAction({
            title: "Update name",
            path: "/users/me/",
            method: "PATCH",
            initial: { name: user?.name },
            fields: [{ name: "name", label: "Full name", required: true }],
          })
        }
      >
        Edit name
      </Button>
      {action && (
        <ActionForm
          action={action}
          onClose={() => setAction(undefined)}
          onDone={() => {
            void api<Account>("/users/me/").then(setUser);
          }}
        />
      )}
    </Screen>
  );
}
export function OfflineQueue() {
  const [items, setItems] = useState<Queued[]>([]),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [discardId, setDiscardId] = useState<string>();
  const reload = React.useCallback(async () => {
    try {
      setItems(await queue());
    } catch (e) {
      setError(String(e));
    }
  }, []);
  React.useEffect(() => {
    // Load persisted device records once, then subscribe to external queue changes.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void reload();
    return subscribe(() => void reload());
  }, [reload]);
  const run = async (operation: () => Promise<void>) => {
    setBusy(true);
    try {
      await operation();
      await reload();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Screen refreshing={busy} onRefresh={() => void run(syncQueue)}>
      <Text variant="headlineSmall">Offline sync</Text>
      <Text>
        Saved handovers belong to the account that recorded them. An expired
        code needs a fresh capture. The same retry key prevents duplicate
        custody changes after a lost response.
      </Text>
      <ErrorBox error={error} />
      <Button
        mode="contained"
        disabled={busy}
        onPress={() => void run(syncQueue)}
      >
        Sync now
      </Button>
      {!items.length && <Text>Everything is synchronized.</Text>}
      {items.map((item) => (
        <Card key={item.id}>
          <Card.Content>
            <Text variant="titleMedium">
              Assignment {item.path.split("/")[2]}
            </Text>
            <Text>{new Date(item.createdAt).toLocaleString()}</Text>
            <Text>{item.error || "Pending server confirmation"}</Text>
            <Button
              disabled={busy}
              onPress={() => void run(() => retryQueued(item.id))}
            >
              Retry same capture
            </Button>
            <Button disabled={busy} onPress={() => setDiscardId(item.id)}>
              Discard
            </Button>
            {discardId === item.id && (
              <Button
                onPress={() => {
                  setDiscardId(undefined);
                  void run(() => discardQueued(item.id));
                }}
              >
                Confirm discard for assignment {item.path.split("/")[2]}
              </Button>
            )}
          </Card.Content>
        </Card>
      ))}
    </Screen>
  );
}
