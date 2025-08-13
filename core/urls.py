from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("", admin.site.urls),
    path("sales/", include(("sales.urls", "sales"), namespace="sales")),
]
