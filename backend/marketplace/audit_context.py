"""Audit authenticated API changes without passwords, OTPs or document contents."""
import json
from contextvars import ContextVar
from django.core.serializers.json import DjangoJSONEncoder
from django.db import transaction
from django.db.models.signals import pre_save, post_save
from django.db.models.signals import m2m_changed
from django.dispatch import receiver
from .models import User, Station, RateTableEntry, Carrier, Rider, CarrierTrip, PlatformSettings, AdminAudit

request_context=ContextVar("operations_request",default=None)
FIELDS={
 User:("name","phone","role","is_active"),
 Station:("name","city_id","operator_id","address","active","service_status","opening_hours","holding_capacity","contact_phone"),
 RateTableEntry:("origin_city_id","destination_city_id","station_override_id","weight_band","price"),
 Carrier:("status","capacity_kg","capacity_m3","suspended","reverification_required","document_expires_at","review_note"),
 Rider:("status","home_station_id","available","suspended","reverification_required","document_expires_at","review_note"),
 CarrierTrip:("carrier_id","origin_city_id","destination_city_id","departure_at","capacity_kg","capacity_m3","active"),
 PlatformSettings:("key",),
}
def snapshot(instance):
    return json.loads(json.dumps({f:getattr(instance,f) for f in FIELDS[type(instance)]},cls=DjangoJSONEncoder))

class AdminAuditMiddleware:
    def __init__(self,get_response):self.get_response=get_response
    def __call__(self,request):
        if request.method not in ("POST","PUT","PATCH","DELETE") or not request.path.startswith(("/api/","/admin/")):return self.get_response(request)
        token=request_context.set(request)
        try:
            with transaction.atomic():return self.get_response(request)
        finally:request_context.reset(token)

@receiver(pre_save)
def capture_before(sender,instance,**kwargs):
    if sender not in FIELDS or not request_context.get():return
    previous=sender.objects.filter(pk=instance.pk).first() if instance.pk else None
    instance._audit_before=snapshot(previous) if previous else {}

@receiver(post_save)
def capture_after(sender,instance,**kwargs):
    request=request_context.get()
    if sender not in FIELDS or not request or not getattr(request.user,"is_authenticated",False):return
    before=getattr(instance,"_audit_before",{});after=snapshot(instance)
    if before!=after:
        AdminAudit.objects.create(actor=request.user,action=f"{sender._meta.model_name}_changed",target=f"{sender._meta.model_name}:{instance.pk}",reason=f"{request.method} {request.path}",before=before,after=after)

@receiver(m2m_changed,sender=User.user_permissions.through)
def audit_permission_changes(sender,instance,action,reverse,pk_set,**kwargs):
    request=request_context.get()
    if not request or reverse or not request.user.is_authenticated:return
    if action.startswith('pre_'):instance._permission_before=list(instance.user_permissions.values_list('codename',flat=True))
    elif action.startswith('post_'):
        before=getattr(instance,'_permission_before',[]);after=list(instance.user_permissions.values_list('codename',flat=True))
        if set(before)!=set(after):AdminAudit.objects.create(actor=request.user,action='user_permissions_changed',target=f'user:{instance.pk}',reason=f'{request.method} {request.path}',before={'permissions':before},after={'permissions':after})
