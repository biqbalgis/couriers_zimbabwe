from django.conf import settings
from django.http import FileResponse
from django.core.files.storage import default_storage
from django.db.models import Q, Prefetch
from rest_framework import viewsets
from rest_framework.decorators import api_view, permission_classes, authentication_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework_simplejwt.tokens import RefreshToken
from drf_spectacular.utils import extend_schema

from .models import *
from .serializers import *
from .permissions import IsAdmin, IsOpsOrFinance, has_role
from .views import validated, visible_parcels
from . import workflows

class PhoneThrottle(AnonRateThrottle):
    rate="10/hour"

@extend_schema(request=PhoneRequestSerializer,responses=dict)
@api_view(("POST",))
@authentication_classes(())
@permission_classes((AllowAny,))
@throttle_classes((PhoneThrottle,))
def phone_request(request): return Response(workflows.request_phone_code(validated(PhoneRequestSerializer,request.data)))

@extend_schema(request=PhoneVerifySerializer,responses=dict)
@api_view(("POST",))
@authentication_classes(())
@permission_classes((AllowAny,))
@throttle_classes((PhoneThrottle,))
def phone_verify(request):
    user=workflows.verify_phone_code(validated(PhoneVerifySerializer,request.data))
    token=RefreshToken.for_user(user)
    return Response({"access":str(token.access_token),"refresh":str(token),"user":ProfileSerializer(user).data})

@extend_schema(request=DeliverySerializer,responses=PublicParcelSerializer)
@api_view(("GET","POST"))
@authentication_classes(())
@permission_classes((AllowAny,))
def recipient_preferences(request,token):
    from rest_framework.generics import get_object_or_404
    parcel=get_object_or_404(Parcel,recipient_access_token=token)
    if request.method=="POST":
        if parcel.status in (*workflows.CLOSED,"out_for_delivery"): raise ValidationError("Delivery preferences are locked.")
        data=validated(DeliverySerializer,request.data)
        parcel.delivery_choice=data["choice"]; parcel.delivery_address=data["address"]; parcel.save(update_fields=("delivery_choice","delivery_address"))
    return Response(PublicParcelSerializer(parcel).data)

@extend_schema(request=None,responses=dict)
@api_view(("POST",))
@authentication_classes(())
@permission_classes((AllowAny,))
def recipient_code(request,token):
    from rest_framework.generics import get_object_or_404
    parcel=get_object_or_404(Parcel,recipient_access_token=token)
    return Response(workflows.issue_handover_code(parcel,"delivered",recipient=True))

class TripViewSet(viewsets.ModelViewSet):
    search_fields=("origin_city__name","destination_city__name","carrier__user__name")
    ordering=("-departure_at",)
    serializer_class=TripSerializer
    filterset_fields=("carrier","origin_city","destination_city","active")
    http_method_names=("get","post","patch","head","options")
    def get_queryset(self):
        qs=CarrierTrip.objects.select_related("carrier__user","origin_city","destination_city").prefetch_related("parcels",Prefetch('return_cases',queryset=OperationalCase.objects.filter(status__in=('approved','in_progress')).select_related('parcel'),to_attr='capacity_returns'))
        if getattr(self,"swagger_fake_view",False): return qs.none()
        return qs.filter(carrier__user=self.request.user) if self.request.user.role=="carrier" else qs
    def perform_create(self,serializer):
        if not has_role(self.request.user,"carrier","ops","admin"): raise PermissionDenied()
        if self.request.user.role=="carrier" and serializer.validated_data["carrier"].user_id!=self.request.user.pk: raise PermissionDenied()
        serializer.save()
    def perform_update(self,serializer):
        if not has_role(self.request.user,"carrier","ops","admin"): raise PermissionDenied()
        if self.request.user.role=="carrier" and serializer.validated_data.get("carrier",serializer.instance.carrier).user_id!=self.request.user.pk: raise PermissionDenied()
        serializer.save()

class PilotViewSet(viewsets.ModelViewSet):
    queryset=PilotRoute.objects.select_related("origin_city","destination_city")
    serializer_class=PilotSerializer
    def get_permissions(self): return [AllowAny()] if self.action in ("list","retrieve") else [IsAdmin()]

class FinanceAuditViewSet(viewsets.ReadOnlyModelViewSet):
    queryset=FinanceEvent.objects.select_related("actor").order_by("-created_at")
    serializer_class=FinanceEventSerializer
    permission_classes=(IsOpsOrFinance,)

@extend_schema(responses=dict)
@api_view(("GET",))
def dashboard(request):
    parcels=visible_parcels(request.user)
    tasks=Task.objects.filter(assigned_to=request.user)
    tickets=SupportTicket.objects.all() if has_role(request.user,"ops","admin","support") else SupportTicket.objects.filter(raised_by=request.user)
    return Response({"parcels":parcels.count(),"in_transit":parcels.filter(status__in=("in_transit","out_for_delivery")).count(),"delivered":parcels.filter(status="delivered").count(),"exceptions":parcels.filter(status="exception").count(),"payment_pending":Payment.objects.filter(parcel__in=parcels,status="pending").count(),"offered_tasks":tasks.filter(status="offered").count(),"active_tasks":tasks.filter(status="accepted").count(),"open_tickets":tickets.exclude(status__in=("resolved","closed")).count(),"pilot":PilotSerializer(PilotRoute.objects.filter(active=True),many=True).data})

@extend_schema(responses=dict)
@api_view(("GET",))
@permission_classes((IsAdmin,))
def integration_status(request):
    return Response({"sms_mode":settings.SMS_DELIVERY_MODE,"sms_configured":bool(settings.SMS_WEBHOOK_URL and settings.SMS_WEBHOOK_TOKEN),"helpdesk_configured":bool(settings.HELPDESK_WEBHOOK_URL and settings.HELPDESK_WEBHOOK_TOKEN),"support_phone":settings.SUPPORT_PHONE,"support_hours":"08:00–20:00 Africa/Harare","helpdesk_url":settings.HELPDESK_PORTAL_URL,"queued":IntegrationDelivery.objects.filter(status="queued").count(),"deferred":IntegrationDelivery.objects.filter(status="queued",available_at__gt=timezone.now()).count(),"failed":IntegrationDelivery.objects.filter(status="failed").count(),"development":IntegrationDelivery.objects.filter(status="development").count()})

@extend_schema(responses=dict)
@api_view(("GET",))
@permission_classes((AllowAny,))
def support_contact(request):
    return Response({"phone":settings.SUPPORT_PHONE,"portal_url":settings.HELPDESK_PORTAL_URL,"hours":"08:00–20:00 Africa/Harare","after_hours":"After-hours reports queue until the next opening."})

@extend_schema(responses=bytes)
@api_view(("GET",))
def private_file(request,path):
    # Never expose receipts, signatures or identity documents through public media serving.
    allowed=has_role(request.user,"ops","admin")
    if not allowed:
        parcels=visible_parcels(request.user)
        allowed=parcels.filter(photo=path).exists() or Task.objects.filter(parcel__in=parcels).filter(Q(proof_photo=path)|Q(signature=path)).exists()
        allowed=allowed or Payment.objects.filter(receipt_photo=path,parcel__in=parcels).exists()
        from .models import CustodyEvidence
        allowed=allowed or CustodyEvidence.objects.filter(photo=path,parcel__in=parcels).exists()
        allowed=allowed or Carrier.objects.filter(user=request.user,document=path).exists() or Rider.objects.filter(user=request.user,document=path).exists()
    if not allowed: raise PermissionDenied()
    if not default_storage.exists(path):
        from rest_framework.exceptions import NotFound
        raise NotFound("This demo record has no uploaded file.")
    return FileResponse(default_storage.open(path,"rb"),as_attachment=True)
