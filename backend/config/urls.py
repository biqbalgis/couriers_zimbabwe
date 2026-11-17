from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

urlpatterns = [path("admin/", admin.site.urls), path("api/auth/token/", TokenObtainPairView.as_view()), path("api/auth/token/refresh/", TokenRefreshView.as_view()), path("api/schema/", SpectacularAPIView.as_view(),name="schema"), path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema")), path("api/", include("marketplace.urls"))]
