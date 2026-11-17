# Parcel exceptions and operational completion

Implemented 2 October 2026 in the canonical Django API, React/MUI workspace and React Native/Expo application.

Open **Exceptions & parcel care** in either application. Customers and field workers see only their permitted shipments; operations, finance and support retain their existing role scopes. Tabs provide an exception inbox, cases, delivery attempts, custody evidence, administrative audit, performance, exports and policy.

## Feature coverage

| Use case | Feature | Implemented behavior |
| --- | --- | --- |
| UC27 | Cancellation | Sender request; automatic cancellation only for unassigned sender-held bookings; operations approval for assigned/collected parcels; stage-specific snapshotted fees; declines outstanding work and releases cancelled trip reservations. |
| UC28 | Return to sender | Approved case; destination collection, reverse-route trip, origin receipt and sender-confirmed collection. Origin-only returns skip inter-town movement. Every handover needs an independent expiring code and condition photo. |
| UC29 | Failed delivery | Accepted last-mile rider records unavailable recipient, incorrect address, refusal or unreachable recipient; chooses contact, scheduled retry or return review. Exhausted attempts stop forward delivery. |
| UC30 | Refund management | Request, independent approval, amount/fee checks, external payout reconciliation when needed, unique external payment reference and append-only audit. Original payment/payout records are preserved. |
| UC31 | Loss/damage claims | Claim, case-linked private photo evidence, independent review, cumulative declared-value/liability ceiling, approval and external compensation reference. |
| UC32 | Liability / insurance | Declared value and booking-time policy snapshot. Compensation requires reviewed terms and configured liability. Insurance is explicitly unavailable; the API rejects unintegrated insurance advertising. |
| UC33 | Prohibited/restricted items | Server-enforced normalized categories and configurable prohibited/restricted lists displayed during booking. Restricted categories require operations handling outside standard booking. |
| UC34 | Dimensions and size limits | Complete positive length/width/height, optional mandatory dimensions, maximum dimensions and volume. Existing dimension-less bookings remain usable on weight-only trips. |
| UC35 | Carrier capacity | Transaction-locked weight/volume reservations, including approved/in-progress returns. Volume-limited trips reject parcels without dimensions. |
| UC36 | Carrier schedules | Origin, destination, future departure, vehicle registration, weight and volume capacity; route, worker eligibility and vehicle limits are checked. |
| UC37 | Addresses and locations | Full addresses/instructions, saved-address reuse, interactive map pins and permission-based GPS. Coordinates are EPSG:4326. Configurable authenticated address search offers suggestions, not a delivery guarantee. |
| UC38 | Attempt history | API records include rider, failure reason, time, next action, retry time and optional coordinates. Existing attempts cannot be overwritten through the API. |
| UC39 | Custody photos | Private evidence attaches to parcel, claim or accepted custody event. Station handovers accept a photo; returns require one. Booking/delivery proof remain canonical. |
| UC40 | Notifications | Administrator-configured event triggers use the existing durable outbox for custody, booking, failed delivery and case changes. This does not configure a live SMS provider. |
| UC41 | User management | Create, update/deactivate accounts and assign existing roles. Additional refund-approval and refund-payment permissions are separately assignable to eligible staff and audited. |
| UC42 | Station management | Contact, address, coordinates, opening-hours information, active/service status and holding capacity. Closed/full stations reject new bookings. |
| UC43 | Partner lifecycle | Existing application rejection; reasoned suspension, re-verification or reactivation. Accepted work must be reassigned first. Expired/suspended/unverified workers cannot accept or start work. |
| UC44 | Administrative audit | Before/after user, permission, station, rate, partner and trip changes; operational decisions, payment reviews, policy, corrections and exports. Passwords/OTPs/arbitrary settings values are excluded. |
| UC45 | Operational corrections | Reasoned recipient/address corrections and unassigned station corrections preserving the quote. Non-return exceptions can restore their recorded previous custody state with a new event; arbitrary status/holder jumps are prohibited. |
| UC46 | Duplicate/fraud controls | Recent booking fingerprints, receipt SHA-256 reuse and transaction-reference reuse. Suspicious evidence blocks verification until reasoned review. These are heuristics, not a fraud guarantee. |
| UC47 | Customer history | Existing paginated/filterable parcel history covers active/closed bookings and payments; cases and receipts are reachable from each parcel. |
| UC48 | Saved recipients/addresses | Private records include recipient contact, coordinates and instructions and can prefill repeat bookings. |
| UC49 | Digital receipt | Download/share authenticated booking/payment confirmation; not a tax invoice and never represents pending payment as verified. |
| UC50 | Performance | Station shipment/delivery/exception/cancellation counts, current carrier shipment/delivery/exception counts, rider failed attempts and existing pilot quality reports. Operational counts, not historical assignment or SLA certification. |
| UC51 | Operational exports | Authenticated shipment, customer, station, carrier, attempt, exception and audit CSV exports. Formula-like text is neutralized. |
| UC52 | Exception inbox | Scoped parcels with open cases, exception state, unresolved payment/handover problems or stale progress, linked to the original journey. Resolved handover failures and closed journeys without open cases leave the inbox. |

## Cancellation and physical returns

1. Unassigned sender-held bookings can close immediately. Paid bookings create refund **requests**, not transfers.
2. Assigned bookings need operations approval and use the assignment-stage fee.
3. After pickup, cancellation stops outstanding forward tasks and creates an approved return. The parcel remains in exception custody until physical return completion.
4. Origin-held parcels go to sender collection; first-mile custody can return to the origin station without inventing a reverse trip.
5. Destination-station parcels start from reverse-carrier collection. Failed home-delivery parcels can first be collected by a destination rider or received by the destination station.
6. Return codes are hashed, expire after 15 minutes, cannot reset while active, allow at most five incorrect attempts and never appear in case lists. Intermediate codes come from the releasing party; final confirmation comes from the sender.

The system records fees; it does not charge a bank account. Refund approval deducts applicable approved fees and earlier reserved refunds. If partner payouts were approved/paid, finance must reconcile externally and supply a reference rather than rewrite payout history.

## Policy and permissions

Administrator: **Exceptions & parcel care → Policy → Edit policy**. The JSON form uses a dedicated DRF validator. Configure reviewed terms, fees, liability, size limits, restricted/prohibited categories, maximum attempts, stale-progress hours and notification events. Bookings retain their policy snapshot; current rule changes do not silently change past charges or compensation limits.

Initial fees/liability are zero, dimensions optional and terms unreviewed. These are explicit development placeholders, **not approved business or insurance terms**. An owner must set and review policy before launch.

Existing role permissions remain. Finance/administrators can review and record financial cases. Administrators can additionally grant eligible operations/support staff:

- approve_refund: approve/reject refund and compensation cases.
- record_refund_payment: record already-approved external refund/compensation payments.

Use the account's delegated-permission JSON field: ["approve_refund"], ["record_refund_payment"], both, or []. One permission does not grant the other, broaden unrelated access, or permit customers to approve their own claims.

Operational cases, attempts, evidence, audit, payment, payout, parcel and task records are read-only in Django admin; mutate them through service-controlled application workflows.

## Locations and external prerequisites

Web maps use OpenLayers: display EPSG:3857 coordinates convert to stored EPSG:4326 pins. Native maps use React Native Maps. Rebuild native apps after the Expo Location permission/plugin change. Android map credentials and device GPS permission behavior require deployment/device verification.

Address search is off by default. To enable an operator-owned/contracted **Nominatim-compatible** HTTPS gateway, configure GEOCODING_URL, optionally GEOCODING_TOKEN and an identifying GEOCODING_USER_AGENT. Searches are authenticated and explicit, with Zimbabwe filtering, bounded responses/timeouts and no redirects. No public geocoder/subscription/insurance policy is silently selected. Suggestions are not postal validation; confirm ambiguous addresses and access instructions with the recipient.

Payments, refunds and compensation remain external. SMS/helpdesk delivery still requires configured providers and the outbox worker. Insurance is not integrated or advertised.

## Deployment and verification

Apply migrations **0006–0008** before restarting the API. They add metadata, operational tables/indexes, a unique case payment reference and financial permissions. Existing payment/payout amounts are not rewritten.

Backend checks:

    python manage.py migrate
    python manage.py check
    python manage.py test marketplace
    python manage.py spectacular --file schema.yml

Frontend/mobile checks, run from their respective folders:

    npm.cmd run build
    npm.cmd run typecheck
    npm.cmd run lint
    npm.cmd test
    npx.cmd expo-doctor

Browser acceptance uses mobile/tests/mobile_test_settings.py and an isolated SQLite database, never the developer database. The operations-acceptance.mjs script tests all role tabs in both previews, then submits bookings with dimensions/value/map coordinates and damage claims. Native exports prove bundling, not installation, GPS accuracy, live provider delivery or production deployment.

Prior UC01–UC26 videos remain unchanged and predate these additional workflows.

Dependency audit currently reports 16 mobile dependency findings (4 high, 12 moderate), primarily in the Expo tooling/router tree. Resolve with SDK-compatible patches before release; do not use the suggested forced downgrade to Expo 44.
