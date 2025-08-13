from django.contrib import admin

# Register your models here.
from .models import Sale, SaleItem

class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 1
    autocomplete_fields = ["product", "brand", "category"]

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "total")
    date_hierarchy = "created_at"
    inlines = [SaleItemInline]
    search_fields = ("id",)
    list_filter = ()

@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    list_display = ("sale", "product", "brand", "category", "quantity", "price_at_sale", "subtotal", "created_at")
    list_filter = ("brand", "category", "created_at")
    search_fields = ("product__title", "sale__id")
