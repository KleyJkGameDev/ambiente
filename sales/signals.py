from django.db.models.signals import pre_save
from django.dispatch import receiver
from .models import SaleItem

@receiver(pre_save, sender=SaleItem)
def saleitem_autofill(sender, instance: SaleItem, **kwargs):
    instance._autofill_from_product()
