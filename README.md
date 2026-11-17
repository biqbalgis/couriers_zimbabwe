# Pano Logistics marketplace MVP

An asset-light parcel network for partner stations, riders and inter-town carriers. The repository contains a Django REST API and one responsive React/MUI PWA with customer, recipient, field and operations route sets.

## Run locally

Prerequisites: Python 3.11+, Node 20+, and optionally PostgreSQL 16. SQLite is used when the `POSTGRES_*` variables are absent.

```powershell
cd backend
python -m venv venv
./venv/Scripts/python.exe -m pip install -r requirements.txt
./venv/Scripts/python.exe manage.py migrate
./venv/Scripts/python.exe manage.py seed_demo
./venv/Scripts/python.exe manage.py runserver
```

In another terminal:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Open `http://localhost:5173`. API docs are at `http://localhost:8000/api/docs/`. The `/roles` route redirects to the signed-in account workspace, or to login.

## Demo users and role portals

Run `python manage.py seed_demo` from `backend` before using these accounts. All newly created demo users use the password `Demo123!`. The local database has been migrated and populated. These are development accounts, with fictional contact/payment numbers.

| User type | Demo username | Password | Web portal |
| --- | --- | --- | --- |
| Customer | `demo_customer` | `Demo123!` | `/app` |
| Rider | `demo_rider` | `Demo123!` | `/field/tasks` |
| Carrier | `demo_carrier` | `Demo123!` | `/carrier/dashboard` |
| Station operator | `demo_station_operator` | `Demo123!` | `/station/dashboard` |
| Operations | `demo_ops` | `Demo123!` | `/ops/dashboard` |
| Finance | `demo_finance` | `Demo123!` | `/finance/dashboard` |
| Support | `demo_support` | `Demo123!` | `/support/dashboard` |
| Administrator | `demo_admin` | `Demo123!` | `/admin/dashboard` |

Sign in at `/login`, `/field/login`, or `/ops/login` using a username and password. All three use the real JWT API and redirect to the account's role portal. `demo_admin` can also sign in to Django admin at `http://localhost:8000/admin/`. Rider and carrier demo profiles are approved; the rider is available and assigned to a home station.

The active role workspaces require authentication and use live APIs. The UI includes grouped navigation, responsive tables/cards, global search, guided booking, per-step handovers, attachment previews, support conversations, financial review and offline field submissions. Phone sign-in is available for customers, riders and carriers; staff use credentials. No SMS or helpdesk provider is selected, so development delivery is explicitly distinguished from live delivery.

Additional pilot accounts are `demo_rider_mutare`, `demo_rider_chipinge`, `demo_station_chipinge` and `demo_recipient`. Newly created accounts use `Demo123!`. The active pilot route is Mutare–Chipinge in either direction.

The seed is idempotent: rerunning it does not duplicate demo workflows or overwrite existing passwords, rates, settings, or parcel history. To intentionally restore demo passwords, run `python manage.py seed_demo --reset-passwords`. Seeding is refused when `DJANGO_DEBUG=0`.

For PostgreSQL, start `docker compose up -d db`, copy `.env.example` values into your shell/environment, then migrate and seed that database. Django reads environment variables; it does not automatically load `.env`. Production must set a strong Django secret, restricted hosts/CORS origins, HTTPS and real SMS/helpdesk adapters. The seed run performed locally used SQLite; PostgreSQL is supported by the configuration but was not exercised in this run.

## Zimbabwe demo data

The seed creates 24 cities/towns across all ten provinces, 26 fictional partner stations, and 1,729 illustrative USD rate rules. Three bands (`0-2kg`, `2-5kg`, `5-10kg`) cover all ordered city pairs, including same-city transfers between different stations. An Avondale override demonstrates station-specific pricing. These are demo tariffs, not market quotes.

| Province | Seeded cities/towns |
| --- | --- |
| Harare | Harare, Chitungwiza |
| Bulawayo | Bulawayo |
| Manicaland | Mutare, Rusape, Chipinge |
| Midlands | Gweru, Kwekwe, Zvishavane, Shurugwi |
| Masvingo | Masvingo, Chiredzi |
| Mashonaland West | Chinhoyi, Kadoma, Chegutu, Kariba, Norton |
| Mashonaland Central | Bindura |
| Mashonaland East | Marondera |
| Matabeleland South | Gwanda, Beitbridge |
| Matabeleland North | Lupane, Victoria Falls, Hwange |

Station coordinates are approximate city-centre points in EPSG:4326 (latitude/longitude), not surveyed premises. Harare also has Avondale, CBD and Mbare demo stations. The seed creates one booked Mutare–Chipinge pilot parcel and preserves any existing historical fixtures. The reviewed local database also contains seven earlier demonstration journeys across booked, origin, transit, destination, delivered, exception and returned states. These are sample records rather than real operational history. Parcel codes are generated; read them from `/api/parcels/` after login. Request a fresh code for each handover through the authorized confirming-party flow. Ordinary parcel responses never expose OTPs. Seeded completed tasks are fixtures and do not include real proof images.

## Backend API workflows

The backend remains Django/DRF, using serializers for validation, service functions for workflows and Django migrations. Catalog GET endpoints are public; other resources require a JWT bearer token unless stated otherwise. Lists are paginated (`results`, 20 records by default; `page_size` up to 100). Management screens request 12 records, and `search` queries the full authorized dataset.

| Workflow | API |
| --- | --- |
| Login / refresh | `POST /api/auth/token/`, `POST /api/auth/token/refresh/` |
| Current profile | `GET/PATCH /api/users/me/` |
| User administration | `/api/users/` (admin writes; ops/admin reads; delete deactivates) |
| City/station catalog | `/api/cities/`, `/api/cities/{id}/stations/`, `/api/stations/` |
| Rates / quote | `/api/rates/`, `GET /api/rates/lookup/?origin_station={id}&destination_station={id}&weight_band=0-2kg` |
| Book / view parcel | `POST /api/parcels/`, `GET /api/parcels/{code}/` |
| Payment receipt | `POST /api/parcels/{code}/mark-paid/` (`method`, required image `receipt_photo`, multipart) |
| Delivery preference | `POST /api/parcels/{code}/delivery-choice/` (`choice`: station/home; `address` required for home) |
| Station custody handover | `POST /api/parcels/{code}/handover/` (`to_status`, `otp`, optional `note`) |
| Return exception | `POST /api/parcels/{code}/resolve-exception/` (`resolution`: return, `otp`, `note`) |
| Rider/carrier onboarding | `POST /api/riders/`, `POST /api/carriers/` (own role/profile only; documents via multipart) |
| Onboarding decision | `POST /api/onboarding/{id}/approve/` or `reject/` (`type`: rider/carrier) |
| Availability | `POST /api/riders/availability/` (`available`: boolean) |
| Matching | `GET /api/matching/unmatched/`, `POST /api/matching/{parcel_id}/assign/` (`rider` profile ID and/or scheduled `trip` ID) |
| Task response/completion | `/api/tasks/`, `POST /api/tasks/{id}/accept/`, `decline/`, `proof/`, `complete/` |
| Finance | `/api/payments/`, `POST /api/payments/{id}/verify/` (`status`: verified/rejected) |
| Payouts | `/api/payouts/`, `POST /api/payouts/run/` (`parcel`: database ID, `period`: YYYY-MM, first_mile_rider/last_mile_rider/carrier/station decimal amounts (legacy rider remains supported)) |
| CSV exports | `GET /api/payments/export/`, `GET /api/payouts/export/` |
| Earnings | `GET /api/earnings/` (own beneficiary payout lines) |
| Support | `/api/support/`, `POST /api/support/{id}/reply/` (`body`), `set-status/` (support/ops/admin) |
| Support parcel lookup | `GET /api/support/parcel-lookup/?code={code}` |
| Addresses | `/api/addresses/`, `POST /api/addresses/{id}/set-default/` (own records) |
| Notifications | `/api/notifications/`, `POST /api/notifications/{id}/read/` (own phone) |
| Settings | `/api/settings/network/` (admin; JSON `value`) |
| Audit / reporting | `/api/status-events/`, `/api/reports/summary/` |
| Recipient tracking | `GET /api/track/{recipientAccessToken}/` (public secret-link access) |

Assigning an approved worker creates offered tasks. Workers must accept before completing. Carrier collection records departure through the assigned task; destination station receipt completes that leg. Task handovers require `to_status` and `otp`; final home delivery also requires multipart `proof_photo` and `signature` images. Station operators see parcels belonging to their stations; field users see assigned work; customers see their own parcels. User role changes require admin access. Payments are priced server-side, verified receipts cannot be overwritten, and payout runs require delivery plus verified payment, balance leg allocations to the parcel price and reject duplicate runs. Exception resolution currently supports return; retry/collection preview options do not yet have backend transitions.

To check the backend and frontend:

```powershell
cd backend
python manage.py check
python manage.py test
python manage.py makemigrations --check --dry-run
python manage.py spectacular --file schema.yml
cd ../frontend
npm.cmd run build
node --test tests/offline.test.mjs
```

## Key routes

- Role-aware entry: `/roles`
- Customer PWA: `/app`; booking: `/app/book`
- Rider tasks: `/field/tasks`
- Carrier: `/carrier/dashboard`
- Station operator: `/station/dashboard`
- Guest recipient tracking: `/track/:recipientAccessToken`
- Operations: `/ops/dashboard`; matching: `/ops/matching-board`
- Finance: `/finance/dashboard`
- Support: `/support/dashboard`
- Administrator: `/admin/dashboard`
- Support companion lookup: `/support/parcel-lookup`

The task handover form queues offline submissions and files in account-scoped IndexedDB, then retries with a stable idempotency key. Fetched responses are cached per account for offline reading; the service worker caches only public catalogs. Queue failures remain visible for retry or discard. `IntegrationDelivery` is the durable SMS/helpdesk/archive outbox; run `python manage.py process_outbox --kind event_log` for archive replication. External providers and worker scheduling must be configured for a live pilot.

## Security and accounting boundaries

Custody events reject updates/deletes at model level. Parcel transitions are service-controlled, compare the handover OTP securely, and append rejected attempts as alert events. Public tracking hides internal notes, actor identity, sender accounts and financial details. Recipient secret links allow a delivery-specific receiving code to be requested; ordinary tracking responses do not expose an OTP. Treat the secret links as credentials. Payment and payout exports require ops/finance/admin roles. The payout service validates the split before creating all partner-leg lines and platform remainder transactionally; it records pending settlement and does not transmit money.

## Project documentation

The documents describe the implemented system and its current limits, dated 1 October 2026. HTML editions are self-contained, include printable styling and embed diagrams without external dependencies. Markdown editions are editable repository sources.

| Document | Readable edition | Source |
| --- | --- | --- |
| Use cases and actors | [Use case document](docs/use-cases.html) | [Markdown](docs/use-cases.md) |
| Operational workflows | [Workflows document](docs/workflows.html) | [Markdown](docs/workflows.md) |
| Tables relationships and ER | [Database document](docs/database.html) | [Markdown](docs/database.md) |

[Complete ER diagram source](docs/er-diagram.mmd) includes all reflected application/framework tables. Run `python docs/export_schema.py` to read current model metadata without modifying the database.

The backend remains Django/DRF. Current limits include external payments, unconfigured SMS/helpdesk providers, and no automatic refunds or dispatch matching. The workflow document records the exact custody and payment checks rather than assuming every proposal item is complete.

Account profile updates cannot change a verified phone directly; phone migration requires a separately verified administrative process to avoid exposing another person's shipment notifications.
## Operational completion (2 October 2026)

Both workspaces now include **Exceptions & parcel care**, cancellation/RTS/refund/claim workflows, delivery attempts, custody evidence, policy controls, partner lifecycle, separately assignable financial permissions, administrative audit, corrections, fraud flags, volume capacity, address pins/GPS, booking confirmations, performance and exports. [Coverage, setup and limits](docs/operational-completion.html).

Apply migrations **0006–0008** before restarting the API. Review fees/liability/limits in the administrator policy tab. Optional address search requires a configured HTTPS gateway. GPS requires a rebuilt native app/device permissions. Insurance and live refund transfers are not integrated. UC01–UC26 videos predate this extension and remain unchanged.

## Proposal completion (1 October 2026)

The [proposal coverage audit](docs/proposal-audit.html) records implemented requirements, deferred roadmap items and external launch blockers. Updates add rider-leg settlements, API-required booking photos and onboarding documents, hashed handover codes, SMS status synchronization, after-hours helpdesk delivery, and same-key offline retries after connection loss. Apply migration 0005 before restarting the API; existing handover codes expire and must be requested again. Historical payouts remain unchanged.

See the [pilot launch runbook](docs/launch-runbook.html) and [role training guide](docs/training.html). Run `python manage.py check_pilot` for a read-only deployment gate; `--development` skips infrastructure checks but still reports missing providers. A passing configuration check does not certify live provider delivery or pilot launch.
