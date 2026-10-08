"""Simple per-IP rate limiting for the HTML auth forms (login, admin login, signup, password reset).

The DRF throttles only cover /api/; these forms need their own guard against password guessing,
mass sign-ups and reset-email bombing.
"""
from functools import wraps

from django.core.cache import cache
from django.http import HttpResponse
from rest_framework.throttling import BaseThrottle

TOO_MANY = ("Too many attempts from your network. Please wait a few minutes and try again.")


def client_ip(request):
    # Reuses DRF's logic so REST_FRAMEWORK["NUM_PROXIES"] is honoured the same way everywhere.
    return BaseThrottle().get_ident(request)


def rate_limit(scope, limit, window, failures_only=False):
    """
    Allow `limit` POSTs per IP per `window` seconds. With failures_only, only POSTs that re-render
    the form (status 200, i.e. invalid credentials) count; successful logins redirect.
    """
    def decorator(view):
        @wraps(view)
        def wrapped(request, *args, **kwargs):
            if request.method != "POST":
                return view(request, *args, **kwargs)
            key = f"ratelimit:{scope}:{client_ip(request)}"
            if cache.get(key, 0) >= limit:
                return HttpResponse(TOO_MANY, status=429, content_type="text/plain; charset=utf-8")
            response = view(request, *args, **kwargs)
            if not failures_only or response.status_code == 200:
                if cache.add(key, 1, window) is False:
                    try:
                        cache.incr(key)
                    except ValueError:  # expired between add and incr
                        cache.set(key, 1, window)
            return response
        return wrapped
    return decorator
