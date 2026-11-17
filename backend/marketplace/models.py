import secrets
from datetime import time
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

class User(AbstractUser):
    class Role(models.TextChoices):
        CUSTOMER="customer","Customer"; RIDER="rider","Rider"; CARRIER="carrier","Carrier"; STATION_OPERATOR="station_operator","Station operator"; OPS="ops","Ops"; FINANCE="finance","Finance"; SUPPORT="support","Support"; ADMIN="admin","Admin"
    role=models.CharField(max_length=24, choices=Role.choices, default=Role.CUSTOMER, db_index=True)
    phone=models.CharField(max_length=24, unique=True); name=models.CharField(max_length=160); verified=models.BooleanField(default=False)

class City(models.Model):
    name=models.CharField(max_length=100); province=models.CharField(max_length=100)
    class Meta: ordering=("name",); constraints=[models.UniqueConstraint(fields=("name","province"), name="unique_city_region")]
    def __str__(self): return f"{self.name}, {self.province}"

class Station(models.Model):
    contact_phone=models.CharField(max_length=24,blank=True)
    opening_hours=models.JSONField(default=dict,blank=True)
    service_status=models.CharField(max_length=16,default="open",choices=(("open","Open"),("limited","Limited"),("closed","Closed")))
    holding_capacity=models.PositiveIntegerField(null=True,blank=True)
    name=models.CharField(max_length=140); city=models.ForeignKey(City, on_delete=models.PROTECT, related_name="stations"); address=models.TextField(); latitude=models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True); longitude=models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True); operator=models.ForeignKey(User, on_delete=models.PROTECT, related_name="operated_stations"); active=models.BooleanField(default=True, db_index=True); payment_number=models.CharField(max_length=32)
    class Meta: indexes=[models.Index(fields=("city","active"))]
    def __str__(self): return self.name

class ApprovalStatus(models.TextChoices): PENDING="pending","Pending"; APPROVED="approved","Approved"; REJECTED="rejected","Rejected"
class Carrier(models.Model):
    suspended=models.BooleanField(default=False,db_index=True)
    document_expires_at=models.DateField(null=True,blank=True)
    reverification_required=models.BooleanField(default=False)
    vehicle_registration=models.CharField(max_length=32,blank=True)
    capacity_m3=models.DecimalField(max_digits=9,decimal_places=4,null=True,blank=True)
    review_note=models.TextField(blank=True)
    user=models.OneToOneField(User,on_delete=models.CASCADE,related_name="carrier_profile"); vehicle_type=models.CharField(max_length=80); licence_no=models.CharField(max_length=80,unique=True); capacity_kg=models.DecimalField(max_digits=9,decimal_places=2); status=models.CharField(max_length=12,choices=ApprovalStatus.choices,default=ApprovalStatus.PENDING,db_index=True); document=models.FileField(upload_to="onboarding/",blank=True)
class Rider(models.Model):
    suspended=models.BooleanField(default=False,db_index=True)
    document_expires_at=models.DateField(null=True,blank=True)
    reverification_required=models.BooleanField(default=False)
    review_note=models.TextField(blank=True)
    user=models.OneToOneField(User,on_delete=models.CASCADE,related_name="rider_profile"); home_station=models.ForeignKey(Station,on_delete=models.PROTECT,related_name="riders"); status=models.CharField(max_length=12,choices=ApprovalStatus.choices,default=ApprovalStatus.PENDING,db_index=True); available=models.BooleanField(default=False); document=models.FileField(upload_to="onboarding/",blank=True)

class RateTableEntry(models.Model):
    origin_city=models.ForeignKey(City,on_delete=models.CASCADE,related_name="rates_from"); destination_city=models.ForeignKey(City,on_delete=models.CASCADE,related_name="rates_to"); weight_band=models.CharField(max_length=32); price=models.DecimalField(max_digits=10,decimal_places=2); station_override=models.ForeignKey(Station,on_delete=models.CASCADE,null=True,blank=True,related_name="rate_overrides")
    class Meta:
        constraints=[models.UniqueConstraint(fields=("origin_city","destination_city","weight_band","station_override"),name="unique_rate_rule"),models.UniqueConstraint(fields=("origin_city","destination_city","weight_band"),condition=models.Q(station_override__isnull=True),name="unique_default_rate_rule")]
        indexes=[models.Index(fields=("origin_city","destination_city","weight_band"))]

class Parcel(models.Model):
    description=models.CharField(max_length=500,blank=True)
    contents_category=models.CharField(max_length=40,default="general")
    declared_value=models.DecimalField(max_digits=12,decimal_places=2,default=0)
    length_cm=models.DecimalField(max_digits=8,decimal_places=2,null=True,blank=True)
    width_cm=models.DecimalField(max_digits=8,decimal_places=2,null=True,blank=True)
    height_cm=models.DecimalField(max_digits=8,decimal_places=2,null=True,blank=True)
    pickup_latitude=models.DecimalField(max_digits=9,decimal_places=6,null=True,blank=True)
    pickup_longitude=models.DecimalField(max_digits=9,decimal_places=6,null=True,blank=True)
    delivery_latitude=models.DecimalField(max_digits=9,decimal_places=6,null=True,blank=True)
    delivery_longitude=models.DecimalField(max_digits=9,decimal_places=6,null=True,blank=True)
    location_instructions=models.TextField(blank=True)
    policy_snapshot=models.JSONField(default=dict,editable=False)
    duplicate_fingerprint=models.CharField(max_length=64,blank=True,db_index=True,editable=False)
    pickup_address=models.TextField(blank=True)
    sender_name=models.CharField(max_length=160,blank=True)
    sender_phone=models.CharField(max_length=24,blank=True)
    booked_by=models.ForeignKey(User,on_delete=models.PROTECT,null=True,related_name="booked_parcels")
    trip=models.ForeignKey("CarrierTrip",on_delete=models.PROTECT,null=True,blank=True,related_name="parcels")
    otp_expires_at=models.DateTimeField(null=True,blank=True)
    otp_target=models.CharField(max_length=32,blank=True)
    otp_attempts=models.PositiveSmallIntegerField(default=0)
    notes=models.TextField(blank=True)
    delivery_choice=models.CharField(max_length=12,choices=(("station","Station collection"),("home","Home delivery")),default="station")
    delivery_address=models.TextField(blank=True)
    class Status(models.TextChoices): BOOKED="booked","Booked"; PICKED_UP="picked_up","Picked up"; AT_ORIGIN="at_origin_station","At origin station"; IN_TRANSIT="in_transit","In transit"; AT_DESTINATION="at_destination_station","At destination station"; OUT_FOR_DELIVERY="out_for_delivery","Out for delivery"; DELIVERED="delivered","Delivered"; EXCEPTION="exception","Exception"; RETURNED="returned","Returned"; CANCELLED="cancelled","Cancelled"
    code=models.CharField(max_length=6,unique=True,db_index=True); sender=models.ForeignKey(User,on_delete=models.PROTECT,related_name="parcels"); recipient_name=models.CharField(max_length=160); recipient_phone=models.CharField(max_length=24); recipient_access_token=models.CharField(max_length=64,unique=True,default=secrets.token_urlsafe,editable=False); origin_station=models.ForeignKey(Station,on_delete=models.PROTECT,related_name="outbound_parcels"); destination_station=models.ForeignKey(Station,on_delete=models.PROTECT,related_name="inbound_parcels"); weight_band=models.CharField(max_length=32); price=models.DecimalField(max_digits=10,decimal_places=2,default=0); photo=models.ImageField(upload_to="parcels/",blank=True); status=models.CharField(max_length=32,choices=Status.choices,default=Status.BOOKED,db_index=True); current_holder=models.ForeignKey(User,on_delete=models.SET_NULL,null=True,blank=True,related_name="held_parcels"); assigned_carrier=models.ForeignKey(Carrier,on_delete=models.SET_NULL,null=True,blank=True,related_name="parcels"); assigned_rider=models.ForeignKey(Rider,on_delete=models.SET_NULL,null=True,blank=True,related_name="parcels"); handover_otp=models.CharField(max_length=128); created_at=models.DateTimeField(auto_now_add=True,db_index=True)

class Task(models.Model):
    class Type(models.TextChoices): FIRST_MILE="first_mile_pickup","First-mile pickup"; INTER_TOWN="inter_town_transport","Inter-town transport"; LAST_MILE="last_mile_delivery","Last-mile delivery"
    class Status(models.TextChoices): OFFERED="offered","Offered"; ACCEPTED="accepted","Accepted"; DECLINED="declined","Declined"; COMPLETED="completed","Completed"
    parcel=models.ForeignKey(Parcel,on_delete=models.CASCADE,related_name="tasks"); type=models.CharField(max_length=30,choices=Type.choices); assigned_to=models.ForeignKey(User,on_delete=models.PROTECT,related_name="tasks"); status=models.CharField(max_length=12,choices=Status.choices,default=Status.OFFERED,db_index=True); proof_photo=models.ImageField(upload_to="proof/",blank=True); signature=models.ImageField(upload_to="signatures/",blank=True)

class AppendOnlyQuerySet(models.QuerySet):
    def update(self,**kwargs): raise ValidationError("Status events are append-only.")
    def delete(self): raise ValidationError("Status events cannot be deleted.")

class StatusEvent(models.Model):
    released_by=models.ForeignKey(User,on_delete=models.PROTECT,null=True,blank=True,related_name="released_events")
    received_by=models.ForeignKey(User,on_delete=models.PROTECT,null=True,blank=True,related_name="received_events")
    recipient_confirmed=models.BooleanField(default=False)
    parcel=models.ForeignKey(Parcel,on_delete=models.PROTECT,related_name="events"); from_status=models.CharField(max_length=32); to_status=models.CharField(max_length=32); actor=models.ForeignKey(User,on_delete=models.PROTECT,null=True,related_name="status_events"); note=models.TextField(blank=True); otp_used=models.BooleanField(default=False); accepted=models.BooleanField(default=True); timestamp=models.DateTimeField(auto_now_add=True,db_index=True)
    class Meta: ordering=("timestamp",); indexes=[models.Index(fields=("parcel","timestamp"))]
    objects=AppendOnlyQuerySet.as_manager()
    def save(self,*args,**kwargs):
        if self.pk: raise ValidationError("Status events are append-only.")
        return super().save(*args,**kwargs)
    def delete(self,*args,**kwargs): raise ValidationError("Status events cannot be deleted.")

class Payment(models.Model):
    receipt_sha256=models.CharField(max_length=64,blank=True,db_index=True,editable=False)
    fraud_flags=models.JSONField(default=list,editable=False)
    transaction_reference=models.CharField(max_length=120,blank=True)
    class Status(models.TextChoices): PENDING="pending","Pending"; VERIFIED="verified","Verified"; REJECTED="rejected","Rejected"
    parcel=models.OneToOneField(Parcel,on_delete=models.PROTECT,related_name="payment"); amount=models.DecimalField(max_digits=10,decimal_places=2); method=models.CharField(max_length=40,default="mobile_money"); receipt_photo=models.ImageField(upload_to="receipts/",blank=True); status=models.CharField(max_length=12,choices=Status.choices,default=Status.PENDING,db_index=True); verified_by=models.ForeignKey(User,on_delete=models.PROTECT,null=True,blank=True); verified_at=models.DateTimeField(null=True,blank=True)

class Payout(models.Model):
    leg=models.CharField(max_length=16,blank=True,default="",choices=(("","Legacy/route"),("first_mile","First mile"),("last_mile","Last mile")))
    beneficiary=models.ForeignKey(User,on_delete=models.PROTECT,null=True,blank=True,related_name="payouts")
    approved_by=models.ForeignKey(User,on_delete=models.PROTECT,null=True,blank=True,related_name="approved_payouts")
    approved_at=models.DateTimeField(null=True,blank=True)
    disbursed_at=models.DateTimeField(null=True,blank=True)
    payment_reference=models.CharField(max_length=120,blank=True)
    class Recipient(models.TextChoices): RIDER="rider","Rider"; CARRIER="carrier","Carrier"; STATION="station","Station"; PLATFORM="platform","Platform"
    parcel=models.ForeignKey(Parcel,on_delete=models.PROTECT,related_name="payouts"); recipient=models.CharField(max_length=12,choices=Recipient.choices,db_index=True); period=models.CharField(max_length=20); amount=models.DecimalField(max_digits=10,decimal_places=2); status=models.CharField(max_length=20,default="pending",db_index=True); statement_url=models.URLField(blank=True)
    class Meta: constraints=[models.UniqueConstraint(fields=("parcel","recipient","leg","period"),name="unique_payout_leg")]

class SupportTicket(models.Model):
    raised_by=models.ForeignKey(User,on_delete=models.PROTECT,related_name="tickets"); parcel=models.ForeignKey(Parcel,on_delete=models.PROTECT,null=True,blank=True); subject=models.CharField(max_length=200); status=models.CharField(max_length=20,default="open",db_index=True); messages=models.JSONField(default=list); external_reference=models.CharField(max_length=120,blank=True); received_after_hours=models.BooleanField(default=False,editable=False); created_at=models.DateTimeField(auto_now_add=True,db_index=True)
    def save(self,*args,**kwargs):
        if not self.pk:
            local=timezone.localtime(); self.received_after_hours=not (time(8)<=local.time().replace(tzinfo=None)<time(20))
        super().save(*args,**kwargs)

class Notification(models.Model):
    message=models.TextField(blank=True)
    read_at=models.DateTimeField(null=True,blank=True)
    parcel=models.ForeignKey(Parcel,on_delete=models.PROTECT,related_name="notifications"); channel=models.CharField(max_length=8,choices=(("sms","SMS"),("push","Push"))); trigger_event=models.CharField(max_length=32); recipient_phone=models.CharField(max_length=24); sent_at=models.DateTimeField(null=True,blank=True); status=models.CharField(max_length=20,default="queued",db_index=True)

class Address(models.Model):
    latitude=models.DecimalField(max_digits=9,decimal_places=6,null=True,blank=True)
    longitude=models.DecimalField(max_digits=9,decimal_places=6,null=True,blank=True)
    instructions=models.TextField(blank=True)
    user=models.ForeignKey(User,on_delete=models.CASCADE,related_name="addresses")
    label=models.CharField(max_length=80)
    contact_name=models.CharField(max_length=160,blank=True)
    phone=models.CharField(max_length=24,blank=True)
    city=models.ForeignKey(City,on_delete=models.PROTECT)
    address=models.TextField()
    is_default=models.BooleanField(default=False)
    class Meta:
        constraints=[models.UniqueConstraint(fields=("user",),condition=models.Q(is_default=True),name="one_default_address_per_user")]

class PlatformSettings(models.Model):
    key=models.CharField(max_length=80,unique=True)
    value=models.JSONField(default=dict)

class PilotRoute(models.Model):
    name=models.CharField(max_length=120)
    origin_city=models.ForeignKey(City,on_delete=models.PROTECT,related_name="pilot_origins")
    destination_city=models.ForeignKey(City,on_delete=models.PROTECT,related_name="pilot_destinations")
    active=models.BooleanField(default=True)

class CarrierTrip(models.Model):
    capacity_m3=models.DecimalField(max_digits=9,decimal_places=4,null=True,blank=True)
    vehicle_registration=models.CharField(max_length=32,blank=True)
    carrier=models.ForeignKey(Carrier,on_delete=models.PROTECT,related_name="trips")
    origin_city=models.ForeignKey(City,on_delete=models.PROTECT,related_name="departures")
    destination_city=models.ForeignKey(City,on_delete=models.PROTECT,related_name="arrivals")
    departure_at=models.DateTimeField()
    capacity_kg=models.DecimalField(max_digits=9,decimal_places=2)
    active=models.BooleanField(default=True)
    class Meta:
        indexes=[models.Index(fields=("origin_city","destination_city","departure_at"))]

class PhoneChallenge(models.Model):
    phone=models.CharField(max_length=24,db_index=True)
    code_hash=models.CharField(max_length=128)
    name=models.CharField(max_length=160)
    role=models.CharField(max_length=24,default="customer")
    expires_at=models.DateTimeField()
    attempts=models.PositiveSmallIntegerField(default=0)
    used=models.BooleanField(default=False)
    created_at=models.DateTimeField(auto_now_add=True)

class IntegrationDelivery(models.Model):
    available_at=models.DateTimeField(default=timezone.now,db_index=True)
    kind=models.CharField(max_length=20,choices=(("sms","SMS"),("helpdesk","Helpdesk"),("event_log","Event log")))
    payload=models.JSONField(default=dict)
    status=models.CharField(max_length=20,default="queued",db_index=True)
    attempts=models.PositiveIntegerField(default=0)
    last_error=models.TextField(blank=True)
    external_reference=models.CharField(max_length=160,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    delivered_at=models.DateTimeField(null=True,blank=True)

class FinanceEvent(models.Model):
    actor=models.ForeignKey(User,on_delete=models.PROTECT)
    action=models.CharField(max_length=50)
    reference=models.CharField(max_length=100)
    details=models.JSONField(default=dict)
    created_at=models.DateTimeField(auto_now_add=True)
    objects=AppendOnlyQuerySet.as_manager()
    def save(self,*args,**kwargs):
        if self.pk: raise ValidationError("Finance events are append-only.")
        return super().save(*args,**kwargs)
    def delete(self,*args,**kwargs): raise ValidationError("Finance events are append-only.")

class MutationReceipt(models.Model):
    user=models.ForeignKey(User,on_delete=models.CASCADE)
    key=models.CharField(max_length=80)
    fingerprint=models.CharField(max_length=64)
    response=models.JSONField(default=dict)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta:
        constraints=[models.UniqueConstraint(fields=("user","key"),name="unique_user_mutation")]

class OperationalCase(models.Model):
    class Kind(models.TextChoices):
        CANCELLATION="cancellation","Cancellation"; RETURN="return","Return to sender"; FAILED_DELIVERY="failed_delivery","Failed delivery"; REFUND="refund","Refund"; LOSS="loss","Loss claim"; DAMAGE="damage","Damage claim"; DELAY="delay","Delay"; PAYMENT="payment","Payment problem"
    parcel=models.ForeignKey(Parcel,on_delete=models.PROTECT,related_name="operational_cases")
    kind=models.CharField(max_length=24,choices=Kind.choices,db_index=True)
    status=models.CharField(max_length=24,default="requested",db_index=True,choices=(("requested","Requested"),("approved","Approved"),("rejected","Rejected"),("in_progress","In progress"),("paid","Paid"),("resolved","Resolved")))
    reason=models.TextField()
    requested_by=models.ForeignKey(User,on_delete=models.PROTECT,related_name="requested_cases")
    assigned_to=models.ForeignKey(User,on_delete=models.PROTECT,null=True,blank=True,related_name="managed_cases")
    amount=models.DecimalField(max_digits=12,decimal_places=2,default=0)
    fee=models.DecimalField(max_digits=12,decimal_places=2,default=0)
    decision_note=models.TextField(blank=True)
    payment_reference=models.CharField(max_length=120,blank=True)
    policy_snapshot=models.JSONField(default=dict)
    return_stage=models.CharField(max_length=24,blank=True)
    return_trip=models.ForeignKey(CarrierTrip,on_delete=models.PROTECT,null=True,blank=True,related_name="return_cases")
    return_rider=models.ForeignKey(Rider,on_delete=models.PROTECT,null=True,blank=True)
    code_hash=models.CharField(max_length=128,blank=True,editable=False)
    code_target=models.CharField(max_length=24,blank=True,editable=False)
    code_expires_at=models.DateTimeField(null=True,blank=True,editable=False)
    code_attempts=models.PositiveSmallIntegerField(default=0,editable=False)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    class Meta:
        ordering=("-id",)
        permissions=(('approve_refund','Can approve refunds and parcel compensation'),('record_refund_payment','Can record external refund and compensation payments'))
        indexes=[models.Index(fields=("parcel","kind","status"))]
        constraints=[models.CheckConstraint(condition=models.Q(amount__gte=0,fee__gte=0),name="case_amounts_nonnegative"),models.UniqueConstraint(fields=('payment_reference',),condition=~models.Q(payment_reference=''),name='unique_case_payment_reference')]

class DeliveryAttempt(models.Model):
    parcel=models.ForeignKey(Parcel,on_delete=models.PROTECT,related_name="delivery_attempts")
    rider=models.ForeignKey(User,on_delete=models.PROTECT)
    outcome=models.CharField(max_length=24,choices=(("unavailable","Recipient unavailable"),("incorrect_address","Incorrect address"),("refused","Refused"),("unreachable","Unreachable")))
    note=models.TextField()
    next_action=models.CharField(max_length=24,choices=(("retry","Retry"),("contact","Contact recipient"),("return","Return to sender")))
    scheduled_at=models.DateTimeField(null=True,blank=True)
    latitude=models.DecimalField(max_digits=9,decimal_places=6,null=True,blank=True)
    longitude=models.DecimalField(max_digits=9,decimal_places=6,null=True,blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta: ordering=("-id",); indexes=[models.Index(fields=("parcel","created_at"))]

class CustodyEvidence(models.Model):
    parcel=models.ForeignKey(Parcel,on_delete=models.PROTECT,related_name="custody_evidence")
    case=models.ForeignKey(OperationalCase,on_delete=models.PROTECT,null=True,blank=True,related_name="evidence")
    event=models.ForeignKey(StatusEvent,on_delete=models.PROTECT,null=True,blank=True,related_name="evidence")
    uploaded_by=models.ForeignKey(User,on_delete=models.PROTECT)
    photo=models.ImageField(upload_to="custody-evidence/")
    condition=models.CharField(max_length=24,choices=(("intact","Intact"),("damaged","Damaged"),("missing","Contents missing"),("packaging","Packaging concern")))
    note=models.TextField(blank=True)
    created_at=models.DateTimeField(auto_now_add=True)
    class Meta: ordering=("-id",)

class AdminAudit(models.Model):
    actor=models.ForeignKey(User,on_delete=models.PROTECT,null=True)
    action=models.CharField(max_length=80,db_index=True)
    target=models.CharField(max_length=120,db_index=True)
    reason=models.TextField(blank=True)
    before=models.JSONField(default=dict)
    after=models.JSONField(default=dict)
    created_at=models.DateTimeField(auto_now_add=True,db_index=True)
    objects=AppendOnlyQuerySet.as_manager()
    class Meta: ordering=("-id",)
    def save(self,*args,**kwargs):
        if self.pk: raise ValidationError("Administrative audit is append-only.")
        super().save(*args,**kwargs)
    def delete(self,*args,**kwargs): raise ValidationError("Administrative audit is append-only.")
