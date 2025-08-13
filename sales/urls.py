# sales/urls.py
from django.urls import path
from . import views

app_name = "sales"

urlpatterns = [
    path("product-info/", views.product_info, name="product_info"),
]
