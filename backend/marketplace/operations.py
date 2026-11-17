"""Canonical parcel operations. Monetary values record external decisions, never move money."""
import hashlib
import secrets
from datetime import timedelta
from decimal import Decimal
from django.contrib.auth.hashers import make_password, check_password
from django.db import transaction
from django.db.models import Sum, Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError, PermissionDenied
from .models import (Parcel, Payment, Task, OperationalCase, DeliveryAttempt, CustodyEvidence,
                     AdminAudit, PlatformSettings, Rider, Carrier, CarrierTrip, StatusEvent)
from .permissions import has_role

DEFAULT_POLICY={"version":"1", "reviewed":False,"currency":"USD", "cancellation_before_pickup":"0.00",
 "cancellation_assigned":"0.00","cancellation_after_pickup":"0.00","return_fee":"0.00",
 "liability_limit":"0.00","max_length_cm":None,"max_width_cm":None,"max_height_cm":None,
 "max_volume_m3":None,"dimensions_required":False,"max_delivery_attempts":3,
 "prohibited_categories":["illegal","hazardous","dangerous"],"restricted_categories":["fragile"],
 "notifications":list(Parcel.Status.values)+["failed_delivery","case_updated"],
 "terms":"Operational policy requires owner review. No parcel insurance is offered.","insurance_available":False,"stale_after_hours":72}

def policy():
    record=PlatformSettings.objects.filter(key="operations-policy").first()
    return {**DEFAULT_POLICY,**(record.value if record else {})}

def audit(actor,action,target,reason="",before=None,after=None):
    return AdminAudit.objects.create(actor=actor,action=action,target=str(target),reason=reason,before=before or {},after=after or {})

def eligible_partner(profile):
    role='carrier' if isinstance(profile,Carrier) else 'rider'
    return profile.user.role==role and profile.status=="approved" and not profile.suspended and not profile.reverification_required and profile.user.is_active and (not profile.document_expires_at or profile.document_expires_at>=timezone.localdate())

def volume(parcel):
    values=(parcel.length_cm,parcel.width_cm,parcel.height_cm)
    return Decimal("0") if any(v is None for v in values) else values[0]*values[1]*values[2]/Decimal("1000000")

def validate_booking(data):
    rules=policy()
    category=data.get("contents_category","general").strip().lower()
    if category in [v.strip().lower() for v in rules["prohibited_categories"]+rules["restricted_categories"]]:
        raise ValidationError({"contents_category":"This category is prohibited or requires operations approval outside standard booking."})
    dimensions=[data.get(k) for k in ("length_cm","width_cm","height_cm")]
    if rules["dimensions_required"] and any(v is None for v in dimensions): raise ValidationError("Enter all three parcel dimensions.")
    if any(v is not None for v in dimensions) and any(v is None for v in dimensions): raise ValidationError("Enter all three dimensions or leave all blank.")
    for key in ("length_cm","width_cm","height_cm"):
        value=data.get(key); limit=rules["max_"+key]
        if value is not None and (value<=0 or (limit is not None and value>Decimal(str(limit)))): raise ValidationError({key:"Dimension exceeds the configured size limit or is not positive."})
    if all(v is not None for v in dimensions) and rules["max_volume_m3"] is not None and dimensions[0]*dimensions[1]*dimensions[2]/Decimal("1000000")>Decimal(str(rules["max_volume_m3"])): raise ValidationError("Parcel exceeds the volume limit.")
    for prefix in ("pickup","delivery"):
        lat=data.get(prefix+"_latitude");lon=data.get(prefix+"_longitude")
        if (lat is None)!=(lon is None) or (lat is not None and not (-90<=lat<=90 and -180<=lon<=180)): raise ValidationError("Location must be a complete EPSG:4326 latitude/longitude pair.")
    return rules

def payment_flags(parcel,data):
    photo=data.get("receipt_photo"); digest=""
    if photo:
        digest=hashlib.sha256(photo.read()).hexdigest();photo.seek(0)
    others=Payment.objects.exclude(parcel=parcel)
    flags=[]
    if digest and others.filter(receipt_sha256=digest).exists(): flags.append("receipt_reused")
    ref=data.get("transaction_reference","").strip()
    if ref and others.filter(transaction_reference__iexact=ref).exists(): flags.append("reference_reused")
    return digest,flags

def booking_fingerprint(data,sender):
    raw=f"{sender.pk}:{data['origin_station'].pk}:{data['destination_station'].pk}:{data['recipient_phone']}:{data['weight_band']}"
    return hashlib.sha256(raw.encode()).hexdigest()

def transition_note(parcel,actor,to_status,note):
    old=parcel.status;parcel.status=to_status;parcel.save(update_fields=["status"])
    StatusEvent.objects.create(parcel=parcel,from_status=old,to_status=to_status,actor=actor,released_by=parcel.current_holder,received_by=parcel.current_holder,note=note)
    from .services import queue_notifications
    queue_notifications(parcel,to_status)

@transaction.atomic
def open_case(parcel,actor,data):
    parcel=Parcel.objects.select_for_update().get(pk=parcel.pk)
    kind=data["kind"]
    if kind in ("refund","cancellation","loss","damage") and actor.pk!=parcel.sender_id and not has_role(actor,"ops","admin","finance","support"):
        raise PermissionDenied("Only the sender or authorized staff may request this case.")
    if OperationalCase.objects.filter(parcel=parcel,kind=kind,status__in=("requested","approved","in_progress")).exists(): raise ValidationError("An active case of this kind already exists.")
    if kind=="cancellation" and parcel.status in ("delivered","cancelled","returned"): raise ValidationError("This journey is already closed.")
    rules=parcel.policy_snapshot or policy()
    stage="after_pickup" if parcel.status not in ("booked",) else "assigned" if parcel.trip_id or parcel.assigned_rider_id else "before_pickup"
    fee=Decimal(str(rules.get("cancellation_"+stage,0))) if kind=="cancellation" else Decimal(str(rules.get("return_fee",0))) if kind=="return" else Decimal("0")
    case=OperationalCase.objects.create(parcel=parcel,requested_by=actor,kind=kind,reason=data["reason"],amount=data.get("amount",0),fee=fee,policy_snapshot=rules)
    if kind=="cancellation" and parcel.status=="booked" and not parcel.trip_id and not parcel.assigned_rider_id:
        decide_case(case,actor,{"action":"approve","note":"Pre-pickup cancellation", "amount":case.amount},automatic=True)
    audit(actor,"case_requested",f"case:{case.pk}",case.reason,after={"kind":kind,"fee":str(fee)})
    return case

@transaction.atomic
def decide_case(case,actor,data,automatic=False):
    parcel=Parcel.objects.select_for_update().get(pk=case.parcel_id)
    case=OperationalCase.objects.select_for_update().get(pk=case.pk)
    action=data["action"]
    financial=case.kind in ("refund","loss","damage")
    capability='record_refund_payment' if action=='pay' else 'approve_refund'
    delegated=financial and actor.role in ('ops','finance','support','admin') and actor.has_perm('marketplace.'+capability)
    if not automatic and not (has_role(actor,*( ("finance","admin") if financial else ("ops","admin") )) or delegated): raise PermissionDenied()
    if financial and actor.pk==parcel.sender_id:raise PermissionDenied('Financial cases require an independent reviewer.')
    if action in ("approve","reject") and case.status!="requested": raise ValidationError("Only requested cases can be decided.")
    if action=="reject":case.status="rejected"
    elif action=="approve":
        amount=data.get("amount",case.amount)
        if financial:
            if case.kind=="refund":
                payment=Payment.objects.filter(parcel=parcel,status="verified").first()
                if not payment: raise ValidationError("Refunds require verified payment.")
                reserved=OperationalCase.objects.filter(parcel=parcel,kind="refund",status__in=("approved","paid")).exclude(pk=case.pk).aggregate(total=Sum("amount"))["total"] or Decimal("0")
                fees=OperationalCase.objects.filter(parcel=parcel,kind__in=('cancellation','return'),status__in=('approved','in_progress','resolved')).aggregate(total=Sum('fee'))['total'] or Decimal('0')
                if amount>payment.amount-reserved-fees: raise ValidationError("Refund exceeds remaining verified payment after applicable fees.")
                paid_payouts=parcel.payouts.filter(status__in=("approved","paid")).exists()
                if paid_payouts:
                    reference=data.get('reconciliation_reference','').strip()
                    if not reference:raise ValidationError("Reconcile approved/disbursed payouts externally and supply the reconciliation reference before approving a refund.")
                    case.policy_snapshot={**case.policy_snapshot,'payout_reconciliation_reference':reference}
                    audit(actor,'refund_payout_reconciliation',f'case:{case.pk}',data['note'],after={'reference':reference})
            else:
                if not case.policy_snapshot.get('reviewed',False):raise ValidationError('Owner review of liability terms is required before compensation approval.')
                limit=min(parcel.declared_value,Decimal(str(case.policy_snapshot.get("liability_limit",0))))
                other=OperationalCase.objects.filter(parcel=parcel,kind__in=("loss","damage"),status__in=("approved","paid")).exclude(pk=case.pk).aggregate(total=Sum("amount"))["total"] or Decimal("0")
                if amount>limit-other: raise ValidationError("Compensation exceeds remaining declared-value/policy limit.")
                if not case.evidence.exists(): raise ValidationError("Evidence is required before compensation approval.")
            if amount<=0: raise ValidationError("An approved financial case requires a positive amount.")
            case.amount=amount
        case.status="approved"
        if case.kind=="cancellation":
            parcel.tasks.filter(status__in=("offered","accepted")).update(status="declined")
            if parcel.status=="booked":
                transition_note(parcel,actor,"cancelled",case.reason);parcel.trip=None;parcel.assigned_rider=None;parcel.assigned_carrier=None;parcel.save(update_fields=["trip","assigned_rider","assigned_carrier"]);case.status="resolved"
            else:
                previous_status=parcel.status
                transition_note(parcel,actor,"exception","Cancellation requires physical return: "+case.reason)
                if not parcel.operational_cases.filter(kind="return",status__in=("requested","approved","in_progress")).exists():
                    stage='at_origin' if parcel.current_holder_id==parcel.origin_station.operator_id else 'collected' if parcel.current_holder_id==parcel.destination_station.operator_id else 'awaiting_collection'
                    OperationalCase.objects.create(parcel=parcel,kind="return",requested_by=actor,reason=case.reason,fee=Decimal(str(case.policy_snapshot.get("return_fee",0))),policy_snapshot={**case.policy_snapshot,'return_origin_only':previous_status in ('booked','picked_up','at_origin_station')},status="approved",return_stage=stage)
            payment=Payment.objects.filter(parcel=parcel,status="verified").first()
            if payment and not parcel.operational_cases.filter(kind="refund",status__in=("requested","approved","paid")).exists():
                return_fee=Decimal(str(case.policy_snapshot.get('return_fee',0))) if parcel.status=='exception' else Decimal('0')
                refund_amount=max(Decimal("0"),payment.amount-case.fee-return_fee)
                if refund_amount:OperationalCase.objects.create(parcel=parcel,kind="refund",requested_by=actor,reason="Cancellation refund review",amount=refund_amount,policy_snapshot=case.policy_snapshot)
        elif case.kind=="return":
            if parcel.status in ("returned","cancelled"): raise ValidationError("No custody return is needed for a closed parcel.")
            if parcel.status=='booked' and parcel.current_holder_id==parcel.sender_id:raise ValidationError('The parcel is still with its sender. Use cancellation rather than a physical return.')
            previous=parcel.status
            case.policy_snapshot={**case.policy_snapshot,'return_origin_only':previous in ('booked','picked_up','at_origin_station')}
            case.return_stage='at_origin' if parcel.current_holder_id==parcel.origin_station.operator_id else 'collected' if parcel.current_holder_id==parcel.destination_station.operator_id else 'awaiting_collection'
            transition_note(parcel,actor,"exception","Return approved: "+case.reason)
            parcel.tasks.filter(status__in=('offered','accepted')).update(status='declined')
    elif action=="pay":
        if not financial or case.status!="approved":raise ValidationError("Approve the financial case before recording payment.")
        reference=data.get("reference","").strip()
        if not reference:raise ValidationError("Record an external payment reference.")
        if OperationalCase.objects.filter(payment_reference=reference,status="paid").exists():raise ValidationError("This external payment reference was already recorded.")
        case.payment_reference=reference;case.status="paid"
    elif action=="resolve":
        if financial or case.kind in ("return","cancellation") or case.status not in ("requested","approved","in_progress"):raise ValidationError("This case needs its dedicated financial, cancellation or return workflow.")
        case.status="resolved"
    case.decision_note=data["note"];case.assigned_to=actor
    from django.db import IntegrityError
    try:
        with transaction.atomic():case.save()
    except IntegrityError:raise ValidationError('This external payment reference has already been recorded.')
    audit(actor,"case_"+action,f"case:{case.pk}",data["note"],after={"status":case.status,"amount":str(case.amount),"reference":case.payment_reference})
    from .services import queue_notifications
    queue_notifications(parcel,"case_updated")
    return case

@transaction.atomic
def record_attempt(parcel,actor,data):
    parcel=Parcel.objects.select_for_update().get(pk=parcel.pk)
    if parcel.status!="out_for_delivery" or not parcel.tasks.filter(assigned_to=actor,type="last_mile_delivery",status="accepted").exists():raise PermissionDenied("Only the accepted last-mile rider can record a delivery attempt.")
    attempt=DeliveryAttempt.objects.create(parcel=parcel,rider=actor,**data)
    if not parcel.operational_cases.filter(kind="failed_delivery",status__in=("requested","approved","in_progress")).exists():
        open_case(parcel,actor,{"kind":"failed_delivery","reason":data["outcome"]+": "+data["note"]})
    if data["next_action"]=="return" or parcel.delivery_attempts.count()>=(parcel.policy_snapshot or policy()).get("max_delivery_attempts",3):
        if not parcel.operational_cases.filter(kind="return",status__in=("requested","approved","in_progress")).exists():open_case(parcel,actor,{"kind":"return","reason":"Failed delivery return review"})
        transition_note(parcel,actor,'exception','Delivery attempts exhausted or return requested; operations review required.')
    from .services import queue_notifications
    queue_notifications(parcel,"failed_delivery")
    audit(actor,"delivery_attempt",f"parcel:{parcel.pk}",data["note"],after={"outcome":data["outcome"],"next_action":data["next_action"]})
    return attempt

RETURN_NEXT={"awaiting_collection":"collected","collected":"in_transit","in_transit":"at_origin","at_origin":"returned"}

def check_trip_capacity(trip,parcel,exclude_return=None):
    from .workflows import BANDS,CLOSED
    forwards=list(trip.parcels.exclude(pk=parcel.pk).exclude(status__in=CLOSED))
    returns=[c.parcel for c in trip.return_cases.filter(status__in=('approved','in_progress')).exclude(pk=exclude_return).select_related('parcel')]
    parcels=forwards+returns+[parcel]
    if sum((BANDS[p.weight_band] for p in parcels),Decimal('0'))>trip.capacity_kg:raise ValidationError('Trip has insufficient remaining weight capacity.')
    if trip.capacity_m3 is not None:
        if any(p.length_cm is None or p.width_cm is None or p.height_cm is None for p in parcels):raise ValidationError('Volume-limited trips require dimensions for every assigned parcel.')
        if sum((volume(p) for p in parcels),Decimal('0'))>trip.capacity_m3:raise ValidationError('Trip has insufficient remaining volume capacity.')

@transaction.atomic
def return_action(case,actor,data):
    parcel=Parcel.objects.select_for_update().get(pk=case.parcel_id)
    case=OperationalCase.objects.select_for_update().get(pk=case.pk)
    if case.kind!="return" or case.status not in ("approved","in_progress"):raise ValidationError("Approve the return before dispatch.")
    target=RETURN_NEXT.get(case.return_stage)
    if case.policy_snapshot.get('return_origin_only') and target=='in_transit':target='at_origin'
    if case.policy_snapshot.get('return_origin_only') and target=='collected' and not case.return_rider_id:target='at_origin'
    if data["action"]=="assign":
        if not has_role(actor,"ops","admin"):raise PermissionDenied()
        if case.return_stage in ('in_transit','at_origin'):raise ValidationError('Return worker assignments are locked after reverse transport begins.')
        trip=data.get("trip");rider=data.get("rider")
        if trip:
            trip=CarrierTrip.objects.select_for_update().select_related("carrier__user").get(pk=trip.pk)
            if not trip.active or not eligible_partner(trip.carrier) or trip.departure_at<=timezone.now() or (trip.origin_city_id,trip.destination_city_id)!=(parcel.destination_station.city_id,parcel.origin_station.city_id):raise ValidationError("Choose a vetted future reverse-route trip.")
            from .workflows import BANDS,CLOSED
            reserved=sum((BANDS[p.weight_band] for p in trip.parcels.exclude(status__in=CLOSED)),Decimal("0"))+sum((BANDS[c.parcel.weight_band] for c in trip.return_cases.filter(status__in=("approved","in_progress")).exclude(pk=case.pk).select_related("parcel")),Decimal("0"))
            if reserved+BANDS[parcel.weight_band]>trip.capacity_kg:raise ValidationError("Return trip is full.")
            check_trip_capacity(trip,parcel,case.pk)
            case.return_trip=trip
        if rider:
            town=parcel.origin_station.city_id if case.policy_snapshot.get('return_origin_only') else parcel.destination_station.city_id
            if not eligible_partner(rider) or not rider.available or rider.home_station.city_id!=town:raise ValidationError("Choose an available approved collection-town rider.")
            case.return_rider=rider
        case.save();audit(actor,"return_assigned",f"case:{case.pk}",data["note"]);return {"detail":"Return workers assigned."}
    confirmer=parcel.sender if target=="returned" else parcel.current_holder or parcel.sender
    if data["action"]=="code":
        if actor.pk!=confirmer.pk:raise PermissionDenied("Only the independent releasing party can issue this code.")
        if case.code_expires_at and case.code_expires_at>timezone.now():raise ValidationError('A return code is already active. Use it or wait for expiry.')
        code=f"{secrets.randbelow(1000000):06d}";case.code_hash=make_password(code);case.code_target=target;case.code_expires_at=timezone.now()+timedelta(minutes=15);case.code_attempts=0;case.save();return {"code":code,"expires_at":case.code_expires_at}
    receiver=(case.return_rider.user if case.return_rider_id else parcel.origin_station.operator if case.policy_snapshot.get('return_origin_only') else parcel.destination_station.operator) if target=="collected" else case.return_trip.carrier.user if target=="in_transit" and case.return_trip_id else parcel.origin_station.operator if target in ("at_origin","returned") else None
    if not target or not receiver or actor.pk!=receiver.pk:raise PermissionDenied("Only the assigned receiver can confirm this return leg.")
    if receiver.pk==confirmer.pk:raise ValidationError('Return handovers require independent confirming and receiving parties.')
    if target=='in_transit' and not eligible_partner(case.return_trip.carrier):raise ValidationError('Return carrier is no longer eligible.')
    if case.code_target!=target or not case.code_expires_at or case.code_expires_at<=timezone.now() or case.code_attempts>=5:raise ValidationError("Request a fresh return handover code.")
    # Save failed attempts outside a transaction rollback through a bounded database update.
    if not check_password(data.get("otp",""),case.code_hash):
        case.code_attempts+=1;case.save(update_fields=["code_attempts"])
        audit(actor,'return_code_rejected',f'case:{case.pk}','Incorrect return code',after={'attempts':case.code_attempts})
        return {"detail":"Incorrect return code.","invalid":True}
    if not data.get("photo"):raise ValidationError("Return handovers require a condition photo.")
    evidence=CustodyEvidence.objects.create(parcel=parcel,case=case,uploaded_by=actor,photo=data["photo"],condition=data.get('condition','intact'),note=data["note"])
    previous=parcel.current_holder;case.return_stage=target;case.status="resolved" if target=="returned" else "in_progress";case.code_hash="";case.code_expires_at=None;case.save()
    parcel.current_holder=parcel.sender if target=="returned" else receiver
    if target=="returned":parcel.status="returned"
    parcel.save(update_fields=["current_holder","status"])
    if target=='returned':parcel.operational_cases.filter(kind__in=('cancellation','failed_delivery'),status__in=('requested','approved','in_progress')).update(status='resolved',decision_note='Physical return confirmed by sender code.',assigned_to=actor)
    event=StatusEvent.objects.create(parcel=parcel,from_status="exception",to_status=parcel.status,actor=actor,released_by=previous,received_by=parcel.current_holder,recipient_confirmed=target=="returned",note=f"RTS {target}: {data['note']}",otp_used=True)
    evidence.event=event;evidence.save(update_fields=['event'])
    audit(actor,"return_handover",f"case:{case.pk}",data["note"],after={"stage":target})
    from .services import queue_notifications
    queue_notifications(parcel,'returned' if target=='returned' else 'case_updated')
    return {"detail":"Return stage confirmed.","stage":target}

@transaction.atomic
def correct_parcel(code,actor,data):
    if not has_role(actor,"ops","admin"):raise PermissionDenied()
    from django.shortcuts import get_object_or_404
    parcel=get_object_or_404(Parcel.objects.select_for_update(),code=code);data=dict(data);note=data.pop("note")
    if parcel.status in ("delivered","returned","cancelled"):raise ValidationError("Closed journeys cannot be overwritten.")
    restore=data.pop('restore_previous_status',False)
    if not data and not restore:raise ValidationError("Provide a correction.")
    if restore:
        if parcel.status!='exception' or parcel.operational_cases.filter(kind__in=('cancellation','return'),status__in=('requested','approved','in_progress')).exists():raise ValidationError('Only non-return exceptions can be restored.')
        event=parcel.events.filter(accepted=True,to_status='exception').order_by('-id').first()
        if not event or event.from_status in ('exception','delivered','returned','cancelled'):raise ValidationError('No safe previous custody state exists.')
        data['status']=event.from_status
        StatusEvent.objects.create(parcel=parcel,from_status='exception',to_status=event.from_status,actor=actor,released_by=parcel.current_holder,received_by=parcel.current_holder,note='Audited exception correction: '+note)
    if any(k in data for k in ("origin_station","destination_station")):
        if parcel.status!="booked" or parcel.tasks.filter(status__in=("offered","accepted")).exists() or parcel.trip_id:raise ValidationError("Station corrections require unassigned booked custody.")
        origin=data.get("origin_station",parcel.origin_station);destination=data.get("destination_station",parcel.destination_station)
        from .workflows import require_pilot
        require_pilot(origin,destination)
        if origin==destination:raise ValidationError("Stations must differ.")
        from .services import lookup_rate
        rate=lookup_rate(origin,destination,parcel.weight_band)
        if not rate or rate.price!=parcel.price:raise ValidationError('Correction changes the quoted price. Cancel and rebook rather than overwrite financial records.')
    before={k:str(getattr(parcel,k)) for k in data}
    for key,value in data.items():setattr(parcel,key,value)
    parcel.save(update_fields=list(data))
    audit(actor,"parcel_override",f"parcel:{parcel.pk}",note,before,{k:str(v) for k,v in data.items()})
    return parcel

@transaction.atomic
def partner_action(profile,actor,data):
    if not has_role(actor,"ops","admin"):raise PermissionDenied()
    profile=type(profile).objects.select_for_update().get(pk=profile.pk)
    action=data["action"]
    if action=="suspend":
        profile.suspended=True
        if isinstance(profile,Rider):profile.available=False
        if Task.objects.filter(assigned_to=profile.user,status="accepted").exists():raise ValidationError("Reassign active accepted work before suspension.")
        Task.objects.filter(assigned_to=profile.user,status="offered").update(status="declined")
        if isinstance(profile,Carrier):profile.trips.filter(active=True).update(active=False)
    elif action=="reverify":
        if Task.objects.filter(assigned_to=profile.user,status="accepted").exists():raise ValidationError("Reassign active accepted work before re-verification.")
        profile.reverification_required=True;profile.status="pending"
    else:
        if not profile.document or (profile.document_expires_at and profile.document_expires_at<timezone.localdate()):raise ValidationError("A current document is required before reactivation.")
        profile.suspended=False;profile.reverification_required=False;profile.status="approved"
    profile.review_note=data["note"];profile.save();audit(actor,"partner_"+action,f"{profile._meta.model_name}:{profile.pk}",data["note"]);return profile
