import React, { useEffect, useState } from "react";
import { router } from "expo-router";
import { Text, Button, Card } from "react-native-paper";
import { useSession } from "../session";
import { api, read, rows } from "../api";
import {
  options,
  money,
  type Entity,
  type Page,
  type Values,
  type Field,
  type Parcel,
} from "../domain";
import {bookingCareFields} from "../operationsFields";
import LocationPin from "../components/LocationPin";
import { Screen, Fields, ErrorBox, useLoad, validate, Select } from "../components/UI";
export function Booking() {
  const { user } = useSession();
  const pilots = useLoad<Page<Entity>>("/pilot-routes/?active=true");
  const [reverse, setReverse] = useState(false),
    [step, setStep] = useState(0),
    [values, setValues] = useState<Values>({
      weight_band: "0-2kg",
      contents_category:"general", declared_value:"0",delivery_choice:"station",
      recipient_phone: "+263",
      ...(user?.role !== "customer" ? { sender_phone: "+263" } : {}),
    }),
    [quote, setQuote] = useState<{ price: string }>(),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const saved=useLoad<Page<Entity>>("/addresses/");
  const rules=useLoad<Record<string,unknown>>("/operations/policy/",true);
  const pilot = pilots.data && rows(pilots.data).find((item) => item.active);
  const origin = pilot?.[reverse ? "destination_city" : "origin_city"],
    destination = pilot?.[reverse ? "origin_city" : "destination_city"];
  const route: Field[] = [
    {
      name: "origin_station",
      label: "Drop-off station",
      type: "select",
      resource: `/stations/?active=true&city=${origin || ""}${user?.role === "station_operator" ? `&operator=${user.id}` : ""}`,
      required: true,
    },
    {
      name: "destination_station",
      label: "Destination station",
      type: "select",
      resource: `/stations/?active=true&city=${destination || ""}`,
      required: true,
    },
  ];
  const people: Field[] = [
    ...(user?.role !== "customer"
      ? [
          { name: "sender_name", label: "Sender full name", required: true },
          { name: "sender_phone", label: "Sender phone", required: true },
        ]
      : []),
    { name: "recipient_name", label: "Recipient full name", required: true },
    { name: "recipient_phone", label: "Recipient phone", required: true },
  ];
  const parcel: Field[] = [
    {
      name: "weight_band",
      label: "Weight band",
      type: "select",
      options: options(["0-2kg", "2-5kg", "5-10kg"]),
      required: true,
    },
    { name: "photo", label: "Parcel photo", type: "image", required: true },
    {
      name: "pickup_address",
      label: "Pickup address (optional)",
      type: "multiline",
    },
    { name: "notes", label: "Handling instructions", type: "multiline" },
  ];
  const fields =
    step === 0 ? route : step === 1 ? people : step === 2 ? [...parcel,...bookingCareFields] : [];
  useEffect(() => {
    let active = true;
    void (async () => {
      await Promise.resolve();
      if (active) setQuote(undefined);
      if (!values.origin_station || !values.destination_station) return;
      try {
        const data = await read<{ price: string }>(
          `/rates/lookup/?origin_station=${values.origin_station}&destination_station=${values.destination_station}&weight_band=${values.weight_band}`,
        );
        if (active) {
          setQuote(data);
          setError("");
        }
      } catch (e) {
        if (active) setError(String(e));
      }
    })();
    return () => {
      active = false;
    };
  }, [values.origin_station, values.destination_station, values.weight_band]);
  return (
    <Screen>
      <Text variant="headlineSmall">Book a parcel</Text>
      <ErrorBox error={pilots.error} />
      <Text>
        {String(pilot?.name || "Loading pilot route…")} · Step {step + 1} of 4
      </Text>
      <Button
        disabled={busy}
        onPress={() => {
          setReverse(!reverse);
          setStep(0);
          setValues({ ...values, origin_station: "", destination_station: "" });
        }}
      >
        Reverse route
      </Button>
      <Card>
        <Card.Content>
          <Text variant="titleMedium">Your quote</Text>
          <Text variant="headlineLarge">
            {quote ? money(quote.price) : "Choose stations"}
          </Text>
          <Text>Payment is recorded after booking. No online charge.</Text>
        </Card.Content>
      </Card>
      <ErrorBox error={error} />
      {step < 3 ? (
        <>{step===1&&user?.role==="customer"&&<Select field={{name:"saved",label:"Use saved recipient",options:(saved.data?.results||[]).map(a=>({value:String(a.id),label:String(a.label)}))}} value="" onChange={v=>{const a=saved.data?.results.find(a=>a.id===Number(v));if(a)setValues({...values,recipient_name:String(a.contact_name||""),recipient_phone:String(a.phone||""),delivery_address:String(a.address||""),delivery_latitude:a.latitude?String(a.latitude):undefined,delivery_longitude:a.longitude?String(a.longitude):undefined,location_instructions:String(a.instructions||"")})}}/>}<Fields fields={fields} values={values} onChange={setValues}/>{step===2&&<><Text>{String(rules.data?.terms||"Loading parcel policy…")} Prohibited: {String(rules.data?.prohibited_categories||"")}. Restricted: {String(rules.data?.restricted_categories||"")}. Liability limit: {money(rules.data?.liability_limit)}.</Text><LocationPin prefix="pickup" values={values} onChange={setValues}/><LocationPin prefix="delivery" values={values} onChange={setValues}/></>}</>
      ) : (
        <Card>
          <Card.Content>
            <Text variant="titleLarge">Review booking</Text>
            <Text>
              {String(values.recipient_name)} · {String(values.recipient_phone)}
            </Text>
            <Text>
              {String(values.weight_band)} · {quote && money(quote.price)}
            </Text>
            <Text>{String(values.pickup_address || "Station drop-off")}</Text>
            <Text>{String(values.notes || "No handling instructions")}</Text>
          </Card.Content>
        </Card>
      )}
      <Button
        mode="contained"
        loading={busy}
        disabled={busy || !quote}
        onPress={async () => {
          const invalid = validate(fields, values);
          if (invalid) {
            setError(invalid);
            return;
          }
          if (step < 3) {
            setError("");
            setStep(step + 1);
            return;
          }
          setBusy(true);
          try {
            const result = await api<Parcel>("/parcels/", "POST", Object.fromEntries(Object.entries(values).filter(([,v])=>v!==""&&v!==undefined)), {
              multipart: true,
            });
            router.replace(`/parcel/${result.code}`);
          } catch (e) {
            setError(e instanceof Error ? e.message : String(e));
          } finally {
            setBusy(false);
          }
        }}
      >
        {step === 3 ? "Confirm booking" : "Continue"}
      </Button>
      <Button disabled={!step || busy} onPress={() => setStep(step - 1)}>
        Back
      </Button>
    </Screen>
  );
}
