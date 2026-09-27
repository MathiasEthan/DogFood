from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken

from .models import User
from .serializers import (
    UserSerializer,
    UserRegistrationSerializer,
    UserLoginSerializer,
    RoleUpdateSerializer,
)


def set_auth_cookies(response: Response, refresh_token: RefreshToken) -> Response:
    """Helper utility to attach JWT access and refresh tokens as HttpOnly cookies."""
    access_token = refresh_token.access_token

    access_expiry = int(settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds())
    refresh_expiry = int(settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds())

    cookie_secure = getattr(settings, 'JWT_COOKIE_SECURE', False)
    cookie_samesite = getattr(settings, 'JWT_COOKIE_SAMESITE', 'Lax')
    cookie_path = getattr(settings, 'JWT_COOKIE_PATH', '/')

    response.set_cookie(
        key=getattr(settings, 'JWT_ACCESS_COOKIE_NAME', 'access_token'),
        value=str(access_token),
        max_age=access_expiry,
        httponly=True,
        secure=cookie_secure,
        samesite=cookie_samesite,
        path=cookie_path,
    )

    response.set_cookie(
        key=getattr(settings, 'JWT_REFRESH_COOKIE_NAME', 'refresh_token'),
        value=str(refresh_token),
        max_age=refresh_expiry,
        httponly=True,
        secure=cookie_secure,
        samesite=cookie_samesite,
        path=cookie_path,
    )

    return response


def clear_auth_cookies(response: Response) -> Response:
    """Helper utility to clear JWT cookies on logout."""
    cookie_samesite = getattr(settings, 'JWT_COOKIE_SAMESITE', 'Lax')
    cookie_path = getattr(settings, 'JWT_COOKIE_PATH', '/')

    response.delete_cookie(
        key=getattr(settings, 'JWT_ACCESS_COOKIE_NAME', 'access_token'),
        path=cookie_path,
        samesite=cookie_samesite,
    )
    response.delete_cookie(
        key=getattr(settings, 'JWT_REFRESH_COOKIE_NAME', 'refresh_token'),
        path=cookie_path,
        samesite=cookie_samesite,
    )
    return response


class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'

    def post(self, request):
        serializer = UserRegistrationSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            refresh = RefreshToken.for_user(user)

            response_data = {
                'message': 'Registration successful',
                'user': UserSerializer(user).data,
            }
            response = Response(response_data, status=status.HTTP_201_CREATED)
            return set_auth_cookies(response, refresh)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'auth'

    def post(self, request):
        serializer = UserLoginSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            refresh = RefreshToken.for_user(user)

            response_data = {
                'message': 'Login successful',
                'user': UserSerializer(user).data,
            }
            response = Response(response_data, status=status.HTTP_200_OK)
            return set_auth_cookies(response, refresh)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RefreshTokenView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.COOKIES.get(
            getattr(settings, 'JWT_REFRESH_COOKIE_NAME', 'refresh_token')
        ) or request.data.get('refresh')

        if not refresh_token:
            return Response(
                {'detail': 'Refresh token cookie is missing.'},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        try:
            token = RefreshToken(refresh_token)
            new_access_token = token.access_token

            access_expiry = int(settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'].total_seconds())
            cookie_secure = getattr(settings, 'JWT_COOKIE_SECURE', False)
            cookie_samesite = getattr(settings, 'JWT_COOKIE_SAMESITE', 'Lax')
            cookie_path = getattr(settings, 'JWT_COOKIE_PATH', '/')

            response = Response({'message': 'Token refreshed successfully'}, status=status.HTTP_200_OK)
            response.set_cookie(
                key=getattr(settings, 'JWT_ACCESS_COOKIE_NAME', 'access_token'),
                value=str(new_access_token),
                max_age=access_expiry,
                httponly=True,
                secure=cookie_secure,
                samesite=cookie_samesite,
                path=cookie_path,
            )

            # If token rotation is active, rotate refresh cookie as well
            if settings.SIMPLE_JWT.get('ROTATE_REFRESH_TOKENS', False):
                # Blacklist the presented refresh token so it cannot be replayed after rotation
                if settings.SIMPLE_JWT.get('BLACKLIST_AFTER_ROTATION', False):
                    try:
                        token.blacklist()
                    except AttributeError:
                        pass
                token.set_jti()
                token.set_exp()
                refresh_expiry = int(settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'].total_seconds())
                response.set_cookie(
                    key=getattr(settings, 'JWT_REFRESH_COOKIE_NAME', 'refresh_token'),
                    value=str(token),
                    max_age=refresh_expiry,
                    httponly=True,
                    secure=cookie_secure,
                    samesite=cookie_samesite,
                    path=cookie_path,
                )

            return response
        except (TokenError, InvalidToken) as exc:
            response = Response({'detail': f'Invalid token: {str(exc)}'}, status=status.HTTP_401_UNAUTHORIZED)
            return clear_auth_cookies(response)


class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.COOKIES.get(
            getattr(settings, 'JWT_REFRESH_COOKIE_NAME', 'refresh_token')
        ) or request.data.get('refresh')

        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except Exception:
                pass  # Ignore invalid token during logout attempt

        response = Response({'message': 'Logged out successfully'}, status=status.HTTP_200_OK)
        return clear_auth_cookies(response)


class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminUserListView(APIView):
    """Admin-only view to list platform users for role management."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_platform_admin:
            return Response(
                {'detail': 'Only administrators can view the full user list.'},
                status=status.HTTP_403_FORBIDDEN,
            )
        users = User.objects.all().order_by('-created_at')
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AppointJudgeView(APIView):
    """Admin-only view to appoint a user as a Judge."""
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        if not request.user.is_platform_admin:
            return Response(
                {'detail': 'Only administrators can appoint judges.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        try:
            target_user = User.objects.get(pk=pk)
        except User.DoesNotExist:
            return Response({'detail': 'User not found.'}, status=status.HTTP_404_NOT_FOUND)

        target_user.role = User.Role.JUDGE
        target_user.save()

        return Response({
            'message': f'User {target_user.username} has been appointed as a Judge.',
            'user': UserSerializer(target_user).data,
        }, status=status.HTTP_200_OK)


class AppointableJudgesView(APIView):
    """
    Allows organizers and administrators to search/list platform users
    to appoint them as judges for an event.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.role not in ['organizer', 'admin'] and not request.user.is_superuser:
            return Response(
                {'detail': 'Only organizers and administrators can search users to appoint judges.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        query = request.query_params.get('q', '').strip()
        users = User.objects.all()
        if query:
            from django.db.models import Q
            users = users.filter(
                Q(username__icontains=query) |
                Q(email__icontains=query) |
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query)
            )
        users = users.order_by('username')[:40]
        serializer = UserSerializer(users, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)
