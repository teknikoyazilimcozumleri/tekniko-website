from django.contrib import admin
from django.urls import include, path

from .api import api

urlpatterns = [
    path("admin/", admin.site.urls),
    

    path("api/v1/subscriptions/", include("apps.subscriptions.urls", namespace="subscriptions_api")),

    path("", include("apps.accounts.urls")),
    path("payments/", include("apps.payments.urls")),
    
    path("subscriptions/", include("apps.subscriptions.urls", namespace="subscriptions")),
    
    path("api/", api.urls),
]