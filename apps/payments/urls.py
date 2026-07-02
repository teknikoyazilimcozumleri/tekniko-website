from django.urls import path

from . import views

urlpatterns = [
    path("start/", views.payment_start, name="payment_start"),
    path("callback/", views.payment_callback, name="payment_callback"),
    path("result/", views.payment_result, name="payment_result"),
   ]
