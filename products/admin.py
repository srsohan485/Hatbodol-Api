from django.contrib import admin
from .models import Area, BlockedUser, Category, Product, ProductImage, ProductReport, SavedProduct


class ProductImageInline(admin.TabularInline):
    model = ProductImage
    extra = 0


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("title", "price", "seller", "status", "created_at")
    list_filter = ("status", "category")
    search_fields = ("title",)
    inlines = [ProductImageInline]


@admin.register(ProductReport)
class ProductReportAdmin(admin.ModelAdmin):
    list_display = ("product", "reporter", "reason", "created_at")
    list_filter = ("reason",)


admin.site.register(Category)
admin.site.register(Area)
admin.site.register(SavedProduct)
admin.site.register(BlockedUser)