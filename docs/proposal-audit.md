# Pano Logistics Proposal Coverage Audit

Version 1.1 · 1 October 2026 · Source: Revised_Courier_Proposal_MVP (1).pdf, MVP 1.0 draft

## Review boundary

The PDF is a requirements reference, not authority to procure services, spend money, send messages or launch production. This review covers the proposal's MVP scope; section 15 remains deferred. The agreed pilot is Mutare–Chipinge, in either direction. No SMS or helpdesk provider has been selected.

## Coverage and changes

| Proposal requirement | Result in the repository | Remaining evidence or dependency |
| --- | --- | --- |
| Single responsive app, role-based customer/field/station/ops areas (sections 3, 6, 8) | Authenticated React/MUI role workspaces and Django/DRF permissions; responsive cards, tables and dialogs | Pilot-device acceptance and staff training |
| Phone verification (7.1) | Hashed, expiring phone challenges and throttled sign-in | Live SMS provider and delivery test |
| Station and web booking with photo (5, 7.1, 8) | Guided booking; API now requires a validated image, supported weight band and Zimbabwe recipient phone; station bookings require a customer identity | Real premises, tariffs and payment numbers must replace fictional seed values |
| Six-digit shipment code and fixed location/weight pricing (3, 5, 16) | Generated unique code, server-side tariff lookup and authorized rate management | Operator approval of real tariffs |
| Optional first mile, origin custody, route matching, destination and last mile (5) | Vetted assignments, accepted tasks and custody transitions; requested pickup can no longer skip directly to origin receipt | Full operator-supervised journey on real devices |
| Code plus OTP at each handover, immutable evidence (5, 9) | Per-step expiring OTP, five attempts, receiving-party checks, rejected-attempt alerts; OTP is now hashed and cannot be regenerated while active | Primary events have application-level guards; archive has SQL append-only triggers. Backup/restore and archive worker scheduling are required |
| Rider/carrier ID and vehicle vetting (7.2) | API now requires an identity/operating upload; approvals reject missing documents; profiles and trips retain licence/capacity checks | Human verification of identity, combined carrier vehicle/licence documents and signed participation agreements |
| POD and recording payment in field/station areas (7.2, 8) | Private delivery photo/signature, external-payment receipt capture, operations verification before route/home dispatch | Real payment channel and verifier procedure |
| Assisted splits, approval, disbursement and statements (7.3, 10) | Added distinct completed pickup/delivery rider beneficiaries and leg amounts; balanced transactional allocations, review audit, approval, external references, private statements and CSV | Staff still make actual payments outside the app; operator agrees amounts and cycle |
| Field PWA cached screens and queued sync (8, 16) | Account-scoped IndexedDB cache/files/queue; network-loss fallback now preserves the original retry key | Install/offline tests on pilot devices; codes may expire before sync and need recapture |
| SMS tracking updates (3, 8, 16) | Durable adapter outbox, tracking links; all journey states notify; Notification status now follows linked outbox results | Credentials, provider-specific bridge and actual handset delivery. “Sent” means provider acceptance, not handset delivery |
| Configured SaaS helpdesk and phone line (11, 16) | Existing companion ticket capture/lookup retained; create/reply/status outbox, public contact configuration and portal link. After-hours deliveries wait until next 08:00 | Provider selection, SaaS queue/telephony setup, credentials, support phone, inbound workflow and staffing. Local companion UI is not a delivered SaaS/telephony system |
| Basic reports and success measures (7.3, 21) | Volumes, delivered parcels, verified amounts, paid allocations, custody and pre-dispatch metrics with denominators | Collect customer/carrier feedback using the training log; validate >80% first-attempt success and 100% custody completeness on real pilot parcels |
| One town pair (3, 16) | Active pilot route restriction and seeded Mutare/Chipinge stations and tariffs | Confirm signed stations. Broad Zimbabwe catalogs remain demo references, not rollout authorization |
| Mapping/geocoding availability (17) | Stations expose EPSG:4326 coordinates and addresses; existing OpenLayers dependency is retained | No commercial geocoder is selected or certified; surveyed station locations and operator map/vendor choice remain prerequisites if geocoding is required |
| Training materials and launch runbook (16) | Added role training guide, launch/rollback/backup checklist and read-only check_pilot gate | Operator assigns owners, runs rehearsals and signs launch acceptance |

## Changes implemented in this review

- Migration 0005 adds Payout.leg, an expanded payout uniqueness constraint and IntegrationDelivery.available_at; enlarges the OTP field for a password hash and expires existing handover codes.
- Historical payout records keep their beneficiary, amount, status and blank legacy leg. They are not recalculated or redistributed.
- New explicit-leg payouts resolve riders from completed tasks. The legacy rider API stays compatible but rejects combining two different completed workers into one nonzero allocation.
- API photo/ID validation now matches the existing UI; missing-document onboarding cannot be approved.
- Notifications synchronize development, failed and provider-accepted states; helpdesk replies/status changes are propagated rather than remaining local-only.
- After-hours contact delivery is deferred to the next support opening. This is not a guarantee of staff response time.
- Offline submission retries retain the original key after a lost response; cached reads do not bypass server authorization failures.

## External launch blockers

SMS, SaaS helpdesk/telephony, HTTPS production hosting, scheduled workers, signed stations, real payment numbers, verified tariffs, regulatory approval, backup restoration and pilot acceptance cannot be completed from this checkout alone. The code includes configuration and checks, not evidence that those dependencies are fulfilled. No provider, payment or customer message was sent during this review.

The generic HTTPS adapters require the provider or an operator-controlled bridge to accept the documented JSON payload and return an optional id. They are not pre-certified connectors for an unspecified vendor. Helpdesk portal configuration does not provide inbound webhook synchronization or telephony by itself.

## Deferred scope preserved

No payment gateway, wallet, double-entry ledger, automatic refund, automatic dispatch engine, native app, barcode scanner, USSD, B2B API, full custom helpdesk, advanced routing or multi-route rollout was added. These are explicitly post-launch items in section 15, not missing MVP implementation tasks.

## Verification record

Local verification passed 26 Django tests, four Node offline-helper tests, the frontend production build, Django system checks and migration-drift checks. The two-rider regression exercises pickup, origin receipt, carrier departure, destination receipt, home delivery with proof, preserved pickup-worker visibility and balanced leg payouts. Browser review checked the support-hours banner, separate allocation controls and rendered documents; document links and embedded SVGs were validated.

Migration 0005 was applied to the local SQLite database. check_pilot --development confirmed the active Mutare–Chipinge pair, staffed stations and six directional tariffs, and reported missing live SMS, helpdesk credentials and support phone. PostgreSQL migration/concurrency, real handset/SaaS delivery, telephony, device offline persistence and deployment acceptance were not exercised. Helper tests use an isolated IndexedDB stand-in and do not replace field-device testing.

## Proposal ambiguities needing business approval

The draft's team section lists counts totaling fourteen while stating approximately twelve; its salary section budgets five people. It also gives software-development totals of $22,500 and $22,250 in different sections. Those staffing/budget inconsistencies are not software requirements and were not silently resolved. The risk table says “scan + OTP” while the MVP explicitly excludes scanning; implemented handovers use entered shipment code plus OTP.

See [Use cases](use-cases.md), [Workflows](workflows.md), [Database and ER](database.md), [Launch runbook](launch-runbook.md) and [Training](training.md).
