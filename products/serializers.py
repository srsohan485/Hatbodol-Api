from rest_framework import serializers

from .models import Area, Category, Product
from .utils import user_brief


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "slug"]


class AreaSerializer(serializers.ModelSerializer):
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()

    class Meta:
        model = Area
        fields = ["id", "name", "latitude", "longitude"]


class ProductListSerializer(serializers.ModelSerializer):
    category = serializers.SerializerMethodField()
    condition_label = serializers.CharField(source="get_condition_display", read_only=True)
    thumbnail = serializers.SerializerMethodField()
    has_video = serializers.SerializerMethodField()
    distance_km = serializers.SerializerMethodField()
    is_saved = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id", "title", "price", "category", "condition", "condition_label",
            "area", "thumbnail", "has_video", "distance_km", "is_saved",
            "status", "created_at",
        ]

    def _url(self, f):
        request = self.context.get("request")
        return request.build_absolute_uri(f.url) if request else f.url

    def get_category(self, obj):
        return obj.category.name if obj.category else None

    def get_thumbnail(self, obj):
        imgs = list(obj.images.all())
        return self._url(imgs[0].image) if imgs else None

    def get_has_video(self, obj):
        return bool(obj.video)

    def get_distance_km(self, obj):
        return getattr(obj, "distance_km", None)

    def get_is_saved(self, obj):
        return obj.id in self.context.get("saved_ids", set())


class ProductDetailSerializer(ProductListSerializer):
    images = serializers.SerializerMethodField()
    video = serializers.SerializerMethodField()
    seller = serializers.SerializerMethodField()
    is_mine = serializers.SerializerMethodField()
    category_id = serializers.IntegerField(read_only=True)
    latitude = serializers.FloatField(read_only=True)
    longitude = serializers.FloatField(read_only=True)

    class Meta(ProductListSerializer.Meta):
        fields = ProductListSerializer.Meta.fields + [
            "description", "images", "video", "seller", "is_mine",
            "category_id", "latitude", "longitude", "views_count", "updated_at",
        ]

    def get_images(self, obj):
        return [{"id": i.id, "url": self._url(i.image)} for i in obj.images.all()]

    def get_video(self, obj):
        return self._url(obj.video) if obj.video else None

    def get_seller(self, obj):
        data = user_brief(obj.seller, self.context.get("request"))
        data["products_count"] = obj.seller.products.filter(status="active").count()
        return data

    def get_is_mine(self, obj):
        request = self.context.get("request")
        return bool(request and obj.seller_id == request.user.id)


class ProductWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ["title", "description", "price", "category", "condition", "area", "latitude", "longitude"]
        extra_kwargs = {"category": {"required": True, "allow_null": False}}

    def to_internal_value(self, data):
        # GPS এর লম্বা দশমিক ছেঁটে ৬ ঘরে আনা
        if hasattr(data, "copy"):
            data = data.copy()
        for k in ("latitude", "longitude"):
            try:
                if data.get(k) not in (None, ""):
                    data[k] = round(float(data[k]), 6)
            except (TypeError, ValueError):
                pass
        return super().to_internal_value(data)

    def validate_title(self, v):
        v = v.strip()
        if len(v) < 3:
            raise serializers.ValidationError("শিরোনাম কমপক্ষে ৩ অক্ষরের হতে হবে।")
        return v

    def validate_price(self, v):
        if v <= 0:
            raise serializers.ValidationError("দাম ০ এর বেশি হতে হবে।")
        return v

    def validate_category(self, v):
        if not v.is_active:
            raise serializers.ValidationError("এই ক্যাটাগরি এখন চালু নেই।")
        return v