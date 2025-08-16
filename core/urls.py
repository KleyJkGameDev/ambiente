# core/urls.py
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    # 1) Coloque as rotas do app antes do admin na raiz:
    path("sales/", include(("sales.urls", "sales"), namespace="sales")),

    # 2) Deixe o admin por último (na raiz):
    path("", admin.site.urls),
]
