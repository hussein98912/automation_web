# utils.py

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
