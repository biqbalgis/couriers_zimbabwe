# Pano Logistics Use Case Document

Version 1.1 · 1 October 2026 · Mutare–Chipinge pilot

## Purpose and scope

This document describes how senders, recipients, delivery partners and staff use the implemented Pano Logistics application. It is intended for product owners, pilot operators, developers and acceptance testers. The application uses React and MUI with a Django REST Framework backend. PostgreSQL is supported through configuration; the reviewed local database uses SQLite.

The pilot route is Mutare–Chipinge in either direction. The network uses partner stations, local riders and inter-town carriers. Payments and disbursements happen outside the application; the system records receipts, verification and settlement references. No SMS or helpdesk provider has been selected. Configurable server adapters and a durable outbox exist, but this does not establish live provider delivery.

## Actors and responsibilities

| Actor | Responsibilities | Record scope |
| --- | --- | --- |
| Customer | Book parcels, upload receipts, choose delivery preferences, save addresses and request support | Parcels sent by the account and its own addresses |
| Guest recipient | Track a shipment, choose station or home delivery and obtain a receiving code | The shipment identified by a secret recipient link |
| Rider | Apply for approval, set availability, accept local assignments, collect and deliver parcels | Assigned tasks and related shipments |
| Carrier | Apply with vehicle details, schedule trips and accept inter-town assignments | Own trips, assigned tasks and related shipments |
| Station operator | Book walk-in shipments, receive custody, hand over station collections and inspect station shipments | Shipments whose origin or destination is an operated station |
| Operations | Review partners, assign transport, review receipts, handle exceptions and inspect reports | Operational shipment records across the network |
| Finance | Review receipts, allocate and approve settlement, record disbursement references and export records | Network financial records and reporting |
| Support | View network parcels, manage support conversations and change ticket status | Network support records |
| Administrator | Manage accounts, reference data, pilot configuration and operational workflows | Administrative and operational records |

The server is the authorization authority. Hiding a navigation item does not grant or remove an API permission. Ordinary staff privileges are controlled by the role field; Django superuser access is an additional administrative override. A station operator can book only from a station operated by that account.

## Use case catalog

| ID | Use case | Primary actor | Related workflow |
| --- | --- | --- | --- |
| UC01 | Sign in with credentials | All account holders | WF01 |
| UC02 | Verify a phone and create or access an account | Customer, rider, carrier | WF01 |
| UC03 | Submit or resubmit a partner application | Rider, carrier | WF02 |
| UC04 | Review a partner application | Operations, administrator | WF02 |
| UC05 | Book a parcel | Customer | WF03 |
| UC06 | Book for a walk-in sender | Station operator, operations, administrator | WF03 |
| UC07 | Obtain a route and weight quote | Sender or booking staff | WF03 |
| UC08 | Schedule a carrier trip | Carrier, operations, administrator | WF04 |
| UC09 | Assign a rider or trip | Station operator, operations, administrator | WF04 |
| UC10 | Accept or decline an assignment | Assigned rider or carrier | WF04 |
| UC11 | Submit and review payment evidence | Sender, assigned worker, staff | WF05 |
| UC12 | Collect a first-mile parcel | Assigned rider | WF06 |
| UC13 | Receive a parcel at origin | Origin station operator | WF06 |
| UC14 | Transport a parcel between towns | Carrier and destination operator | WF06 |
| UC15 | Choose a receiving method | Sender or guest recipient | WF07 |
| UC16 | Complete station collection | Recipient and destination operator | WF07 |
| UC17 | Complete home delivery | Recipient and assigned rider | WF07 |
| UC18 | Cancel before dispatch | Sender, operations, administrator | WF08 |
| UC19 | Record an exception and return a parcel | Custodian, station staff, operations | WF08 |
| UC20 | Allocate and settle a payout | Finance, operations, administrator | WF09 |
| UC21 | Review earnings and statements | Rider, carrier, station operator | WF09 |
| UC22 | Open and manage a support conversation | Account holder and support staff | WF10 |
| UC23 | Read notifications and save addresses | Account holder or customer | WF10 |
| UC24 | Synchronize an offline handover | Assigned field worker | WF11 |
| UC25 | Review performance and custody records | Authorized staff | WF12 |
| UC26 | Manage users and network configuration | Administrator and authorized reference-data staff | WF12 |

## Account and partner use cases

### UC01 Sign in with credentials

Precondition: an active account exists. The user enters a username and password. The API issues access and refresh tokens, and the frontend obtains the authoritative account profile before opening the role workspace. Incorrect credentials produce an error. A session retrieval failure offers retry; an authentication failure redirects to login. Outcome: the account can use its permitted workspace. Access tokens currently last eight hours; automatic frontend refresh is not implemented.

### UC02 Verify a phone

The user supplies a full name, a Zimbabwe phone number in +263 followed by nine digits, and customer, rider or carrier as the intended role. The system creates a hashed challenge valid for ten minutes and queues the code. Verification allows at most five attempts, consumes the challenge on success, and returns account tokens. New accounts are created with an unusable password and verified phone status. Existing staff accounts cannot sign in through this route. A one-minute repeat-request check and API throttling restrict repeated requests. In local development, the sign-in page explicitly displays the development code and states that no SMS was sent.

### UC03 Submit or resubmit a partner application

A rider chooses a home station; a carrier provides vehicle type, licence number and capacity. The UI requires an identity or combined operating document. The API creates the profile in pending status. Owners may resubmit, which resets status to pending and clears the review note. An approved profile is required before matching. Duplicate profile creation and an application for a different account role are rejected. The API requires an upload for creation and rejects approval without a document. Existing approved seed fixtures are illustrative, not proof of real vetting.

### UC04 Review a partner application

Operations or an administrator inspects the application and privately served attachment, then approves or rejects it with a review note. A rejected applicant sees the note and can resubmit. Outcome: approved partners become eligible for assignments, subject to availability, town, vehicle and trip checks. This is a manual review process; identity verification is not delegated to an external service.

## Booking and assignment use cases

### UC05 Book a parcel

The customer completes four steps: route, people, parcel and review. Origin and destination are different active stations on an active pilot pair. Recipient details, a supported weight band and a parcel photo are supplied; pickup address and handling instructions are optional. The server calculates the price from the applicable station override or default rate. It creates a six-digit shipment code, a secret recipient token, a booking event and queued notifications. Outcome: a booked shipment with payment still to be recorded. Both UI and API require a valid parcel photo; the API also validates the weight band and Zimbabwe recipient phone.

### UC06 Book for a walk-in sender

Authorized booking staff supplies the sender name and phone, then follows UC05. The backend resolves the phone to an existing account or creates a customer account with an unusable password. The shipment keeps sender separately from booked_by so ownership is not confused with the staff member who entered it. Station operators are limited to their own origin station.

### UC07 Obtain a quote

The user selects origin station, destination station and 0–2 kg, 2–5 kg or 5–10 kg. The server uses the city pair and weight band, preferring an origin-station override. The booking UI shows the price in USD before confirmation. Missing tariffs prevent booking. Stored parcel prices are snapshots and are not recalculated when a tariff later changes.

### UC08 Schedule a carrier trip

An approved carrier or authorized staff selects the route, a future departure and available capacity within the vehicle capacity. The trip appears with available capacity. Carriers manage their own trips. Trips with assigned parcels cannot be edited through the current validation rules. Outcome: an active departure that operations can select for matching.

### UC09 Assign transport

Authorized station staff or operations selects an active future trip and/or an approved available rider. The server verifies route direction, capacity and the rider's town. Weight bands reserve their upper bounds of 2, 5 or 10 kg. Assigning creates offered tasks; conflicting active offers for the same leg are declined. Outcome: designated workers receive tasks. Matching remains manual.

### UC10 Respond to an assignment

Only the assigned worker can accept or decline an offered task. An accepted task is required before collecting a parcel for pickup, carrier departure or home delivery. Already answered offers cannot be answered again. Outcome: the task becomes accepted or declined; accepting does not itself transfer custody.

## Payment and custody use cases

### UC11 Record and review a receipt

The sender, authorized station/operations staff or a worker with an accepted assignment uploads a receipt image and selects a payment method. The amount comes from the booked price. Finance, operations or an administrator reviews the receipt and marks it verified or rejected. A verified record cannot be replaced. Dispatch and home-delivery departure require a verified payment. Outcome: evidence and the reviewer identity are retained; no charge is executed by the app.

### UC12 Collect a first-mile parcel

An assigned rider accepts the pickup task and requests the next handover code. The independent releasing party receives the code. On collection, the rider submits picked_up and the code. The server requires a pickup address, a matching accepted task and the correct receiving worker. Outcome: rider custody is recorded. Origin-station receipt later completes the pickup task.

### UC13 Receive a parcel at origin

The origin operator confirms at_origin_station using the sender's or current rider's code. The operator must be the designated receiving custodian and must differ from the releasing account. The server records both parties and advances the shipment. A walk-in drop-off can move directly from booked to origin receipt. Payment verification is needed before subsequent carrier departure.

### UC14 Transport between towns

The carrier accepts its task, obtains the origin operator's code and confirms in_transit. On arrival, the destination operator obtains the carrier's code and confirms at_destination_station. The receiving account, sequence, code validity and accepted task are checked. Outcome: the carrier task completes when the destination station confirms receipt.

### UC15 Select the receiving method

The sender uses the authenticated shipment page or the recipient opens the secret tracking link. The user chooses station collection or home delivery; home delivery requires an address. The preference is locked once out_for_delivery or a closed state is reached. Public tracking shows only recipient-safe shipment information. Possession of the link authorizes access to that shipment.

### UC16 Complete station collection

At the destination station, the recipient generates a receiving code using the secret link. The destination operator confirms delivered. The server requires station collection preference and the correct operator. Outcome: a recipient-confirmed delivery event is recorded and current_holder becomes null, representing release from network custody.

### UC17 Complete home delivery

A destination-town rider accepts a last-mile task, collects from the station using its releasing-party code and confirms out_for_delivery. At the recipient, the rider submits the recipient's receiving code, a delivery photo and a confirmed signature image. The server requires the assigned rider and both images. Outcome: delivered status and completed last-mile task, with private proof files.

## Exceptions and finance use cases

### UC18 Cancel before dispatch

The sender, operations or administrator supplies a reason while the parcel is booked or at_origin_station and has no verified payment. The server appends a cancellation event, sets cancelled and declines active tasks. A paid or already transported parcel requires support handling. No automated refund workflow exists.

### UC19 Record an exception and return

A permitted custodian or station/operations user records the issue. The server retains an exception event and status. The supported next custody state is returned, confirmed by a station operator using a fresh code issued to the sender. Retrying delivery and automatic exception recovery are not implemented as state transitions.

### UC20 Allocate and settle a payout

Finance, operations or administrator selects a delivered parcel with a verified payment and enters first-mile rider, last-mile rider, carrier and origin-station allocations for a period. The remaining price becomes the platform allocation. Negative or over-budget amounts and repeated payout runs are rejected. Each nonzero partner allocation needs a beneficiary. Lines progress from pending to approved to paid; the last step records an external reference after payment outside the app. Outcome: balanced allocations and finance audit events for the run, approval, disbursement and receipt review. Legacy single-rider requests remain supported only when they do not ambiguously combine two different completed riders.

### UC21 Review earnings

A partner opens its own beneficiary-scoped allocations and downloadable statements. The overview distinguishes allocated amounts from the recorded status of payment. It does not connect to a bank or wallet. First-mile and last-mile rider allocations are separately recorded using the completed task's worker, so replacing the active rider does not lose the pickup beneficiary.

## Support and administration use cases

### UC22 Manage support

An account holder opens an issue, optionally linking a permitted shipment. Support, operations and administrator manage the network conversation and status. Messages retain author and time in the ticket JSON. Tickets created outside 08:00–20:00 Africa/Harare are flagged after hours. Creation, replies and status changes enter the helpdesk outbox. After-hours contacts are deferred until the next 08:00 opening; this queues delivery, not an automated staff SLA. The configured phone line and public helpdesk link are shown in the support page.

### UC23 Notifications and addresses

Users view notifications addressed to their account phone, mark them read and follow shipment links. Customers create and remove saved addresses and choose one default. A database constraint permits only one default address per account. Read status and external SMS delivery status are different concepts.

Self-service profile updates cannot change the verified phone. A separately verified administrative process is required for phone migration; otherwise a user could claim another person's notification address.

### UC24 Offline handover

The field worker records a handover while disconnected. The device stores the submission, files, owning account and retry key in IndexedDB. On reconnection, queued work for that account is submitted. Successful task completion retries return the stored result for the same key and payload. Invalid or expired codes remain visible as failed queue entries; the user must obtain a fresh code and record a new submission. An offline capture is not a confirmed server handover.

### UC25 Review reports and audit

Authorized staff view volumes, delivered shipments, verified revenue, recorded disbursements and quality measures with their qualifying counts. Custody viewers can inspect accepted events and rejected attempts with named parties. The event archive can be checked or used to rebuild status and holder projections after replication is drained. A separate archive is not a substitute for database and media backups.

### UC26 Manage accounts and configuration

Administrators create users, edit their role or access status and manage pilot activation. Authorized reference-data staff manage stations and rates; finance can edit rates through its authorized API. User deletion deactivates the account. Provider readiness is read from server configuration; secrets are not editable in the web UI.

## Acceptance criteria

1. An account never gains access to another customer's shipment through global search.
2. A booking price is calculated by the server and matches the displayed quote.
3. Carrier and home-delivery departure fail when payment is unverified.
4. Every custody change checks order, independent parties and a fresh per-step code.
5. Home delivery fails without a proof photo and signature.
6. A completed handover retry does not create a second transition.
7. A payout run balances to the booked price and cannot be repeated.
8. Recipient tracking does not reveal internal notes, staff identities or finance records.
9. Long forms scroll inside dialogs while their actions remain reachable.
10. Desktop lists and narrow-screen cards show readable names without unintended horizontal scrolling.

## Additional parcel-care use cases (2 October 2026)

UC27–UC52 extend existing journeys with cancellations, RTS, failed delivery, refunds, claims, policy, dimensions/capacity, locations, custody evidence, administration, fraud reviews, corrections, performance and exports. See the [operational completion guide](operational-completion.md) for exact behavior, permissions, policy configuration and external prerequisites. Open **Exceptions & parcel care** in web or mobile. Existing UC01–UC26 videos have not been regenerated.

## Implementation references

- Roles and data: backend/marketplace/models.py
- Custody, phone verification and settlement: backend/marketplace/workflows.py
- Booking, matching and payment services: backend/marketplace/services.py
- API permissions: backend/marketplace/permissions.py and views.py
- Active UI: frontend/src/workspace and frontend/src/pages/Auth.tsx
- Related documents: [Workflows](workflows.md) and [Database reference](database.md)
