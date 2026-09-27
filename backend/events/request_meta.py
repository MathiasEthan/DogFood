"""Small helpers shared by judging (T2) and community (T3) views."""
from django.conf import settings


def client_ip(request):
    """
    Best-effort client IP.

    X-Forwarded-For is only honoured when TRUST_X_FORWARDED_FOR is enabled, because
    without a trusted reverse proxy the header is attacker-controlled.
    """
    if getattr(settings, 'TRUST_X_FORWARDED_FOR', False):
        forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
        if forwarded:
            return forwarded.split(',')[0].strip() or None
    return request.META.get('REMOTE_ADDR') or None


def user_agent(request):
    return request.META.get('HTTP_USER_AGENT', '')[:500]
