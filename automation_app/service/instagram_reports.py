from datetime import datetime, time
from collections import Counter
from ..utils import get_month_range,gpt_classify_text
from ..models import InstagramMessage, InstagramComment
import requests

def monthly_report(user, year, month):
    start_date, end_date = get_month_range(year, month)
    instagram_id = user.instagram_account_id

    start_dt = datetime.combine(start_date, time.min)
    end_dt = datetime.combine(end_date, time.max)

    messages = InstagramMessage.objects.filter(
        recipient_id=instagram_id,
        timestamp__range=(start_dt, end_dt)
    )

    comments = InstagramComment.objects.filter(
        recipient_id=instagram_id,
        timestamp__range=(start_dt, end_dt)
    )

    unique_senders = set(
        list(messages.values_list("sender_id", flat=True)) +
        list(comments.values_list("sender_id", flat=True))
    )

    days = (end_date - start_date).days + 1

    return {
        "period": start_date.strftime("%Y-%m"),
        "messages_total": messages.count(),
        "messages_daily_avg": round(messages.count() / days, 2),
        "comments_total": comments.count(),
        "comments_daily_avg": round(comments.count() / days, 2),
        "conversations": len(unique_senders),
    }


def best_worst_posts(user, year, month):
    start_date, end_date = get_month_range(year, month)

    url = f"https://graph.facebook.com/v23.0/{user.instagram_account_id}/media"
    params = {
        "fields": "id,permalink,timestamp,like_count,comments_count",
        "access_token": user.instagram_access_token,
        "limit": 50
    }

    data = requests.get(url, params=params).json().get("data", [])

    posts = []
    for post in data:
        post_date = datetime.fromisoformat(post["timestamp"]).date()
        if start_date <= post_date <= end_date:
            engagement = post.get("like_count", 0) + post.get("comments_count", 0)
            post["engagement"] = engagement
            posts.append(post)

    if not posts:
        return None

    return {
        "best_post": max(posts, key=lambda x: x["engagement"]),
        "worst_post": min(posts, key=lambda x: x["engagement"]),
    }


def complaints_and_reviews(user, year, month):
    start_date, end_date = get_month_range(year, month)
    instagram_id = user.instagram_account_id

    messages = InstagramMessage.objects.filter(
        recipient_id=instagram_id,
        timestamp__date__range=(start_date, end_date)
    )

    comments = InstagramComment.objects.filter(
        recipient_id=instagram_id,
        timestamp__date__range=(start_date, end_date)
    )

    complaints = []
    sentiment = {"Positive": 0, "Neutral": 0, "Negative": 0}

    for obj in list(messages) + list(comments):
        text = getattr(obj, "message", None) or obj.comment
        s = gpt_classify_text(text, "sentiment")
        c = gpt_classify_text(text, "complaint")

        if s in sentiment:
            sentiment[s] += 1
        if c == "Yes":
            complaints.append(text)

    top = Counter(complaints).most_common(5)

    return {
        "sentiment": sentiment,
        "top_complaints": [{"topic": k, "count": v} for k, v in top]
    }
