from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

from events.views import (
    PublicCertificateDetailView,
    DownloadCertificateSVGView,
    PublicJudgeRecordVerifyView,
    MyCertificatesListView,
    SigningKeyView,
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('users.urls')),
    path('api/events/', include('events.urls')),
    path('api/certificates/<str:code>/', PublicCertificateDetailView.as_view(), name='root_public_certificate_detail'),
    path('api/certificates/<str:code>/download/', DownloadCertificateSVGView.as_view(), name='root_download_certificate_svg'),
    path('api/my-certificates/', MyCertificatesListView.as_view(), name='root_my_certificates'),
    path('api/signing-key/', SigningKeyView.as_view(), name='signing_key'),
    path('api/judges/records/<str:record_id>/verify/', PublicJudgeRecordVerifyView.as_view(), name='root_public_judge_record_verify'),
]

if settings.MEDIA_URL:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
