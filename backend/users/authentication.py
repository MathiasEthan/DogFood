import hashlib
import hmac

from django.conf import settings
from django.utils import timezone
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework_simplejwt.exceptions import InvalidToken

from .models import ApiKey


class CookieJWTAuthentication(JWTAuthentication):
    """
    Custom JWT Authentication that extracts the token from HttpOnly cookies.
    Falls back to the standard Authorization header if no cookie is present.
    """

    def authenticate(self, request):
        cookie_name = getattr(settings, 'JWT_ACCESS_COOKIE_NAME', 'access_token')
        raw_token = request.COOKIES.get(cookie_name)

        if raw_token is None:
            # Fall back to Authorization: Bearer <token>
            header = self.get_header(request)
            if header is None:
                return None
            raw_token = self.get_raw_token(header)
            if raw_token is None:
                return None

        try:
            validated_token = self.get_validated_token(raw_token)
            user = self.get_user(validated_token)
            return (user, validated_token)
        except InvalidToken as exc:
            raise AuthenticationFailed(exc.args[0])


class ApiKeyAuthentication(BaseAuthentication):
    """
    T4: programmatic access for external tools that can't hold a browser cookie.
    Expects `Authorization: ApiKey <the key>`.

    Returns None (never raises) for any request that isn't using this scheme, so it
    can sit right after CookieJWTAuthentication in DEFAULT_AUTHENTICATION_CLASSES
    without breaking normal logged-in browser requests.
    """

    keyword = 'ApiKey'

    def authenticate(self, request):
        header = request.META.get('HTTP_AUTHORIZATION', '')
        parts = header.split()
        if len(parts) != 2 or parts[0] != self.keyword:
            return None

        raw_key = parts[1]
        key_hash = hashlib.sha256(raw_key.encode('utf-8')).hexdigest()
        api_key = ApiKey.objects.filter(prefix=raw_key[:12], is_active=True).select_related('user').first()

        if api_key is None or not hmac.compare_digest(api_key.key_hash, key_hash):
            raise AuthenticationFailed('Invalid or revoked API key.')

        ApiKey.objects.filter(pk=api_key.pk).update(last_used_at=timezone.now())
        return (api_key.user, api_key)

    def authenticate_header(self, request):
        return self.keyword
