from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import IntegrationDelivery,StatusEvent

@receiver(post_save,sender=StatusEvent)
def queue_event_archive(sender,instance,created,**kwargs):
    if not created: return
    IntegrationDelivery.objects.create(kind="event_log",payload={
        "event_id":instance.pk,"parcel_id":instance.parcel_id,"from_status":instance.from_status,
        "to_status":instance.to_status,"actor_id":instance.actor_id,"released_by_id":instance.released_by_id,
        "received_by_id":instance.received_by_id,"recipient_confirmed":instance.recipient_confirmed,
        "accepted":instance.accepted,"otp_used":instance.otp_used,"note":instance.note,"timestamp":instance.timestamp.isoformat(),
    })
