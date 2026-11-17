import {stationCareFields,tripCareFields,addressCareFields,permissionField} from "./operationsFields";
import {partnerLifecycle,fraudReview} from "./screens/Operations";
import {
  has,
  options,
  closed,
  type Account,
  type Action,
  type Entity,
  type Field,
  type Parcel,
  type Values,
} from "./domain";
export const stationField: Field = {
  name: "home_station",
  label: "Home station",
  type: "select",
  resource: "/stations/?active=true",
  required: true,
};
export const carrierFields: Field[] = [
  ...tripCareFields,
  { name: "vehicle_type", label: "Vehicle type", required: true },
  { name: "licence_no", label: "Licence number", required: true },
  {
    name: "capacity_kg",
    label: "Vehicle capacity (kg)",
    type: "number",
    required: true,
  },
];
export const statusOptions: Record<string, string[]> = {
  parcels: [
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
  ],
  tasks: ["offered", "accepted", "completed", "declined"],
  partners: ["pending", "approved", "rejected"],
  payments: ["pending", "verified", "rejected"],
  payouts: ["pending", "approved", "paid"],
  support: ["open", "waiting_customer", "resolved", "closed"],
};
const city = (name: string, label: string): Field => ({
  name,
  label,
  type: "select",
  resource: "/cities/",
  required: true,
});
const userRoles = options([
  "customer",
  "rider",
  "carrier",
  "station_operator",
  "ops",
  "finance",
  "support",
  "admin",
]);
const rateFields: Field[] = [
  city("origin_city", "Origin city"),
  city("destination_city", "Destination city"),
  {
    name: "weight_band",
    label: "Weight band",
    type: "select",
    options: options(["0-2kg", "2-5kg", "5-10kg"]),
    required: true,
  },
  {
    name: "station_override",
    label: "Origin station override (optional)",
    type: "select",
    resource: "/stations/",
  },
  { name: "price", label: "Rate (USD)", type: "number", required: true },
];
const stationFields: Field[] = [
  ...stationCareFields,
  { name: "name", label: "Station name", required: true },
  city("city", "City"),
  {
    name: "operator",
    label: "Operator",
    type: "select",
    resource: "/users/?role=station_operator",
    required: true,
  },
  { name: "address", label: "Address", type: "multiline", required: true },
  { name: "payment_number", label: "Payment number", required: true },
  { name: "latitude", label: "Latitude (EPSG:4326)", type: "number" },
  { name: "longitude", label: "Longitude (EPSG:4326)", type: "number" },
  {
    name: "active",
    label: "Active",
    type: "select",
    options: options(["true", "false"]),
  },
];
const tripFields: Field[] = [
  ...tripCareFields,
  {
    name: "carrier",
    label: "Approved carrier",
    type: "select",
    resource: "/carriers/?status=approved",
    required: true,
  },
  city("origin_city", "Origin city"),
  city("destination_city", "Destination city"),
  {
    name: "departure_at",
    label: "Departure including timezone",
    type: "date",
    required: true,
    help: "Example: 2026-10-03T09:00:00+02:00 (Zimbabwe)",
  },
  {
    name: "capacity_kg",
    label: "Capacity (kg)",
    type: "number",
    required: true,
  },
  {
    name: "active",
    label: "Active",
    type: "select",
    options: options(["true", "false"]),
  },
];
const normalize = (values: Values) =>
  Object.fromEntries(
    Object.entries(values)
      .filter(([, v]) => v !== undefined && v !== "")
      .map(([key, v]) => [
        key,
        ["active", "is_active", "available"].includes(key)
          ? v === "true" || v === true
          : ["opening_hours","operational_permissions"].includes(key) ? JSON.parse(String(v)) : key === "departure_at"
            ? new Date(String(v)).toISOString()
            : v,
      ]),
  );
const initial = (row: Entity, fields: Field[]): Values =>
  Object.fromEntries(
    fields.map((field) => [
      field.name,
      field.name==="operational_permissions"?JSON.stringify(row[field.name]||[]):field.name==="opening_hours"?JSON.stringify(row[field.name]||{}):row[field.name] === null ? "" : String(row[field.name] ?? ""),
    ]),
  );
export function createAction(
  screen: string,
  user: Account,
): Action | undefined {
  if (screen === "support")
    return {
      title: "Open support request",
      path: "/support/",
      fields: [
        { name: "subject", label: "Subject", required: true },
        { name: "parcel_code", label: "Related parcel code (optional)" },
        { name: "body", label: "Message", type: "multiline", required: true },
      ],
      transform: (v) => ({
        subject: v.subject,
        parcel_code: v.parcel_code || "",
        messages: [{ body: v.body }],
      }),
    };
  if (screen === "addresses" && user.role === "customer")
    return {
      title: "Save address",
      path: "/addresses/",
      fields: [
        ...addressCareFields,
        { name: "label", label: "Address label", required: true },
        { name: "contact_name", label: "Contact name" },
        { name: "phone", label: "Phone (+263…) " },
        city("city", "City"),
        {
          name: "address",
          label: "Address and directions",
          type: "multiline",
          required: true,
        },
      ],
    };
  if (screen === "trips" && has(user, "carrier", "ops", "admin"))
    return {
      title: "Schedule trip",
      path: "/trips/",
      fields: tripFields,
      initial: { active: "true" },
      transform: normalize,
    };
  if (screen === "payouts" && has(user, "finance", "ops", "admin"))
    return {
      title: "Allocate settlement",
      description:
        "Use a delivered parcel with verified payment. Zero means an unused leg. This records allocations; payments happen externally.",
      path: "/payouts/run/",
      initial: {
        period: new Date().toISOString().slice(0, 7),
        first_mile_rider: "0",
        last_mile_rider: "0",
        carrier: "0",
        station: "0",
      },
      fields: [
        {
          name: "parcel",
          label: "Delivered parcel",
          type: "select",
          resource: "/parcels/?status=delivered",
          required: true,
        },
        { name: "period", label: "Period (YYYY-MM)", required: true },
        ...["first_mile_rider", "last_mile_rider", "carrier", "station"].map(
          (name) => ({
            name,
            label: name.replace(/_/g, " ") + " allocation (USD)",
            type: "number" as const,
            required: true,
          }),
        ),
      ],
    };
  if (screen === "users" && user.role === "admin")
    return {
      title: "Create account",
      path: "/users/",
      transform:normalize,
      fields: [
        permissionField,
        { name: "username", label: "Username", required: true },
        { name: "name", label: "Full name", required: true },
        { name: "phone", label: "Phone (+263…) ", required: true },
        {
          name: "role",
          label: "Role",
          type: "select",
          options: userRoles,
          required: true,
        },
        {
          name: "password",
          label: "Password (8+ characters)",
          type: "password",
          required: true,
        },
      ],
    };
  if (screen === "rates" && has(user, "ops", "finance", "admin"))
    return {
      title: "Add rate",
      path: "/rates/",
      fields: rateFields,
      transform: normalize,
    };
  if (screen === "stations" && has(user, "ops", "admin"))
    return {
      title: "Add station",
      path: "/stations/",
      fields: stationFields,
      initial: { active: "true" },
      transform: normalize,
    };
  if (screen === "cities" && has(user, "ops", "admin"))
    return {
      title: "Add city",
      path: "/cities/",
      fields: [
        { name: "name", label: "City name", required: true },
        { name: "province", label: "Province", required: true },
      ],
    };
}
export function rowActions(
  screen: string,
  row: Entity,
  user: Account,
  partner = "riders",
): Action[] {
  const actions: Action[] = [];
  if(screen==="partners"&&has(user,"ops","admin"))actions.push(...partnerLifecycle(row,partner));
  if(screen==="payments"&&has(user,"ops","finance","admin")&&Array.isArray(row.fraud_flags)&&row.fraud_flags.length)actions.push(fraudReview(row));
  const path = `/${screen}/${row.id}/`;
  if (screen === "partners" && has(user, "ops", "admin"))
    for (const decision of ["approve", "reject"])
      actions.push({
        title:
          decision === "approve"
            ? "Approve application"
            : "Request application changes",
        path: `/onboarding/${row.id}/${decision}/`,
        initial: { type: partner === "riders" ? "rider" : "carrier" },
        fields: [
          {
            name: "reason",
            label: "Review note",
            type: "multiline",
            required: decision === "reject",
          },
        ],
      });
  if (
    screen === "payments" &&
    row.status === "pending" &&
    has(user, "ops", "finance", "admin")
  )
    for (const status of ["verified", "rejected"])
      actions.push({
        title: status === "verified" ? "Verify receipt" : "Reject receipt",
        path: path + "verify/",
        initial: { status },
        fields: [],
        description: `Receipt amount: USD ${row.amount}. Verify the uploaded evidence before accepting.`,
      });
  if (screen === "payouts" && has(user, "ops", "finance", "admin")) {
    if (row.status === "pending")
      actions.push({
        title: "Approve allocation",
        path: path + "settle/",
        initial: { action: "approve" },
        fields: [],
      });
    if (row.status === "approved")
      actions.push({
        title: "Record external disbursement",
        path: path + "settle/",
        initial: { action: "disburse" },
        fields: [
          {
            name: "reference",
            label: "External payment reference",
            required: true,
          },
        ],
        description: "Record this only after making the external payment.",
      });
  }
  if (screen === "support") {
    if (row.status !== "closed")
      actions.push({
        title: "Reply to support",
        path: path + "reply/",
        fields: [
          { name: "body", label: "Message", type: "multiline", required: true },
        ],
      });
    if (has(user, "support", "ops", "admin"))
      actions.push({
        title: "Change ticket status",
        path: path + "set-status/",
        fields: [
          {
            name: "status",
            label: "Status",
            type: "select",
            required: true,
            options: options(statusOptions.support),
          },
        ],
        initial: { status: String(row.status) },
      });
  }
  if (screen === "addresses" && user.role === "customer") {
    if (!row.is_default)
      actions.push({
        title: "Make default address",
        path: path + "set-default/",
        fields: [],
      });
    const creation = createAction(screen, user)!;
    actions.push(
      {
        ...creation,
        title: "Edit address",
        path,
        method: "PATCH",
        initial: initial(row, creation.fields),
      },
      {
        title: "Remove address",
        path,
        method: "DELETE",
        fields: [],
        description: "Remove this saved address?",
      },
    );
  }
  if (screen === "notifications" && !row.read_at)
    actions.push({
      title: "Mark notification read",
      path: path + "read/",
      fields: [],
    });
  if (screen === "users" && user.role === "admin") {
    const fields: Field[] = [
      permissionField,
      { name: "name", label: "Full name", required: true },
      {
        name: "role",
        label: "Role",
        type: "select",
        options: userRoles,
        required: true,
      },
      {
        name: "is_active",
        label: "Account access",
        type: "select",
        options: options(["true", "false"]),
        required: true,
      },
    ];
    actions.push({
      title: "Edit account access",
      path,
      method: "PATCH",
      fields,
      initial: initial(row, fields),
      transform: normalize,
    });
  }
  if (screen === "rates" && has(user, "ops", "finance", "admin"))
    actions.push({
      title: "Edit rate",
      path,
      method: "PATCH",
      fields: rateFields,
      initial: initial(row, rateFields),
      transform: normalize,
    });
  if (screen === "stations" && has(user, "ops", "admin"))
    actions.push({
      title: "Edit station",
      path,
      method: "PATCH",
      fields: stationFields,
      initial: initial(row, stationFields),
      transform: normalize,
    });
  if (screen === "cities" && has(user, "ops", "admin")) {
    const creation = createAction(screen, user)!;
    actions.push({
      ...creation,
      title: "Edit city",
      path,
      method: "PATCH",
      initial: initial(row, creation.fields),
    });
  }
  if (screen === "trips" && has(user, "carrier", "ops", "admin"))
    actions.push({
      title: "Edit trip",
      path,
      method: "PATCH",
      fields: tripFields,
      initial: initial(row, tripFields),
      transform: normalize,
    });
  if (screen === "pilot-routes" && user.role === "admin") {
    const fields: Field[] = [
      { name: "name", label: "Route name", required: true },
      city("origin_city", "Origin city"),
      city("destination_city", "Destination city"),
      {
        name: "active",
        label: "Active",
        type: "select",
        options: options(["true", "false"]),
        required: true,
      },
    ];
    actions.push({
      title: "Edit pilot route",
      path,
      method: "PATCH",
      fields,
      initial: initial(row, fields),
      transform: normalize,
    });
  }
  return actions;
}
export function parcelActions(p: Parcel, user: Account): Action[] {
  const list: Action[] = [];
  const path = `/parcels/${p.code}/`;
  const owner = p.sender === user.id,
    station = has(user, "station_operator", "ops", "admin"),
    field = has(user, "rider", "carrier");
  if (p.next_steps?.length)
    list.push({
      title: "Request handover code",
      path: path + "handover-code/",
      initial: { to_status: p.next_steps[0] },
      fields: [
        {
          name: "to_status",
          label: "Next handover",
          type: "select",
          options: options(p.next_steps),
          required: true,
        },
      ],
      description:
        "The releasing party receives the code and shares it when custody changes.",
    });
  if (station && p.next_steps?.length)
    list.push({
      title: "Confirm station handover",
      path: path + "handover/",
      multipart:true,
      initial: { to_status: p.next_steps[0] },
      fields: [
        {
          name: "to_status",
          label: "Next handover",
          type: "select",
          options: options(p.next_steps),
          required: true,
        },
        { name: "otp", label: "Releasing party’s code", required: true },
        { name: "note", label: "Note" },
        {name:"photo",label:"Handover condition photo (optional)",type:"image"},
      ],
    });
  if (p.payment?.status !== "verified" && (owner || station || field))
    list.push({
      title: "Upload payment receipt",
      path: path + "mark-paid/",
      multipart: true,
      initial: { method: "mobile_money" },
      fields: [
        {
          name: "method",
          label: "Payment method",
          type: "select",
          options: options(["mobile_money", "cash", "bank_transfer"]),
          required: true,
        },
        { name: "transaction_reference", label: "Transaction reference" },
        {
          name: "receipt_photo",
          label: "Receipt image",
          type: "image",
          required: true,
        },
      ],
    });
  if (station && !closed.includes(p.status) && p.status !== "exception")
    list.push({
      title: "Assign rider / trip",
      path: `/matching/${p.id}/assign/`,
      fields: [
        {
          name: "trip",
          label: "Future carrier trip",
          type: "select",
          resource: "/trips/?active=true",
        },
        {
          name: "rider",
          label: "Available rider",
          type: "select",
          resource: "/riders/?status=approved&available=true",
        },
      ],
      transform: normalize,
    });
  if (owner && !closed.includes(p.status) && p.status !== "out_for_delivery")
    list.push({
      title: "Change delivery preference",
      path: path + "delivery-choice/",
      initial: { choice: p.delivery_choice, address: p.delivery_address },
      fields: [
        {
          name: "choice",
          label: "Receiving method",
          type: "select",
          options: options(["station", "home"]),
          required: true,
        },
        { name: "address", label: "Home address", type: "multiline" },
      ],
      transform: (v) => {
        if (v.choice === "home" && !String(v.address || "").trim())
          throw new Error("Home delivery needs an address.");
        return v;
      },
    });
  if (
    (owner || has(user, "ops", "admin")) &&
    ["booked", "at_origin_station"].includes(p.status) &&
    p.payment?.status !== "verified"
  )
    list.push({
      title: "Cancel booking",
      path: path + "cancel/",
      fields: [
        {
          name: "note",
          label: "Cancellation reason",
          type: "multiline",
          required: true,
        },
      ],
    });
  if (
    (station || field || p.current_holder === user.id) &&
    !closed.includes(p.status) &&
    p.status !== "exception"
  )
    list.push({
      title: "Record exception",
      path: path + "exception/",
      fields: [
        {
          name: "note",
          label: "What happened?",
          type: "multiline",
          required: true,
        },
      ],
    });
  return list;
}
