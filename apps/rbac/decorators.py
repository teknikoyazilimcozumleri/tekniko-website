from functools import wraps

from django.http import JsonResponse


def require_role(*required_roles):
    normalized = {role.lower() for role in required_roles}

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return JsonResponse({"detail": "Authentication required."}, status=401)

            user_roles = {role.name.lower() for role in request.user.roles.all()}
            if not normalized.intersection(user_roles):
                return JsonResponse({"detail": "Insufficient role permissions."}, status=403)

            return view_func(request, *args, **kwargs)

        return wrapped

    return decorator
