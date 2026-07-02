from ninja import Router

from apps.accounts.jwt_utils import JWTAuthBearer

from .decorators import require_role

router = Router(tags=["rbac"])


@router.get("/rbac/protected/", auth=JWTAuthBearer())
@require_role("admin", "support")
def protected_role_endpoint(request):
    return {"status": "ok", "roles": [r.name for r in request.user.roles.all()]}
