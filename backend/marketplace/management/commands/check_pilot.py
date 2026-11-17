"""Read-only deployment gate; never contacts providers or changes records."""
from urllib.parse import urlparse
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from marketplace.models import PilotRoute, RateTableEntry, Station

class Command(BaseCommand):
    help="Check pilot prerequisites without sending messages or modifying data."
    def add_arguments(self,parser):
        parser.add_argument("--development",action="store_true",help="Skip production infrastructure gates, but still report provider dependencies.")
    def handle(self,*args,**options):
        failures=[]
        def check(label,ok):
            self.stdout.write(f"{'PASS' if ok else 'BLOCKED'}: {label}")
            if not ok: failures.append(label)
        routes=list(PilotRoute.objects.filter(active=True).select_related("origin_city","destination_city"))
        check("Exactly one active pilot town pair",len(routes)==1)
        for route in routes:
            for city in (route.origin_city,route.destination_city):
                check(f"Active staffed payment-ready station in {city.name}",Station.objects.filter(city=city,active=True,operator__is_active=True,operator__role="station_operator").exclude(payment_number="").exists())
            for origin,destination in ((route.origin_city,route.destination_city),(route.destination_city,route.origin_city)):
                for band in ("0-2kg","2-5kg","5-10kg"):
                    check(f"Default positive tariff {origin.name} -> {destination.name} / {band}",RateTableEntry.objects.filter(origin_city=origin,destination_city=destination,weight_band=band,station_override__isnull=True,price__gt=0).exists())
        check("SMS HTTPS adapter with token (live mode)",settings.SMS_DELIVERY_MODE=="webhook" and urlparse(settings.SMS_WEBHOOK_URL).scheme=="https" and bool(settings.SMS_WEBHOOK_TOKEN))
        check("Helpdesk HTTPS adapter with token",urlparse(settings.HELPDESK_WEBHOOK_URL).scheme=="https" and bool(settings.HELPDESK_WEBHOOK_TOKEN))
        check("Support phone line configured",bool(settings.SUPPORT_PHONE))
        if not options["development"]:
            check("Debug disabled",not settings.DEBUG)
            check("Non-development secret key",len(settings.SECRET_KEY)>=50 and "dev-only" not in settings.SECRET_KEY)
            check("Restricted hosts",bool(settings.ALLOWED_HOSTS) and "*" not in settings.ALLOWED_HOSTS)
            check("Public app served over HTTPS",urlparse(settings.PUBLIC_WEB_URL).scheme=="https")
            check("PostgreSQL selected",connection.vendor=="postgresql")
        self.stdout.write("Manual evidence still required: provider delivery, scheduled workers, backup restore, signed stations, staff training, devices and a full pilot parcel journey.")
        if failures: raise CommandError(f"{len(failures)} prerequisite(s) remain blocked; not launch-ready.")
