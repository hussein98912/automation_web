# utils.py
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import random
import openai
import os
from dotenv import load_dotenv

# دالة لتوليد اسم workflow مقترح
def suggest_workflow_name(service_title):
    suggestions = {
        "Workflow Automation": ["AutoFlow 2025", "Smart Workflow", "QuickProcess"],
        "Robotic Process Automation": ["RPA Bot 1", "AutoBot Workflow", "RPA Streamline"],
        "AI Chatbot": ["SmartChat 2025", "BotFlow", "AI Assistant Workflow"],
        "Predictive Analytics": ["PredictPro", "DataInsight", "ForecastFlow"],
        "Workflow Design": ["DesignFlow", "ProcessBuilder", "Custom Workflow"]
    }
    return random.choice(suggestions.get(service_title, ["My Workflow"]))

# دالة لتوليد تفاصيل workflow مقترحة
def suggest_workflow_details(workflow_name):
    templates = [
        f"{workflow_name} will automate repetitive tasks to save time.",
        f"{workflow_name} integrates multiple services for smooth workflow.",
        f"{workflow_name} provides notifications and reports automatically.",
        f"{workflow_name} tracks data and generates insights."
    ]
    return random.choice(templates)


def send_real_time_notification(user_id: int, message: str):
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"user_{user_id}",
        {
            "type": "send_notification",
            "message": message,
            "user_id": user_id
        }
    )

import secrets
import string

def generate_api_key():
    alphabet = string.ascii_letters + string.digits
    return "sk_" + "".join(secrets.choice(alphabet) for _ in range(32))


from datetime import date
import calendar

def get_month_range(year=None, month=None):
    """
    Returns start_date and end_date for a given month.
    If year/month are not provided, defaults to current month.
    """
    today = date.today()

    year = int(year) if year else today.year
    month = int(month) if month else today.month

    if month < 1 or month > 12:
        raise ValueError("Month must be between 1 and 12")

    start_date = date(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    end_date = date(year, month, last_day)

    return start_date, end_date

load_dotenv()
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

def gpt_classify_text(text, task="sentiment"):
    if not text:
        return "neutral" if task == "sentiment" else "No"

    if task == "sentiment":
        prompt = f'Classify the sentiment of the following text as Positive, Neutral, or Negative.\nText: "{text}"\nRespond with exactly one word: Positive, Neutral, or Negative.'
    elif task == "complaint":
        prompt = f'Does the following text contain a complaint about a product or service?\nText: "{text}"\nRespond with exactly Yes or No.'
    else:
        raise ValueError("Invalid task")

    try:
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": "You are a text classifier."},
                {"role": "user", "content": prompt}
            ],
            temperature=0
        )

        # New API returns content like this:
        answer = response.choices[0].message.content.strip()
        return answer

    except Exception as e:
        print("GPT classification error:", e)
        return "neutral" if task == "sentiment" else "No"