from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import F, Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Area, BlockedUser, Category, Product, ProductImage, ProductReport, SavedProduct
from .serializers import (
    AreaSerializer, CategorySerializer, ProductDetailSerializer,
    ProductListSerializer, ProductWriteSerializer,
)
from .utils import blocked_ids, bounding_box, haversine_km, user_brief

User = get_user_model()

MAX_IMAGES = 8
MAX_IMAGE_MB = 5
MAX_VIDEO_MB = 30


# ---------- helpers ----------
def to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def base_queryset():
    return Product.objects.select_related("category", "seller").prefetch_related("images")


def get_center(request):
    """lat/lng না দিলে user এর প্রোফাইলের location"""
    lat = to_float(request.query_params.get("lat"))
    lng = to_float(request.query_params.get("lng"))
    if lat is None or lng is None:
        prof = getattr(request.user, "profile", None)
        if prof and prof.latitude is not None and prof.longitude is not None:
            return float(prof.latitude), float(prof.longitude)
        return None, None
    return lat, lng


def attach_distance(product, lat, lng):
    if lat is None or product.latitude is None or product.longitude is None:
        product.distance_km = None
    else:
        product.distance_km = round(haversine_km(lat, lng, product.latitude, product.longitude), 1)
    return product


def ctx(request):
    saved = set(SavedProduct.objects.filter(user=request.user).values_list("product_id", flat=True))
    return {"request": request, "saved_ids": saved}


def check_media(images, video, existing=0):
    if existing + len(images) > MAX_IMAGES:
        return {"images": [f"সর্বোচ্চ {MAX_IMAGES}টি ছবি দেওয়া যাবে।"]}
    for img in images:
        if not (img.content_type or "").startswith("image/"):
            return {"images": ["শুধু ছবির ফাইল দিন।"]}
        if img.size > MAX_IMAGE_MB * 1024 * 1024:
            return {"images": [f"প্রতিটি ছবি {MAX_IMAGE_MB}MB এর কম হতে হবে।"]}
    if video:
        if video.content_type not in ("video/mp4", "video/quicktime", "video/webm"):
            return {"video": ["mp4, mov বা webm ভিডিও দিন।"]}
        if video.size > MAX_VIDEO_MB * 1024 * 1024:
            return {"video": [f"ভিডিও {MAX_VIDEO_MB}MB এর কম হতে হবে।"]}
    return None


# ---------- Home feed + পণ্য পোস্ট ----------
class ProductListCreateView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        p = request.query_params
        user = request.user
        qs = base_queryset().filter(status="active").exclude(seller_id__in=blocked_ids(user))

        seller = p.get("seller")
        if seller and seller.isdigit():
            qs = qs.filter(seller_id=int(seller))
        else:
            seller = None
            qs = qs.exclude(seller=user)

        category = p.get("category")
        if category and category != "all":
            qs = qs.filter(category__slug=category)

        q = (p.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))

        if (v := p.get("min_price")) and v.isdigit():
            qs = qs.filter(price__gte=int(v))
        if (v := p.get("max_price")) and v.isdigit():
            qs = qs.filter(price__lte=int(v))

        lat, lng = get_center(request)
        radius = to_float(p.get("radius"))
        radius = 10 if radius is None else min(max(radius, 0), 200)  # 0 = সীমা নেই
        use_radius = lat is not None and radius > 0 and not seller

        if use_radius:
            la1, la2, lo1, lo2 = bounding_box(lat, lng, radius)
            qs = qs.filter(latitude__range=(la1, la2), longitude__range=(lo1, lo2))

        items = [attach_distance(x, lat, lng) for x in qs]
        if use_radius:
            items = [x for x in items if x.distance_km is not None and x.distance_km <= radius]

        sort = p.get("sort") or ("nearby" if lat is not None else "newest")
        if sort == "nearby":
            items.sort(key=lambda x: x.distance_km if x.distance_km is not None else 10**9)
        elif sort == "price_low":
            items.sort(key=lambda x: x.price)
        elif sort == "price_high":
            items.sort(key=lambda x: x.price, reverse=True)
        # newest: DB থেকেই নতুন আগে

        page = max(int(p["page"]), 1) if p.get("page", "").isdigit() else 1
        size = min(int(p["page_size"]), 50) if p.get("page_size", "").isdigit() and int(p["page_size"]) > 0 else 20
        start = (page - 1) * size
        chunk = items[start:start + size]

        return Response({
            "count": len(items),
            "page": page,
            "page_size": size,
            "has_next": start + size < len(items),
            "results": ProductListSerializer(chunk, many=True, context=ctx(request)).data,
        })

    def post(self, request):
        profile = getattr(request.user, "profile", None)
        if not profile:
            return Response({"error": "আগে প্রোফাইল তৈরি করুন।"}, status=400)

        s = ProductWriteSerializer(data=request.data)
        s.is_valid(raise_exception=True)

        images = request.FILES.getlist("images")
        video = request.FILES.get("video")
        if not images:
            return Response({"images": ["কমপক্ষে একটি ছবি দিন।"]}, status=400)
        err = check_media(images, video)
        if err:
            return Response(err, status=400)

        d, extra = s.validated_data, {}
        if not d.get("area"):
            extra["area"] = profile.area
        if d.get("latitude") is None or d.get("longitude") is None:
            extra["latitude"], extra["longitude"] = profile.latitude, profile.longitude

        with transaction.atomic():
            product = s.save(seller=request.user, video=video, **extra)
            for i, f in enumerate(images):
                ProductImage.objects.create(product=product, image=f, order=i)

        product = get_object_or_404(base_queryset(), pk=product.pk)
        return Response(ProductDetailSerializer(product, context=ctx(request)).data, status=201)


class MyProductsView(APIView):
    """প্রোফাইল screen এর 'আমার পোস্ট'"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        st = request.query_params.get("status")
        qs = base_queryset().filter(seller=request.user)
        if st in ("active", "sold", "hidden"):
            qs = qs.filter(status=st)
        items = list(qs)
        return Response({"count": len(items),
                         "results": ProductListSerializer(items, many=True, context=ctx(request)).data})


# ---------- বিস্তারিত ----------
class ProductDetailView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request, pk):
        product = get_object_or_404(base_queryset(), pk=pk)
        mine = product.seller_id == request.user.id
        if not mine and (product.status == "hidden" or product.seller_id in blocked_ids(request.user)):
            return Response({"detail": "Not found."}, status=404)
        if not mine:
            Product.objects.filter(pk=pk).update(views_count=F("views_count") + 1)
            product.views_count += 1
        lat, lng = get_center(request)
        attach_distance(product, lat, lng)
        return Response(ProductDetailSerializer(product, context=ctx(request)).data)

    def patch(self, request, pk):
        product = get_object_or_404(base_queryset(), pk=pk, seller=request.user)
        s = ProductWriteSerializer(product, data=request.data, partial=True)
        s.is_valid(raise_exception=True)

        new_images = request.FILES.getlist("images")
        video = request.FILES.get("video")
        raw = request.data.getlist("remove_images") if hasattr(request.data, "getlist") \
            else request.data.get("remove_images", [])
        remove_ids = [int(i) for i in raw if str(i).isdigit()]
        remove_video = str(request.data.get("remove_video", "")).lower() in ("1", "true")

        existing = product.images.exclude(id__in=remove_ids).count()
        if existing + len(new_images) == 0:
            return Response({"images": ["কমপক্ষে একটি ছবি থাকতে হবে।"]}, status=400)
        err = check_media(new_images, video, existing)
        if err:
            return Response(err, status=400)

        with transaction.atomic():
            product = s.save()
            for img in product.images.filter(id__in=remove_ids):
                img.image.delete(save=False)
                img.delete()
            start = product.images.count()
            for i, f in enumerate(new_images):
                ProductImage.objects.create(product=product, image=f, order=start + i)
            if video:
                if product.video:
                    product.video.delete(save=False)
                product.video = video
                product.save(update_fields=["video"])
            elif remove_video and product.video:
                product.video.delete(save=False)
                product.video = None
                product.save(update_fields=["video"])

        product = get_object_or_404(base_queryset(), pk=pk)
        return Response(ProductDetailSerializer(product, context=ctx(request)).data)

    def delete(self, request, pk):
        product = get_object_or_404(base_queryset(), pk=pk, seller=request.user)
        for img in product.images.all():
            img.image.delete(save=False)
        if product.video:
            product.video.delete(save=False)
        product.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ProductStatusView(APIView):
    """mark-sold/ আর relist/"""
    permission_classes = [IsAuthenticated]
    new_status = None

    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk, seller=request.user)
        product.status = self.new_status
        product.save(update_fields=["status", "updated_at"])
        return Response({"id": product.id, "status": product.status})


# ---------- সেভ ----------
class SaveProductView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        SavedProduct.objects.get_or_create(user=request.user, product=product)
        return Response({"is_saved": True}, status=201)

    def delete(self, request, pk):
        SavedProduct.objects.filter(user=request.user, product_id=pk).delete()
        return Response({"is_saved": False})


class SavedListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        ids = list(SavedProduct.objects.filter(user=request.user).values_list("product_id", flat=True))
        order = {pid: i for i, pid in enumerate(ids)}
        items = [x for x in base_queryset().filter(id__in=ids).exclude(status="hidden")]
        items.sort(key=lambda x: order[x.id])
        lat, lng = get_center(request)
        items = [attach_distance(x, lat, lng) for x in items]
        return Response({"count": len(items),
                         "results": ProductListSerializer(items, many=True, context=ctx(request)).data})


# ---------- রিপোর্ট, ব্লক, যোগাযোগ ----------
class ReportReasonsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response([{"value": v, "label": l} for v, l in ProductReport.REASON_CHOICES])


class ProductReportView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        if product.seller_id == request.user.id:
            return Response({"error": "নিজের পোস্ট রিপোর্ট করা যায় না।"}, status=400)
        reason = request.data.get("reason")
        if reason not in [c[0] for c in ProductReport.REASON_CHOICES]:
            return Response({"reason": ["সঠিক কারণ বেছে নিন।"]}, status=400)
        note = str(request.data.get("note") or "")[:500]
        _, created = ProductReport.objects.get_or_create(
            product=product, reporter=request.user, defaults={"reason": reason, "note": note}
        )
        if not created:
            return Response({"message": "আপনি আগেই এই পোস্ট রিপোর্ট করেছেন।"})
        return Response({"message": "রিপোর্ট পাঠানো হয়েছে।"}, status=201)


class BlockUserView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, user_id):
        if user_id == request.user.id:
            return Response({"error": "নিজেকে ব্লক করা যায় না।"}, status=400)
        target = get_object_or_404(User, pk=user_id)
        BlockedUser.objects.get_or_create(blocker=request.user, blocked=target)
        return Response({"message": "ব্লক করা হয়েছে।"}, status=201)

    def delete(self, request, user_id):
        BlockedUser.objects.filter(blocker=request.user, blocked_id=user_id).delete()
        return Response({"message": "আনব্লক করা হয়েছে।"})


class ProductContactView(APIView):
    """'কল করুন' বাটন: ফোন নম্বর শুধু এখান থেকে পাওয়া যায়"""
    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        product = get_object_or_404(Product, pk=pk)
        if product.seller_id in blocked_ids(request.user):
            return Response({"error": "যোগাযোগ করা যাবে না।"}, status=403)
        prof = getattr(product.seller, "profile", None)
        if not prof or not prof.phone:
            return Response({"error": "বিক্রেতা ফোন নম্বর দেননি। মেসেজ করুন।"}, status=404)
        return Response({"phone": prof.phone, "seller_name": prof.full_name})


# ---------- বিক্রেতার প্রোফাইল ----------
class SellerProfileView(APIView):
    """তার পোস্টগুলো: GET products/?seller=<user_id>"""
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        user = get_object_or_404(User, pk=user_id)
        prof = getattr(user, "profile", None)
        data = user_brief(user, request)
        data.update({
            "joined_at": prof.created_at if prof else user.date_joined,
            "products_count": Product.objects.filter(seller=user, status="active").count(),
            "is_blocked_by_me": BlockedUser.objects.filter(blocker=request.user, blocked=user).exists(),
        })
        return Response(data)


# ---------- ক্যাটাগরি, এলাকা, সতর্কবার্তা ----------
class CategoryListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(CategorySerializer(Category.objects.filter(is_active=True), many=True).data)


class AreaListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = Area.objects.all()
        q = (request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(name__icontains=q)
        return Response(AreaSerializer(qs, many=True).data)


class SafetyTipsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({
            "title": "নিরাপদে কেনাবেচা করুন",
            "subtitle": "বিক্রেতার সাথে যোগাযোগের আগে এই বিষয়গুলো মনে রাখুন",
            "tips": [
                "অগ্রিম টাকা পাঠাবেন না",
                "সামনাসামনি দেখে কিনুন",
                "পণ্য যাচাই করে টাকা দিন",
            ],
        })