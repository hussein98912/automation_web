# utils.py
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import random

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