from django.urls import path
from .views import ContactListView, MessageHistoryView, SendManualMessageView

urlpatterns = [
    path("contacts/", ContactListView.as_view(), name="contact-list"),
    path("contacts/<int:id>/messages/", MessageHistoryView.as_view(), name="message-history"),
    path("messages/send/", SendManualMessageView.as_view(), name="send-manual-message"),
]
