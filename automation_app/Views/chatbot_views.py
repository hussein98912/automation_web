from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.contrib.auth import get_user_model
from difflib import get_close_matches
import re
from ..models import ChatHistory, Order, Service
from ..Ai import suggest_workflow_name, suggest_workflow_details
from ..price import calculate_order_price

User = get_user_model()

ORDER_TEMP = {}
SERVICE_KEYWORDS = {
    "workflow automation": "Workflow Automation",
    "robotic process automation": "Robotic Process Automation",
    "rpa": "Robotic Process Automation",
    "ai chatbot": "AI Chatbot",
    "chatbot": "AI Chatbot",
    "predictive analytics": "Predictive Analytics",
    "workflow design": "Workflow Design"
}

def normalize_text(text):
    return re.sub(r'[^a-z0-9]', '', text.lower())

def fuzzy_match(word, options):
    word = word.lower()
    options = [opt.lower() for opt in options]
    matches = get_close_matches(word, options, n=1, cutoff=0.6)
    return matches[0] if matches else None

def clean_suggestions(raw_lines, max_words=5):
    """
    Remove headers and keep only meaningful suggestions.
    """
    cleaned = [line.strip("•-0123456789. ").strip() for line in raw_lines if line.strip()]
    cleaned = [line for line in cleaned if len(line.split()) <= max_words and not line.lower().startswith("here are")]
    return cleaned[:3]


@api_view(["POST"])
def chatbot_api(request):
    user_id = request.data.get("user_id")
    message = request.data.get("message")
    if not isinstance(message, str):
        message = ""  # prevent .lower() errors

    user = User.objects.filter(id=user_id).first() if user_id else None

    # Retrieve last 5 conversations
    history_qs = ChatHistory.objects.filter(user_id=user_id).order_by("-timestamp")[:5]
    history = [{"q": h.message, "a": h.response} for h in history_qs][::-1]

    # Load temp order
    temp_order = ORDER_TEMP.get(user_id, {
        "service": None,
        "industry": None,
        "host_duration": None,
        "workflow_name": None,
        "workflow_details": None,
        "workflow_name_choices": None,
        "workflow_details_choices": None
    })

    # Safe normalization helper
    def safe_normalize(txt):
        try:
            return normalize_text(txt)
        except:
            return ""

    normalized_msg = safe_normalize(message)

    # ===== Step 1: Select Service =====
    if not temp_order["service"]:
        found_service = None
        for svc in Service.objects.all():
            if safe_normalize(svc.title) in normalized_msg:
                found_service = svc
                break
        if not found_service:
            svc_titles = [s.title for s in Service.objects.all()]
            matched_title = fuzzy_match(normalized_msg, svc_titles)
            if matched_title:
                found_service = Service.objects.filter(title=matched_title).first()
        if found_service:
            temp_order["service"] = found_service
            bot_reply = f"✅ Service selected: {found_service.title}\nWhich industry?"
        else:
            bot_reply = "Which service do you want to automate? (Workflow Automation, RPA, AI Chatbot, Predictive Analytics, Workflow Design)"

    # ===== Step 2: Industry =====
    elif not temp_order["industry"]:
        temp_order["industry"] = message.strip() if message.strip() else "General"
        bot_reply = f"✅ Industry: {temp_order['industry']}\nWhich hosting plan? (1 month, 3 months, 6 months, 12 months)"

    # ===== Step 3: Hosting Duration =====
    elif not temp_order["host_duration"]:
        durations = ["1 month", "3 months", "6 months", "12 months"]
        selected = fuzzy_match(normalized_msg, durations)
        if selected:
            temp_order["host_duration"] = selected.replace(" ", "_")
            bot_reply = "Perfect! What should be the workflow name? Type 'suggest' if needed."
        else:
            bot_reply = "Please select a valid hosting duration: 1, 3, 6, or 12 months."

    # ===== Step 4: Workflow Name =====
    elif not temp_order["workflow_name"]:
        if "suggest" in normalized_msg:
            service_title = temp_order["service"].title
            industry = temp_order["industry"]
            choices = clean_suggestions(suggest_workflow_name(service_title, industry), max_words=5)
            temp_order["workflow_name_choices"] = choices
            bot_reply = "Here are 3 workflow name suggestions:\n" + "\n".join([f"{i+1}. {c}" for i, c in enumerate(choices)])
        elif temp_order.get("workflow_name_choices"):
            choice = ''.join(filter(str.isdigit, normalized_msg))
            if choice in ["1", "2", "3"]:
                temp_order["workflow_name"] = temp_order["workflow_name_choices"][int(choice)-1]
                temp_order.pop("workflow_name_choices", None)
                bot_reply = "✅ Workflow name selected. Now provide workflow details or type 'suggest'."
            else:
                temp_order["workflow_name"] = message
                temp_order.pop("workflow_name_choices", None)
                bot_reply = "Got it! Provide workflow details or type 'suggest'."
        else:
            temp_order["workflow_name"] = message
            bot_reply = "Got it! Provide workflow details or type 'suggest'."

    # ===== Step 5: Workflow Details =====
    elif not temp_order["workflow_details"]:
        if "suggest" in normalized_msg:
            choices = clean_suggestions(
                suggest_workflow_details(temp_order["workflow_name"], temp_order["service"].title, temp_order["industry"]),
                max_words=30
            )
            temp_order["workflow_details_choices"] = choices
            bot_reply = "Suggestions:\n" + "\n".join([f"{i+1}. {c}" for i, c in enumerate(choices)])
        elif temp_order.get("workflow_details_choices"):
            choice = ''.join(filter(str.isdigit, normalized_msg))
            if choice in ["1", "2", "3"]:
                temp_order["workflow_details"] = temp_order["workflow_details_choices"][int(choice)-1]
                temp_order.pop("workflow_details_choices", None)
                bot_reply = "✅ Workflow details saved. You can type 'price' to see total or 'confirm' to submit."
            else:
                temp_order["workflow_details"] = message
                temp_order.pop("workflow_details_choices", None)
                bot_reply = "Workflow details saved. You can type 'price' or 'confirm'."
        else:
            temp_order["workflow_details"] = message
            bot_reply = "Workflow details saved. You can type 'price' or 'confirm'."

    # ===== Step 6: Price + Confirm =====
    else:
        answer = message.lower().strip()
        if answer in ["price", "total", "how much"]:
            total_price = calculate_order_price(temp_order["service"].title, temp_order["host_duration"])
            bot_reply = f"💰 Total price: ${total_price:.2f}\nType 'confirm' or 'cancel'."
        elif answer in ["confirm", "ok", "okay", "submit"]:
            total_price = calculate_order_price(temp_order["service"].title, temp_order["host_duration"])
            Order.objects.create(
                user=user,
                service=temp_order["service"],
                industry=temp_order["industry"],
                host_duration=temp_order["host_duration"],
                workflow_name=temp_order["workflow_name"],
                workflow_details=temp_order["workflow_details"],
                total_price=total_price
            )
            bot_reply = f"✅ Order **{temp_order['workflow_name']}** submitted! 💰 Total: ${total_price:.2f}"
            ORDER_TEMP.pop(user_id, None)
        elif answer in ["cancel", "stop", "no"]:
            ORDER_TEMP.pop(user_id, None)
            bot_reply = "❌ Order cancelled."
        else:
            bot_reply = "Type 'confirm', 'cancel', or 'price'."

    # Save conversation
    ChatHistory.objects.create(
        user_id=user_id or "guest",
        message=message,
        response=bot_reply
    )

    ORDER_TEMP[user_id] = temp_order

    return Response({
        "user_message": message,
        "bot_response": bot_reply,
        "conversation": history + [{"q": message, "a": bot_reply}]
    })



