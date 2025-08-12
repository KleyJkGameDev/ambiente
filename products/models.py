from django.db import models

# Create your models here.

class Brand(models.Model): # Brand = marcas
    name = models.CharField(max_length=100, verbose_name="Nome")  # Nome da marca
    is_active = models.BooleanField(default=True, verbose_name="Ativo")  # Marca está ativa?
    description = models.TextField(null=True, blank=True, verbose_name="Descrição")  # Descrição
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")
    
    class Meta:  # Classe de meta dados da classe Brand
        ordering = ['name']  # Organizar por nome
        verbose_name = "Marca"  # usuário enxergar este nome
        
    def __str__(self):
        return self.name

class Category(models.Model):
    name = models.CharField(max_length=100, verbose_name="Nome")
    is_active = models.BooleanField(default=True, verbose_name="Ativo")
    description = models.TextField(null=True, blank=True, verbose_name="Descrição")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")
    
    class Meta:  # Classe de meta dados da classe Category
        ordering = ['name']  # Organizar por nome
        verbose_name = "Categoria"  # usuário enxergar este nome
        
    def __str__(self):
        return self.name
    
class Product(models.Model):
    title = models.CharField(max_length=100, verbose_name="Título")
    # Pegando chave estrangeira - Relacionamento de Tabelas
    brand = models.ForeignKey(Brand, on_delete=models.PROTECT,
                              related_name="products", verbose_name="Marca")
    category = models.ForeignKey(Category, on_delete=models.PROTECT,
                                 related_name="products", verbose_name="Categoria")
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Preço")
    is_active = models.BooleanField(default=True, verbose_name="Ativo")
    description = models.TextField(null=True, blank=True, verbose_name="Descrição")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Criado em")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Atualizado em")
    
    class Meta:  # Classe de meta dados da classe Product
        ordering = ['title']  # Ordenar por título
        verbose_name = "Produto" # Mostrar este nome ao usuário
        
    def __str__(self):
        return self.title
    