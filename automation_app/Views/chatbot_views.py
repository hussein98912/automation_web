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
    message = request.data.get("message", "")
    files = request.FILES.get("attachment")
    user = User.objects.filter(id=user_id).first() if user_id else None

    # Retrieve last 5 conversations
    history_qs = ChatHistory.objects.filter(user_id=user_id).order_by("-timestamp")[:5]
    history = [{"q": h.message, "a": h.response} for h in history_qs][::-1]

    bot_reply = ""
    temp_order = ORDER_TEMP.get(user_id, {
        "service": None,
        "industry": None,
        "host_duration": None,
        "workflow_name": None,
        "workflow_details": None,
        "workflow_name_choices": None,
        "workflow_details_choices": None,
        "file_attached": None,
        "file_attached_checked": False
    })

    normalized_msg = normalize_text(message)

    # ===== Step 1: Select Service =====
    if not temp_order["service"]:
        found_service = None
        for svc in Service.objects.all():
            if normalize_text(svc.title) in normalized_msg:
                found_service = svc
                break
        if not found_service:
            svc_titles = [s.title for s in Service.objects.all()]
            matched_title = fuzzy_match(normalized_msg, svc_titles)
            if matched_title:
                found_service = Service.objects.filter(title=matched_title).first()

        if found_service:
            temp_order["service"] = found_service
            bot_reply = f"✅ Great! You selected **{found_service.title}**."
            bot_reply += "\nWhich industry does this workflow belong to? (type your own or leave blank for 'General')"
        else:
            bot_reply = "Hello! Which service do you want to automate? (Workflow Automation, RPA, AI Chatbot, Predictive Analytics, Workflow Design)"

    # ===== Step 2: Select Industry =====
    elif temp_order["service"] and not temp_order["industry"]:
        industry_input = message.strip()
        temp_order["industry"] = industry_input if industry_input else "General"
        bot_reply = f"✅ Industry set to **{temp_order['industry']}**.\nWhich hosting plan do you want? (1 month, 3 months, 6 months, 12 months)"

    # ===== Step 3: Select Hosting Duration =====
    elif not temp_order["host_duration"]:
        durations = ["1 month", "3 months", "6 months", "12 months"]
        selected = fuzzy_match(normalized_msg, durations)
        if selected:
            temp_order["host_duration"] = selected.replace(" ", "_")
            bot_reply = "Perfect! What should be the workflow name? You can type 'suggest' to get suggestions."
        else:
            bot_reply = "Please select a valid hosting duration: 1 month, 3 months, 6 months, 12 months."

    # ===== Step 4: Workflow Name =====
    elif not temp_order["workflow_name"]:
        if "suggest" in normalized_msg:
            # Pass both service and industry for better relevance
            service_title = temp_order["service"].title if temp_order.get("service") else "Automation"
            industry = temp_order.get("industry", "General")
            choices = suggest_workflow_name(service_title, industry)  # 👈 updated here
            choices = clean_suggestions(choices, max_words=5)  # clean suggestions if you have that helper
            temp_order["workflow_name_choices"] = choices

            bot_reply = (
                f"Here are 3 workflow name suggestions for the **{industry}** industry:\n"
                + "\n".join([f"{i+1}. {c}" for i, c in enumerate(choices)])
                + "\nReply with the number of your choice or type your own."
            )

        elif temp_order.get("workflow_name_choices"):
            choice = ''.join(filter(str.isdigit, normalized_msg))
            if choice in ["1", "2", "3"]:
                idx = int(choice) - 1
                temp_order["workflow_name"] = temp_order["workflow_name_choices"][idx]
                temp_order.pop("workflow_name_choices", None)  # remove suggestions
                bot_reply = (
                    f"✅ Selected workflow name: **{temp_order['workflow_name']}**\n"
                    "Now, can you provide workflow details or type 'suggest'?"
                )
            else:
                temp_order["workflow_name"] = message
                temp_order.pop("workflow_name_choices", None)
                bot_reply = (
                    "Got it! Can you provide the workflow details? You can type 'suggest' to get suggestions."
                )

        else:
            temp_order["workflow_name"] = message
            bot_reply = (
                "Got it! Can you provide the workflow details? You can type 'suggest' to get suggestions."
            )

    # ===== Step 5: Workflow Details =====
    elif not temp_order["workflow_details"]:
        if "suggest" in normalized_msg:
            choices = suggest_workflow_details(
                temp_order["workflow_name"],
                service=temp_order["service"].title if temp_order.get("service") else None,
                industry=temp_order.get("industry")
                )
            choices = clean_suggestions(choices, max_words=30)  # allow longer descriptions
            temp_order["workflow_details_choices"] = choices
            bot_reply = "Here are 3 workflow details suggestions:\n" + \
                        "\n".join([f"{i+1}. {c}" for i, c in enumerate(choices)]) + \
                        "\nReply with the number of your choice or type your own."
        elif temp_order.get("workflow_details_choices"):
            choice = ''.join(filter(str.isdigit, normalized_msg))
            if choice in ["1", "2", "3"]:
                idx = int(choice)-1
                temp_order["workflow_details"] = temp_order["workflow_details_choices"][idx]
                temp_order.pop("workflow_details_choices", None)
                bot_reply = "✅ Workflow details saved.\nDo you want to attach a file? (yes/no)"
            else:
                temp_order["workflow_details"] = message
                temp_order.pop("workflow_details_choices", None)
                bot_reply = "Do you want to attach a file? (yes/no)"
        else:
            temp_order["workflow_details"] = message
            bot_reply = "Do you want to attach a file? (yes/no)"

    # ===== Step 6: File Attachment =====
    elif not temp_order.get("file_attached_checked"):
        normalized_msg = message.lower().strip()
        if normalized_msg in ["no", "nope", "nah"]:
            temp_order["file_attached"] = None
            temp_order["file_attached_checked"] = True
            bot_reply = "Okay, no problem 😊 You can type 'price' to see the total or 'confirm' to submit."
        elif normalized_msg in ["yes", "yep", "yeah"]:
            temp_order["file_attached"] = True
            bot_reply = "Please upload your file now 📎"
        else:
            bot_reply = "Please answer 'yes' or 'no'."

    # ===== Step 7: Price & Confirm =====
    else:
        normalized_msg = message.lower().strip()
        if normalized_msg in ["price", "total", "how much"]:
            if temp_order["service"] and temp_order["host_duration"]:
                total_price = calculate_order_price(temp_order["service"].title, temp_order["host_duration"])
                bot_reply = f"💰 Total price: ${total_price:.2f}\nType 'confirm' to submit or 'cancel' to discard."
            else:
                bot_reply = "Please complete your service and hosting selection first."
        elif normalized_msg in ["confirm", "submit", "ok", "okay"]:
                total_price = calculate_order_price(temp_order["service"].title, temp_order["host_duration"])
                order = Order.objects.create(
                    user=user,
                    service=temp_order["service"],
                    industry=temp_order["industry"],
                    host_duration=temp_order["host_duration"],
                    workflow_name=temp_order["workflow_name"],
                    workflow_details=temp_order["workflow_details"],
                    attachment=files if temp_order.get("file_attached") else None,
                    total_price=total_price
                )

                # Build the friendly final message
                bot_reply = (
                    f"✅ Order **{temp_order['workflow_name']}** submitted successfully! 🎉\n\n"
                    f"💼 Service: {temp_order['service'].title}\n"
                    f"🏭 Industry: {temp_order['industry']}\n"
                    f"🕒 Hosting Duration: {temp_order['host_duration'].replace('_', ' ')}\n"
                    f"💡 Workflow Name: {temp_order['workflow_name']}\n"
                    f"📄 Workflow Details: {temp_order['workflow_details']}\n"
                    f"💰 Total Price: ${total_price:.2f}\n\n"
                    "Our team will contact you soon to start building your workflow. Thank you! 😊"
                )

                ORDER_TEMP.pop(user_id, None)
        elif normalized_msg in ["cancel", "no", "stop"]:
            ORDER_TEMP.pop(user_id, None)
            bot_reply = "❌ Your order has been cancelled."
        else:
            bot_reply = "Type 'confirm' to submit, 'cancel' to discard, or 'price' to see total."

    # Save conversation
    ChatHistory.objects.create(user_id=user_id or "guest", message=message, response=bot_reply)
    ORDER_TEMP[user_id] = temp_order

    return Response({
        "user_message": message,
        "bot_response": bot_reply,
        "conversation": history + [{"q": message, "a": bot_reply}]
    })