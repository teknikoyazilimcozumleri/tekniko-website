from django.urls import path

from .views import protected_role_endpoint

urlpatterns = [
    path("rbac/protected/", protected_role_endpoint, name="rbac_protected"),
]
