import React, { useState } from "react";
import { View, Share } from "react-native";
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
import { download, openFile, rows } from "../api";
import {parcelCareActions} from "./Operations";
import { parcelActions } from "../workflows";
import {
  label,
  money,
  options,
  type Parcel,
  type Page,
  type Action,
  type Task,
  type Station,
  type PublicParcel,
} from "../domain";
import {
  Screen,
  ErrorBox,
  Select,
  ActionForm,
  useLoad,
} from "../components/UI";
import StationMap from "../components/StationMap";
const statuses = options([
  "booked",
  "picked_up",
  "at_origin_station",
  "in_transit",
  "at_destination_station",
  "out_for_delivery",
  "delivered",
  "exception",
  "returned",
  "cancelled",
]);
export function Parcels() {
  const [page, setPage] = useState(1),
    [search, setSearch] = useState(""),
    [term, setTerm] = useState(""),
    [status, setStatus] = useState("");
  const q = useLoad<Page<Parcel>>(
    `/parcels/?page=${page}&page_size=12&search=${encodeURIComponent(term)}${status ? `&status=${status}` : ""}`,
  );
  return (
    <Screen refreshing={q.loading} onRefresh={() => void q.reload()}>
      <Text variant="headlineSmall">Parcel journeys</Text>
      <TextInput
        label="Search code, recipient or town"
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
      <Select
        field={{ name: "status", label: "Status", options: statuses }}
        value={status}
        onChange={(value) => {
          setStatus(value);
          setPage(1);
        }}
      />
      <ErrorBox error={q.error} retry={() => void q.reload()} />
      {q.loading && !q.data && <ActivityIndicator />}
      {q.data &&
        rows(q.data).map((p) => (
          <Card key={p.id} onPress={() => router.push(`/parcel/${p.code}`)}>
            <Card.Content>
              <Text variant="titleMedium">
                Parcel {p.code} · {money(p.price)}
              </Text>
              <Text>
                {p.origin_station_detail.city_name} →{" "}
                {p.destination_station_detail.city_name}
              </Text>
              <Text>{p.recipient_name}</Text>
              <Chip style={{ alignSelf: "flex-start", marginTop: 8 }}>
                {label(p.status)}
              </Chip>
            </Card.Content>
          </Card>
        ))}
      {q.data && !q.data.count && <Text>No matching parcels.</Text>}
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
    </Screen>
  );
}
export function ParcelDetail({ code }: { code: string }) {
  const { user } = useSession();
  const q = useLoad<Parcel>(`/parcels/${encodeURIComponent(code)}/`);
  const [action, setAction] = useState<Action>(),
    [error, setError] = useState("");
  if (!user) return null;
  const p = q.data;
  return (
    <Screen refreshing={q.loading} onRefresh={() => void q.reload()}>
      <Text variant="headlineSmall">Parcel {code}</Text>
      <ErrorBox error={q.error} retry={() => void q.reload()} />
      <ErrorBox error={error} />
      {p && (
        <>
          <Card>
            <Card.Content>
              <Text variant="titleLarge">
                {p.origin_station_detail.city_name} →{" "}
                {p.destination_station_detail.city_name}
              </Text>
              <Chip style={{ alignSelf: "flex-start", marginVertical: 10 }}>
                {label(p.status)}
              </Chip>
              <Text>
                {p.recipient_name} · {p.recipient_phone}
              </Text>
              <Text>
                {money(p.price)} · {p.weight_band}
              </Text>
              <Text>
                {label(p.delivery_choice)} ·{" "}
                {p.delivery_address || "Station collection"}
              </Text>
              {!!p.pickup_address && <Text>Pickup: {p.pickup_address}</Text>}
              {!!p.notes && <Text>{p.notes}</Text>}
              {[p.origin_station_detail, p.destination_station_detail].map(
                (station) => (
                  <Button
                    key={station.id}
                    onPress={() => router.push(`/station/${station.id}`)}
                  >
                    {station.name} · station map
                  </Button>
                ),
              )}
              <Text>Payment: {p.payment?.status || "Not submitted"}</Text>
              <Text>
                Pay origin station: {p.origin_station_detail.payment_number} ·
                Reference {p.code}
              </Text>
              {[
                { label: "Parcel photo", path: p.photo },
                { label: "Payment receipt", path: p.payment?.receipt_photo },
              ].map((item) =>
                item.path ? (
                  <Button
                    key={item.label}
                    onPress={async () => {
                      try {
                        await openFile(item.path!);
                      } catch (e) {
                        setError(String(e));
                      }
                    }}
                  >
                    View {item.label}
                  </Button>
                ) : null,
              )}
            </Card.Content>
          </Card>
          <Button onPress={()=>void download("/parcels/"+p.code+"/receipt/","booking-"+p.code+".html").catch(e=>setError(String(e)))}>Download booking receipt</Button>
          {[...parcelActions(p, user),...parcelCareActions(p,user)].map((item) => (
            <Button
              key={item.title}
              mode="outlined"
              onPress={() => setAction(item)}
            >
              {item.title}
            </Button>
          ))}
          {p.recipient_access_token && p.sender === user.id && (
            <>
              <Button
                onPress={() =>
                  router.push(`/track/${p.recipient_access_token}`)
                }
              >
                Open recipient tracking
              </Button>
              <Button
                onPress={() =>
                  void Share.share({
                    message: `${process.env.EXPO_PUBLIC_TRACKING_URL || "pano://track"}/${p.recipient_access_token}`,
                  })
                }
              >
                Share private recipient link
              </Button>
            </>
          )}
          <Text variant="titleLarge">Custody timeline</Text>
          {p.events.map((event, i) => (
            <Card key={event.id || i}>
              <Card.Content>
                <Text variant="titleMedium">
                  {label(event.to_status)}
                  {event.accepted === false ? " · Rejected attempt" : ""}
                </Text>
                <Text>{new Date(event.timestamp).toLocaleString()}</Text>
                <Text>{event.note}</Text>
                <Text>
                  {event.released_by_name || "Sender"} →{" "}
                  {event.received_by_name || "Recipient"}
                </Text>
              </Card.Content>
            </Card>
          ))}
        </>
      )}
      {action && (
        <ActionForm
          key={action.title}
          action={action}
          onClose={() => setAction(undefined)}
          onDone={() => void q.reload()}
        />
      )}
    </Screen>
  );
}
export function Tasks() {
  const { user } = useSession();
  const [status, setStatus] = useState(""),
    [page, setPage] = useState(1),
    [action, setAction] = useState<Action>();
  const q = useLoad<Page<Task>>(
    `/tasks/?page=${page}&page_size=12${status ? `&status=${status}` : ""}`,
  );
  return (
    <Screen refreshing={q.loading} onRefresh={() => void q.reload()}>
      <Text variant="headlineSmall">My assignments</Text>
      <Button onPress={() => router.push("/workspace/queue")}>
        Offline sync
      </Button>
      {user?.role === "rider" && (
        <Button
          onPress={() =>
            setAction({
              title: "Update availability",
              path: "/riders/availability/",
              fields: [
                {
                  name: "available",
                  label: "Available for assignments",
                  type: "select",
                  options: options(["true", "false"]),
                  required: true,
                },
              ],
              transform: (v) => ({ available: v.available === "true" }),
            })
          }
        >
          Update availability
        </Button>
      )}
      <Select
        field={{
          name: "status",
          label: "Assignment status",
          options: options(["offered", "accepted", "declined", "completed"]),
        }}
        value={status}
        onChange={(value) => {
          setStatus(value);
          setPage(1);
        }}
      />
      <ErrorBox error={q.error} />
      {q.data &&
        rows(q.data).map((task) => (
          <Card key={task.id}>
            <Card.Content>
              <Text variant="titleMedium">
                {label(task.type)} · Parcel {task.parcel_detail.code}
              </Text>
              <Text>
                {label(task.status)} ·{" "}
                {task.parcel_detail.origin_station_detail.city_name} →{" "}
                {task.parcel_detail.destination_station_detail.city_name}
              </Text>
              <Button
                onPress={() =>
                  router.push(`/parcel/${task.parcel_detail.code}`)
                }
              >
                Parcel journey & code request
              </Button>
              {task.status === "offered" &&
                ["accept", "decline"].map((decision) => (
                  <Button
                    key={decision}
                    onPress={() =>
                      setAction({
                        title:
                          decision === "accept"
                            ? "Accept assignment"
                            : "Decline assignment",
                        path: `/tasks/${task.id}/${decision}/`,
                        fields: [],
                      })
                    }
                  >
                    {label(decision)}
                  </Button>
                ))}
              {task.status === "accepted" && (
                <Button
                  mode="contained"
                  onPress={() => router.push(`/handover/${task.id}`)}
                >
                  Record handover
                </Button>
              )}
              {[
                { path: task.proof_photo, title: "Photo proof" },
                { path: task.signature, title: "Signature proof" },
              ].map((item) =>
                item.path ? <FileLink key={item.title} {...item} /> : null,
              )}
            </Card.Content>
          </Card>
        ))}
      <View style={{ flexDirection: "row", justifyContent: "space-between" }}>
        <Button
          disabled={page === 1 || q.loading}
          onPress={() => setPage(page - 1)}
        >
          Previous
        </Button>
        <Text>Page {page}</Text>
        <Button
          disabled={!q.data?.next || q.loading}
          onPress={() => setPage(page + 1)}
        >
          Next
        </Button>
      </View>
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
function FileLink({ path, title }: { path: string; title: string }) {
  const [error, setError] = useState("");
  return (
    <>
      <Button
        onPress={async () => {
          try {
            await openFile(path);
          } catch (e) {
            setError(String(e));
          }
        }}
      >
        {title}
      </Button>
      <ErrorBox error={error} />
    </>
  );
}
export function Handover({ id }: { id: string }) {
  const q = useLoad<Task>(`/tasks/${id}/`);
  const [target, setTarget] = useState(""),
    [open, setOpen] = useState(false);
  const { user } = useSession();
  const next =
    q.data?.parcel_detail.next_steps.filter(
      (value) =>
        (value === "delivered" && q.data?.type === "last_mile_delivery") ||
        (value === "picked_up" && q.data?.type === "first_mile_pickup") ||
        (value === "in_transit" && q.data?.type === "inter_town_transport") ||
        (value === "out_for_delivery" && q.data?.type === "last_mile_delivery"),
    ) || [];
  return (
    <Screen>
      <Text variant="headlineSmall">Record handover</Text>
      <ErrorBox error={q.error} />
      {q.data && (
        <>
          <Text>
            Parcel {q.data.parcel_detail.code} · {label(q.data.type)}
          </Text>
          <Text>
            The releasing party shares the code when custody changes. Station
            receipt is confirmed by the receiving station operator.
          </Text>
          <Select
            field={{
              name: "to_status",
              label: "Your next custody action",
              options: options(next),
              required: true,
            }}
            value={target}
            onChange={setTarget}
          />
          <Button
            mode="contained"
            disabled={
              !target ||
              q.data.status !== "accepted" ||
              q.data.assigned_to !== user?.id
            }
            onPress={() => setOpen(true)}
          >
            Capture handover
          </Button>
          {!next.length && (
            <Text>Waiting for station receipt or the next journey step.</Text>
          )}
          {open && (
            <ActionForm
              action={{
                title: "Confirm " + label(target),
                path: `/tasks/${id}/complete/`,
                multipart: true,
                offline: true,
                initial: { to_status: target },
                fields: [
                  {
                    name: "otp",
                    label: "Releasing party’s six-digit code",
                    required: true,
                  },
                  ...(target === "delivered"
                    ? [
                        {
                          name: "proof_photo",
                          label: "Delivery photo",
                          type: "image" as const,
                          required: true,
                        },
                        {
                          name: "signature",
                          label: "Recipient signature",
                          type: "signature" as const,
                          required: true,
                        },
                      ]
                    : []),
                ],
              }}
              onClose={() => setOpen(false)}
              onDone={() => void q.reload()}
            />
          )}
        </>
      )}
    </Screen>
  );
}
export function Recipient({ token }: { token: string }) {
  const q = useLoad<PublicParcel>(
    `/track/${encodeURIComponent(token)}/preferences/`,
    true,
  );
  const [action, setAction] = useState<Action>();
  return (
    <Screen refreshing={q.loading} onRefresh={() => void q.reload()}>
      <Text variant="headlineSmall">Your delivery</Text>
      <ErrorBox error={q.error} retry={() => void q.reload()} />
      {q.data && (
        <>
          <Text variant="titleLarge">
            Parcel {q.data.code} · {label(q.data.status)}
          </Text>
          <Text>{q.data.recipient_name}</Text>
          <Text>
            {q.data.destination_station.name} ·{" "}
            {q.data.destination_station.address}
          </Text>
          <StationMap station={q.data.destination_station} />
          <Text>
            {label(q.data.delivery_choice)} ·{" "}
            {q.data.delivery_address || "Station collection"}
          </Text>
          {!["out_for_delivery", "delivered", "returned", "cancelled"].includes(
            q.data.status,
          ) && (
            <Button
              onPress={() =>
                setAction({
                  title: "Choose receiving method",
                  path: `/track/${encodeURIComponent(token)}/preferences/`,
                  initial: {
                    choice: q.data!.delivery_choice,
                    address: q.data!.delivery_address,
                  },
                  fields: [
                    {
                      name: "choice",
                      label: "Receiving method",
                      type: "select",
                      options: options(["station", "home"]),
                      required: true,
                    },
                    {
                      name: "address",
                      label: "Home address",
                      type: "multiline",
                    },
                  ],
                  transform: (v) => {
                    if (v.choice === "home" && !String(v.address || "").trim())
                      throw new Error("Home delivery needs an address");
                    return v;
                  },
                })
              }
            >
              Change receiving preference
            </Button>
          )}
          {["at_destination_station", "out_for_delivery"].includes(
            q.data.status,
          ) && (
            <Button
              mode="contained"
              onPress={() =>
                setAction({
                  title: "Generate receiving code",
                  description:
                    "Generate this code when the parcel is in front of you. Share it after checking the parcel.",
                  path: `/track/${encodeURIComponent(token)}/code/`,
                  fields: [],
                })
              }
            >
              Get receiving code
            </Button>
          )}
          {q.data.events.map((event, index) => (
            <Text key={index}>
              {label(event.to_status)} ·{" "}
              {new Date(event.timestamp).toLocaleString()}
            </Text>
          ))}
        </>
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
export function StationDetail({ id }: { id: string }) {
  const q = useLoad<Station>(`/stations/${id}/`);
  return (
    <Screen>
      <ErrorBox error={q.error} />
      {q.data && (
        <>
          <Text variant="headlineSmall">{q.data.name}</Text>
          <Text>
            {q.data.city_name} · {q.data.address}
          </Text>
          <Text>Payment contact: {q.data.payment_number}</Text>
          <StationMap station={q.data} />
        </>
      )}
    </Screen>
  );
}
