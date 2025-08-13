from django.db import models

# Create your models here.
from django.utils import timezone
from products.models import Product, Brand, Category


class Sale(models.Model):
    created_at = models.DateTimeField(default=timezone.now, verbose_name="Data da venda")
    notes = models.CharField(max_length=255, blank=True, null=True, verbose_name="Observações")

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Venda"
        verbose_name_plural = "Vendas"

    def __str__(self):
        return f"Venda #{self.pk} - {self.created_at:%d/%m/%Y %H:%M}"

    @property
    def total(self):
        return sum((item.subtotal for item in self.items.all()), start=0)


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="items", verbose_name="Venda")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, verbose_name="Produto")
    quantity = models.PositiveIntegerField(default=1, verbose_name="Quantidade")
    price_at_sale = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Preço na venda")

    # Snapshot preenchido automaticamente — não aparece para edição
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT, editable=False, null=True, blank=True, verbose_name="Marca")
    category = models.ForeignKey(Category, on_delete=models.PROTECT, editable=False, null=True, blank=True, verbose_name="Categoria")

    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Registrado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")
        # sales/models.py (SaleItem)
    def _autofill_from_product(self):
        if self.product_id:
            if not self.price_at_sale:
                self.price_at_sale = getattr(self.product, "price", self.price_at_sale)
            if not self.brand_id and getattr(self.product, "brand_id", None):
                self.brand_id = self.product.brand_id
            if not self.category_id and getattr(self.product, "category_id", None):
                self.category_id = self.product.category_id

    def save(self, *args, **kwargs):
        self._autofill_from_product()
        super().save(*args, **kwargs)

    class Meta:
        verbose_name = "Item de Venda"
        verbose_name_plural = "Itens de Venda"

    def __str__(self):
        return f"{self.product} x{self.quantity}"

    @property
    def subtotal(self):
        return self.quantity * self.price_at_sale

    def _autofill_from_product(self):
        """
        Preenche marca, categoria e preço (se necessário) a partir do produto.
        """
        if self.product_id:
            if not self.price_at_sale:
                # Se desejar SEMPRE usar o preço atual do produto, remova o "if" acima
                self.price_at_sale = getattr(self.product, "price", self.price_at_sale)
            if not self.brand_id and getattr(self.product, "brand_id", None):
                self.brand_id = self.product.brand_id
            if not self.category_id and getattr(self.product, "category_id", None):
                self.category_id = self.product.category_id

    def save(self, *args, **kwargs):
        self._autofill_from_product()
        super().save(*args, **kwargs)
