from django.urls import path

from . import views

app_name = "subscriptions_api"

urlpatterns = [
    #path("", views.plan_list, name="plan_list"),
    path("plans/", views.plan_list, name="plan_list"),
    path("my/", views.my_subscriptions, name="my_subscriptions"),

    path("checkout/<int:plan_id>/", views.checkout_start, name="checkout_start"),
    path("checkout/form/", views.checkout_form, name="checkout_form"),
    path("checkout/form/public/", views.public_checkout_form, name="public_checkout_form"),
    path("callback/", views.subscription_callback, name="callback"),
    path("result/", views.subscription_result, name="result"),
    #path("my/", views.my_subscriptions, name="my_subscriptions"),
    path("webhook/", views.subscription_webhook, name="webhook"),
]
