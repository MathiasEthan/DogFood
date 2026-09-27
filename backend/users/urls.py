from django.urls import path
from .views import (
    RegisterView,
    LoginView,
    RefreshTokenView,
    LogoutView,
    CurrentUserView,
    AdminUserListView,
    AppointJudgeView,
    AppointableJudgesView,
    ApiKeyListCreateView,
    ApiKeyDetailView,
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='auth_register'),
    path('login/', LoginView.as_view(), name='auth_login'),
    path('refresh/', RefreshTokenView.as_view(), name='auth_refresh'),
    path('logout/', LogoutView.as_view(), name='auth_logout'),
    path('me/', CurrentUserView.as_view(), name='auth_me'),
    path('users/', AdminUserListView.as_view(), name='admin_user_list'),
    path('users/<int:pk>/appoint-judge/', AppointJudgeView.as_view(), name='appoint_judge'),
    path('appointable-judges/', AppointableJudgesView.as_view(), name='appointable_judges'),

    # T4 - API keys for programmatic access
    path('api-keys/', ApiKeyListCreateView.as_view(), name='api_key_list_create'),
    path('api-keys/<int:pk>/', ApiKeyDetailView.as_view(), name='api_key_detail'),
]
