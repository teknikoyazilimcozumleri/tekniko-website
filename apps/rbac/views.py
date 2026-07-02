from django.http import JsonResponse

from .decorators import require_role


@require_role("admin", "support")
def protected_role_endpoint(request):
    # Example usage:
    # @require_role("admin")
    # def admin_only_endpoint(request):
    #     return JsonResponse({"detail": "only admin can access"})
    return JsonResponse({"status": "ok", "roles": [r.name for r in request.user.roles.all()]})
