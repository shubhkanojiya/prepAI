"""Root URL configuration for PrepAI."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "PrepAI Administration"
admin.site.site_title = "PrepAI Admin"
admin.site.index_title = "Content & platform management"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include("config.api_urls")),
    path("", include("core.urls")),
    path("accounts/", include("accounts.urls")),
    path("boards/", include("boards.urls")),
    path("questions/", include("questions.urls")),
    path("", include("papers.urls")),
    path("study-material/", include("content.urls")),
    path("tests/", include("testengine.urls")),
    path("saved/", include("bookmarks.urls")),
    path("dashboard/", include("dashboard.urls")),
    path("scanner/", include("scanner.urls")),
    path("assistant/", include("assistant.urls")),
    path("notifications/", include("notifications.urls")),
    path("search/", include("search.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

handler400 = "core.views.error_400"
handler403 = "core.views.error_403"
handler404 = "core.views.error_404"
handler500 = "core.views.error_500"
