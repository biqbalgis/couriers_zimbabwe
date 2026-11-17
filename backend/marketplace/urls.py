from django.urls import include,path
from rest_framework.routers import DefaultRouter
from .views import *
from .api_workflows import support_contact
from .operations_api import CaseViewSet,AttemptViewSet,EvidenceViewSet,AdminAuditViewSet,operational_policy,override_parcel,partner_lifecycle,receipt,operational_export,operational_metrics,payment_fraud_review
from .operations_api import exception_inbox
from .locations import location_search,location_config
from .api_workflows import TripViewSet,PilotViewSet,FinanceAuditViewSet,phone_request,phone_verify,recipient_preferences,recipient_code,dashboard,integration_status,private_file
r=DefaultRouter(); r.register("users",UserViewSet); r.register("carriers",CarrierViewSet,basename="carrier"); r.register("riders",RiderViewSet,basename="rider"); r.register("status-events",StatusEventViewSet); r.register("cities",CityViewSet); r.register("stations",StationViewSet); r.register("rates",RateViewSet); r.register("parcels",ParcelViewSet,basename="parcel"); r.register("tasks",TaskViewSet,basename="task"); r.register("payments",PaymentViewSet,basename="payment"); r.register("payouts",PayoutViewSet); r.register("support",SupportViewSet,basename="support"); r.register("notifications",NotificationViewSet,basename="notification"); r.register("onboarding",OnboardingViewSet,basename="onboarding"); r.register("matching",MatchingViewSet,basename="matching")
r.register("addresses",AddressViewSet,basename="address"); r.register("settings",SettingsViewSet)
urlpatterns=[path("support-contact/",support_contact)]
urlpatterns += [path('locations/search/',location_search),path('locations/config/',location_config)]
urlpatterns += [path('operations/inbox/',exception_inbox)]
r.register('operational-cases',CaseViewSet,basename='operational-case'); r.register('delivery-attempts',AttemptViewSet,basename='delivery-attempt'); r.register('custody-evidence',EvidenceViewSet,basename='custody-evidence'); r.register('admin-audit',AdminAuditViewSet,basename='admin-audit')
urlpatterns += [path('operations/policy/',operational_policy),path('operations/metrics/',operational_metrics),path('exports/<str:kind>/',operational_export),path('parcels/<str:code>/receipt/',receipt),path('parcels/<str:code>/override/',override_parcel),path('partners/<str:kind>/<int:pk>/lifecycle/',partner_lifecycle),path('payments/<int:pk>/fraud-review/',payment_fraud_review)]
r.register("trips",TripViewSet,basename="trip"); r.register("pilot-routes",PilotViewSet); r.register("finance-audit",FinanceAuditViewSet)
urlpatterns+=[path("",include(r.urls)),path("track/<str:token>/",public_track),path("track/<str:token>/preferences/",recipient_preferences),path("track/<str:token>/code/",recipient_code),path("reports/summary/",report_summary),path("earnings/",earnings),path("auth/phone/request/",phone_request),path("auth/phone/verify/",phone_verify),path("dashboard/",dashboard),path("integrations/status/",integration_status),path("files/<path:path>",private_file)]
