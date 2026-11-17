import json
import sqlite3
from django.conf import settings
from django.core.management.base import BaseCommand,CommandError
from django.db import transaction
from marketplace.models import Parcel,IntegrationDelivery

class Command(BaseCommand):
    help="Check or rebuild parcel status/holder projections from the separate custody archive."
    def add_arguments(self,parser): parser.add_argument("--apply",action="store_true")
    def handle(self,*args,**options):
        if IntegrationDelivery.objects.filter(kind="event_log").exclude(status="sent").exists(): raise CommandError("Archive replication is pending. Run process_outbox --kind event_log first.")
        try:
            with sqlite3.connect(f"file:{settings.EVENT_ARCHIVE_PATH}?mode=ro",uri=True) as archive:
                events=[json.loads(row[0]) for row in archive.execute("SELECT payload FROM custody_events ORDER BY event_id")]
        except sqlite3.Error as exc: raise CommandError("Custody archive is not available.") from exc
        projections={}
        for event in events:
            if event["accepted"]: projections[event["parcel_id"]]=event
        for pk,event in projections.items():
            parcel=Parcel.objects.get(pk=pk)
            if parcel.status!=event["to_status"] or parcel.current_holder_id!=event["received_by_id"]:
                self.stdout.write(f"{parcel.code}: {parcel.status} -> {event['to_status']}")
                if options["apply"]:
                    with transaction.atomic(): Parcel.objects.filter(pk=pk).update(status=event["to_status"],current_holder_id=event["received_by_id"])
        self.stdout.write(f"Checked {len(projections)} parcel projections; apply={options['apply']}.")
