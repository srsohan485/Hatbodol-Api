from math import asin, cos, radians, sin, sqrt

from .models import BlockedUser


def haversine_km(lat1, lon1, lat2, lon2):
    lat1, lon1, lat2, lon2 = (radians(float(v)) for v in (lat1, lon1, lat2, lon2))
    a = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 6371 * 2 * asin(sqrt(a))


def bounding_box(lat, lng, radius_km):
    dlat = radius_km / 111.0
    dlng = radius_km / (111.0 * max(cos(radians(lat)), 0.01))
    return lat - dlat, lat + dlat, lng - dlng, lng + dlng


def blocked_ids(user):
    """আমি যাদের ব্লক করেছি + যারা আমাকে ব্লক করেছে"""
    a = BlockedUser.objects.filter(blocker=user).values_list("blocked_id", flat=True)
    b = BlockedUser.objects.filter(blocked=user).values_list("blocker_id", flat=True)
    return set(a) | set(b)


def user_brief(user, request=None):
    p = getattr(user, "profile", None)
    photo = None
    if p and p.photo:
        photo = request.build_absolute_uri(p.photo.url) if request else p.photo.url
    return {
        "id": user.id,
        "name": p.full_name if p else user.username,
        "photo": photo,
        "area": p.area if p else "",
        "phone_verified": p.is_phone_verified if p else False,
    }