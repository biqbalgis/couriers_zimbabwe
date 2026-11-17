export type Role =
  | "customer"
  | "rider"
  | "carrier"
  | "station_operator"
  | "ops"
  | "finance"
  | "support"
  | "admin";
export interface Account {
  id: number;
  name: string;
  username: string;
  role: Role;
  phone: string;
  verified: boolean;
  operational_permissions?:string[];
}
export interface Entity {
  id: number;
  [key: string]: unknown;
}
export interface LocationResult{display_name:string;latitude:string;longitude:string}
export interface Page<T> {
  results: T[];
  count: number;
  next: string | null;
  previous: string | null;
}
export interface Station extends Entity {
  name: string;
  city: number;
  city_name: string;
  operator: number;
  address: string;
  payment_number: string;
  latitude: string | null;
  longitude: string | null;
}
export interface Event {
  id?: number;
  to_status: string;
  timestamp: string;
  accepted?: boolean;
  note?: string;
  released_by_name?: string;
  received_by_name?: string;
}
export interface Parcel extends Entity {
  code: string;
  sender: number;
  recipient_name: string;
  recipient_phone: string;
  price: string;
  weight_band: string;
  status: string;
  origin_station_detail: Station;
  destination_station_detail: Station;
  photo: string;
  pickup_address: string;
  notes: string;
  delivery_choice: string;
  delivery_address: string;
  recipient_access_token?: string;
  next_steps: string[];
  current_holder: number | null;
  payment: { status: string; receipt_photo: string | null } | null;
  events: Event[];
}
export interface PublicParcel {
  code: string;
  recipient_name: string;
  status: string;
  destination_station: Pick<
    Station,
    "id" | "name" | "address" | "latitude" | "longitude"
  >;
  events: Event[];
  delivery_choice: string;
  delivery_address: string;
}
export interface Task extends Entity {
  status: string;
  type: string;
  parcel_detail: Parcel;
  proof_photo: string;
  signature: string;
}
export interface Attachment {
  uri: string;
  name: string;
  type: string;
}
export type Value = string | number | boolean | Attachment | undefined;
export type Values = Record<string, Value>;
export interface Option {
  value: string;
  label: string;
}
export interface Field {
  name: string;
  label: string;
  type?:
    | "text"
    | "number"
    | "select"
    | "image"
    | "document"
    | "signature"
    | "multiline"
    | "password"
    | "date"
    | "json";
  required?: boolean;
  options?: Option[];
  resource?: string;
  help?: string;
}
export interface Action {
  title: string;
  path: string;
  method?: "POST" | "PATCH" | "PUT" | "DELETE";
  fields: Field[];
  initial?: Values;
  multipart?: boolean;
  offline?: boolean;
  description?: string;
  transform?: (values: Values) => unknown;
}
export const rows = <T>(data: T[] | Page<T>): T[] =>
  Array.isArray(data) ? data : data.results;
export const label = (value: unknown) => String(value ?? "").replace(/_/g, " ");
export const money = (value: unknown) => `USD ${Number(value || 0).toFixed(2)}`;
export const options = (items: string[]): Option[] =>
  items.map((value) => ({ value, label: label(value) }));
export const closed = ["delivered", "returned", "cancelled"];
export const has = (user: Account | null, ...roles: Role[]) =>
  !!user && roles.includes(user.role);
export const isAttachment = (value: unknown): value is Attachment =>
  !!value &&
  typeof value === "object" &&
  "uri" in value &&
  "name" in value &&
  "type" in value;
export const menus: { key: string; title: string; roles: Role[] }[] = [
  {key:"operations",title:"Exceptions & parcel care",roles:["customer","rider","carrier","station_operator","ops","finance","support","admin"]},
  {
    key: "dashboard",
    title: "Overview",
    roles: [
      "customer",
      "rider",
      "carrier",
      "station_operator",
      "ops",
      "finance",
      "support",
      "admin",
    ],
  },
  {
    key: "parcels",
    title: "Parcels",
    roles: [
      "customer",
      "rider",
      "carrier",
      "station_operator",
      "ops",
      "finance",
      "support",
      "admin",
    ],
  },
  {
    key: "book",
    title: "Book a parcel",
    roles: ["customer", "station_operator", "ops", "admin"],
  },
  { key: "tasks", title: "Assignments", roles: ["rider", "carrier"] },
  { key: "onboarding", title: "My application", roles: ["rider", "carrier"] },
  {
    key: "trips",
    title: "Carrier trips",
    roles: ["carrier", "station_operator", "ops", "admin"],
  },
  {
    key: "partners",
    title: "Delivery partners",
    roles: ["station_operator", "ops", "admin"],
  },
  {
    key: "stations",
    title: "Partner stations",
    roles: [
      "customer",
      "rider",
      "carrier",
      "station_operator",
      "ops",
      "finance",
      "support",
      "admin",
    ],
  },
  {
    key: "payments",
    title: "Payment review",
    roles: ["finance", "ops", "admin"],
  },
  { key: "payouts", title: "Settlement", roles: ["finance", "ops", "admin"] },
  {
    key: "earnings",
    title: "Earnings",
    roles: ["rider", "carrier", "station_operator"],
  },
  {
    key: "support",
    title: "Support",
    roles: [
      "customer",
      "rider",
      "carrier",
      "station_operator",
      "ops",
      "finance",
      "support",
      "admin",
    ],
  },
  { key: "addresses", title: "Saved addresses", roles: ["customer"] },
  {
    key: "notifications",
    title: "Notifications",
    roles: [
      "customer",
      "rider",
      "carrier",
      "station_operator",
      "ops",
      "finance",
      "support",
      "admin",
    ],
  },
  { key: "queue", title: "Offline sync", roles: ["rider", "carrier"] },
  {
    key: "reports",
    title: "Pilot reports",
    roles: ["ops", "finance", "admin"],
  },
  {
    key: "audit",
    title: "Custody trail",
    roles: ["station_operator", "ops", "admin"],
  },
  {
    key: "finance-audit",
    title: "Finance audit",
    roles: ["finance", "ops", "admin"],
  },
  { key: "rates", title: "Rates", roles: ["finance", "ops", "admin"] },
  { key: "users", title: "People & access", roles: ["admin"] },
  { key: "cities", title: "Cities", roles: ["ops", "admin"] },
  { key: "settings", title: "Pilot & integrations", roles: ["admin"] },
  {
    key: "profile",
    title: "My account",
    roles: [
      "customer",
      "rider",
      "carrier",
      "station_operator",
      "ops",
      "finance",
      "support",
      "admin",
    ],
  },
];
