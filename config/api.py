from ninja import NinjaAPI

from apps.accounts.api import router as accounts_router
from apps.payments.api import router as payments_router
from apps.rbac.api import router as rbac_router
from apps.subscriptions.api import router as subscriptions_router

api = NinjaAPI(title="TYC API")
api.add_router("", accounts_router)
api.add_router("", rbac_router)
api.add_router("", payments_router)
api.add_router("", subscriptions_router)
