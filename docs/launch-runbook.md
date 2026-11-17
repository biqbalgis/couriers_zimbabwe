# Pano Logistics Pilot Launch Runbook

Version 1.1 · 1 October 2026 · Mutare–Chipinge

## Launch rule

The repository is not proof of a launched service. The operator must name owners, confirm commercial dependencies and sign off a rehearsal. Keep customer traffic disabled until all launch gates pass. Never run seed_demo against a production database or reuse demo passwords.

## Owners and required evidence

| Owner | Gate | Evidence |
| --- | --- | --- |
| Operator/product owner | Signed stations, approved tariffs/payment numbers, participation/liability and regulatory arrangements | Approved pilot checklist |
| Technical owner | PostgreSQL, private media, restricted hosts/CORS, HTTPS, secret management and backups | Deployment/configuration review and successful restore rehearsal |
| Integration owner | SMS and SaaS helpdesk/telephony procurement, provider bridge, support line | SMS received on a real handset; external ticket/reply/status roundtrip; test call and after-hours queue |
| Operations lead | Vetted workers, assigned trips/capacity and custody rehearsal | Two independent operators, carrier and riders complete an end-to-end parcel |
| Finance lead | Payment verification and agreed payout cycle | Receipt reconciliation, approved leg split, external transfers and participant statements |
| Support lead | 08:00–20:00 Harare coverage, escalation and overnight queue | Roster, emergency/escalation numbers and next-opening handling rehearsal |

## Configure and deploy

1. Provision PostgreSQL and private, backed-up media storage. Current local verification uses SQLite; test migrations and concurrency on PostgreSQL before launch.
2. Set DJANGO_DEBUG=0, a strong DJANGO_SECRET_KEY, restricted DJANGO_ALLOWED_HOSTS and HTTPS CORS_ALLOWED_ORIGINS/PUBLIC_WEB_URL. Do not expose uploads as public static files.
3. Set SMS_DELIVERY_MODE=webhook, SMS_WEBHOOK_URL and SMS_WEBHOOK_TOKEN. The HTTPS bridge accepts to, message and optional notification_id. Never include server tokens in VITE variables.
4. Set HELPDESK_WEBHOOK_URL/TOKEN, SUPPORT_PHONE and optional public HELPDESK_PORTAL_URL. Helpdesk payloads contain action=create/reply/status, ticket_id, external_reference, subject, phone, parcel, messages and status. Configure telephony and staff access in the chosen SaaS product.
5. Back up the database, media and custody archive before migration. Apply the migration using Django; existing handover codes expire under 0005 and must be requested again. Do not roll back the schema blindly after new leg payouts exist.
6. Build the frontend and serve its public PWA assets over HTTPS with the API same-origin or correctly proxied. Install the field PWA on pilot devices.

```powershell
cd backend
python manage.py migrate
python manage.py check
python manage.py check --deploy
python manage.py test marketplace
python manage.py check_pilot
cd ../frontend
npm.cmd run build
```

check_pilot is read-only and does not contact providers. Missing prerequisites fail the command. --development skips production infrastructure gates but still reports missing integrations. A passing check is not a substitute for real provider and operational tests.

## Workers and archive

Schedule the following with a monitored service or scheduler at least once a minute. Keep service credentials private; alert on command failures, failed outbox records and records with ten attempts. Do not repeatedly retry invalid credentials without investigation. available_at prevents processing after-hours helpdesk contacts before the next 08:00 opening.

```powershell
python manage.py process_outbox --kind sms --limit 100
python manage.py process_outbox --kind helpdesk --limit 100
python manage.py process_outbox --kind event_log --limit 100
```

The worker marks a successful HTTPS response sent, not delivered-to-handset. Local console messages remain development. Idempotency-Key pano-{outbox_id} must be honored by provider bridges to prevent duplicate external tickets/messages after uncertain responses. Creation must establish the external ticket before reply/status handling; bridges should resolve the stable ticket_id even if an external reference is still blank.

## Rehearsal and acceptance

Use a real approved test account and consented test phone, not an unsuspecting customer's number.

1. Verify phone sign-up and staff credential access; check another customer's shipment cannot be read.
2. Book both pilot directions, including a walk-in parcel and a photo-based pickup request.
3. Submit a receipt, verify the correct amount and prove route/home dispatch rejects unverified payments.
4. Accept every task and complete each handover with independent confirming-party codes. Prove a wrong/out-of-order code logs an alert without custody movement.
5. Rehearse station collection and home delivery with photo/signature. Test two different pickup/delivery riders and their separate payout beneficiaries.
6. Disconnect a field device, capture a handover and reconnect. Inspect queued/failed work, expiry behavior and duplicate retry prevention. Clear caches from shared devices before handover to another user.
7. Verify tracking SMS, helpdesk contact/replies/status and after-hours next-opening delivery, including a call to the support line.
8. Approve allocations, make external transfers, record references and retrieve statements/CSV. Confirm totals balance and a duplicate run is rejected.
9. Drain archive replication and run rebuild_tracking without --apply; investigate mismatches. Demonstrate a backup restore on an isolated environment.
10. Record metrics and customer/carrier feedback. Authorize traffic only after the operator signs off.

## Incident, rollback and recovery

Stop new booking/dispatch traffic at the ingress during an incident; preserve pending queues, events and accounting records. Do not delete failed attempts or change payout amounts to make totals look correct. Revert application releases only if they remain compatible with migration 0005. Use a maintained backup/restore plan for database, media and archive together.

To repair a projection, stop writes, back up all stores and first drain event_log delivery. Run rebuild_tracking in check mode. Only an authorized technical owner may run rebuild_tracking --apply during maintenance after verifying the archive. Replay repairs status/holder only, not payments, tasks, files or provider messages.

## Pilot review record

Track daily volumes, delivered parcels, first-attempt home delivery (>80% target), complete OTP custody (100% target), verified-before-dispatch rate, payout accuracy, failed outbox/queue items and qualitative feedback. Reports provide counts/denominators, not proof of operator compliance. Keep a weekly learning log with issue, owner, action and follow-up date.
