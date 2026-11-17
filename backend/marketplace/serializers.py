from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from rest_framework import serializers
from drf_spectacular.utils import extend_schema_field
from .models import *

class UserSerializer(serializers.ModelSerializer):
    password=serializers.CharField(write_only=True,required=False,min_length=8)
    operational_permissions=serializers.SlugRelatedField(source='user_permissions',slug_field='codename',many=True,required=False,queryset=Permission.objects.filter(content_type__app_label='marketplace',codename__in=('approve_refund','record_refund_payment')))
    def validate(self,attrs):
        role=attrs.get('role',getattr(self.instance,'role',None))
        permissions=attrs.get('user_permissions',list(self.instance.user_permissions.filter(codename__in=('approve_refund','record_refund_payment'))) if self.instance else [])
        if permissions and role not in ('ops','finance','support','admin'):raise serializers.ValidationError('Delegated financial permissions are restricted to operations, finance, support and administrator roles.')
        return attrs
    def create(self,validated_data):
        password=validated_data.pop("password",None)
        permissions=validated_data.pop('user_permissions',[])
        if not password: raise serializers.ValidationError({"password":"A password is required."})
        user=User.objects.create_user(password=password,**validated_data);user.user_permissions.set(permissions);return user
    def update(self,instance,validated_data):
        password=validated_data.pop("password",None)
        instance=super().update(instance,validated_data)
        if password: instance.set_password(password); instance.save(update_fields=("password",))
        return instance
    class Meta: model=get_user_model(); fields=("id","username","phone","name","role","verified","is_active","password","operational_permissions"); read_only_fields=("verified",)
class ProfileSerializer(serializers.ModelSerializer):
    operational_permissions=serializers.SlugRelatedField(source='user_permissions',slug_field='codename',many=True,read_only=True)
    class Meta: model=User; fields=("id","username","phone","name","role","verified","operational_permissions"); read_only_fields=("id","username","phone","role","verified","operational_permissions")
class CitySerializer(serializers.ModelSerializer):
    class Meta: model=City; fields="__all__"
class StationSerializer(serializers.ModelSerializer):
    city_name=serializers.CharField(source="city.name",read_only=True)
    def validate(self,attrs):
        latitude=attrs.get('latitude',getattr(self.instance,'latitude',None));longitude=attrs.get('longitude',getattr(self.instance,'longitude',None))
        if (latitude is None)!=(longitude is None) or latitude is not None and not(-90<=latitude<=90 and -180<=longitude<=180):raise serializers.ValidationError('Enter a valid EPSG:4326 coordinate pair.')
        hours=attrs.get('opening_hours')
        if hours is not None and (not isinstance(hours,dict) or any(not isinstance(k,str) or not isinstance(v,str) for k,v in hours.items())):raise serializers.ValidationError({'opening_hours':'Use an object mapping day names to opening-hour text.'})
        return attrs
    class Meta: model=Station; fields="__all__"
class CarrierSerializer(serializers.ModelSerializer):
    document=serializers.FileField(required=True)
    user_detail=UserSerializer(source="user",read_only=True)
    class Meta: model=Carrier; fields="__all__"; read_only_fields=("status","user","review_note","suspended","reverification_required")
    def validate_capacity_kg(self,value):
        if value<=0: raise serializers.ValidationError("Capacity must be positive.")
        return value
    def validate_capacity_m3(self,value):
        if value is not None and value<=0:raise serializers.ValidationError('Capacity must be positive.')
        return value
class RiderSerializer(serializers.ModelSerializer):
    document=serializers.FileField(required=True)
    home_station_name=serializers.CharField(source="home_station.name",read_only=True)
    user_detail=UserSerializer(source="user",read_only=True)
    class Meta: model=Rider; fields="__all__"; read_only_fields=("status","user","review_note","suspended","reverification_required")
class RateSerializer(serializers.ModelSerializer):
    origin_name=serializers.CharField(source="origin_city.name",read_only=True)
    destination_name=serializers.CharField(source="destination_city.name",read_only=True)
    station_name=serializers.CharField(source="station_override.name",read_only=True)
    def validate(self,attrs):
        origin=attrs.get("origin_city",getattr(self.instance,"origin_city",None))
        override=attrs.get("station_override",getattr(self.instance,"station_override",None))
        if override and override.city_id!=origin.pk: raise serializers.ValidationError({"station_override":"Override must belong to the origin city."})
        return attrs
    def validate_price(self,value):
        if value<=0: raise serializers.ValidationError("Price must be positive.")
        return value
    class Meta: model=RateTableEntry; fields="__all__"
class StatusEventSerializer(serializers.ModelSerializer):
    parcel_code=serializers.CharField(source="parcel.code",read_only=True)
    released_by_name=serializers.CharField(source="released_by.name",read_only=True,default="Sender")
    received_by_name=serializers.CharField(source="received_by.name",read_only=True,default="Recipient")
    actor_name=serializers.CharField(source="actor.name",read_only=True)
    class Meta: model=StatusEvent; fields="__all__"; read_only_fields=("id","parcel","from_status","to_status","actor","note","otp_used","accepted","timestamp")
class ParcelSerializer(serializers.ModelSerializer):
    photo=serializers.ImageField(required=True)
    weight_band=serializers.ChoiceField(choices=("0-2kg","2-5kg","5-10kg"))
    recipient_phone=serializers.RegexField(r"^\+263[0-9]{9}$")
    sender_phone=serializers.RegexField(r"^\+263[0-9]{9}$",required=False,allow_blank=True)
    payment=serializers.SerializerMethodField()
    sender_detail=ProfileSerializer(source="sender",read_only=True)
    next_steps=serializers.SerializerMethodField()
    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_payment(self,obj):
        payment=getattr(obj,"payment",None)
        return {"id":payment.pk,"status":payment.status,"amount":str(payment.amount),"receipt_photo":payment.receipt_photo.url if payment.receipt_photo else None} if payment else None
    @extend_schema_field(serializers.ListField(child=serializers.CharField()))
    def get_next_steps(self,obj):
        from .workflows import NEXT
        if obj.status=="booked": return ["picked_up"] if obj.pickup_address else ["at_origin_station"]
        if obj.status=="at_destination_station": return ["out_for_delivery"] if obj.delivery_choice=="home" else ["delivered"]
        return list(NEXT.get(obj.status,()))
    def to_representation(self,instance):
        data=super().to_representation(instance)
        data.pop("handover_otp",None)
        data.pop("otp_expires_at",None); data.pop("otp_target",None); data.pop("otp_attempts",None)
        user=getattr(self.context.get("request"),"user",None)
        if not user or instance.sender_id!=user.pk: data.pop("recipient_access_token",None)
        return data
    def validate(self,attrs):
        request=self.context.get('request')
        if not self.instance and request and request.user.role in ('station_operator','ops','admin'):
            if not attrs.get('sender_phone') or not attrs.get('sender_name'):
                raise serializers.ValidationError('Station-assisted bookings require the customer name and phone.')
            existing=User.objects.filter(phone=attrs['sender_phone']).first()
            if existing and existing.role!='customer': raise serializers.ValidationError('Select a customer phone, not a staff or worker account.')
        for field in ("origin_station","destination_station"):
            if field in attrs and not attrs[field].active: raise serializers.ValidationError({field:"Station is inactive."})
        if attrs.get("origin_station") and attrs.get("origin_station")==attrs.get("destination_station"): raise serializers.ValidationError("Select different origin and destination stations.")
        from .operations import validate_booking
        validate_booking(attrs)
        if attrs.get('declared_value',0)<0: raise serializers.ValidationError({'declared_value':'Declared value cannot be negative.'})
        if attrs.get('delivery_choice')=='home' and not attrs.get('delivery_address','').strip():raise serializers.ValidationError({'delivery_address':'Home delivery requires a full address.'})
        return attrs
    events=StatusEventSerializer(many=True,read_only=True); origin_station_detail=StationSerializer(source="origin_station",read_only=True); destination_station_detail=StationSerializer(source="destination_station",read_only=True)
    class Meta: model=Parcel; fields="__all__"; read_only_fields=("code","recipient_access_token","status","price","current_holder","assigned_carrier","assigned_rider","handover_otp","sender","booked_by","trip","otp_expires_at","otp_target","otp_attempts","policy_snapshot","duplicate_fingerprint")
class PublicEventSerializer(serializers.ModelSerializer):
    class Meta: model=StatusEvent; fields=("to_status","timestamp")
class PublicStationSerializer(serializers.ModelSerializer):
    class Meta: model=Station; fields=("id","name","address","city","latitude","longitude")
class PublicParcelSerializer(serializers.ModelSerializer):
    events=serializers.SerializerMethodField(); destination_station=PublicStationSerializer(read_only=True)
    @extend_schema_field(PublicEventSerializer(many=True))
    def get_events(self,obj): return PublicEventSerializer([e for e in obj.events.all() if e.accepted],many=True).data
    class Meta: model=Parcel; fields=("code","recipient_name","status","destination_station","events","delivery_choice","delivery_address")
class TaskSerializer(serializers.ModelSerializer):
    parcel_detail=ParcelSerializer(source="parcel",read_only=True)
    class Meta: model=Task; fields="__all__"
class PaymentSerializer(serializers.ModelSerializer):
    parcel_code=serializers.CharField(source="parcel.code",read_only=True)
    class Meta: model=Payment; fields="__all__"; read_only_fields=("status","verified_by","verified_at","receipt_sha256","fraud_flags")
class PayoutSerializer(serializers.ModelSerializer):
    beneficiary_name=serializers.SerializerMethodField()
    def get_beneficiary_name(self,obj) -> str:
        return obj.beneficiary.name if obj.beneficiary_id else ('Platform' if obj.recipient=='platform' else 'Unassigned beneficiary')
    parcel_code=serializers.CharField(source="parcel.code",read_only=True)
    class Meta: model=Payout; fields="__all__"
class SupportTicketSerializer(serializers.ModelSerializer):
    parcel_code=serializers.CharField(write_only=True,required=False,allow_blank=True)
    class Meta: model=SupportTicket; fields="__all__"; read_only_fields=("raised_by","received_after_hours","created_at","external_reference","status")
    def validate(self,attrs):
        code=attrs.pop("parcel_code","")
        if code:
            try: attrs["parcel"]=Parcel.objects.get(code=code)
            except Parcel.DoesNotExist: raise serializers.ValidationError({"parcel_code":"Parcel not found."})
        parcel=attrs.get("parcel")
        user=self.context["request"].user
        if parcel and user.role not in ("ops","admin","support") and parcel.sender_id!=user.pk and not parcel.tasks.filter(assigned_to=user).exists(): raise serializers.ValidationError({"parcel":"Choose a parcel you sent or are assigned to."})
        return attrs
class NotificationSerializer(serializers.ModelSerializer):
    parcel_code=serializers.CharField(source="parcel.code",read_only=True)
    class Meta: model=Notification; fields="__all__"; read_only_fields=("id","parcel","channel","trigger_event","recipient_phone","sent_at","status")

class AddressSerializer(serializers.ModelSerializer):
    city_name=serializers.CharField(source="city.name",read_only=True)
    def validate(self,attrs):
        lat=attrs.get('latitude',getattr(self.instance,'latitude',None));lon=attrs.get('longitude',getattr(self.instance,'longitude',None))
        if (lat is None)!=(lon is None) or lat is not None and not(-90<=lat<=90 and -180<=lon<=180):raise serializers.ValidationError('Enter a valid EPSG:4326 coordinate pair.')
        return attrs
    class Meta: model=Address; fields="__all__"; read_only_fields=("user","is_default")
class SettingsSerializer(serializers.ModelSerializer):
    def validate(self,attrs):
        if attrs.get('key',getattr(self.instance,'key',None))=='operations-policy':raise serializers.ValidationError('Use the validated operations/policy endpoint to configure parcel policy.')
        return attrs
    class Meta: model=PlatformSettings; fields="__all__"
class AvailabilitySerializer(serializers.Serializer):
    available=serializers.BooleanField()
class HandoverSerializer(serializers.Serializer):
    photo=serializers.ImageField(required=False)
    to_status=serializers.ChoiceField(choices=Parcel.Status.choices)
    otp=serializers.RegexField(r"^\d{6}$")
    note=serializers.CharField(required=False,allow_blank=True,default="")
class DeliverySerializer(serializers.Serializer):
    choice=serializers.ChoiceField(choices=("station","home"))
    address=serializers.CharField(required=False,allow_blank=True,default="")
    def validate(self,attrs):
        if attrs["choice"]=="home" and not attrs["address"].strip(): raise serializers.ValidationError({"address":"Home delivery requires an address."})
        return attrs
class ReplySerializer(serializers.Serializer):
    body=serializers.CharField(max_length=5000)
class TicketStatusSerializer(serializers.Serializer):
    status=serializers.ChoiceField(choices=("open","waiting_customer","resolved","closed"))
class ApprovalSerializer(serializers.Serializer):
    type=serializers.ChoiceField(choices=("rider","carrier"))
    reason=serializers.CharField(required=False,allow_blank=True)
class AssignmentSerializer(serializers.Serializer):
    trip=serializers.PrimaryKeyRelatedField(queryset=CarrierTrip.objects.filter(active=True),required=False)
    carrier=serializers.PrimaryKeyRelatedField(queryset=Carrier.objects.filter(status="approved"),required=False)
    rider=serializers.PrimaryKeyRelatedField(queryset=Rider.objects.filter(status="approved"),required=False)
    def validate(self,attrs):
        if not attrs: raise serializers.ValidationError("Select a rider or carrier.")
        return attrs
class PaymentRecordSerializer(serializers.Serializer):
    method=serializers.ChoiceField(choices=("mobile_money","cash","bank_transfer"),default="mobile_money")
    receipt_photo=serializers.ImageField()
    transaction_reference=serializers.CharField(required=False,allow_blank=True,max_length=120)
class PaymentDecisionSerializer(serializers.Serializer):
    status=serializers.ChoiceField(choices=("verified","rejected"))
class PayoutRunSerializer(serializers.Serializer):
    parcel=serializers.PrimaryKeyRelatedField(queryset=Parcel.objects.all())
    period=serializers.RegexField(r"^\d{4}-(0[1-9]|1[0-2])$")
    rider=serializers.DecimalField(max_digits=10,decimal_places=2,min_value=0,required=False,default=0)
    first_mile_rider=serializers.DecimalField(max_digits=10,decimal_places=2,min_value=0,required=False)
    last_mile_rider=serializers.DecimalField(max_digits=10,decimal_places=2,min_value=0,required=False)
    carrier=serializers.DecimalField(max_digits=10,decimal_places=2,min_value=0)
    station=serializers.DecimalField(max_digits=10,decimal_places=2,min_value=0)
    def validate(self,attrs):
        if attrs['rider'] and ('first_mile_rider' in attrs or 'last_mile_rider' in attrs):
            raise serializers.ValidationError("Use either the legacy rider allocation or explicit first/last-mile allocations, not both.")
        return attrs
class TaskCompletionSerializer(serializers.Serializer):
    to_status=serializers.ChoiceField(choices=Parcel.Status.choices)
    otp=serializers.RegexField(r"^\d{6}$")
    proof_photo=serializers.ImageField(required=False)
    signature=serializers.ImageField(required=False)
class ExceptionResolutionSerializer(serializers.Serializer):
    resolution=serializers.ChoiceField(choices=("return",))
    otp=serializers.RegexField(r"^\d{6}$")
    note=serializers.CharField()
class RateLookupSerializer(serializers.Serializer):
    origin_station=serializers.PrimaryKeyRelatedField(queryset=Station.objects.filter(active=True))
    destination_station=serializers.PrimaryKeyRelatedField(queryset=Station.objects.filter(active=True))
    weight_band=serializers.ChoiceField(choices=("0-2kg","2-5kg","5-10kg"))
class MatchingFilterSerializer(serializers.Serializer):
    station=serializers.IntegerField(min_value=1,required=False)

class PhoneRequestSerializer(serializers.Serializer):
    phone=serializers.RegexField(r"^\+263[0-9]{9}$")
    name=serializers.CharField(max_length=160)
    role=serializers.ChoiceField(choices=("customer","rider","carrier"),default="customer")
class PhoneVerifySerializer(serializers.Serializer):
    challenge_id=serializers.IntegerField(min_value=1)
    code=serializers.RegexField(r"^\d{6}$")
class CodeRequestSerializer(serializers.Serializer):
    to_status=serializers.ChoiceField(choices=Parcel.Status.choices)
class NoteSerializer(serializers.Serializer):
    note=serializers.CharField(max_length=2000)
class SettlementSerializer(serializers.Serializer):
    action=serializers.ChoiceField(choices=("approve","disburse"))
    reference=serializers.CharField(max_length=120,required=False,allow_blank=True)
class TripSerializer(serializers.ModelSerializer):
    carrier_name=serializers.CharField(source="carrier.user.name",read_only=True)
    origin_name=serializers.CharField(source="origin_city.name",read_only=True)
    destination_name=serializers.CharField(source="destination_city.name",read_only=True)
    remaining_kg=serializers.SerializerMethodField()
    remaining_m3=serializers.SerializerMethodField()
    def get_remaining_m3(self,obj) -> str | None:
        from .operations import volume
        from .workflows import CLOSED
        if obj.capacity_m3 is None:return None
        parcels=[p for p in obj.parcels.all() if p.status not in CLOSED]+[c.parcel for c in self.capacity_returns(obj)]
        return str(obj.capacity_m3-sum((volume(p) for p in parcels),0))
    def get_remaining_kg(self,obj) -> str:
        from .workflows import BANDS,CLOSED
        return str(obj.capacity_kg-sum(BANDS.get(p.weight_band,0) for p in obj.parcels.all() if p.status not in CLOSED)-sum(BANDS[c.parcel.weight_band] for c in self.capacity_returns(obj)))
    def capacity_returns(self,obj):
        if not hasattr(obj,'capacity_returns'):
            obj.capacity_returns=list(obj.return_cases.filter(status__in=('approved','in_progress')).select_related('parcel'))
        return obj.capacity_returns
    def validate(self,attrs):
        from django.utils import timezone
        carrier=attrs.get("carrier",getattr(self.instance,"carrier",None))
        from .operations import eligible_partner
        if not carrier or not eligible_partner(carrier): raise serializers.ValidationError("A vetted carrier with current documents is required.")
        capacity=attrs.get('capacity_m3',getattr(self.instance,'capacity_m3',None))
        if capacity is not None and (capacity<=0 or carrier.capacity_m3 is None or capacity>carrier.capacity_m3):raise serializers.ValidationError('Trip volume must fit the declared vehicle volume.')
        if self.instance and (self.instance.parcels.exists() or self.instance.return_cases.filter(status__in=('approved','in_progress')).exists()): raise serializers.ValidationError("An assigned trip cannot be edited. Create another trip.")
        weight=attrs.get('capacity_kg',getattr(self.instance,'capacity_kg',0))
        if weight<=0 or weight>carrier.capacity_kg: raise serializers.ValidationError("Trip capacity must fit the carrier vehicle.")
        if attrs.get("departure_at",getattr(self.instance,'departure_at',timezone.now()))<=timezone.now(): raise serializers.ValidationError("Select a future departure time.")
        if attrs.get("origin_city",getattr(self.instance,'origin_city',None))==attrs.get("destination_city",getattr(self.instance,'destination_city',None)): raise serializers.ValidationError("Choose different towns.")
        return attrs
    class Meta: model=CarrierTrip; fields="__all__"
class PilotSerializer(serializers.ModelSerializer):
    origin_name=serializers.CharField(source="origin_city.name",read_only=True)
    destination_name=serializers.CharField(source="destination_city.name",read_only=True)
    class Meta: model=PilotRoute; fields="__all__"
class FinanceEventSerializer(serializers.ModelSerializer):
    class Meta: model=FinanceEvent; fields="__all__"
