# sales/admin.py
from django.contrib import admin
from django.http import HttpResponseRedirect
from django.urls import reverse

from .models import Sale, SaleItem

class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    inlines = [SaleItemInline]
    list_display = ("id", "created_at")
    ordering = ("-id",)

    # IMPORTANTE: remover qualquer change_form_template custom que não exista
    # Ex.: change_form_template = "admin/sales/sale/change_form.html"  -> REMOVER

    # Quando o usuário acessar /admin/sales/sale/add/ (ou clicar em "Adicionar venda"),
    # redirecionamos para o PDV (/sales/pos/)
    def add_view(self, request, form_url="", extra_context=None):
        return HttpResponseRedirect(reverse("sales:pos_page"))

@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    list_display = ("id", "sale", "product", "quantity")
    ordering = ("-id",)
