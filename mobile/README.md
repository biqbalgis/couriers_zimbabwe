# Pano Logistics mobile

Expo / React Native application using the existing Django API and canonical accounts, shipments and assignments.

Run `npm install`, copy `.env.example` to `.env`, then run `npm start`. Use `npm run android` for an Android emulator. The default API URL uses Android emulator host address `10.0.2.2`. On a physical phone, configure `EXPO_PUBLIC_API_URL` with your computer's LAN address and expose Django on `0.0.0.0:8000` with an explicit allowed host. Use an HTTPS API in production. Environment values are public; never put secrets in them.

Implemented mobile workspaces for all eight roles, using canonical Django permissions and records.

| Use cases | Mobile implementation |
| --- | --- |
| UC01–02 | Credentials, session refresh/restore/logout, phone verification and guest tracking |
| UC03–04 | Partner applications, document uploads/resubmission, approval/rejection |
| UC05–07 | Customer and walk-in booking, route/stations, quote and parcel photo |
| UC08–10 | Trip scheduling/editing, assignment, task acceptance/decline and availability |
| UC11 | Receipt upload and authorized verification/rejection |
| UC12–14 | First-mile, station and carrier custody transitions, releasing-party codes and timeline |
| UC15–17 | Guest preferences/codes, collection/home delivery, proof photo and confirmed drawn signature |
| UC18–19 | Cancellation, exceptions and confirmed returns |
| UC20–21 | Payout leg allocation, approval/disbursement, earnings and statements |
| UC22–23 | Support conversations/status/helpdesk hours, notifications and saved addresses |
| UC24 | Durable native handover queue, persisted proof, stable idempotency keys, retry/discard and foreground/reconnect synchronization |
| UC25–26 | Reports/audits, finance exports, accounts/access, cities/stations/rates, pilot/network configuration |

Native maps use EPSG:4326 station coordinates and include external directions. Android standalone maps need `GOOGLE_MAPS_ANDROID_API_KEY` at build time, restricted to the selected package/signing certificate; iOS uses Apple Maps. See [Expo map setup](https://docs.expo.dev/versions/v57.0.0/sdk/map-view/). Store identifiers, signing and publishing require owner release configuration.

Offline capture is native-only; the browser preview submits online. Captures persist proof before sending and preserve exact bytes/idempotency keys on retry. Rejected codes remain visible; expired codes need a fresh capture rather than changing an existing idempotent request. Queue and cache are account/API scoped; guest responses are not cached. Logout retains pending captures for their owning account. Local proof/cache contains personal information: device protection and deliberate queue disposal remain operational requirements.

Notifications use existing backend records, not an invented push provider. Authenticated downloads serve receipt, application and proof review. Business rules remain server-side.

## Verification

Run `npm run typecheck`, `npm run lint`, `npm test`, `npx expo-doctor`, and `npx expo export --platform android --platform ios`.

`tests/acceptance.mjs` uses the existing frontend Playwright installation. It visits all role screens at a phone viewport and books a parcel through the UI. Artifacts are ignored under `tests/artifacts`. Run the app on port 8083 against isolated API port 8001. `tests/mobile_test_settings.py` puts test database/media under artifacts, separate from developer data. From backend, set PYTHONPATH to the mobile/tests directory, run migrations and seed_demo with `--settings=mobile_test_settings`, then runserver `127.0.0.1:8001` with those settings. Temporarily set `EXPO_PUBLIC_API_URL=http://localhost:8001/api` for that browser test and restore it afterward.

Native camera/signature capture, files surviving app termination, reconnect behavior, native sharing/maps, signed binaries and store delivery require device/release acceptance. Browser and JavaScript bundle success do not claim these passed.

Recorded local checks (2026-10-02): TypeScript and lint passed; seven offline queue tests passed; existing Django suite passed 26 tests; Expo Doctor passed 21/21 checks. Browser checks covered all eight role workspaces, photo booking, private guest tracking and saving home-delivery preferences. The final operations rerun passed 19 checks after avoiding a development hot-reload session reset. This is not end-to-end native acceptance of every custody/payment mutation.

## Operational extension — UC27–UC52

Open **Exceptions & parcel care** for cancellation/RTS, refunds/claims, delivery attempts, condition photos, policy, audit, performance and exports. Booking adds declared value, dimensions, saved-recipient reuse and editable map/GPS pins. Management adds station service details, volume-capacity trips, partner suspension/re-verification, delegated financial permissions and suspicious-receipt review. [Workflow rules and launch prerequisites](../docs/operational-completion.html).

Latest extension verification: 45 Django tests, 7 offline tests and 93 Playwright checks passed; TypeScript, lint, frontend build, Android/iOS/web exports and Expo Doctor (21/21) passed. OpenAPI generation has no warnings/errors and migration checks show no drift. Browser checks include all eight roles, bookings with dimensions/value/map coordinates and case-linked damage photos. Native exports are not installed-device acceptance.

Fees/liability require owner-reviewed policy. Optional address search requires the configured HTTPS gateway; insurance is unavailable and financial transfers remain external. The dependency audit reports 16 findings (4 high, 12 moderate); release needs SDK-compatible remediation. Existing use-case videos predate this extension.
