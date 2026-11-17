import React, { useCallback, useEffect, useRef, useState } from "react";
import {
  ScrollView,
  View,
  KeyboardAvoidingView,
  Platform,
  RefreshControl,
  Image,
  PanResponder,
} from "react-native";
import {
  Text,
  Button,
  TextInput,
  Card,
  ActivityIndicator,
  HelperText,
  Portal,
  Modal,
  Checkbox,
  Divider,
  useTheme,
} from "react-native-paper";
import Svg, { Path } from "react-native-svg";
import { captureRef } from "react-native-view-shot";
import * as ImagePicker from "expo-image-picker";
import * as DocumentPicker from "expo-document-picker";
import { api, all, handover, read } from "../api";
import {
  isAttachment,
  label,
  type Action,
  type Attachment,
  type Entity,
  type Field,
  type Option,
  type Values,
} from "../domain";

export function Screen({
  children,
  refreshing = false,
  onRefresh,
}: {
  children: React.ReactNode;
  refreshing?: boolean;
  onRefresh?: () => void;
}) {
  return (
    <KeyboardAvoidingView
      style={{ flex: 1 }}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
    >
      <ScrollView
        keyboardShouldPersistTaps="handled"
        contentContainerStyle={{ padding: 20, gap: 16, paddingBottom: 40 }}
        refreshControl={
          onRefresh ? (
            <RefreshControl refreshing={refreshing} onRefresh={onRefresh} />
          ) : undefined
        }
      >
        {children}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}
export function ErrorBox({
  error,
  retry,
}: {
  error: string;
  retry?: () => void;
}) {
  const t = useTheme();
  return error ? (
    <Card style={{ backgroundColor: t.colors.errorContainer }}>
      <Card.Content>
        <Text accessibilityRole="alert">{error}</Text>
        {retry && <Button onPress={retry}>Retry</Button>}
      </Card.Content>
    </Card>
  ) : null;
}
export function useLoad<T>(path: string, publicRead = false) {
  const [snapshot, setSnapshot] = useState<{ path: string; data: T }>(),
    [error, setError] = useState(""),
    [loading, setLoading] = useState(true);
  const version = useRef(0);
  const reload = useCallback(async () => {
    const current = ++version.current;
    await Promise.resolve();
    setLoading(true);
    setError("");
    try {
      const value = await read<T>(path, publicRead);
      if (current === version.current) setSnapshot({ path, data: value });
    } catch (e) {
      if (current === version.current)
        setError(e instanceof Error ? e.message : String(e));
    } finally {
      if (current === version.current) setLoading(false);
    }
  }, [path, publicRead]);
  const invalidate = useCallback(() => {
    version.current++;
  }, []);
  useEffect(() => {
    // This is an asynchronous external API subscription, not derived render state.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void reload();
    return invalidate;
  }, [reload, invalidate]);
  return {
    data: snapshot?.path === path ? snapshot.data : undefined,
    error,
    loading,
    reload,
  };
}
export function Select({
  field,
  value,
  onChange,
}: {
  field: Field;
  value: string;
  onChange: (value: string) => void;
}) {
  const [open, setOpen] = useState(false),
    [search, setSearch] = useState(""),
    [items, setItems] = useState<Option[]>(field.options || []),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const theme = useTheme();
  const resource = field.resource;
  useEffect(() => {
    let active = true;
    if (resource) {
      void (async () => {
        await Promise.resolve();
        if (active) {
          setBusy(true);
          setError("");
        }
        try {
          const data = await all<Entity>(resource);
          if (active)
            setItems(
              data.map((row) => ({
                value: String(row.id),
                label: String(
                  row.name ||
                    row.code ||
                    (row.parcel_code && `${row.parcel_code} · ${row.kind} · Case #${row.id}`) ||
                    (row.user_detail &&
                      typeof row.user_detail === "object" &&
                      "name" in row.user_detail &&
                      row.user_detail.name) ||
                    row.label ||
                    (row.carrier_name &&
                      `${row.carrier_name}: ${row.origin_name} → ${row.destination_name} · ${row.departure_at} · ${row.remaining_kg} kg`) ||
                    `Record ${row.id}`,
                ),
              })),
            );
        } catch (e) {
          if (active) setError(String(e));
        } finally {
          if (active) setBusy(false);
        }
      })();
    }
    return () => {
      active = false;
    };
  }, [resource]);
  const choices = resource ? items : field.options || [];
  return (
    <>
      <Button
        mode="outlined"
        accessibilityLabel={field.label}
        onPress={() => setOpen(true)}
      >
        {field.label}
        {field.required ? " *" : ""}:{" "}
        {choices.find((item) => item.value === value)?.label || "Choose"}
      </Button>
      <Portal>
        <Modal
          visible={open}
          onDismiss={() => setOpen(false)}
          contentContainerStyle={{
            backgroundColor: theme.colors.surface,
            margin: 20,
            padding: 20,
            borderRadius: 16,
            maxHeight: "80%",
          }}
        >
          <Text variant="titleLarge">{field.label}</Text>
          <TextInput
            label="Search options"
            value={search}
            onChangeText={setSearch}
          />
          {busy && <ActivityIndicator />}
          <ErrorBox error={error} />
          <ScrollView keyboardShouldPersistTaps="handled">
            {!field.required && (
              <Button
                onPress={() => {
                  onChange("");
                  setOpen(false);
                }}
              >
                None
              </Button>
            )}
            {choices
              .filter((item) =>
                item.label.toLowerCase().includes(search.toLowerCase()),
              )
              .map((item) => (
                <Button
                  key={item.value}
                  onPress={() => {
                    onChange(item.value);
                    setOpen(false);
                  }}
                >
                  {item.label}
                </Button>
              ))}
          </ScrollView>
          <Button onPress={() => setOpen(false)}>Close</Button>
        </Modal>
      </Portal>
    </>
  );
}
export function Signature({
  value,
  onChange,
}: {
  value: Attachment | undefined;
  onChange: (file: Attachment | undefined) => void;
}) {
  const surface = useRef<View>(null),
    drawing = useRef<string[]>([]),
    [paths, setPaths] = useState<string[]>([]),
    [confirmed, setConfirmed] = useState(false),
    [error, setError] = useState("");
  const theme = useTheme();
  const change = useRef(onChange);
  useEffect(() => {
    change.current = onChange;
  }, [onChange]);
  // PanResponder stores callbacks; these refs are read only when touch events fire.
  // eslint-disable-next-line react-hooks/refs
  const [pan] = useState(() =>
    PanResponder.create({
      onStartShouldSetPanResponder: () => true,
      onMoveShouldSetPanResponder: () => true,
      onPanResponderGrant: (e) => {
        change.current(undefined);
        setConfirmed(false);
        drawing.current.push(
          `M ${e.nativeEvent.locationX} ${e.nativeEvent.locationY}`,
        );
        setPaths([...drawing.current]);
      },
      onPanResponderMove: (e) => {
        const i = drawing.current.length - 1;
        if (i >= 0) {
          drawing.current[i] +=
            ` L ${e.nativeEvent.locationX} ${e.nativeEvent.locationY}`;
          setPaths([...drawing.current]);
        }
      },
    }),
  );
  return (
    <View style={{ gap: 8 }}>
      <Text variant="titleMedium">Recipient signature</Text>
      <View
        ref={surface}
        collapsable={false}
        style={{
          height: 180,
          backgroundColor: theme.colors.surface,
          borderWidth: 1,
          borderColor: theme.colors.outline,
        }}
        {...pan.panHandlers}
      >
        <Svg height="100%" width="100%">
          {paths.map((path, i) => (
            <Path
              key={i}
              d={path}
              stroke={theme.colors.onSurface}
              strokeWidth={3}
              fill="none"
              strokeLinecap="round"
            />
          ))}
        </Svg>
      </View>
      <Checkbox.Item
        label="Recipient confirms this signature"
        status={confirmed ? "checked" : "unchecked"}
        onPress={() => {
          setConfirmed(!confirmed);
          onChange(undefined);
        }}
      />
      <Button
        disabled={!confirmed || paths.every((path) => !path.includes(" L "))}
        onPress={async () => {
          try {
            const uri = await captureRef(surface, {
              format: "png",
              quality: 1,
            });
            onChange({ uri, name: "signature.png", type: "image/png" });
          } catch (e) {
            setError(String(e));
          }
        }}
      >
        {value ? "Signature saved" : "Save signature"}
      </Button>
      <Button
        onPress={() => {
          drawing.current = [];
          setPaths([]);
          setConfirmed(false);
          onChange(undefined);
        }}
      >
        Clear signature
      </Button>
      <ErrorBox error={error} />
    </View>
  );
}
export function Upload({
  field,
  value,
  onChange,
}: {
  field: Field;
  value: Attachment | undefined;
  onChange: (value: Attachment | undefined) => void;
}) {
  const [error, setError] = useState("");
  const choose = async (camera = false) => {
    try {
      setError("");
      if (field.type === "document") {
        const result = await DocumentPicker.getDocumentAsync({
          type: ["application/pdf", "image/*"],
          copyToCacheDirectory: true,
        });
        if (!result.canceled) {
          const file = result.assets[0];
          onChange({
            uri: file.uri,
            name: file.name,
            type: file.mimeType || "application/pdf",
          });
        }
      } else {
        if (
          camera &&
          !(await ImagePicker.requestCameraPermissionsAsync()).granted
        )
          throw new Error("Camera access is needed to take a photo.");
        const result = await (camera
          ? ImagePicker.launchCameraAsync({
              mediaTypes: ["images"],
              quality: 0.8,
            })
          : ImagePicker.launchImageLibraryAsync({
              mediaTypes: ["images"],
              quality: 0.8,
            }));
        if (!result.canceled) {
          const file = result.assets[0];
          onChange({
            uri: file.uri,
            name: file.fileName || "photo.jpg",
            type: file.mimeType || "image/jpeg",
          });
        }
      }
    } catch (e) {
      setError(String(e));
    }
  };
  return (
    <View style={{ gap: 8 }}>
      <Text>
        {field.label}
        {field.required ? " *" : ""}
      </Text>
      {value && (
        <>
          <Text>{value.name}</Text>
          {value.type.startsWith("image/") && (
            <Image
              source={{ uri: value.uri }}
              style={{ height: 140, resizeMode: "contain" }}
            />
          )}
          <Button onPress={() => onChange(undefined)}>Remove attachment</Button>
        </>
      )}
      <Button mode="outlined" onPress={() => void choose()}>
        Choose {field.type === "document" ? "document" : "photo"}
      </Button>
      {field.type === "image" && (
        <Button onPress={() => void choose(true)}>Take photo</Button>
      )}
      <ErrorBox error={error} />
    </View>
  );
}
export function Fields({
  fields,
  values,
  onChange,
}: {
  fields: Field[];
  values: Values;
  onChange: (values: Values) => void;
}) {
  return (
    <View style={{ gap: 14 }}>
      {fields.map((field) => (
        <View key={field.name} style={{ gap: 4 }}>
          {field.type === "select" ? (
            <Select
              field={field}
              value={String(values[field.name] ?? "")}
              onChange={(value) => onChange({ ...values, [field.name]: value })}
            />
          ) : field.type === "signature" ? (
            <Signature
              value={
                isAttachment(values[field.name])
                  ? (values[field.name] as Attachment)
                  : undefined
              }
              onChange={(value) => onChange({ ...values, [field.name]: value })}
            />
          ) : field.type === "image" || field.type === "document" ? (
            <Upload
              field={field}
              value={
                isAttachment(values[field.name])
                  ? (values[field.name] as Attachment)
                  : undefined
              }
              onChange={(value) => onChange({ ...values, [field.name]: value })}
            />
          ) : (
            <TextInput
              mode="outlined"
              label={field.label + (field.required ? " *" : "")}
              accessibilityLabel={field.label}
              value={String(values[field.name] ?? "")}
              onChangeText={(value) =>
                onChange({ ...values, [field.name]: value })
              }
              multiline={field.type === "multiline" || field.type === "json"}
              secureTextEntry={field.type === "password"}
              autoCapitalize="none"
              keyboardType={field.type === "number" ? "decimal-pad" : "default"}
            />
          )}
          {!!field.help && <HelperText type="info">{field.help}</HelperText>}
        </View>
      ))}
    </View>
  );
}
export function validate(fields: Field[], values: Values) {
  for (const field of fields) {
    const value = values[field.name];
    if (
      field.required &&
      (value === undefined || (typeof value === "string" && !value.trim()))
    )
      return `${field.label} is required.`;
    if (value && field.type === "number" && !Number.isFinite(Number(value)))
      return `${field.label} must be a number.`;
    if (
      value &&
      field.type === "date" &&
      !Number.isFinite(Date.parse(String(value)))
    )
      return "Enter a departure time with timezone, for example 2026-10-03T09:00:00+02:00.";
    if (
      value &&
      ["recipient_phone", "sender_phone", "phone"].includes(field.name) &&
      !/^\+263\d{9}$/.test(String(value))
    )
      return "Phone must use +263 followed by nine digits.";
    if (value && field.name === "otp" && !/^\d{6}$/.test(String(value)))
      return "Enter the six-digit receiving code.";
  }
  return "";
}
export function ActionForm({
  action,
  onClose,
  onDone,
}: {
  action: Action;
  onClose: () => void;
  onDone: () => void;
}) {
  const [values, setValues] = useState<Values>(action.initial || {}),
    [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [result, setResult] = useState<unknown>();
  const theme = useTheme();
  return (
    <Portal>
      <Modal
        visible
        onDismiss={() => {
          if (!busy) onClose();
        }}
        contentContainerStyle={{
          backgroundColor: theme.colors.surface,
          margin: 16,
          padding: 20,
          borderRadius: 16,
          maxHeight: "92%",
        }}
      >
        <ScrollView
          keyboardShouldPersistTaps="handled"
          contentContainerStyle={{ gap: 16 }}
        >
          <Text variant="headlineSmall">{action.title}</Text>
          {!!action.description && <Text>{action.description}</Text>}
          <ErrorBox error={error} />
          {result !== undefined ? (
            <>
              <Text>
                {typeof result === "object" && result && "queued" in result
                  ? "Saved on this device. Check Offline sync for server confirmation."
                  : typeof result === "object" &&
                      result &&
                      "code" in result &&
                      (action.path.endsWith("/code/") ||
                        action.path.endsWith("/handover-code/"))
                    ? `Receiving code: ${String(result.code)}`
                    : typeof result === "object" && result && "detail" in result
                      ? String(result.detail)
                      : "Saved successfully."}
              </Text>
              <Button
                onPress={() => {
                  onDone();
                  onClose();
                }}
              >
                Done
              </Button>
            </>
          ) : (
            <>
              <Fields
                fields={action.fields}
                values={values}
                onChange={setValues}
              />
              <Button
                mode="contained"
                loading={busy}
                disabled={busy}
                onPress={async () => {
                  const invalid = validate(action.fields, values);
                  if (invalid) {
                    setError(invalid);
                    return;
                  }
                  setBusy(true);
                  setError("");
                  try {
                    const data = action.transform
                      ? action.transform(values)
                      : Object.fromEntries(
                          Object.entries(values).filter(
                            ([, v]) => v !== undefined,
                          ),
                        );
                    const response = action.offline
                      ? await handover(action.path, data as Values)
                      : await api(
                          action.path,
                          action.method || "POST",
                          action.method === "DELETE" ? undefined : data,
                          { multipart: action.multipart },
                        );
                    setResult(response ?? {});
                    onDone();
                  } catch (e) {
                    setError(e instanceof Error ? e.message : String(e));
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                Confirm
              </Button>
              <Button disabled={busy} onPress={onClose}>
                Cancel
              </Button>
            </>
          )}
        </ScrollView>
      </Modal>
    </Portal>
  );
}
export function Details({ value }: { value: unknown }) {
  if (value === null || value === undefined) return null;
  if (typeof value !== "object") return <Text>{String(value)}</Text>;
  return (
    <View style={{ gap: 8 }}>
      {Object.entries(value)
        .filter(
          ([key]) =>
            !["recipient_access_token", "handover_otp", "password"].includes(
              key,
            ),
        )
        .map(([key, item]) => (
          <View key={key}>
            <Text variant="labelLarge">{label(key)}</Text>
            {typeof item === "object" ? (
              <Text>{JSON.stringify(item, null, 2)}</Text>
            ) : (
              <Text>{String(item ?? "—")}</Text>
            )}
            <Divider />
          </View>
        ))}
    </View>
  );
}
