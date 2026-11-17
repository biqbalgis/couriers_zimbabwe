from decimal import Decimal
from django.db.models import Q, Count
from django.http import HttpResponse
from django.utils import timezone
from django.utils.html import escape
from rest_framework import serializers, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied, ValidationError
from drf_spectacular.utils import extend_schema
from .models import *
from .views import visible_parcels, validated, FilteredViewSet
from .permissions import has_role, IsOps
from . import operations as service
from .serializers import ParcelSerializer

class CaseSerializer(serializers.ModelSerializer):
    parcel_code=serializers.CharField(source="parcel.code",read_only=True)
    amount=serializers.DecimalField(max_digits=12,decimal_places=2,min_value=0,required=False)
    class Meta:
        model=OperationalCase
        exclude=("code_hash","code_target","code_expires_at","code_attempts")
        read_only_fields=("requested_by","status","fee","assigned_to","decision_note","payment_reference","policy_snapshot","return_stage","return_trip","return_rider")

class DecisionSerializer(serializers.Serializer):
    action=serializers.ChoiceField(choices=("approve","reject","pay","resolve"))
    note=serializers.CharField(max_length=2000)
    amount=serializers.DecimalField(max_digits=12,decimal_places=2,min_value=0,required=False)
    reference=serializers.CharField(max_length=120,required=False,allow_blank=True)
    reconciliation_reference=serializers.CharField(max_length=120,required=False,allow_blank=True)

class ReturnSerializer(serializers.Serializer):
    action=serializers.ChoiceField(choices=("assign","code","confirm"))
    note=serializers.CharField(max_length=2000)
    trip=serializers.PrimaryKeyRelatedField(queryset=CarrierTrip.objects.all(),required=False)
    rider=serializers.PrimaryKeyRelatedField(queryset=Rider.objects.select_related("user","home_station"),required=False)
    otp=serializers.RegexField(r"^\d{6}$",required=False)
    photo=serializers.ImageField(required=False)
    condition=serializers.ChoiceField(choices=('intact','damaged','missing_packaging'),default='intact')

class AttemptSerializer(serializers.ModelSerializer):
    class Meta:model=DeliveryAttempt;fields="__all__";read_only_fields=("rider",)
    def validate(self,data):
        if (data.get("latitude") is None)!=(data.get("longitude") is None):raise serializers.ValidationError("Provide both coordinates.")
        if data.get("latitude") is not None and not (-90<=data["latitude"]<=90 and -180<=data["longitude"]<=180):raise serializers.ValidationError("Use EPSG:4326 coordinates.")
        if data.get("scheduled_at") and data["scheduled_at"]<=timezone.now():raise serializers.ValidationError("Retry time must be in the future.")
        if data.get("next_action")=="retry" and not data.get("scheduled_at"):raise serializers.ValidationError("A retry needs a scheduled time.")
        return data

class EvidenceSerializer(serializers.ModelSerializer):
    class Meta:model=CustodyEvidence;fields="__all__";read_only_fields=("uploaded_by",)
    def validate(self,data):
        if data.get("case") and data["case"].parcel_id!=data["parcel"].pk:raise serializers.ValidationError("Evidence case must belong to this parcel.")
        if data.get("event") and data["event"].parcel_id!=data["parcel"].pk:raise serializers.ValidationError("Evidence event must belong to this parcel.")
        return data

class AuditSerializer(serializers.ModelSerializer):
    actor_name=serializers.CharField(source="actor.name",read_only=True,default="System")
    class Meta:model=AdminAudit;fields="__all__"

class OperationalPolicySerializer(serializers.Serializer):
    version=serializers.CharField(max_length=40)
    reviewed=serializers.BooleanField()
    currency=serializers.ChoiceField(choices=("USD",))
    terms=serializers.CharField(max_length=10000)
    insurance_available=serializers.BooleanField()
    cancellation_before_pickup=serializers.DecimalField(max_digits=10,decimal_places=2,min_value=0)
    cancellation_assigned=serializers.DecimalField(max_digits=10,decimal_places=2,min_value=0)
    cancellation_after_pickup=serializers.DecimalField(max_digits=10,decimal_places=2,min_value=0)
    return_fee=serializers.DecimalField(max_digits=10,decimal_places=2,min_value=0)
    liability_limit=serializers.DecimalField(max_digits=12,decimal_places=2,min_value=0)
    max_length_cm=serializers.DecimalField(max_digits=8,decimal_places=2,min_value=Decimal("0.01"),allow_null=True)
    max_width_cm=serializers.DecimalField(max_digits=8,decimal_places=2,min_value=Decimal("0.01"),allow_null=True)
    max_height_cm=serializers.DecimalField(max_digits=8,decimal_places=2,min_value=Decimal("0.01"),allow_null=True)
    max_volume_m3=serializers.DecimalField(max_digits=9,decimal_places=4,min_value=Decimal("0.0001"),allow_null=True)
    dimensions_required=serializers.BooleanField()
    max_delivery_attempts=serializers.IntegerField(min_value=1,max_value=20)
    stale_after_hours=serializers.IntegerField(min_value=1,max_value=8760)
    prohibited_categories=serializers.ListField(child=serializers.CharField(max_length=40),max_length=100)
    restricted_categories=serializers.ListField(child=serializers.CharField(max_length=40),max_length=100)
    notifications=serializers.ListField(child=serializers.ChoiceField(choices=service.DEFAULT_POLICY["notifications"]),max_length=30)
    def validate_insurance_available(self,value):
        if value:raise serializers.ValidationError("No insurance provider contract is integrated. Do not advertise insurance.")
        return value

class ReasonSerializer(serializers.Serializer):
    note=serializers.CharField(max_length=2000)
    action=serializers.ChoiceField(choices=("suspend","reactivate","reverify"))

class FraudReviewSerializer(serializers.Serializer):
    note=serializers.CharField(max_length=2000)

@extend_schema(request=FraudReviewSerializer,responses=dict)
@api_view(('POST',))
def payment_fraud_review(request,pk):
    if not has_role(request.user,'ops','finance','admin'):raise PermissionDenied()
    from django.db import transaction
    from django.shortcuts import get_object_or_404
    note=validated(FraudReviewSerializer,request.data)['note']
    with transaction.atomic():
        payment=get_object_or_404(Payment.objects.select_for_update(),pk=pk)
        if payment.status!='pending' or not payment.fraud_flags:raise ValidationError('Only flagged pending evidence can be reviewed.')
        service.audit(request.user,'payment_fraud_review',f'payment:{pk}',note,before={'fraud_flags':payment.fraud_flags},after={'fraud_flags':[]})
        payment.fraud_flags=[];payment.save(update_fields=['fraud_flags'])
    return Response({'detail':'Flags reviewed. Verification remains a separate action.'})

class OverrideSerializer(serializers.Serializer):
    note=serializers.CharField(max_length=2000)
    restore_previous_status=serializers.BooleanField(required=False)
    recipient_name=serializers.CharField(max_length=160,required=False)
    recipient_phone=serializers.RegexField(r"^\+263\d{9}$",required=False)
    delivery_address=serializers.CharField(required=False,allow_blank=True)
    location_instructions=serializers.CharField(required=False,allow_blank=True)
    origin_station=serializers.PrimaryKeyRelatedField(queryset=Station.objects.filter(active=True,service_status__in=("open","limited")),required=False)
    destination_station=serializers.PrimaryKeyRelatedField(queryset=Station.objects.filter(active=True,service_status__in=("open","limited")),required=False)

class CaseViewSet(FilteredViewSet):
    http_method_names=("get","post","head","options")
    serializer_class=CaseSerializer;permission_classes=(IsAuthenticated,)
    filterset_fields=("kind","status","parcel")
    def get_queryset(self):
        if getattr(self,"swagger_fake_view",False):return OperationalCase.objects.none()
        return OperationalCase.objects.filter(parcel__in=visible_parcels(self.request.user)).select_related("parcel","requested_by","assigned_to").prefetch_related("evidence")
    def perform_create(self,serializer):
        data=dict(serializer.validated_data);parcel=data.pop("parcel")
        if not visible_parcels(self.request.user).filter(pk=parcel.pk).exists():raise PermissionDenied()
        serializer.instance=service.open_case(parcel,self.request.user,data)
    @extend_schema(request=DecisionSerializer)
    @action(detail=True,methods=("post",))
    def decide(self,request,pk=None):return Response(self.get_serializer(service.decide_case(self.get_object(),request.user,validated(DecisionSerializer,request.data))).data)
    @extend_schema(request=ReturnSerializer,responses=dict)
    @action(detail=True,methods=("post",),url_path="return-action")
    def return_action(self,request,pk=None):
        response=service.return_action(self.get_object(),request.user,validated(ReturnSerializer,request.data))
        return Response(response,status=400 if response.get("invalid") else 200)
    @action(detail=False)
    def export(self,request):
        if not has_role(request.user,"ops","finance","admin"):raise PermissionDenied()
        from .services import csv_response
        return csv_response(self.filter_queryset(self.get_queryset()),("id","parcel_id","kind","status","amount","fee","created_at"),"exceptions")

class AttemptViewSet(FilteredViewSet):
    serializer_class=AttemptSerializer;http_method_names=("get","post","head","options");filterset_fields=("parcel","outcome","rider")
    def get_queryset(self):
        if getattr(self,"swagger_fake_view",False):return DeliveryAttempt.objects.none()
        return DeliveryAttempt.objects.filter(parcel__in=visible_parcels(self.request.user)).select_related("rider","parcel")
    def perform_create(self,serializer):
        data=dict(serializer.validated_data);parcel=data.pop("parcel")
        if not visible_parcels(self.request.user).filter(pk=parcel.pk).exists():raise PermissionDenied()
        serializer.instance=service.record_attempt(parcel,self.request.user,data)

class EvidenceViewSet(FilteredViewSet):
    serializer_class=EvidenceSerializer;http_method_names=("get","post","head","options");filterset_fields=("parcel","case","condition")
    def get_queryset(self):
        if getattr(self,"swagger_fake_view",False):return CustodyEvidence.objects.none()
        return CustodyEvidence.objects.filter(parcel__in=visible_parcels(self.request.user)).select_related("parcel","uploaded_by","case","event")
    def perform_create(self,serializer):
        parcel=serializer.validated_data["parcel"]
        if not visible_parcels(self.request.user).filter(pk=parcel.pk).exists():raise PermissionDenied()
        if self.request.user.pk!=parcel.sender_id and not has_role(self.request.user,"ops","admin","station_operator") and not parcel.tasks.filter(assigned_to=self.request.user,status__in=("accepted","completed")).exists():raise PermissionDenied()
        serializer.save(uploaded_by=self.request.user)

class AdminAuditViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=AdminAudit.objects.select_related("actor");serializer_class=AuditSerializer;permission_classes=(IsOps,)
    filterset_fields=("action","target","actor")

@extend_schema(responses=dict,request=OperationalPolicySerializer)
@api_view(("GET","PUT"))
@permission_classes((AllowAny,))
def operational_policy(request):
    if request.method=="GET":return Response(service.policy())
    if not has_role(request.user,"admin"):raise PermissionDenied()
    value=validated(OperationalPolicySerializer,request.data)
    value={k:str(v) if isinstance(v,Decimal) else v for k,v in value.items()}
    before=service.policy();PlatformSettings.objects.update_or_create(key="operations-policy",defaults={"value":value})
    service.audit(request.user,"policy_update","operations-policy","Policy configuration",before,value)
    return Response(value)

@extend_schema(request=OverrideSerializer,responses=ParcelSerializer)
@api_view(("POST",))
def override_parcel(request,code):
    parcel=service.correct_parcel(code,request.user,validated(OverrideSerializer,request.data))
    return Response(ParcelSerializer(parcel,context={"request":request}).data)

@extend_schema(request=ReasonSerializer,responses=dict)
@api_view(("POST",))
def partner_lifecycle(request,kind,pk):
    from django.shortcuts import get_object_or_404
    model=Rider if kind=="riders" else Carrier if kind=="carriers" else None
    if not model:raise ValidationError("Unknown partner kind.")
    profile=service.partner_action(get_object_or_404(model,pk=pk),request.user,validated(ReasonSerializer,request.data))
    return Response({"status":profile.status,"suspended":profile.suspended,"reverification_required":profile.reverification_required})

@extend_schema(responses=bytes)
@api_view(("GET",))
def receipt(request,code):
    from django.shortcuts import get_object_or_404
    parcel=get_object_or_404(visible_parcels(request.user).select_related("sender"),code=code)
    payment=Payment.objects.filter(parcel=parcel).first()
    html=f'<!doctype html><html><meta charset="utf-8"><title>Booking confirmation {escape(code)}</title><h1>Pano Logistics booking confirmation</h1><p>Parcel {escape(code)}</p><p>Booked {escape(str(parcel.created_at))}</p><p>Sender: {escape(parcel.sender.name)}</p><p>Recipient: {escape(parcel.recipient_name)}</p><p>USD {escape(str(parcel.price))}</p><p>Payment status: {escape(payment.status if payment else "not recorded")}</p><p>Reference: {escape(payment.transaction_reference if payment else "")}</p><p>This is a booking/payment record, not a tax invoice or proof of unverified payment.</p></html>'
    response=HttpResponse(html,content_type="text/html");response["Content-Disposition"]=f'attachment; filename="booking-{code}.html"';return response

@extend_schema(responses=bytes)
@api_view(("GET",))
def operational_export(request,kind):
    if not has_role(request.user,"ops","admin"):raise PermissionDenied()
    from .services import csv_response
    catalog={"shipments":(visible_parcels(request.user),("code","sender_id","recipient_name","status","price","created_at")),"customers":(User.objects.filter(role="customer"),("id","name","phone","is_active")),"stations":(Station.objects.all(),("id","name","city_id","service_status","holding_capacity")),"carriers":(Carrier.objects.all(),("id","user_id","status","suspended","capacity_kg","capacity_m3")),"attempts":(DeliveryAttempt.objects.all(),("id","parcel_id","rider_id","outcome","next_action","created_at")),"audit":(AdminAudit.objects.all(),("id","actor_id","action","target","reason","created_at"))}
    if kind not in catalog:raise ValidationError("Unknown export kind.")
    queryset,fields=catalog[kind];service.audit(request.user,"data_export",kind,"Operational data export");return csv_response(queryset,fields,kind)

@extend_schema(responses=dict)
@api_view(("GET",))
def operational_metrics(request):
    if not has_role(request.user,"ops","finance","admin"):raise PermissionDenied()
    parcels=visible_parcels(request.user)
    return Response({"by_station":list(parcels.values("origin_station_id","origin_station__name").annotate(total=Count("id"),delivered=Count("id",filter=Q(status="delivered")),exceptions=Count("id",filter=Q(status="exception")),cancelled=Count("id",filter=Q(status="cancelled")))),"by_rider":list(DeliveryAttempt.objects.values("rider_id","rider__name").annotate(failed_attempts=Count("id"))),"by_carrier":list(parcels.values("assigned_carrier_id","assigned_carrier__user__name").annotate(total=Count("id"),delivered=Count("id",filter=Q(status="delivered")),exceptions=Count("id",filter=Q(status="exception")))),"open_cases":OperationalCase.objects.filter(status__in=("requested","approved","in_progress")).count()})

@extend_schema(responses=ParcelSerializer(many=True))
@api_view(('GET',))
def exception_inbox(request):
    from datetime import timedelta
    from django.db.models import Max, F
    from rest_framework.pagination import PageNumberPagination
    cutoff=timezone.now()-timedelta(hours=service.policy()['stale_after_hours'])
    parcels=visible_parcels(request.user).annotate(last_custody_at=Max('events__timestamp'),last_accepted_at=Max('events__timestamp',filter=Q(events__accepted=True)),last_rejected_at=Max('events__timestamp',filter=Q(events__accepted=False))).filter(
        Q(status='exception')|Q(operational_cases__status__in=('requested','approved','in_progress'))|
        (~Q(status__in=('delivered','returned','cancelled'))&(Q(payment__status='pending')|Q(last_rejected_at__gt=F('last_accepted_at'))|Q(last_rejected_at__isnull=False,last_accepted_at__isnull=True)))|
        (~Q(status__in=('delivered','returned','cancelled'))&Q(last_custody_at__lt=cutoff))
    ).distinct().order_by('last_custody_at','id')
    paginator=PageNumberPagination();paginator.page_size=20
    page=paginator.paginate_queryset(parcels,request)
    return paginator.get_paginated_response(ParcelSerializer(page,many=True,context={'request':request}).data)
