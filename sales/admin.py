from django.contrib import admin
from django.utils.html import format_html
from .models import Sale, SaleItem

class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 1
    fields = ("product", "quantity", "price_at_sale", "brand_display", "category_display", "subtotal_display")
    readonly_fields = ("brand_display", "category_display", "subtotal_display")

    class Media:
        js = ("sales/js/saleitem_autofill.js",)

    def brand_display(self, obj):
        text = str(obj.brand) if getattr(obj, "brand", None) else ""
        return format_html('<span data-saleitem="brand_display">{}</span>', text)
    brand_display.short_description = "Marca"

    def category_display(self, obj):
        text = str(obj.category) if getattr(obj, "category", None) else ""
        return format_html('<span data-saleitem="category_display">{}</span>', text)
    category_display.short_description = "Categoria"

    def subtotal_display(self, obj):
        try:
            return obj.subtotal
        except Exception:
            return "-"
    subtotal_display.short_description = "Subtotal"

@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("id", "created_at", "total")
    date_hierarchy = "created_at"
    inlines = [SaleItemInline]
    search_fields = ("id",)

@admin.register(SaleItem)
class SaleItemAdmin(admin.ModelAdmin):
    list_display = ("sale", "product", "brand", "category", "quantity", "price_at_sale", "subtotal", "created_at")
    list_filter = ("brand", "category", "created_at")
    search_fields = ("product__title", "sale__id")
    readonly_fields = ("brand", "category")
