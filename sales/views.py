# sales/views.py
from django.http import JsonResponse, Http404
from django.contrib.admin.views.decorators import staff_member_required
from products.models import Product  # não importe sales.urls aqui!

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
        "price": getattr(p, "price", None),
        "brand_name": getattr(p.brand, "name", None) if getattr(p, "brand_id", None) else None,
        "brand_id": getattr(p, "brand_id", None),
        "category_name": getattr(p.category, "name", None) if getattr(p, "category_id", None) else None,
        "category_id": getattr(p, "category_id", None),
    })
