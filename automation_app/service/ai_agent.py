import os
import json
from django.utils import timezone
from openai import OpenAI

from .instagram_reports import (
    monthly_report,
    best_worst_posts,
    complaints_and_reviews
)
from .model_extractors import most_active_users


SYSTEM_PROMPT = """
You are an AI assistant for Instagram business analytics.

Rules:
- Use tools only
- Never guess
- Use today's date to resolve phrases like "this month" or "last month"
- If no data exists, say so clearly
- Summarize insights clearly and professionally
"""


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "monthly_report",
            "description": "Get Instagram monthly statistics",
            "parameters": {
                "type": "object",
                "properties": {
                    "year": {"type": "integer"},
                    "month": {"type": "integer"}
                },
                "required": ["year", "month"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "best_worst_posts",
            "description": "Get best and worst posts",
            "parameters": {
                "type": "object",
                "properties": {
                    "year": {"type": "integer"},
                    "month": {"type": "integer"}
                },
                "required": ["year", "month"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "complaints_and_reviews",
            "description": "Analyze complaints and sentiment",
            "parameters": {
                "type": "object",
                "properties": {
                    "year": {"type": "integer"},
                    "month": {"type": "integer"}
                },
                "required": ["year", "month"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "most_active_users",
            "description": "Get most active users",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        }
    }
]


client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def run_ai_agent(user, user_message):
    today = timezone.now().date()

    messages = [
        {
            "role": "system",
            "content": f"{SYSTEM_PROMPT}\n\nToday's date is {today}."
        },
        {
            "role": "user",
            "content": user_message
        }
    ]

    response = client.chat.completions.create(
        model="gpt-4.1",
        messages=messages,
        tools=TOOLS,
        tool_choice="auto"
    )

    msg = response.choices[0].message

    # 🔹 MUST append assistant message FIRST
    messages.append(msg)

    # ---------- MULTI TOOL HANDLING ----------
    if msg.tool_calls:
        for tool_call in msg.tool_calls:
            tool_name = tool_call.function.name

            args = {}
            if tool_call.function.arguments:
                args = json.loads(tool_call.function.arguments)

            year = args.get("year", today.year)
            month = args.get("month", today.month)

            if tool_name == "monthly_report":
                result = monthly_report(user, year=year, month=month)

            elif tool_name == "best_worst_posts":
                result = best_worst_posts(user, year=year, month=month)

            elif tool_name == "complaints_and_reviews":
                result = complaints_and_reviews(user, year=year, month=month)

            elif tool_name == "most_active_users":
                result = most_active_users(user)

            else:
                result = {"error": "Unknown tool"}

            # 🔹 CRITICAL: respond to EACH tool_call_id
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": json.dumps(result)
            })

        # 🔹 Final model response
        final = client.chat.completions.create(
            model="gpt-4.1",
            messages=messages
        )

        return final.choices[0].message.content

    return msg.content

# Facebok ----------------------------------------------------------------------------


from .Facebook_reports import (
    monthly_report,
    best_worst_posts,
    complaints_and_reviews
)
from .model_extractors import most_active_users

SYSTEM_PROMPT = """
You are an AI assistant for Facebook business analytics.

Rules:
- Use tools only
- Never guess
- Use today's date to resolve phrases like "this month" or "last month"
- If no data exists, say so clearly
- Summarize insights clearly and professionally
"""



