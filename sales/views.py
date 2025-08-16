from django.http import JsonResponse, Http404
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.urls import reverse
from django.db import transaction

from products.models import Product
from .models import Sale, SaleItem

# Util: pega/cria a venda da sessão
def _get_or_create_session_sale(request):
    sale_id = request.session.get("pos_sale_id")
    sale = None
    if sale_id:
        sale = Sale.objects.filter(pk=sale_id).first()
    if sale is None:
        sale = Sale.objects.create(notes="PDV")
        request.session["pos_sale_id"] = sale.pk
    return sale

def _serialize_sale(sale):
    items = []
    subtotal = 0
    for it in SaleItem.objects.select_related("product").filter(sale=sale).order_by("id"):
        unit = float(it.price_at_sale or it.product.price or 0)
        line = unit * it.quantity
        subtotal += line
        items.append({
            "id": it.id,
            "product_id": it.product_id,
            "title": it.product.title,
            "quantity": it.quantity,
            "unit": unit,
            "line_total": line,
        })
    return {"sale_id": sale.pk, "items": items, "subtotal": subtotal, "total": subtotal}

# --- Produto (opcional)
@staff_member_required
def product_info(request):
    pid = request.GET.get("id")
    if not pid:
        raise Http404("Product id is required")
    try:
        p = Product.objects.select_related("brand", "category").get(pk=pid)
    except Product.DoesNotExist:
        raise Http404("Product not found")
    return JsonResponse({
        "title": p.title,
        "description": p.description or "",
        "price": str(p.price) if p.price is not None else None,
        "brand_name": getattr(p.brand, "name", None) if getattr(p, "brand_id", None) else None,
        "brand_id": getattr(p, "brand_id", None),
        "category_name": getattr(p.category, "name", None) if getattr(p, "category_id", None) else None,
        "category_id": getattr(p, "category_id", None),
    })

# --- Página POS
@login_required
def pos_page(request):
    products = Product.objects.filter(is_active=True).order_by("title").only("id", "title", "price")
    sale = _get_or_create_session_sale(request)
    state = _serialize_sale(sale)
    return render(request, "sales/pos.html", {"products": products, "state": state})

# --- Ações POS (AJAX)
@login_required
@transaction.atomic
def pos_add_item(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Método inválido"}, status=405)
    pid = request.POST.get("product_id")
    qty = int(request.POST.get("quantity") or "1")
    if not pid:
        return JsonResponse({"ok": False, "error": "Produto obrigatório"}, status=400)
    qty = max(1, qty)

    sale = _get_or_create_session_sale(request)
    try:
        product = Product.objects.get(pk=pid, is_active=True)
    except Product.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Produto inválido"}, status=404)

    item, created = SaleItem.objects.select_for_update().get_or_create(
        sale=sale, product=product, defaults={"quantity": qty}
    )
    if not created:
        item.quantity += qty
        item.save(update_fields=["quantity"])

    state = _serialize_sale(sale)
    return JsonResponse({"ok": True, "state": state})

@login_required
@transaction.atomic
def pos_update_qty(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Método inválido"}, status=405)
    item_id = request.POST.get("item_id")
    qty = int(request.POST.get("quantity") or "1")
    qty = max(1, qty)

    sale = _get_or_create_session_sale(request)
    try:
        item = SaleItem.objects.select_for_update().get(pk=item_id, sale=sale)
    except SaleItem.DoesNotExist:
        return JsonResponse({"ok": False, "error": "Item não encontrado"}, status=404)

    item.quantity = qty
    item.save(update_fields=["quantity"])

    state = _serialize_sale(sale)
    return JsonResponse({"ok": True, "state": state})

@login_required
@transaction.atomic
def pos_remove_item(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "error": "Método inválido"}, status=405)
    item_id = request.POST.get("item_id")

    sale = _get_or_create_session_sale(request)
    SaleItem.objects.filter(pk=item_id, sale=sale).delete()

    state = _serialize_sale(sale)
    return JsonResponse({"ok": True, "state": state})

@login_required
@transaction.atomic
def pos_finish(request):
    sale = _get_or_create_session_sale(request)
    admin_url = reverse("admin:sales_sale_change", args=[sale.pk])
    try:
        del request.session["pos_sale_id"]
    except KeyError:
        pass
    return JsonResponse({"ok": True, "sale_id": sale.pk, "admin_url": admin_url})
