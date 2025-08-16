# sales/urls.py
from django.urls import path
from . import views

app_name = "sales"

urlpatterns = [
    path("pos/", views.pos_page, name="pos_page"),
    path("pos/add-item/", views.pos_add_item, name="pos_add_item"),
    path("pos/update-qty/", views.pos_update_qty, name="pos_update_qty"),
    path("pos/remove-item/", views.pos_remove_item, name="pos_remove_item"),
    path("pos/finish/", views.pos_finish, name="pos_finish"),
]
