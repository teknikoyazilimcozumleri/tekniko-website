import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache

from apps.rbac.models import Role
from apps.subscriptions.models import SubscriptionPlan


@pytest.fixture(autouse=True)
def clear_cache():
    cache.clear()


@pytest.fixture
def user(db):
    model = get_user_model()
    return model.objects.create_user(
        username="pytest_user",
        email="pytest@example.com",
        password="StrongPass123!",
    )


@pytest.fixture
def admin_role(db):
    return Role.objects.create(name="admin")


@pytest.fixture
def subscription_plan(db):
    """Subscription plan without Iyzico ref (from migration 0002; for testing error path)."""
    return SubscriptionPlan.objects.get(slug="basic")


@pytest.fixture
def subscription_plan_with_iyzico(db):
    """Subscription plan with Iyzico ref (from migration 0002, updated for mocking checkout)."""
    plan = SubscriptionPlan.objects.get(slug="pro")
    plan.iyzico_product_reference_code = "prod-1"
    plan.iyzico_pricing_plan_reference_code = "plan-1"
    plan.save(update_fields=["iyzico_product_reference_code", "iyzico_pricing_plan_reference_code"])
    return plan
