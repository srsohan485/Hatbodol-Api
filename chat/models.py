from django.conf import settings
from django.db import models

User = settings.AUTH_USER_MODEL


class Conversation(models.Model):
    product = models.ForeignKey(
        "products.Product", null=True, blank=True,
        on_delete=models.SET_NULL, related_name="conversations",
    )
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="buying_chats")
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name="selling_chats")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at"]
        constraints = [
            models.UniqueConstraint(fields=["product", "buyer"], name="unique_chat_per_product_buyer")
        ]


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name="sent_messages")
    text = models.TextField(blank=True)
    image = models.ImageField(upload_to="chat/", null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["id"]