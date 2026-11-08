from django.urls import path
from . import views as v

urlpatterns = [
    path("start/", v.StartConversationView.as_view()),
    path("conversations/", v.ConversationListView.as_view()),
    path("conversations/<int:pk>/messages/", v.MessagesView.as_view()),
    path("unread-count/", v.UnreadCountView.as_view()),
    path("quick-replies/", v.QuickRepliesView.as_view()),
]


