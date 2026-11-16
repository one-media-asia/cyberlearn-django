from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("", include("academy.urls")),
    path("admin/", admin.site.urls),
    path("api/cyberagent/", include("cyberagent.urls")),
    path("api/academy/", include("academy.api_urls")),
    path("api/academy/", include("academy.urls")),
]
