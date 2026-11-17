from django.core.management.base import BaseCommand
from marketplace.models import IntegrationDelivery
from marketplace.integrations import deliver_one
from django.utils import timezone

class Command(BaseCommand):
    help="Deliver pending SMS/helpdesk work and replicate immutable custody events; safe to retry."
    def add_arguments(self,parser):
        parser.add_argument("--limit",type=int,default=100)
        parser.add_argument("--kind",choices=("sms","helpdesk","event_log"))
    def handle(self,*args,**options):
        rows=IntegrationDelivery.objects.filter(status__in=("queued","failed"),attempts__lt=10,available_at__lte=timezone.now()).order_by("id")
        if options["kind"]: rows=rows.filter(kind=options["kind"])
        for pk in rows.values_list("pk",flat=True)[:options["limit"]]: self.stdout.write(f"Delivery {pk}: {deliver_one(pk)}")
