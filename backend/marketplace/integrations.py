"""Outbox adapters: provider credentials stay server-side; failures remain retryable."""
import json
import sqlite3
from urllib.request import Request,urlopen
from urllib.parse import urlparse
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from .models import IntegrationDelivery, SupportTicket, Notification

def synchronize_notification(item):
    if item.kind=="sms" and item.payload.get("notification_id"):
        Notification.objects.filter(pk=item.payload["notification_id"]).update(status=item.status,sent_at=item.delivered_at)

def archive_event(payload):
    # The custody archive is a separate append-only database, without cross-database FKs.
    # A transactionally queued outbox makes archive delivery recoverable.
    with sqlite3.connect(settings.EVENT_ARCHIVE_PATH,timeout=20) as archive:
        archive.execute("CREATE TABLE IF NOT EXISTS custody_events (event_id INTEGER PRIMARY KEY, parcel_id INTEGER NOT NULL, payload TEXT NOT NULL)")
        archive.execute("CREATE TRIGGER IF NOT EXISTS custody_no_update BEFORE UPDATE ON custody_events BEGIN SELECT RAISE(ABORT, 'append-only'); END")
        archive.execute("CREATE TRIGGER IF NOT EXISTS custody_no_delete BEFORE DELETE ON custody_events BEGIN SELECT RAISE(ABORT, 'append-only'); END")
        encoded=json.dumps(payload,sort_keys=True)
        existing=archive.execute("SELECT payload FROM custody_events WHERE event_id=?",(payload["event_id"],)).fetchone()
        if existing and existing[0]!=encoded: raise ValueError("Archive event mismatch; manual investigation required.")
        archive.execute("INSERT OR IGNORE INTO custody_events(event_id,parcel_id,payload) VALUES(?,?,?)",(payload["event_id"],payload["parcel_id"],encoded))

def deliver_one(delivery_id):
    with transaction.atomic():
        item=IntegrationDelivery.objects.select_for_update().get(pk=delivery_id)
        if item.status in ("sent","development"): return item.status
        if item.available_at>timezone.now(): return "deferred"
        item.attempts+=1
        try:
            if item.kind=="event_log": archive_event(item.payload)
            elif item.kind=="sms" and settings.SMS_DELIVERY_MODE=="console" and settings.DEBUG:
                item.status="development"; item.last_error="Local development delivery only; no external SMS sent."
                item.save(); synchronize_notification(item); return item.status
            else:
                url=settings.SMS_WEBHOOK_URL if item.kind=="sms" else settings.HELPDESK_WEBHOOK_URL
                token=settings.SMS_WEBHOOK_TOKEN if item.kind=="sms" else settings.HELPDESK_WEBHOOK_TOKEN
                if not url or not token: raise ValueError("Provider endpoint and token are not configured.")
                if urlparse(url).scheme!="https": raise ValueError("Provider endpoints must use HTTPS.")
                request=Request(url,data=json.dumps(item.payload).encode(),headers={"Content-Type":"application/json","Authorization":f"Bearer {token}","Idempotency-Key":f"pano-{item.pk}"},method="POST")
                with urlopen(request,timeout=15) as response:
                    data=json.loads(response.read(65536) or b"{}")
                item.external_reference=str(data.get("id",""))[:160]
                if item.kind=="helpdesk" and item.external_reference:
                    SupportTicket.objects.filter(pk=item.payload.get("ticket_id")).update(external_reference=item.external_reference)
            item.status="sent"; item.delivered_at=timezone.now(); item.last_error=""
        except Exception as exc:
            item.status="failed"; item.last_error=type(exc).__name__+": "+str(exc)[:300]
        item.save(); synchronize_notification(item); return item.status
