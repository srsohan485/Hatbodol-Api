from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from products.models import Product
from products.utils import blocked_ids, user_brief

from .models import Conversation, Message

QUICK_REPLIES = ["এটা কি এখনো আছে?", "দাম কমবে?", "কোথায় দেখতে পাবো?"]
SAFETY_NOTICE = "নিরাপত্তার জন্য দেখা না করে অগ্রিম টাকা পাঠাবেন না।"


def abs_url(request, f):
    return request.build_absolute_uri(f.url) if f else None


def other_user(conv, user):
    return conv.seller if conv.buyer_id == user.id else conv.buyer


def product_card(conv, request):
    p = conv.product
    if not p:
        return None
    first = p.images.first()
    return {
        "id": p.id, "title": p.title, "price": p.price, "status": p.status,
        "thumbnail": abs_url(request, first.image if first else None),
    }


def msg_dict(m, user, request):
    return {
        "id": m.id, "text": m.text, "image": abs_url(request, m.image),
        "is_mine": m.sender_id == user.id, "is_read": m.is_read, "created_at": m.created_at,
    }


def conv_dict(conv, user, request, unread=0, last=None):
    return {
        "id": conv.id,
        "role": "buying" if conv.buyer_id == user.id else "selling",
        "other_user": user_brief(other_user(conv, user), request),
        "product": product_card(conv, request),
        "last_message": None if not last else {
            "text": last.text or "📷 ছবি",
            "is_mine": last.sender_id == user.id,
            "created_at": last.created_at,
        },
        "unread_count": unread,
        "updated_at": conv.updated_at,
    }


def get_conv(request, pk):
    conv = get_object_or_404(Conversation.objects.select_related("product", "buyer", "seller"), pk=pk)
    if request.user.id not in (conv.buyer_id, conv.seller_id):
        raise PermissionDenied("এই চ্যাটে আপনার অনুমতি নেই।")
    return conv


class StartConversationView(APIView):
    """'এসএমএস/মেসেজ' বাটন"""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        pid = str(request.data.get("product_id", ""))
        if not pid.isdigit():
            return Response({"product_id": ["পণ্যের id দিন।"]}, status=400)
        product = get_object_or_404(Product, pk=int(pid))
        if product.seller_id == request.user.id:
            return Response({"error": "নিজের পণ্যে মেসেজ করা যায় না।"}, status=400)
        if product.seller_id in blocked_ids(request.user):
            return Response({"error": "এই বিক্রেতাকে মেসেজ করা যাবে না।"}, status=403)
        conv, created = Conversation.objects.get_or_create(
            product=product, buyer=request.user, defaults={"seller": product.seller}
        )
        return Response(conv_dict(conv, request.user, request), status=201 if created else 200)


class ConversationListView(APIView):
    """?tab=all | buying | selling"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        tab = request.query_params.get("tab", "all")
        b = blocked_ids(user)
        qs = (Conversation.objects.filter(Q(buyer=user) | Q(seller=user))
              .exclude(Q(buyer_id__in=b) | Q(seller_id__in=b))
              .select_related("product", "buyer", "seller"))
        if tab == "buying":
            qs = qs.filter(buyer=user)
        elif tab == "selling":
            qs = qs.filter(seller=user)
        qs = (qs.annotate(
                total=Count("messages"),
                unread=Count("messages", filter=Q(messages__is_read=False) & ~Q(messages__sender=user)),
            ).filter(total__gt=0).order_by("-updated_at"))

        results = []
        for c in qs:
            last = c.messages.order_by("-id").first()
            results.append(conv_dict(c, user, request, unread=c.unread, last=last))
        return Response({"count": len(results), "results": results})


class MessagesView(APIView):
    """GET ?after=<last_message_id> দিয়ে নতুন মেসেজ আনো (polling)। POST: মেসেজ পাঠাও"""
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request, pk):
        conv = get_conv(request, pk)
        user = request.user
        after = request.query_params.get("after", "")
        qs = conv.messages.select_related("sender")
        if after.isdigit():
            msgs = list(qs.filter(id__gt=int(after)).order_by("id"))
        else:
            msgs = list(reversed(qs.order_by("-id")[:200]))

        conv.messages.filter(is_read=False).exclude(sender=user).update(is_read=True)

        other = other_user(conv, user)
        return Response({
            "conversation": conv_dict(conv, user, request),
            "safety_notice": SAFETY_NOTICE,
            "is_blocked": other.id in blocked_ids(user),
            "messages": [msg_dict(m, user, request) for m in msgs],
        })

    def post(self, request, pk):
        conv = get_conv(request, pk)
        user = request.user
        text = str(request.data.get("text") or "").strip()
        image = request.FILES.get("image")

        if not text and not image:
            return Response({"error": "মেসেজ লিখুন বা ছবি দিন।"}, status=400)
        if len(text) > 2000:
            return Response({"text": ["মেসেজ ২০০০ অক্ষরের বেশি হতে পারবে না।"]}, status=400)
        if image:
            if not (image.content_type or "").startswith("image/"):
                return Response({"image": ["শুধু ছবির ফাইল দিন।"]}, status=400)
            if image.size > 5 * 1024 * 1024:
                return Response({"image": ["ছবি ৫MB এর কম হতে হবে।"]}, status=400)
        if other_user(conv, user).id in blocked_ids(user):
            return Response({"error": "এই ব্যবহারকারীকে মেসেজ করা যাবে না।"}, status=403)

        msg = Message.objects.create(conversation=conv, sender=user, text=text, image=image)
        conv.save(update_fields=["updated_at"])
        return Response(msg_dict(msg, user, request), status=201)


class UnreadCountView(APIView):
    """নিচের নেভিগেশনের মেসেজ ব্যাজ"""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        n = (Message.objects.filter(is_read=False)
             .filter(Q(conversation__buyer=user) | Q(conversation__seller=user))
             .exclude(sender=user).count())
        return Response({"unread": n})


class QuickRepliesView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response({"replies": QUICK_REPLIES})