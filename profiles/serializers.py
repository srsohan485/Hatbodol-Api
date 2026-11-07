import re
from rest_framework import serializers
from .models import Profile


class ProfileSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    photo = serializers.ImageField(required=False, allow_null=True)

    class Meta:
        model = Profile
        fields = [
            "id", "email", "username", "full_name", "photo",
            "area", "latitude", "longitude",
            "phone", "is_phone_verified", "created_at",
        ]
        read_only_fields = ["id", "is_phone_verified", "created_at"]
        extra_kwargs = {
            "full_name": {"error_messages": {"blank": "নাম দিন।", "required": "নাম দিন।"}},
            "area": {"error_messages": {"blank": "এলাকা দিন।", "required": "এলাকা দিন।"}},
        }

    def validate_full_name(self, value):
        value = value.strip()
        if len(value) < 2:
            raise serializers.ValidationError("নাম কমপক্ষে ২ অক্ষরের হতে হবে।")
        return value

    def validate_phone(self, value):
        value = value.strip().replace(" ", "").replace("-", "")
        if not value:
            return ""
        if value.startswith("+880"):
            value = "0" + value[4:]
        elif value.startswith("880"):
            value = "0" + value[3:]
        if not re.fullmatch(r"01[3-9]\d{8}", value):
            raise serializers.ValidationError("সঠিক বাংলাদেশি ফোন নম্বর দিন (যেমন 01712345678)।")
        qs = Profile.objects.filter(phone=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("এই ফোন নম্বর আগে থেকেই ব্যবহার হচ্ছে।")
        return value

    def validate_photo(self, value):
        if value and value.size > 5 * 1024 * 1024:
            raise serializers.ValidationError("ছবি ৫MB এর বেশি হতে পারবে না।")
        return value


class PublicProfileSerializer(serializers.ModelSerializer):
    """অন্যের প্রোফাইল দেখার জন্য: ফোন/email লুকানো"""
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = Profile
        fields = ["id", "user_id", "username", "full_name", "photo", "area", "created_at"]