from django.db import transaction
from django.db.models import Count, Q, Sum, Min, F
from django.http import HttpResponse
from django.utils.html import escape
from django.utils import timezone
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.generics import get_object_or_404
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from drf_spectacular.utils import extend_schema, extend_schema_view
from .models import *
from .permissions import *
from .serializers import *
from .services import create_parcel, csv_response, transition, verify_payment, record_payment, assign_parcel, respond_task, complete_task, set_default_address, reply_ticket, run_payout
from . import workflows

def validated(serializer_class,data):
    serializer=serializer_class(data=data); serializer.is_valid(raise_exception=True); return serializer.validated_data

def visible_parcels(user):
    qs=Parcel.objects.select_related("sender","payment","origin_station__city","destination_station__city","assigned_rider__user","assigned_carrier__user").prefetch_related("sender__user_permissions","events__actor","events__released_by","events__received_by")
    if not user.is_authenticated: return qs.none()
    if has_role(user,"ops","finance","support","admin"): return qs
    if has_role(user,"station_operator"): return qs.filter(Q(origin_station__operator=user)|Q(destination_station__operator=user))
    return qs.filter(Q(sender=user)|Q(current_holder=user)|Q(assigned_rider__user=user)|Q(assigned_carrier__user=user)|Q(tasks__assigned_to=user,tasks__status__in=("accepted","completed"))|Q(operational_cases__kind='return',operational_cases__return_rider__user=user)|Q(operational_cases__kind='return',operational_cases__return_trip__carrier__user=user)).distinct()

class FilteredViewSet(viewsets.ModelViewSet):
    filterset_fields="__all__"
    ordering=("-id",)
    @property
    def search_fields(self):
        model=self.get_serializer_class().Meta.model
        return {
            City:("name",), Station:("name","address","city__name"),
            Carrier:("user__name","vehicle_type","licence_no"), Rider:("user__name","home_station__name"),
            RateTableEntry:("origin_city__name","destination_city__name","weight_band"),
            Parcel:("code","recipient_name","recipient_phone","origin_station__city__name","destination_station__city__name"),
            Task:("parcel__code","type"), Payment:("parcel__code","transaction_reference"),
            Payout:("parcel__code","beneficiary__name","period"),
            SupportTicket:("subject",), Address:("label","address","city__name"),
        }.get(model,())
@extend_schema_view(me=extend_schema(request=ProfileSerializer,responses=ProfileSerializer))
class UserViewSet(viewsets.ModelViewSet):
    search_fields=("name","username","phone","role")
    ordering=("-id",)
    queryset=User.objects.prefetch_related('user_permissions'); serializer_class=UserSerializer; permission_classes=(IsOps,); filterset_fields=("role","verified")
    def get_permissions(self):
        if self.action=="me": return [IsAuthenticated()]
        if self.action in ("list","retrieve"): return [IsOps()]
        return [IsAdmin()]
    @action(detail=False,methods=("get","patch"),permission_classes=(IsAuthenticated,))
    def me(self,request):
        serializer=ProfileSerializer(request.user,data=request.data,partial=True) if request.method=="PATCH" else ProfileSerializer(request.user)
        if request.method=="PATCH": serializer.is_valid(raise_exception=True); serializer.save()
        return Response(serializer.data)
    def perform_destroy(self,instance):
        instance.is_active=False; instance.save(update_fields=("is_active",))
class CarrierViewSet(FilteredViewSet):
    serializer_class=CarrierSerializer; filterset_fields=("status","vehicle_type")
    def get_queryset(self):
        qs=Carrier.objects.select_related("user").prefetch_related('user__user_permissions')
        if getattr(self,"swagger_fake_view",False): return qs.none()
        return qs if has_role(self.request.user,"station_operator","ops","admin") else qs.filter(user=self.request.user)
    def get_permissions(self): return [IsAuthenticated()] if self.action in ("list","retrieve","create","partial_update","update") else [IsOps()]
    def perform_update(self,serializer):
        if serializer.instance.user_id!=self.request.user.pk and not has_role(self.request.user,"ops","admin"): raise serializers.ValidationError("Only the owner or operations can edit this application.")
        serializer.save(status="pending",review_note="")
    def perform_create(self,serializer):
        if self.request.user.role!="carrier" or Carrier.objects.filter(user=self.request.user).exists(): raise serializers.ValidationError("A carrier account without an existing profile is required.")
        serializer.save(user=self.request.user)
@extend_schema_view(availability=extend_schema(request=AvailabilitySerializer,responses=RiderSerializer))
class RiderViewSet(FilteredViewSet):
    serializer_class=RiderSerializer; filterset_fields=("status","available","home_station")
    def get_queryset(self):
        qs=Rider.objects.select_related("user","home_station").prefetch_related('user__user_permissions')
        if getattr(self,"swagger_fake_view",False): return qs.none()
        return qs if has_role(self.request.user,"station_operator","ops","admin") else qs.filter(user=self.request.user)
    def get_permissions(self): return [IsAuthenticated()] if self.action in ("list","retrieve","create","availability","partial_update","update") else [IsOps()]
    def perform_update(self,serializer):
        if serializer.instance.user_id!=self.request.user.pk and not has_role(self.request.user,"ops","admin"): raise serializers.ValidationError("Only the owner or operations can edit this application.")
        serializer.save(status="pending",review_note="")
    def perform_create(self,serializer):
        if self.request.user.role!="rider" or Rider.objects.filter(user=self.request.user).exists(): raise serializers.ValidationError("A rider account without an existing profile is required.")
        serializer.save(user=self.request.user)
    @action(detail=False,methods=("post",))
    def availability(self,request):
        try: rider=Rider.objects.get(user=request.user,status=ApprovalStatus.APPROVED)
        except Rider.DoesNotExist: return Response({"detail":"An approved rider profile is required."},status=403)
        rider.available=validated(AvailabilitySerializer,request.data)["available"]; rider.save(update_fields=("available",)); return Response(self.get_serializer(rider).data)
class StatusEventViewSet(viewsets.ReadOnlyModelViewSet):
    search_fields=("parcel__code","actor__name","note")
    ordering=("-id",)
    queryset=StatusEvent.objects.select_related("parcel","actor","released_by","received_by"); serializer_class=StatusEventSerializer; permission_classes=(IsStationOps,); filterset_fields=("parcel","accepted","to_status")
    def get_queryset(self): return super().get_queryset().filter(parcel__in=visible_parcels(self.request.user))
class CityViewSet(FilteredViewSet):
    queryset=City.objects.all(); serializer_class=CitySerializer; permission_classes=(RoleWriteOrReadOnly,)
    @action(detail=True)
    def stations(self,request,pk=None): return Response(StationSerializer(self.get_object().stations.filter(active=True),many=True).data)
class StationViewSet(FilteredViewSet):
    queryset=Station.objects.select_related("city","operator"); serializer_class=StationSerializer; permission_classes=(RoleWriteOrReadOnly,)
    filterset_fields=('city','operator','active','service_status')
class RateViewSet(FilteredViewSet):
    def get_permissions(self): return [AllowAny()] if self.action in ("list","retrieve","lookup") else [IsOpsOrFinance()]
    queryset=RateTableEntry.objects.select_related("origin_city","destination_city","station_override"); serializer_class=RateSerializer; permission_classes=(RoleWriteOrReadOnly,)
    @action(detail=False)
    def lookup(self,request):
        data=validated(RateLookupSerializer,request.query_params)
        origin=data["origin_station"]; destination=data["destination_station"]
        from .services import lookup_rate
        rate=lookup_rate(origin,destination,data["weight_band"])
        return Response(RateSerializer(rate).data if rate else {"detail":"Rate not found."},status=200 if rate else 404)
@extend_schema_view(handover=extend_schema(request=HandoverSerializer,responses=ParcelSerializer),mark_paid=extend_schema(request=PaymentRecordSerializer,responses=PaymentSerializer),delivery_choice=extend_schema(request=DeliverySerializer,responses=ParcelSerializer))
class ParcelViewSet(FilteredViewSet):
    http_method_names=("get","post","head","options")
    serializer_class=ParcelSerializer; lookup_field="code"; filterset_fields={"status":["exact"],"origin_station":["exact"],"destination_station":["exact"],"origin_station__city":["exact"],"destination_station__city":["exact"],"created_at":["date","gte","lte"]}
    def get_queryset(self):
        return visible_parcels(self.request.user)
    def perform_create(self,serializer):
        if not has_role(self.request.user,"customer","station_operator","ops","admin"): raise serializers.ValidationError("This role cannot book parcels.")
        if self.request.user.role=="station_operator" and serializer.validated_data["origin_station"].operator_id!=self.request.user.pk: raise serializers.ValidationError("Book from your own station.")
        serializer.instance=create_parcel(serializer.validated_data,self.request.user)
    @action(detail=True,methods=("post",))
    def handover(self,request,code=None):
        parcel=self.get_object(); data=validated(HandoverSerializer,request.data); target=data["to_status"]
        privileged=has_role(request.user,"station_operator","ops","admin")
        assigned=Task.objects.filter(parcel=parcel,assigned_to=request.user,status=Task.Status.ACCEPTED).first()
        if not privileged and not assigned: return Response({"detail":"Only the assigned field worker or station operations may perform this handover."},status=403)
        if assigned and not privileged: return Response({"detail":"Use the task completion endpoint to capture proof and enforce task order."},status=400)
        parcel=transition(parcel,request.user,target,data["otp"],data["note"],data.get('photo'))
        return Response(self.get_serializer(parcel).data)
    @extend_schema(request=CodeRequestSerializer,responses=dict)
    @action(detail=True,methods=("post",),url_path="handover-code")
    def handover_code(self,request,code=None):
        data=validated(CodeRequestSerializer,request.data)
        return Response(workflows.issue_handover_code(self.get_object(),data["to_status"],request.user))
    @extend_schema(request=NoteSerializer)
    @action(detail=True,methods=("post",))
    def cancel(self,request,code=None): return Response(self.get_serializer(workflows.cancel_parcel(self.get_object(),request.user,validated(NoteSerializer,request.data)["note"])).data)
    @extend_schema(request=NoteSerializer)
    @action(detail=True,methods=("post",))
    def exception(self,request,code=None): return Response(self.get_serializer(workflows.flag_exception(self.get_object(),request.user,validated(NoteSerializer,request.data)["note"])).data)
    @action(detail=True,methods=("post",),url_path="mark-paid")
    def mark_paid(self,request,code=None):
        parcel=self.get_object()
        if parcel.sender_id!=request.user.pk and not has_role(request.user,"station_operator","ops","admin") and not parcel.tasks.filter(assigned_to=request.user,status="accepted").exists(): return Response({"detail":"You cannot record this payment."},status=403)
        payment=record_payment(parcel,validated(PaymentRecordSerializer,request.data)); return Response(PaymentSerializer(payment).data)
    @action(detail=True,methods=("post",),url_path="delivery-choice")
    def delivery_choice(self,request,code=None):
        parcel=self.get_object()
        if parcel.sender_id!=request.user.pk: return Response({"detail":"Only the sender may change delivery preferences."},status=403)
        if parcel.status in ("delivered","returned","cancelled","out_for_delivery"): return Response({"detail":"Delivery preferences are locked for this journey."},status=400)
        data=validated(DeliverySerializer,request.data); parcel.delivery_choice=data["choice"]; parcel.delivery_address=data["address"]; parcel.save(update_fields=("delivery_choice","delivery_address")); return Response(self.get_serializer(parcel).data)
    @extend_schema(request=ExceptionResolutionSerializer,responses=ParcelSerializer)
    @action(detail=True,methods=("post",),url_path="resolve-exception",permission_classes=(IsStationOps,))
    def resolve_exception(self,request,code=None):
        parcel=self.get_object(); data=validated(ExceptionResolutionSerializer,request.data)
        if parcel.status!="exception": raise serializers.ValidationError("This parcel is not in exception status.")
        return Response(self.get_serializer(transition(parcel,request.user,"returned",data["otp"],data["note"])).data)
@extend_schema_view(accept=extend_schema(request=None),decline=extend_schema(request=None),complete=extend_schema(request=TaskCompletionSerializer),proof=extend_schema(request=TaskCompletionSerializer))
class TaskViewSet(FilteredViewSet):
    http_method_names=("get","post","head","options")
    serializer_class=TaskSerializer; filterset_fields=("status","type","parcel")
    def get_queryset(self):
        qs=Task.objects.select_related("parcel__origin_station__city","parcel__destination_station__city","parcel__sender","parcel__payment","assigned_to").prefetch_related("parcel__sender__user_permissions","parcel__events__actor","parcel__events__released_by","parcel__events__received_by")
        if getattr(self,"swagger_fake_view",False): return qs.none()
        return qs.filter(parcel__in=visible_parcels(self.request.user)) if has_role(self.request.user,"ops","admin","station_operator") else qs.filter(assigned_to=self.request.user)
    def get_permissions(self):
        return [IsStationOps()] if self.action in ("create","destroy") else [IsAuthenticated()]
    def perform_update(self,serializer):
        if has_role(self.request.user,"ops","admin","station_operator"): serializer.save()
        else: serializer.save(assigned_to=self.request.user,parcel=serializer.instance.parcel,type=serializer.instance.type)
    def perform_create(self,serializer): raise serializers.ValidationError("Create tasks through matching assignments.")
    @action(detail=True,methods=("post",))
    def accept(self,request,pk=None): return Response(self.get_serializer(respond_task(self.get_object(),request.user,True)).data)
    @action(detail=True,methods=("post",))
    def decline(self,request,pk=None): return Response(self.get_serializer(respond_task(self.get_object(),request.user,False)).data)
    @action(detail=True,methods=("post",))
    def complete(self,request,pk=None):
        task=self.get_object(); data=validated(TaskCompletionSerializer,request.data)
        def operation():
            if task.assigned_to_id!=request.user.pk or task.status!="accepted": raise serializers.ValidationError("Accept your assigned task first.")
            workflows.custody_transition(task.parcel,request.user,data["to_status"],data["otp"],proof_photo=data.get("proof_photo"),signature=data.get("signature"))
            task.refresh_from_db(); return self.get_serializer(task).data
        return Response(workflows.run_idempotent(request.user,request.headers.get("Idempotency-Key"),request.path,request.data,operation))
    @action(detail=True,methods=("post",))
    def proof(self,request,pk=None):
        task=self.get_object()
        if task.assigned_to_id!=request.user.pk or task.status!="accepted": return Response({"detail":"Proof requires your accepted task."},status=403)
        data=validated(TaskCompletionSerializer,{"otp":"000000",**request.data.dict()} if hasattr(request.data,"dict") else {"otp":"000000",**request.data})
        for key in ("proof_photo","signature"):
            if key in data: setattr(task,key,data[key])
        task.save(); return Response(self.get_serializer(task).data)
@extend_schema_view(verify=extend_schema(request=PaymentDecisionSerializer,responses=PaymentSerializer))
class PaymentViewSet(FilteredViewSet):
    http_method_names=("get","post","head","options")
    serializer_class=PaymentSerializer; filterset_fields=("status","method")
    def get_queryset(self):
        qs=Payment.objects.select_related("parcel","verified_by")
        if getattr(self,"swagger_fake_view",False): return qs.none()
        return qs if has_role(self.request.user,"ops","finance","admin") else qs.filter(parcel__sender=self.request.user)
    def get_permissions(self): return [IsOpsOrFinance()] if self.action in ("verify","export") else [IsAuthenticated()]
    @action(detail=True,methods=("post",))
    def verify(self,request,pk=None): return Response(self.get_serializer(verify_payment(self.get_object(),request.user,validated(PaymentDecisionSerializer,request.data)["status"])).data)
    def perform_create(self,serializer): raise serializers.ValidationError("Record payments through parcels/{code}/mark-paid/.")
    @action(detail=False)
    def export(self,request): return csv_response(self.filter_queryset(self.get_queryset()),("id","parcel_id","amount","method","status","verified_at"),"payments")
@extend_schema_view(run_payout=extend_schema(request=PayoutRunSerializer,responses=PayoutSerializer(many=True)))
class PayoutViewSet(FilteredViewSet):
    http_method_names=("get","post","head","options")
    def perform_create(self,serializer): raise serializers.ValidationError("Use payouts/run/ to create a balanced settlement.")
    queryset=Payout.objects.select_related("parcel"); serializer_class=PayoutSerializer; permission_classes=(IsOpsOrFinance,); filterset_fields=("recipient","period","status")
    def get_queryset(self):
        qs=super().get_queryset().select_related("beneficiary")
        return qs if has_role(self.request.user,"ops","finance","admin") else qs.filter(beneficiary=self.request.user)
    @action(detail=False)
    def export(self,request): return csv_response(self.filter_queryset(self.get_queryset()),("id","parcel_id","beneficiary_id","recipient","leg","period","amount","status","payment_reference","disbursed_at"),"payouts")
    @action(detail=False,methods=("post",),url_path="run")
    def run_payout(self,request):
        with transaction.atomic():
            rows=run_payout(validated(PayoutRunSerializer,request.data))
            workflows.audit(request.user,"payout_run",rows[0].parcel_id,period=rows[0].period)
        return Response(PayoutSerializer(rows,many=True).data,status=201)
    @extend_schema(request=SettlementSerializer)
    @action(detail=True,methods=("post",))
    def settle(self,request,pk=None): return Response(self.get_serializer(workflows.settle_payout(self.get_object(),request.user,validated(SettlementSerializer,request.data))).data)
    @action(detail=True,methods=("get",),permission_classes=(IsAuthenticated,))
    def statement(self,request,pk=None):
        payout=self.get_object()
        rows={"Parcel":payout.parcel.code,"Beneficiary":payout.beneficiary.name if payout.beneficiary else ('Platform' if payout.recipient=='platform' else 'Unassigned beneficiary'),"Leg":payout.get_leg_display(),"Period":payout.period,"Amount (USD)":payout.amount,"Status":payout.status,"Payment reference":payout.payment_reference or "Not disbursed"}
        response=HttpResponse('<!doctype html><html><head><meta charset="utf-8"><title>Pano payout statement</title></head><body><h1>Pano Logistics</h1><h2>Payout statement</h2>'+''.join(f'<p><strong>{escape(k)}</strong>: {escape(str(v))}</p>' for k,v in rows.items())+'</body></html>')
        response["Content-Disposition"]=f'attachment; filename="payout-{payout.pk}.html"'; return response
@extend_schema_view(reply=extend_schema(request=ReplySerializer),set_status=extend_schema(request=TicketStatusSerializer))
class SupportViewSet(FilteredViewSet):
    http_method_names=("get","post","head","options")
    serializer_class=SupportTicketSerializer; filterset_fields=("status","parcel","received_after_hours")
    def get_queryset(self):
        if getattr(self,"swagger_fake_view",False): return SupportTicket.objects.none()
        return SupportTicket.objects.all() if has_role(self.request.user,"support","ops","admin") else SupportTicket.objects.filter(raised_by=self.request.user)
    def perform_create(self,s):
        messages=s.validated_data.pop("messages",[])
        ticket=s.save(raised_by=self.request.user,messages=[{"body":str(m.get("body","")),"author":self.request.user.name,"user_id":self.request.user.pk,"created_at":timezone.now().isoformat()} for m in messages if isinstance(m,dict)])
        workflows.queue_helpdesk(ticket)
    @action(detail=True,methods=("post",))
    def reply(self,request,pk=None): return Response(self.get_serializer(reply_ticket(self.get_object(),request.user,validated(ReplySerializer,request.data)["body"])).data)
    @action(detail=True,methods=("post",),permission_classes=(IsSupport,),url_path="set-status")
    def set_status(self,request,pk=None):
        from .services import set_ticket_status
        ticket=set_ticket_status(self.get_object(),request.user,validated(TicketStatusSerializer,request.data)["status"])
        return Response(self.get_serializer(ticket).data)
    @action(detail=False,url_path="parcel-lookup",permission_classes=(IsSupport,))
    def parcel_lookup(self,request):
        try:p=Parcel.objects.prefetch_related("events").get(code=request.query_params.get("code"))
        except Parcel.DoesNotExist:return Response({"detail":"Parcel not found."},status=404)
        return Response(PublicParcelSerializer(p).data)
class NotificationViewSet(viewsets.ReadOnlyModelViewSet):
    search_fields=("message","trigger_event")
    ordering=("-id",)
    serializer_class=NotificationSerializer; filterset_fields=("status","channel","trigger_event")
    def get_queryset(self):
        if getattr(self,"swagger_fake_view",False) or not self.request.user.is_authenticated: return Notification.objects.none()
        return Notification.objects.select_related("parcel").filter(recipient_phone=self.request.user.phone)
    @action(detail=True,methods=("post",))
    def read(self,request,pk=None):
        notification=self.get_object(); notification.read_at=timezone.now(); notification.save(update_fields=("read_at",)); return Response(self.get_serializer(notification).data)
@extend_schema_view(approve=extend_schema(request=ApprovalSerializer),reject=extend_schema(request=ApprovalSerializer))
class OnboardingViewSet(viewsets.GenericViewSet):
    queryset=Carrier.objects.none()
    permission_classes=(IsOps,)
    serializer_class=CarrierSerializer
    @action(detail=True,methods=("post",))
    def approve(self,request,pk=None): return self._set(pk,"approved")
    @action(detail=True,methods=("post",))
    def reject(self,request,pk=None): return self._set(pk,"rejected")
    def _set(self,pk,value):
        data=validated(ApprovalSerializer,self.request.data)
        model=Carrier if data["type"]=="carrier" else Rider
        obj=get_object_or_404(model,pk=pk)
        if value=='approved' and not obj.document: raise serializers.ValidationError('An identity/operating document is required before approval.')
        obj.status=value; obj.review_note=data.get("reason",""); obj.save(update_fields=("status","review_note")); return Response({"id":obj.id,"status":value,"review_note":obj.review_note})
@extend_schema_view(assign=extend_schema(request=AssignmentSerializer))
class MatchingViewSet(viewsets.GenericViewSet):
    queryset=Parcel.objects.none()
    permission_classes=(IsStationOps,)
    serializer_class=ParcelSerializer
    @action(detail=False)
    def unmatched(self,request):
        station=validated(MatchingFilterSerializer,request.query_params).get("station"); qs=visible_parcels(request.user).filter(assigned_carrier__isnull=True).exclude(status__in=("delivered","returned","cancelled","exception"))
        if station: qs=qs.filter(Q(origin_station_id=station)|Q(destination_station_id=station))
        return Response(ParcelSerializer(qs,many=True).data)
    @action(detail=True,methods=("post",))
    def assign(self,request,pk=None):
        p=get_object_or_404(visible_parcels(request.user),pk=pk)
        return Response(ParcelSerializer(assign_parcel(p,validated(AssignmentSerializer,request.data))).data)

class AddressViewSet(FilteredViewSet):
    serializer_class=AddressSerializer
    def get_queryset(self): return Address.objects.select_related("city").filter(user=self.request.user) if self.request.user.is_authenticated else Address.objects.none()
    def perform_create(self,serializer): serializer.save(user=self.request.user)
    @action(detail=True,methods=("post",),url_path="set-default")
    def set_default(self,request,pk=None): return Response(self.get_serializer(set_default_address(self.get_object())).data)

class SettingsViewSet(FilteredViewSet):
    filterset_fields=("key",)
    queryset=PlatformSettings.objects.all(); serializer_class=SettingsSerializer; permission_classes=(IsAdmin,); lookup_field="key"

@extend_schema(responses=dict)
@api_view(("GET",))
def earnings(request):
    qs=Payout.objects.filter(beneficiary=request.user).select_related("beneficiary","parcel")
    return Response({"total":qs.aggregate(total=Sum("amount"))["total"] or 0,"completed_tasks":Task.objects.filter(assigned_to=request.user,status="completed").count(),"statements":PayoutSerializer(qs,many=True).data})

@extend_schema(responses=PublicParcelSerializer)
@api_view(("GET",))
@permission_classes((AllowAny,))
def public_track(request,token):
    try:p=Parcel.objects.prefetch_related("events").get(recipient_access_token=token)
    except Parcel.DoesNotExist:return Response({"detail":"Tracking link not found."},status=404)
    return Response(PublicParcelSerializer(p).data)
@extend_schema(responses=dict)
@api_view(("GET",))
@permission_classes((IsOpsOrFinance,))
def report_summary(request):
    parcels=visible_parcels(request.user)
    dispatched=parcels.annotate(dispatched_at=Min("events__timestamp",filter=Q(events__accepted=True,events__to_status="in_transit"))).filter(dispatched_at__isnull=False)
    verified=dispatched.filter(payment__status="verified",payment__verified_at__lte=F("dispatched_at")).count()
    last_mile=parcels.filter(events__accepted=True,events__to_status="out_for_delivery").distinct()
    first_success=last_mile.filter(status="delivered").exclude(events__to_status="exception").count()
    completed=parcels.filter(status="delivered"); complete=0
    for parcel in completed:
        confirmed={e.to_status for e in parcel.events.all() if e.accepted and e.otp_used}
        required={"at_origin_station","in_transit","at_destination_station","delivered"}
        if parcel.pickup_address: required.add("picked_up")
        if parcel.delivery_choice=="home": required.add("out_for_delivery")
        complete+=required.issubset(confirmed)
    return Response({"volumes":parcels.count(),"deliveries":completed.count(),"earnings":Payment.objects.filter(status="verified",parcel__in=parcels).aggregate(v=Sum("amount"))["v"] or 0,"payouts":Payout.objects.filter(status="paid",parcel__in=parcels).aggregate(v=Sum("amount"))["v"] or 0,"first_attempt_last_mile_success_rate":round(first_success/max(last_mile.count(),1)*100,1),"custody_record_completeness":round(complete/max(completed.count(),1)*100,1),"pre_dispatch_verification_rate":round(verified/max(dispatched.count(),1)*100,1),"metric_denominators":{"dispatched":dispatched.count(),"home_delivery_attempts":last_mile.count(),"delivered":completed.count()}})
