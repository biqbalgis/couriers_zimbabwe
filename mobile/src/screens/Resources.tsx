import React, { useState } from "react";
import { View, Linking } from "react-native";
import { router } from "expo-router";
import {
  Text,
  Button,
  TextInput,
  Card,
  Chip,
  ActivityIndicator,
} from "react-native-paper";
import { useSession } from "../session";
import { download, openFile } from "../api";
import { createAction, rowActions, statusOptions } from "../workflows";
import {
  label,
  money,
  rows,
  options,
  type Action,
  type Entity,
  type Page,
} from "../domain";
import {
  Screen,
  ErrorBox,
  Select,
  useLoad,
  ActionForm,
} from "../components/UI";

function summary(screen: string, row: Entity) {
  const name = (row.user_detail as { name: string } | undefined)?.name;
  if (screen === "partners")
    return [
      name || `Partner ${row.id}`,
      String(
        row.review_note ||
          row.vehicle_type ||
          row.home_station_name ||
          "Application",
      ),
    ];
  if (screen === "trips")
    return [
      `${row.origin_name} → ${row.destination_name}`,
      `${row.carrier_name} · ${row.remaining_kg} kg free · ${new Date(String(row.departure_at)).toLocaleString()}`,
    ];
  if (screen === "payments")
    return [
      `Parcel ${row.parcel_code} · ${money(row.amount)}`,
      `${label(row.method)} · ${row.transaction_reference || "No reference"}`,
    ];
  if (screen === "payouts" || screen === "earnings")
    return [
      `${row.beneficiary_name || "Allocation"} · ${money(row.amount)}`,
      `Parcel ${row.parcel_code} · ${row.period} · ${label(row.leg || row.recipient)} · ${row.payment_reference || "Awaiting settlement"}`,
    ];
  if (screen === "support")
    return [
      String(row.subject),
      `Ticket ${row.id}${row.received_after_hours ? " · Received after hours" : ""}`,
    ];
  if (screen === "audit")
    return [
      `Parcel ${row.parcel_code} · ${label(row.to_status)}`,
      `${row.actor_name || "System"} · ${new Date(String(row.timestamp)).toLocaleString()} · ${row.note || ""}`,
    ];
  if (screen === "finance-audit")
    return [
      label(row.kind || row.event || row.action),
      `${row.reference || row.note || ""} · ${row.created_at || ""} · ${JSON.stringify(row.details || {})}`,
    ];
  if (screen === "notifications")
    return [label(row.trigger_event), String(row.message || "Shipment update")];
  if (screen === "rates")
    return [
      `${row.origin_name} → ${row.destination_name}`,
      `${row.weight_band} · ${money(row.price)}${row.station_override ? " · Station override" : ""}`,
    ];
  if (screen === "users")
    return [
      String(row.name),
      `${row.username} · ${row.phone} · ${label(row.role)} · ${row.is_active ? "Active" : "Disabled"}`,
    ];
  return [
    String(row.name || row.label || `Record ${row.id}`),
    String(row.address || row.province || ""),
  ];
}
export function ResourceScreen({ screen }: { screen: string }) {
  const { user } = useSession();
  const [search, setSearch] = useState(""),
    [term, setTerm] = useState(""),
    [status, setStatus] = useState(""),
    [page, setPage] = useState(1),
    [partner, setPartner] = useState("riders"),
    [action, setAction] = useState<Action>(),
    [error, setError] = useState(""),
    [conversation, setConversation] = useState<Entity>();
  const resource =
    screen === "partners"
      ? partner
      : screen === "audit"
        ? "status-events"
        : screen;
  const q = useLoad<Page<Entity>>(
    `/${resource}/?page=${page}&page_size=12&search=${encodeURIComponent(term)}${status ? `&status=${encodeURIComponent(status)}` : ""}`,
  );
  if (!user) return null;
  const create = createAction(screen, user);
  const run = async (fn: () => Promise<void>) => {
    try {
      setError("");
      await fn();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  };
  return (
    <Screen refreshing={q.loading} onRefresh={() => void q.reload()}>
      <Text variant="headlineSmall">{label(screen)}</Text>
      {create && (
        <Button mode="contained" onPress={() => setAction(create)}>
          {create.title}
        </Button>
      )}
      {screen === "partners" && (
        <Select
          field={{
            name: "partner",
            label: "Partner type",
            options: [
              { value: "riders", label: "Riders" },
              { value: "carriers", label: "Carriers" },
            ],
            required: true,
          }}
          value={partner}
          onChange={(value) => {
            setPartner(value);
            setPage(1);
            setStatus("");
          }}
        />
      )}
      <TextInput
        label="Search"
        value={search}
        onChangeText={setSearch}
        onSubmitEditing={() => {
          setTerm(search);
          setPage(1);
        }}
        right={
          <TextInput.Icon
            icon="magnify"
            onPress={() => {
              setTerm(search);
              setPage(1);
            }}
          />
        }
      />
      {statusOptions[screen] && (
        <Select
          field={{
            name: "status",
            label: "Status filter",
            options: options(statusOptions[screen]),
          }}
          value={status}
          onChange={(value) => {
            setStatus(value);
            setPage(1);
          }}
        />
      )}
      {["payments", "payouts"].includes(screen) && (
        <Button
          onPress={() =>
            void run(() => download(`/${screen}/export/`, screen + ".csv"))
          }
        >
          Export CSV
        </Button>
      )}
      <ErrorBox error={q.error} retry={() => void q.reload()} />
      <ErrorBox error={error} />
      {q.loading && !q.data && <ActivityIndicator />}
      {q.data &&
        rows(q.data).map((row) => {
          const [title, body] = summary(screen, row);
          return (
            <Card key={row.id}>
              <Card.Content>
                <Text variant="titleMedium">{title}</Text>
                <Text>{body}</Text>
                {screen==="stations"&&<><Text>Service: {String(row.service_status)} · Contact: {String(row.contact_phone||"Not provided")} · Holding capacity: {String(row.holding_capacity??"Not set")}</Text>{Object.entries((row.opening_hours as Record<string,string>)||{}).map(([day,hours])=><Text key={day}>{day}: {hours}</Text>)}</>}
                {screen==="trips"&&<Text>Volume remaining: {String(row.remaining_m3??"Not limited")} m³ · Vehicle: {String(row.vehicle_registration||"Not recorded")}</Text>}
                {screen==="partners"&&<Text>{row.suspended?"Suspended · ":""}{row.reverification_required?"Re-verification required · ":""}Document expiry: {String(row.document_expires_at||"Not recorded")}</Text>}
                {screen==="payments"&&Array.isArray(row.fraud_flags)&&row.fraud_flags.length>0&&<Text accessibilityRole="alert">Suspicious evidence: {row.fraud_flags.join(", ")}</Text>}
                {row.status !== undefined && (
                  <Chip style={{ alignSelf: "flex-start", marginVertical: 8 }}>
                    {label(row.status)}
                  </Chip>
                )}
                {screen === "audit" && (
                  <Text>
                    {row.accepted ? "Confirmed" : "Rejected attempt"} ·{" "}
                    {String(row.released_by_name || "Sender")} →{" "}
                    {String(row.received_by_name || "Recipient")}
                  </Text>
                )}
                {screen === "support" && (
                  <Button
                    onPress={() =>
                      setConversation(
                        conversation?.id === row.id ? undefined : row,
                      )
                    }
                  >
                    Read conversation
                  </Button>
                )}
                {conversation?.id === row.id &&
                  (
                    (row.messages as {
                      body: string;
                      author: string;
                      created_at: string;
                    }[]) || []
                  ).map((message, index) => (
                    <View key={index} style={{ marginVertical: 10 }}>
                      <Text variant="labelLarge">
                        {message.author} ·{" "}
                        {new Date(message.created_at).toLocaleString()}
                      </Text>
                      <Text>{message.body}</Text>
                    </View>
                  ))}
                {["document", "receipt_photo"].map((key) =>
                  row[key] ? (
                    <Button
                      key={key}
                      onPress={() => void run(() => openFile(String(row[key])))}
                    >
                      Review{" "}
                      {key === "document" ? "application document" : "receipt"}
                    </Button>
                  ) : null,
                )}
                {screen === "payouts" && (
                  <Button
                    onPress={() =>
                      void run(() =>
                        download(
                          `/payouts/${row.id}/statement/`,
                          `statement-${row.id}.html`,
                        ),
                      )
                    }
                  >
                    Download statement
                  </Button>
                )}
                {screen === "notifications" && !!row.parcel_code && (
                  <Button
                    onPress={() => router.push(`/parcel/${row.parcel_code}`)}
                  >
                    View parcel
                  </Button>
                )}
                {screen === "stations" && (
                  <>
                    <Text>Payment contact: {String(row.payment_number)}</Text>
                    <Button onPress={() => router.push(`/station/${row.id}`)}>
                      Station details & map
                    </Button>
                  </>
                )}
                {rowActions(screen, row, user, partner).map((item) => (
                  <Button key={item.title} onPress={() => setAction(item)}>
                    {item.title}
                  </Button>
                ))}
              </Card.Content>
            </Card>
          );
        })}
      {q.data && !q.data.count && <Text>No matching records.</Text>}
      <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
        <Button
          disabled={page === 1 || q.loading}
          onPress={() => setPage(page - 1)}
        >
          Previous
        </Button>
        <Text>
          Page {page} · {q.data?.count || 0}
        </Text>
        <Button
          disabled={!q.data?.next || q.loading}
          onPress={() => setPage(page + 1)}
        >
          Next
        </Button>
      </View>
      {screen === "support" && <SupportContact />}
      {action && (
        <ActionForm
          key={action.title + action.path}
          action={action}
          onClose={() => setAction(undefined)}
          onDone={() => {
            setConversation(undefined);
            void q.reload();
          }}
        />
      )}
    </Screen>
  );
}
function SupportContact() {
  const q = useLoad<{
    phone: string;
    portal_url: string;
    hours: string;
    after_hours: string;
  }>("/support-contact/", true);
  return q.data ? (
    <Card>
      <Card.Content>
        <Text>{q.data.hours}</Text>
        <Text>{q.data.after_hours}</Text>
        {!!q.data.phone && (
          <Button onPress={() => void Linking.openURL(`tel:${q.data!.phone}`)}>
            Call support
          </Button>
        )}
        {q.data.portal_url.startsWith("https://") && (
          <Button onPress={() => void Linking.openURL(q.data!.portal_url)}>
            Open helpdesk
          </Button>
        )}
      </Card.Content>
    </Card>
  ) : null;
}
export function Earnings() {
  const q = useLoad<{
    total: string;
    completed_tasks: number;
    statements: Entity[];
  }>("/earnings/");
  const [error, setError] = useState("");
  return (
    <Screen refreshing={q.loading} onRefresh={() => void q.reload()}>
      <Text variant="headlineSmall">Your earnings</Text>
      <ErrorBox error={q.error} retry={() => void q.reload()} />
      <ErrorBox error={error} />
      {q.data && (
        <>
          <Text variant="headlineMedium">Allocated: {money(q.data.total)}</Text>
          <Text>{q.data.completed_tasks} completed assignments</Text>
          {q.data.statements.map((row) => (
            <Card key={row.id}>
              <Card.Content>
                <Text variant="titleMedium">
                  {money(row.amount)} · Parcel {String(row.parcel_code)}
                </Text>
                <Text>
                  {String(row.period)} · {label(row.status)} ·{" "}
                  {label(row.leg || row.recipient)}
                </Text>
                <Text>
                  {String(row.payment_reference || "Awaiting settlement")}
                </Text>
                <Button
                  onPress={async () => {
                    try {
                      await download(
                        `/payouts/${row.id}/statement/`,
                        `statement-${row.id}.html`,
                      );
                    } catch (e) {
                      setError(String(e));
                    }
                  }}
                >
                  Download statement
                </Button>
              </Card.Content>
            </Card>
          ))}
          {!q.data.statements.length && <Text>No earnings yet.</Text>}
        </>
      )}
    </Screen>
  );
}
export function Reports() {
  const q = useLoad<Record<string, unknown>>("/reports/summary/");
  const titles: Record<string, string> = {
    volumes: "Total shipments",
    deliveries: "Delivered shipments",
    earnings: "Verified revenue",
    payouts: "Recorded disbursements",
    first_attempt_last_mile_success_rate: "First-attempt home delivery (%)",
    custody_record_completeness: "Complete custody journeys (%)",
    pre_dispatch_verification_rate: "Verified before dispatch (%)",
  };
  return (
    <Screen refreshing={q.loading} onRefresh={() => void q.reload()}>
      <Text variant="headlineSmall">Pilot reports</Text>
      <ErrorBox error={q.error} />
      {q.data &&
        Object.entries(titles).map(([key, title]) => (
          <Card key={key}>
            <Card.Content>
              <Text>{title}</Text>
              <Text variant="headlineMedium">
                {key === "earnings" || key === "payouts"
                  ? money(q.data![key])
                  : String(q.data![key] ?? 0)}
              </Text>
            </Card.Content>
          </Card>
        ))}
      {!!q.data?.metric_denominators && (
        <Card>
          <Card.Content>
            <Text variant="titleMedium">Qualifying shipments</Text>
            {Object.entries(
              q.data!.metric_denominators as Record<string, number>,
            ).map(([key, value]) => (
              <Text key={key}>
                {label(key)}: {value}
              </Text>
            ))}
          </Card.Content>
        </Card>
      )}
    </Screen>
  );
}
export function Settings() {
  const pilots = useLoad<Page<Entity>>("/pilot-routes/"),
    integrations = useLoad<Record<string, unknown>>("/integrations/status/"),
    network = useLoad<Entity>("/settings/network/");
  const { user } = useSession();
  const [action, setAction] = useState<Action>();
  if (!user) return null;
  return (
    <Screen>
      <Text variant="headlineSmall">Pilot & integrations</Text>
      <ErrorBox error={pilots.error} />
      {pilots.data &&
        rows(pilots.data).map((row) => (
          <Card key={row.id}>
            <Card.Content>
              <Text variant="titleMedium">{String(row.name)}</Text>
              <Text>
                {String(row.origin_name)} ↔ {String(row.destination_name)} ·{" "}
                {row.active ? "Active" : "Inactive"}
              </Text>
              <Button
                onPress={() =>
                  setAction(rowActions("pilot-routes", row, user)[0])
                }
              >
                Edit pilot
              </Button>
            </Card.Content>
          </Card>
        ))}
      <ErrorBox error={integrations.error} />
      {integrations.data && (
        <Card>
          <Card.Content>
            <Text variant="titleLarge">Provider connections</Text>
            {Object.entries(integrations.data).map(([key, value]) => (
              <Text key={key}>
                {label(key)}:{" "}
                {typeof value === "boolean"
                  ? value
                    ? "Ready"
                    : "Not configured"
                  : String(value)}
              </Text>
            ))}
          </Card.Content>
        </Card>
      )}
      <ErrorBox error={network.error} />
      {network.data && (
        <Button
          onPress={() =>
            setAction({
              title: "Edit network configuration",
              path: "/settings/network/",
              method: "PATCH",
              fields: [
                {
                  name: "value",
                  label: "Configuration JSON",
                  type: "json",
                  required: true,
                },
              ],
              initial: { value: JSON.stringify(network.data!.value, null, 2) },
              transform: (v) => ({ value: JSON.parse(String(v.value)) }),
            })
          }
        >
          Edit network configuration
        </Button>
      )}
      {action && (
        <ActionForm
          action={action}
          onClose={() => setAction(undefined)}
          onDone={() => {
            void pilots.reload();
            void network.reload();
            void integrations.reload();
          }}
        />
      )}
    </Screen>
  );
}
