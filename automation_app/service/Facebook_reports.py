from datetime import datetime, time
from collections import Counter
from ..utils import get_month_range, gpt_classify_text
from ..models import FacebookMessage, FacebookComment
import requests


def monthly_report(user, year, month):
    start_date, end_date = get_month_range(year, month)
    page_id = user.facebook_page_id

    if not page_id:
        return {"error": "Facebook page not connected"}

    start_dt = datetime.combine(start_date, time.min)
    end_dt = datetime.combine(end_date, time.max)

    messages = FacebookMessage.objects.filter(
        recipient_page_id=page_id,
        timestamp__range=(start_dt, end_dt)
    )

    comments = FacebookComment.objects.filter(
        recipient_id=page_id,
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

    if not user.facebook_page_id or not user.facebook_access_token:
        return {"error": "Facebook page or access token missing"}

    url = f"https://graph.facebook.com/v24.0/{user.facebook_page_id}/posts"
    params = {
        "fields": "id,created_time,permalink_url,likes.summary(true),comments.summary(true)",
        "access_token": user.facebook_access_token,
        "limit": 50
    }

    data = requests.get(url, params=params).json().get("data", [])

    posts = []
    for post in data:
        post_date = datetime.fromisoformat(
            post["created_time"].replace("Z", "+00:00")
        ).date()

        if start_date <= post_date <= end_date:
            likes = post.get("likes", {}).get("summary", {}).get("total_count", 0)
            comments = post.get("comments", {}).get("summary", {}).get("total_count", 0)

            post["likes"] = likes
            post["comments_count"] = comments
            post["engagement"] = likes + comments

            posts.append(post)

    if not posts:
        return None

    return {
        "best_post": max(posts, key=lambda x: x["engagement"]),
        "worst_post": min(posts, key=lambda x: x["engagement"]),
    }



def complaints_and_reviews(user, year, month):
    start_date, end_date = get_month_range(year, month)
    page_id = user.facebook_page_id

    if not page_id:
        return {"error": "Facebook page not connected"}

    messages = FacebookMessage.objects.filter(
        recipient_page_id=page_id,
        timestamp__date__range=(start_date, end_date)
    )

    comments = FacebookComment.objects.filter(
        recipient_id=page_id,
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
