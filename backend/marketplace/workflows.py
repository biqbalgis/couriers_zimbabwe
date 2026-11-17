"""Validated marketplace workflows shared by HTTP endpoints and workers."""
import hashlib
import secrets
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from .models import (CarrierTrip, FinanceEvent, IntegrationDelivery, MutationReceipt,
                     Parcel, Payment, PhoneChallenge, PilotRoute, Payout, StatusEvent, Task, User)

BANDS = {"0-2kg": Decimal("2"), "2-5kg": Decimal("5"), "5-10kg": Decimal("10")}
NEXT = {"booked": ("picked_up", "at_origin_station"), "picked_up": ("at_origin_station",),
        "at_origin_station": ("in_transit",), "in_transit": ("at_destination_station",),
        "at_destination_station": ("out_for_delivery", "delivered"), "out_for_delivery": ("delivered",),
        "exception": ()}
CLOSED = ("delivered", "returned", "cancelled")

def sms(phone, message, notification_id=None):
    return IntegrationDelivery.objects.create(kind="sms", payload={"to": phone, "message": message, "notification_id":notification_id})

def queue_helpdesk(ticket, action="create", **details):
    """Keep all after-hours contacts durable until the next support opening."""
    now=timezone.localtime(); opening=now.replace(hour=8,minute=0,second=0,microsecond=0)
    if now.hour>=20: opening+=timedelta(days=1)
    available=opening if now.hour<8 or now.hour>=20 else now
    return IntegrationDelivery.objects.create(kind="helpdesk",available_at=available,payload={"action":action,"ticket_id":ticket.pk,"external_reference":ticket.external_reference,"subject":ticket.subject,"phone":ticket.raised_by.phone,"parcel":ticket.parcel.code if ticket.parcel else None,"after_hours":available>now,"messages":ticket.messages,"status":ticket.status,**details})

def audit(actor, action, reference, **details):
    FinanceEvent.objects.create(actor=actor, action=action, reference=str(reference), details=details)
    from .operations import audit as admin_audit
    admin_audit(actor,action,reference,after=details)

def require_pilot(origin, destination):
    active=PilotRoute.objects.filter(active=True)
    if active.exists() and not active.filter(Q(origin_city=origin.city,destination_city=destination.city)|Q(origin_city=destination.city,destination_city=origin.city)).exists():
        raise ValidationError("This route is outside the active pilot. Choose one of the pilot town pairs.")

@transaction.atomic
def request_phone_code(data):
    # Serialize requests for existing accounts; throttle also covers new phone numbers.
    recent=PhoneChallenge.objects.filter(phone=data["phone"],created_at__gte=timezone.now()-timedelta(minutes=1)).exists()
    if recent: raise ValidationError("Please wait one minute before requesting another code.")
    existing=User.objects.filter(phone=data["phone"]).first()
    if existing and existing.role not in ("customer","rider","carrier"):
        raise ValidationError("Staff accounts use username and password.")
    code=f"{secrets.randbelow(1000000):06d}"
    challenge=PhoneChallenge.objects.create(phone=data["phone"],name=data.get("name", ""),role=data.get("role", "customer"),code_hash=make_password(code),expires_at=timezone.now()+timedelta(minutes=10))
    sms(challenge.phone,f"Your Pano Logistics sign-in code is {code}. Valid for 10 minutes.")
    response={"challenge_id":challenge.pk,"expires_in":600,"delivery":"queued"}
    if settings.DEBUG and settings.SMS_DELIVERY_MODE=="console": response.update(development_code=code,delivery="development")
    return response

def verify_phone_code(data):
    error=None; user=None
    with transaction.atomic():
        challenge=PhoneChallenge.objects.select_for_update().filter(pk=data["challenge_id"]).first()
        if not challenge or challenge.used or challenge.attempts>=5 or challenge.expires_at<=timezone.now():
            raise ValidationError("This verification code has expired or is locked. Request another.")
        challenge.attempts+=1
        if not check_password(data["code"],challenge.code_hash): error="Incorrect verification code."
        else:
            user=User.objects.filter(phone=challenge.phone).first()
            if user and (not user.is_active or user.role not in ("customer","rider","carrier")): error="This account cannot sign in by phone."
            elif not user:
                user=User.objects.create_user(username=challenge.phone,phone=challenge.phone,name=challenge.name or challenge.phone,role=challenge.role,verified=True)
            else: user.verified=True; user.save(update_fields=("verified",))
            challenge.used=True
        challenge.save(update_fields=("attempts","used"))
    if error: raise ValidationError(error)
    return user

def release_phone(parcel,target):
    if target in ("delivered","returned"): return parcel.recipient_phone if target=="delivered" else (parcel.sender_phone or parcel.sender.phone)
    if parcel.current_holder_id: return parcel.current_holder.phone
    return parcel.sender_phone or parcel.sender.phone

@transaction.atomic
def issue_handover_code(parcel,target,user=None,recipient=False):
    parcel=Parcel.objects.select_for_update().select_related("sender","current_holder").get(pk=parcel.pk)
    if target not in NEXT.get(parcel.status,()): raise ValidationError("That handover is not the next step.")
    if parcel.status=="booked" and target!=("picked_up" if parcel.pickup_address else "at_origin_station"):
        raise ValidationError("Follow the booked pickup or station-dropoff journey.")
    if parcel.status=="at_destination_station" and target!=("out_for_delivery" if parcel.delivery_choice=="home" else "delivered"):
        raise ValidationError("Follow the selected recipient delivery preference.")
    if recipient and target!="delivered": raise PermissionDenied("Recipient codes only confirm delivery.")
    code=f"{secrets.randbelow(1000000):06d}"
    if parcel.otp_expires_at and parcel.otp_expires_at>timezone.now() and parcel.otp_target==target:
        raise ValidationError("A code is already active for this step. Use the issued code or wait for its expiry.")
    parcel.handover_otp=make_password(code); parcel.otp_target=target; parcel.otp_expires_at=timezone.now()+timedelta(minutes=15); parcel.otp_attempts=0
    parcel.save(update_fields=("handover_otp","otp_target","otp_expires_at","otp_attempts"))
    phone=release_phone(parcel,target)
    sms(phone,f"Pano parcel {parcel.code}: handover code {code}. Share only when handing over or receiving this parcel. Expires in 15 minutes.")
    result={"detail":"Code issued to the confirming party.","expires_at":parcel.otp_expires_at,"phone_hint":phone[-4:]}
    # Only the independent confirming party sees a code; field/ops list serializers never do.
    if recipient or (user and user.phone==phone and (target not in ("delivered","returned") or user.pk==parcel.sender_id)):
        result["code"]=code
    return result

def expected_receiver(parcel,target,actor):
    if target=="picked_up": return parcel.assigned_rider.user if parcel.assigned_rider_id else None
    if target=="at_origin_station": return parcel.origin_station.operator
    if target=="in_transit": return parcel.assigned_carrier.user if parcel.assigned_carrier_id else None
    if target=="at_destination_station": return parcel.destination_station.operator
    if target=="out_for_delivery": return parcel.assigned_rider.user if parcel.assigned_rider_id else None
    return None

def custody_transition(parcel,actor,target,otp,note="",proof_photo=None,signature=None):
    error=None
    with transaction.atomic():
        p=Parcel.objects.select_for_update().select_related("sender","current_holder","assigned_carrier__user","assigned_rider__user","origin_station__operator","destination_station__operator").get(pk=parcel.pk)
        receiver=expected_receiver(p,target,actor)
        if target not in NEXT.get(p.status,()): error="Out-of-sequence handover."
        elif not p.otp_expires_at or p.otp_expires_at<=timezone.now() or p.otp_target!=target or p.otp_attempts>=5: error="Request a fresh handover code for this step."
        elif not check_password(str(otp or ""),p.handover_otp): error="Incorrect handover code."
        elif target in ("in_transit","out_for_delivery") and not Payment.objects.filter(parcel=p,status="verified").exists(): error="Payment must be verified before dispatch."
        elif receiver and receiver.pk!=actor.pk: error="The receiving station operator or assigned worker must confirm this handover."
        elif target in ("picked_up","in_transit","out_for_delivery") and not receiver: error="Assign a vetted worker before dispatch."
        elif target=="picked_up" and not p.pickup_address: error="This parcel has no first-mile pickup request."
        elif target=="at_origin_station" and p.status=="booked" and p.pickup_address: error="Complete the requested first-mile pickup before station receipt."
        elif target=="out_for_delivery" and p.delivery_choice!="home": error="This parcel is scheduled for station collection."
        elif target=="delivered" and p.status=="at_destination_station" and (p.delivery_choice!="station" or actor.pk!=p.destination_station.operator_id): error="Station collection must be confirmed by the destination operator."
        elif target=="delivered" and p.status=="out_for_delivery" and (not p.assigned_rider_id or actor.pk!=p.assigned_rider.user_id): error="Only the assigned delivery rider can complete home delivery."
        elif target=="delivered" and p.status=="out_for_delivery" and not (proof_photo and signature): error="Delivery photo and recipient signature are required."
        elif target=="returned" and actor.pk not in (p.origin_station.operator_id,p.destination_station.operator_id): error="A station operator must record a returned parcel."
        elif receiver and p.current_holder_id==receiver.pk: error="Releasing and receiving custodians must be different people."
        if target in ("picked_up","in_transit","out_for_delivery") and not error:
            from .operations import eligible_partner
            partner=p.assigned_carrier if target=='in_transit' else p.assigned_rider
            if not partner or not eligible_partner(partner):error='The assigned worker is suspended, unverified or has expired documents.'
            task_type={"picked_up":"first_mile_pickup","in_transit":"inter_town_transport","out_for_delivery":"last_mile_delivery"}[target]
            if not Task.objects.filter(parcel=p,type=task_type,assigned_to=actor,status="accepted").exists(): error="Accept the assigned task before collecting the parcel."
        p.otp_attempts+=1
        event=StatusEvent.objects.create(parcel=p,from_status=p.status,to_status=target,actor=actor,released_by=p.current_holder or p.sender,received_by=receiver,recipient_confirmed=not error and target in ("delivered","returned"),note=(note or "Custody confirmed") if not error else f"ALERT: {error}",otp_used=True,accepted=not error)
        if not error:
            if proof_photo:
                from .models import CustodyEvidence
                CustodyEvidence.objects.create(parcel=p,event=event,uploaded_by=actor,photo=proof_photo,condition='intact',note=note or 'Handover condition photo')
            p.status=target; p.current_holder=receiver; p.otp_target=""; p.handover_otp=""; p.otp_expires_at=None
            p.save(update_fields=("status","current_holder","otp_target","handover_otp","otp_expires_at","otp_attempts"))
            finished={"at_origin_station":"first_mile_pickup","at_destination_station":"inter_town_transport","delivered":"last_mile_delivery"}.get(target)
            if finished:
                task=p.tasks.filter(type=finished,status="accepted").first()
                if task:
                    task.status="completed"
                    if proof_photo: task.proof_photo=proof_photo
                    if signature: task.signature=signature
                    task.save()
            from .services import queue_notifications
            queue_notifications(p,target)
        else: p.save(update_fields=("otp_attempts",))
    if error: raise ValidationError(error)
    return p

@transaction.atomic
def cancel_parcel(parcel,actor,reason):
    from .operations import open_case
    open_case(parcel,actor,{'kind':'cancellation','reason':reason})
    parcel.refresh_from_db()
    return parcel

@transaction.atomic
def flag_exception(parcel,actor,note):
    parcel=Parcel.objects.select_for_update().get(pk=parcel.pk)
    if parcel.status in CLOSED: raise ValidationError("This journey is already closed.")
    if actor.pk!=parcel.current_holder_id and actor.role not in ("ops","admin","station_operator"): raise PermissionDenied()
    StatusEvent.objects.create(parcel=parcel,from_status=parcel.status,to_status="exception",actor=actor,released_by=parcel.current_holder,received_by=parcel.current_holder,note=note)
    parcel.status="exception"; parcel.save(update_fields=("status",))
    from .services import queue_notifications
    queue_notifications(parcel,"exception")
    return parcel

@transaction.atomic
def validate_trip_assignment(parcel,trip):
    trip=CarrierTrip.objects.select_for_update().select_related("carrier__user").get(pk=trip.pk)
    from .operations import eligible_partner,check_trip_capacity
    if not trip.active or trip.departure_at<=timezone.now() or not eligible_partner(trip.carrier):
        raise ValidationError("Choose an active future trip operated by an approved carrier.")
    if (trip.origin_city_id,trip.destination_city_id)!=(parcel.origin_station.city_id,parcel.destination_station.city_id): raise ValidationError("Trip route does not match the parcel route.")
    used=sum((BANDS[p.weight_band] for p in trip.parcels.exclude(pk=parcel.pk).exclude(status__in=CLOSED)),Decimal("0"))
    if used+BANDS[parcel.weight_band]>trip.capacity_kg: raise ValidationError("This trip has insufficient remaining capacity.")
    check_trip_capacity(trip,parcel)
    parcel.trip=trip; parcel.save(update_fields=("trip",)); return trip.carrier

@transaction.atomic
def settle_payout(payout,actor,data):
    payout=Payout.objects.select_for_update().get(pk=payout.pk)
    action=data["action"]
    if action=="approve":
        if payout.status!="pending": raise ValidationError("Only pending allocations can be approved.")
        if payout.amount and payout.recipient!="platform" and not payout.beneficiary_id: raise ValidationError("A beneficiary is required before approval.")
        payout.status="approved"; payout.approved_by=actor; payout.approved_at=timezone.now()
    else:
        if payout.status!="approved": raise ValidationError("Approve this allocation before recording payment.")
        if not data.get("reference"): raise ValidationError("An external payment reference is required.")
        payout.status="paid"; payout.payment_reference=data["reference"]; payout.disbursed_at=timezone.now()
    payout.save(); audit(actor,f"payout_{action}",payout.pk,amount=str(payout.amount),beneficiary=payout.beneficiary_id,payment_reference=data.get("reference", ""))
    return payout

def run_idempotent(user,key,path,payload,operation):
    if not key: return operation()
    if len(key)>80: raise ValidationError("Invalid retry key.")
    parts=[]
    for name,value in sorted(payload.items()):
        if hasattr(value,"read"):
            content=value.read(); value.seek(0); parts.append((name,hashlib.sha256(content).hexdigest()))
        else: parts.append((name,str(value)))
    digest=hashlib.sha256((path+repr(parts)).encode()).hexdigest()
    error=None; result=None
    # Account lock serializes retries; PostgreSQL enforces the unique receipt key.
    with transaction.atomic():
        User.objects.select_for_update().get(pk=user.pk)
        receipt=MutationReceipt.objects.filter(user=user,key=key).first()
        if receipt:
            if receipt.fingerprint!=digest: raise ValidationError("This retry key was already used for a different request.")
            return receipt.response
        try: result=operation()
        except ValidationError as exc: error=exc
        if error is None: MutationReceipt.objects.create(user=user,key=key,fingerprint=digest,response=result)
    if error: raise error
    return result
