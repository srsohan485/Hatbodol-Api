from django.conf import settings
from django.db import models

User = settings.AUTH_USER_MODEL


class Category(models.Model):
    name = models.CharField(max_length=60)
    slug = models.SlugField(unique=True)
    order = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["order", "id"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name


class Area(models.Model):
    """'হাতে এলাকা বেছে নিন' এর তালিকা"""
    name = models.CharField(max_length=100)  # যেমন: ধানমন্ডি, ঢাকা
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Product(models.Model):
    CONDITION_CHOICES = (
        ("new", "একদম নতুন"),
        ("like_new", "প্রায় নতুন"),
        ("good", "ভালো"),
        ("fair", "মোটামুটি"),
    )
    STATUS_CHOICES = (("active", "Active"), ("sold", "Sold"), ("hidden", "Hidden"))

    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name="products")
    category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="products"
    )
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    price = models.PositiveIntegerField()  # টাকা
    condition = models.CharField(max_length=10, choices=CONDITION_CHOICES, default="good")
    area = models.CharField(max_length=150, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    video = models.FileField(upload_to="products/videos/", null=True, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="active", db_index=True)
    views_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class ProductImage(models.Model):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="images")
    image = models.ImageField(upload_to="products/")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "id"]


class SavedProduct(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="saved_products")
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="saves")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "product")
        ordering = ["-created_at"]


class ProductReport(models.Model):
    REASON_CHOICES = (
        ("fake", "ভুয়া পোস্ট"),
        ("fraud", "প্রতারণা"),
        ("inappropriate", "আপত্তিকর কনটেন্ট"),
        ("other", "অন্যান্য"),
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="reports")
    reporter = models.ForeignKey(User, on_delete=models.CASCADE, related_name="reports_made")
    reason = models.CharField(max_length=15, choices=REASON_CHOICES)
    note = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("product", "reporter")


class BlockedUser(models.Model):
    blocker = models.ForeignKey(User, on_delete=models.CASCADE, related_name="blocking")
    blocked = models.ForeignKey(User, on_delete=models.CASCADE, related_name="blocked_by")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("blocker", "blocked")