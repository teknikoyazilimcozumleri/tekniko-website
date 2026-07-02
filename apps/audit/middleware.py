from .models import AuditLog


class PIIAccessAuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.path.startswith("/api/gdpr/") or request.path.startswith("/api/pii/"):
            if request.user.is_authenticated:
                AuditLog.objects.create(
                    user=request.user,
                    action="PII_ACCESS",
                    path=request.path,
                    metadata={"method": request.method, "status_code": response.status_code},
                )
        return response
