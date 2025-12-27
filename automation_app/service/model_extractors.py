from django.db.models import Count
from ..models import InstagramMessage,FacebookMessage

def most_active_users(user, limit=5):
    return list(
        InstagramMessage.objects
        .filter(recipient_id=user.instagram_account_id)
        .values("sender_username")
        .annotate(total=Count("id"))
        .order_by("-total")[:limit]
    )

def Facebook_most_active_users(user, limit=5):
    return list(
        FacebookMessage.objects
        .filter(recipient_page_id=user.facebook_page_id)
        .values("sender_name", "sender_id")
        .annotate(total=Count("id"))
        .order_by("-total")[:limit]
    )