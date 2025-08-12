from django.contrib import admin
from .models import Brand, Category, Product
import csv
from django.http import HttpResponse

admin.site.site_title = "Sistema de Gerenciamento"
admin.site.index_title = "S.G"
# Register your models here.

@admin.register(Brand)  # Registrar na tela de admin as sequintes configurações:
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "description", "created_at", "updated_at")  # Listar as seguintes informações
    search_fields = ("name",)  # Fazer busca por nome
    list_filter = ("is_active",) # Filtrar por 
    
@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "description", "created_at", "updated_at")  # Listar as seguintes informações
    search_fields = ("name", )  # Fazer busca por nome
    list_filter = ("is_active",)  # Filtrar por 
    
@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("title", "brand", "category", "description",
                    "created_at", "updated_at")
    search_fields = ("title", "brand__name", "category__name")  # Buscar por titulo e nome dentro de outras tabelas
    list_filter = ("is_active", "brand", "category")

    def export_to_csv(self, request, queryset):  # Queryset --> checkbox marcados no site
        response = HttpResponse(content_type="text/csv")  # Endpoint
        response["Content-Disposition"] = "attachment; filenmae='products.csv'"  # Configurações do arquivo
        writer = csv.writer(response)
        writer.writerow(["Título", "Marca", "Categoria", "Preço",
                         "Ativo", "Descrição", "Criado em", "Atualizado em"])
        for product in queryset:  # Percorrer os itens marcados na checkbox
            writer.writerow([product.title, product.brand.name, product.category.name,
                             product.price, product.is_active, product.description,
                             product.created_at, product.updated_at])
            
        return response
    
    export_to_csv.short_description = "Exportar para CSV"  # Nome da opção do campo Actions
    actions = [export_to_csv]  # Adicionando a função ao campo Actions