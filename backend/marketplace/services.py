import csv, secrets
from decimal import Decimal
from django.db import transaction
from django.http import StreamingHttpResponse
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from .models import Address, Carrier, Notification, Parcel, Payment, Payout, RateTableEntry, Rider, StatusEvent, SupportTicket, Task, User

TRANSITIONS={Parcel.Status.BOOKED:Parcel.Status.AT_ORIGIN,Parcel.Status.AT_ORIGIN:Parcel.Status.IN_TRANSIT,Parcel.Status.IN_TRANSIT:Parcel.Status.AT_DESTINATION,Parcel.Status.AT_DESTINATION:Parcel.Status.DELIVERED,Parcel.Status.EXCEPTION:Parcel.Status.RETURNED}
NOTIFY=set(Parcel.Status.values)
def make_code(model, field="code", digits=6):
    while True:
        value=f"{secrets.randbelow(10**digits):0{digits}d}"
        if not model.objects.filter(**{field:value}).exists(): return value
def lookup_rate(origin,destination,weight_band):
    base=RateTableEntry.objects.filter(origin_city=origin.city,destination_city=destination.city,weight_band=weight_band)
    return base.filter(station_override=origin).first() or base.filter(station_override__isnull=True).first()
def queue_notifications(parcel,to_status):
    from .operations import policy
    if to_status not in policy()['notifications']:return
    recipients={parcel.recipient_phone}
    if parcel.sender.phone: recipients.add(parcel.sender.phone)
    from .workflows import sms
    for phone in recipients:
        message=f"Pano Logistics parcel {parcel.code}: {to_status.replace('_',' ')}."
        if phone==parcel.recipient_phone:
            from django.conf import settings
            message+=f" Track: {settings.PUBLIC_WEB_URL}/track/{parcel.recipient_access_token}"
        notification=Notification.objects.create(parcel=parcel,channel="sms",trigger_event=to_status,recipient_phone=phone,status="queued",message=message)
        sms(phone,message,notification.pk)
@transaction.atomic
def create_parcel(validated,sender):
    from .workflows import require_pilot
    from .models import User
    require_pilot(validated["origin_station"],validated["destination_station"])
    actor=sender
    if sender.role in ("station_operator","ops","admin") and validated.get("sender_phone"):
        phone=validated["sender_phone"]
        sender=User.objects.filter(phone=phone).first()
        if not sender: sender=User.objects.create_user(username=phone,phone=phone,name=validated.get("sender_name") or phone,role="customer")
    rate=lookup_rate(validated["origin_station"],validated["destination_station"],validated["weight_band"])
    if not rate: raise ValidationError({"rate":"No rate exists for this route and weight band."})
    from .operations import validate_booking, booking_fingerprint, audit, open_case
    from .models import Station
    rules=validate_booking(validated)
    for station in Station.objects.select_for_update().filter(pk__in=[validated['origin_station'].pk,validated['destination_station'].pk]).order_by('pk'):
        if not station.active or station.service_status=='closed': raise ValidationError('Selected station is not accepting parcels.')
        if station.holding_capacity is not None and Parcel.objects.filter(current_holder=station.operator,status__in=('at_origin_station','at_destination_station')).count()>=station.holding_capacity: raise ValidationError('Selected station is at its holding capacity.')
    fingerprint=booking_fingerprint(validated,sender)
    from datetime import timedelta
    duplicate=Parcel.objects.filter(duplicate_fingerprint=fingerprint,created_at__gte=timezone.now()-timedelta(minutes=5)).exists()
    parcel=Parcel.objects.create(**validated,sender=sender,booked_by=actor,code=make_code(Parcel),handover_otp=make_code(Parcel,"handover_otp"),price=rate.price,current_holder=sender,policy_snapshot=rules,duplicate_fingerprint=fingerprint)
    if duplicate:
        open_case(parcel,actor,{'kind':'payment','reason':'Potential duplicate booking within five minutes; review before dispatch.'})
        audit(actor,'duplicate_booking',f'parcel:{parcel.pk}','Potential duplicate booking')
    StatusEvent.objects.create(parcel=parcel,from_status="",to_status=Parcel.Status.BOOKED,actor=actor,received_by=sender,note="Parcel booked")
    queue_notifications(parcel,Parcel.Status.BOOKED); return parcel

@transaction.atomic
def record_payment(parcel,validated):
    Parcel.objects.select_for_update().get(pk=parcel.pk)
    if parcel.status in ("cancelled","returned"): raise ValidationError("This parcel is closed.")
    if not validated.get("receipt_photo"): raise ValidationError({"receipt_photo":"Upload a receipt before marking paid."})
    payment=Payment.objects.filter(parcel=parcel).first()
    if payment and payment.status==Payment.Status.VERIFIED:
        raise ValidationError("A verified payment cannot be replaced.")
    from .operations import payment_flags, open_case
    digest,flags=payment_flags(parcel,validated)
    payment,_=Payment.objects.update_or_create(parcel=parcel,defaults={**validated,"amount":parcel.price,"status":"pending","verified_by":None,"verified_at":None,'receipt_sha256':digest,'fraud_flags':flags})
    if flags and not parcel.operational_cases.filter(kind='payment',status__in=('requested','approved','in_progress')).exists(): open_case(parcel,parcel.sender,{'kind':'payment','reason':'Payment evidence flagged: '+', '.join(flags)})
    return payment

@transaction.atomic
def assign_parcel(parcel,validated):
    parcel=Parcel.objects.select_for_update().get(pk=parcel.pk)
    if parcel.status in (Parcel.Status.DELIVERED,Parcel.Status.RETURNED,"cancelled"): raise ValidationError("This parcel journey is closed.")
    if "trip" in validated:
        from .workflows import validate_trip_assignment
        validated={**validated,"carrier":validate_trip_assignment(parcel,validated["trip"])}
        validated.pop("trip")
    elif "carrier" in validated: raise ValidationError("Choose a scheduled trip to validate route and capacity.")
    for key,profile in validated.items():
        if key=="rider" and not ((parcel.status=="booked" and parcel.pickup_address) or (parcel.status=="at_destination_station" and parcel.delivery_choice=="home")):
            raise ValidationError("Assign pickup riders before pickup, or delivery riders after destination receipt with home delivery selected.")
        if key=="carrier" and parcel.status not in ("booked","picked_up","at_origin_station"):
            raise ValidationError("Carrier assignments are locked once transport starts.")
        from .operations import eligible_partner
        if not eligible_partner(profile): raise ValidationError("Assign only active, vetted workers with current documents.")
        if key=="rider" and (not profile.available or profile.home_station.city_id!=(parcel.destination_station.city_id if parcel.status==Parcel.Status.AT_DESTINATION else parcel.origin_station.city_id)):
            raise ValidationError("Choose an available rider based in the correct town.")
        setattr(parcel,f"assigned_{key}",profile)
        task_type=Task.Type.INTER_TOWN if key=="carrier" else (Task.Type.LAST_MILE if parcel.status==Parcel.Status.AT_DESTINATION else Task.Type.FIRST_MILE)
        Task.objects.filter(parcel=parcel,type=task_type,status__in=("offered","accepted")).exclude(assigned_to=profile.user).update(status=Task.Status.DECLINED)
        if not Task.objects.filter(parcel=parcel,type=task_type,assigned_to=profile.user,status__in=("offered","accepted")).exists():
            Task.objects.create(parcel=parcel,type=task_type,assigned_to=profile.user)
    parcel.save(update_fields=tuple(f"assigned_{key}" for key in validated))
    return parcel

@transaction.atomic
def respond_task(task,user,accepted):
    task=Task.objects.select_for_update().get(pk=task.pk)
    if task.assigned_to_id!=user.pk: raise ValidationError("Only the assigned worker may respond.")
    if task.status!=Task.Status.OFFERED: raise ValidationError("Only offered tasks can be accepted or declined.")
    if accepted:
        from .operations import eligible_partner
        profile=getattr(user,'carrier_profile',None) if task.type==Task.Type.INTER_TOWN else getattr(user,'rider_profile',None)
        if not profile or not eligible_partner(profile):raise ValidationError('Current approved worker documents are required before accepting work.')
    task.status=Task.Status.ACCEPTED if accepted else Task.Status.DECLINED
    task.save(update_fields=("status",)); return task

def complete_task(task,user,validated):
    error=None
    with transaction.atomic():
        # Match assignment/payout lock ordering and commit custody + completion together.
        parcel=Parcel.objects.select_for_update().get(pk=task.parcel_id)
        task=Task.objects.select_for_update().get(pk=task.pk)
        if task.assigned_to_id!=user.pk or task.status!=Task.Status.ACCEPTED: raise ValidationError("Accept your assigned task before completing it.")
        targets={Task.Type.FIRST_MILE:Parcel.Status.AT_ORIGIN,Task.Type.INTER_TOWN:Parcel.Status.AT_DESTINATION,Task.Type.LAST_MILE:Parcel.Status.DELIVERED}
        if task.type==Task.Type.LAST_MILE and not ((validated.get("proof_photo") or task.proof_photo) and (validated.get("signature") or task.signature)):
            raise ValidationError("Last-mile delivery requires a proof photo and signature.")
        target=Parcel.Status.IN_TRANSIT if task.type==Task.Type.INTER_TOWN and parcel.status==Parcel.Status.AT_ORIGIN else targets[task.type]
        try: transition(parcel,user,target,validated["otp"])
        except ValidationError as exc: error=exc
        if error is None:
            for field in ("proof_photo","signature"):
                if field in validated: setattr(task,field,validated[field])
            if target!=Parcel.Status.IN_TRANSIT: task.status=Task.Status.COMPLETED
            task.save()
    # Raise after committing the rejected event, so failed attempts stay auditable.
    if error: raise error
    return task

@transaction.atomic
def set_default_address(address):
    User.objects.select_for_update().get(pk=address.user_id)
    Address.objects.filter(user_id=address.user_id,is_default=True).update(is_default=False)
    address.is_default=True; address.save(update_fields=("is_default",)); return address

@transaction.atomic
def reply_ticket(ticket,user,body):
    ticket=SupportTicket.objects.select_for_update().get(pk=ticket.pk)
    if ticket.status=="closed": raise ValidationError("This ticket is closed.")
    ticket.messages=[*ticket.messages,{"body":body,"author":user.name,"user_id":user.pk,"created_at":timezone.now().isoformat()}]
    ticket.save(update_fields=("messages",))
    from .workflows import queue_helpdesk
    queue_helpdesk(ticket,"reply",body=body,author=user.name)
    return ticket

@transaction.atomic
def set_ticket_status(ticket,user,value):
    ticket=SupportTicket.objects.select_for_update().get(pk=ticket.pk)
    ticket.status=value; ticket.save(update_fields=("status",))
    from .workflows import queue_helpdesk
    queue_helpdesk(ticket,"status",actor=user.name)
    return ticket

@transaction.atomic
def run_payout(validated):
    parcel=Parcel.objects.select_for_update().get(pk=validated["parcel"].pk)
    if parcel.status!=Parcel.Status.DELIVERED or not Payment.objects.filter(parcel=parcel,status="verified").exists(): raise ValidationError("Payouts require a delivered parcel and verified payment.")
    if parcel.payouts.exists(): raise ValidationError("A payout run already exists for this parcel.")
    workers={}
    for task in parcel.tasks.filter(status="completed",type__in=(Task.Type.FIRST_MILE,Task.Type.LAST_MILE)).select_related("assigned_to"):
        if task.type in workers and workers[task.type].pk!=task.assigned_to_id: raise ValidationError("Multiple completed workers on one leg require investigation.")
        workers[task.type]=task.assigned_to
    lines=[]
    if "first_mile_rider" in validated or "last_mile_rider" in validated:
        for leg,kind in (("first_mile",Task.Type.FIRST_MILE),("last_mile",Task.Type.LAST_MILE)):
            amount=validated.get(leg+"_rider",Decimal("0")); beneficiary=workers.get(kind)
            if amount and not beneficiary: raise ValidationError(f"No completed {leg} task identifies a rider beneficiary.")
            lines.append(("rider",leg,amount,beneficiary))
    else:
        distinct={u.pk:u for u in workers.values()}
        if validated["rider"] and len(distinct)>1: raise ValidationError("Two different riders worked this parcel. Allocate each leg separately.")
        beneficiary=next(iter(distinct.values()),None) or (parcel.assigned_rider.user if parcel.assigned_rider_id else None)
        lines.append(("rider","",validated["rider"],beneficiary))
    lines.extend((("carrier","",validated["carrier"],parcel.assigned_carrier.user if parcel.assigned_carrier_id else None),("station","",validated["station"],parcel.origin_station.operator)))
    platform=parcel.price-sum((line[2] for line in lines),Decimal("0"))
    if platform<0: raise ValidationError("Split amounts cannot exceed parcel price.")
    lines.append(("platform","",platform,None))
    for recipient,leg,amount,beneficiary in lines:
        if amount and recipient!="platform" and not beneficiary: raise ValidationError(f"No beneficiary is assigned for {recipient}.")
    return [Payout.objects.create(parcel=parcel,recipient=recipient,leg=leg,beneficiary=beneficiary,period=validated["period"],amount=amount) for recipient,leg,amount,beneficiary in lines]
def seed_transition(parcel,actor,target,otp,note=""):
    with transaction.atomic():
        locked=Parcel.objects.select_for_update().get(pk=parcel.pk)
        allowed=Parcel.Status.EXCEPTION if target==Parcel.Status.EXCEPTION and locked.status not in (Parcel.Status.DELIVERED,Parcel.Status.RETURNED) else TRANSITIONS.get(locked.status)
        valid=allowed==target and secrets_match(locked.handover_otp,otp)
        StatusEvent.objects.create(parcel=locked,from_status=locked.status,to_status=target or "",actor=actor,note=note or ("Handover accepted" if valid else "ALERT: rejected handover attempt"),otp_used=bool(otp),accepted=valid)
        if valid:
            locked.status=target; locked.current_holder=actor; locked.save(update_fields=("status","current_holder")); queue_notifications(locked,target)
    if not valid: raise ValidationError({"detail":"Out-of-sequence transition or invalid OTP. The attempt was logged as an alert."})
    return locked
def secrets_match(expected,provided):
    import secrets
    return bool(provided) and secrets.compare_digest(expected,str(provided))
def verify_payment(payment,user,status):
    if status not in (Payment.Status.VERIFIED,Payment.Status.REJECTED): raise ValidationError({"status":"Use verified or rejected."})
    with transaction.atomic():
        payment=Payment.objects.select_for_update().get(pk=payment.pk)
        if payment.status!=Payment.Status.PENDING: raise ValidationError("This payment has already been reviewed.")
        if status==Payment.Status.VERIFIED and payment.fraud_flags: raise ValidationError('Review flagged payment evidence with a reason before verification.')
        if status==Payment.Status.VERIFIED and (not payment.receipt_photo or payment.amount!=payment.parcel.price): raise ValidationError("Verify a receipt matching the parcel price.")
        payment.status=status; payment.verified_by=user; payment.verified_at=timezone.now(); payment.save()
        from .workflows import audit
        audit(user,"payment_review",payment.pk,status=status,amount=str(payment.amount),parcel=payment.parcel_id)
        return payment
def csv_response(queryset,fields,name):
    class Echo: 
        def write(self,value): return value
    def safe(value):
        value='' if value is None else str(value)
        return "'"+value if value.lstrip().startswith(('=','+','-','@')) else value
    writer=csv.writer(Echo()); rows=([safe(getattr(x,f)) for f in fields] for x in queryset.iterator(chunk_size=500))
    from itertools import chain
    response=StreamingHttpResponse(chain([writer.writerow(fields)],(writer.writerow(row) for row in rows)),content_type="text/csv"); response["Content-Disposition"]=f'attachment; filename="{name}.csv"'; return response

def transition(parcel,actor,target,otp,note="",photo=None):
    from .workflows import custody_transition
    return custody_transition(parcel,actor,target,otp,note,proof_photo=photo)
