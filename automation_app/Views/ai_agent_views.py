# ai_agent/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser,AllowAny
from django.conf import settings
from ..models import BusinessSession,BusinessSessionOrder,AgentAPIKey,SDKChatSession,TelegramBot,Plan,Order
from openai import OpenAI
import os
import requests
from dotenv import load_dotenv
from django.shortcuts import get_object_or_404
from rest_framework import status
from ..utils import generate_api_key
from ..serializers import BusinessSessionOrderCreateSerializer,BusinessSessionOrderSerializer, AdminUpdateOrderSerializer
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponse
import stripe



load_dotenv()  # loads .env
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# Create OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)


class AIChatView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        message = request.data.get("message")
        session_id = request.data.get("session_id")

        # Validate input
        if not session_id:
            return Response({"error": "session_id is required"}, status=400)
        if not message:
            return Response({"error": "message is required"}, status=400)

        # Retrieve session safely
        session = get_object_or_404(BusinessSession, id=session_id, user=user)

        # Determine plan and usage limit
        plan = session.plan
        if not plan:
            return Response({"error": "No plan assigned to this session."}, status=403)

        usage_count = session.messages_used

        if usage_count >= plan.max_messages:
            return Response({
                "error": "Message limit reached for your plan.",
                "usage_count": usage_count,
                "usage_limit": plan.max_messages
            }, status=403)

        # Append user message
        chat_history = session.chat_history or []
        chat_history.append({"role": "user", "content": message})

        # Build system prompt
        system_prompt = f"""
You are an AI Customer Service agent for the following business:

Business Name: {session.name}
Business Type: {session.business_type}
Description: {session.business_description}

Speak as the business itself.
Be professional, polite, and helpful.
Answer questions clearly and accurately.
Only ask clarifying questions if necessary.
"""

        messages = [{"role": "system", "content": system_prompt}] + chat_history

        # Call OpenAI
        try:
            completion = client.chat.completions.create(
                model=plan.model_name,
                messages=messages,
                temperature=0.7,
                max_tokens=plan.max_tokens
            )
        except Exception as e:
            return Response({"error": "AI service unavailable", "details": str(e)}, status=503)

        reply = completion.choices[0].message.content

        # Save assistant reply
        chat_history.append({"role": "assistant", "content": reply})
        session.chat_history = chat_history
        session.messages_used += 1
        session.save(update_fields=["chat_history", "messages_used"])

        return Response({
            "message_id": len(chat_history),
            "response": reply,
            "usage_count": session.messages_used,
            "usage_limit": plan.max_messages
        }, status=200)


class CreateBusinessSessionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        name = request.data.get("name")
        business_type = request.data.get("business_type")
        business_description = request.data.get("business_description")
        plan_id = request.data.get("plan_id")  # <- user sends the desired plan

        if not name:
            return Response({"error": "Agent name is required."}, status=400)
        if not business_type or not business_description:
            return Response({"error": "Business type and description are required."}, status=400)
        
        # Determine plan
        if plan_id:
            plan = get_object_or_404(Plan, id=plan_id)
        else:
            plan = Plan.objects.get(name="Free")  # default plan

        session = BusinessSession.objects.create(
            user=user,
            name=name,
            business_type=business_type,
            business_description=business_description,
            plan=plan,
            chat_history=[],
            messages_used=0
        )

        return Response({
            "message": f"AI Customer Service '{name}' for {business_type} created successfully.",
            "session_id": session.id,
            "plan": plan.name
        }, status=201)
    

class ChatHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, session_id):
        user = request.user

        session = get_object_or_404(BusinessSession, id=session_id, user=user)

        chat_history = session.chat_history or []

        # Prepare messages
        messages = [
            {
                "id": idx + 1,
                "role": msg.get("role"),
                "content": msg.get("content"),
                "timestamp": session.created_at.isoformat()
            }
            for idx, msg in enumerate(chat_history)
        ]

        usage_count = sum(1 for msg in chat_history if msg.get("role") == "user")

        # Get plan info
        plan = session.plan
        usage_limit = plan.max_messages if plan else 10
        plan_name = plan.name if plan else "Free"

        # Order info
        order = (
            BusinessSessionOrder.objects
            .filter(session=session, user=user)
            .order_by("-created_at")
            .first()
        )

        return Response(
            {
                "id": str(session.id),
                "business_type": session.business_type,
                "business_description": session.business_description,
                "created_at": session.created_at.isoformat(),
                "plan": plan_name,
                "messages": messages,
                "usage_count": usage_count,
                "usage_limit": usage_limit,
                # Order metadata
                "order": {
                    "order_id": order.id if order else None,
                    "status": order.status if order else None,
                    "status_label": (
                        dict(BusinessSessionOrder.STATUS_CHOICES).get(order.status)
                        if order else None
                    ),
                },
            },
            status=200
        )


class UserBotsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        sessions = BusinessSession.objects.filter(user=user).order_by("-created_at")
        bots = []

        for session in sessions:
            chat_history = session.chat_history or []
            usage_count = sum(1 for msg in chat_history if msg.get("role") == "user")

            # Plan info
            plan = session.plan
            usage_limit = plan.max_messages if plan else 10
            plan_name = plan.name if plan else "Free"

            # Order info
            order = (
                BusinessSessionOrder.objects
                .filter(session=session, user=user)
                .order_by("-created_at")
                .first()
            )

            # Subscriptions
            telegram_subscribed = TelegramBot.objects.filter(
                business_session=session, is_active=True
            ).exists()
            sdk_subscribed = AgentAPIKey.objects.filter(agent=session).exists()

            bots.append({
                "id": str(session.id),
                "name": session.name,
                "business_type": session.business_type,
                "business_description": session.business_description,
                "createdAt": session.created_at.isoformat(),
                "plan": plan_name,
                "usageCount": usage_count,
                "usageLimit": usage_limit,
                "subscriptions": {
                    "telegram": telegram_subscribed,
                    "sdk": sdk_subscribed
                },
                "order": {
                    "order_id": order.id if order else None,
                    "status": order.status if order else None,
                    "status_label": (
                        dict(BusinessSessionOrder.STATUS_CHOICES).get(order.status)
                        if order else None
                    ),
                }
            })

        return Response(bots, status=200)
    

    

class BusinessSessionOrderCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = BusinessSessionOrderCreateSerializer(
            data=request.data,
            context={"request": request}
        )
        if serializer.is_valid():
            order = serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class UserOrdersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_orders = BusinessSessionOrder.objects.filter(user=request.user)
        serializer = BusinessSessionOrderSerializer(user_orders, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminAllOrdersView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        all_orders = BusinessSessionOrder.objects.all()
        serializer = BusinessSessionOrderSerializer(all_orders, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class AdminUpdateOrderView(APIView):
    permission_classes = [IsAdminUser]

    def patch(self, request, order_id):
        order = get_object_or_404(BusinessSessionOrder, id=order_id)
        serializer = AdminUpdateOrderSerializer(order, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response({"message": "Order updated successfully"}, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class GenerateAgentAPIKeyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        agent_id = request.data.get("agent_id")
        if not agent_id:
            return Response({"success": False, "error": "agent_id is required"}, status=400)

        agent = get_object_or_404(BusinessSession, id=agent_id, user=request.user)

        raw_key = generate_api_key()
        key_hash = AgentAPIKey.hash_key(raw_key)

        AgentAPIKey.objects.create(agent=agent, key_hash=key_hash)

        return Response({"success": True, "api_key": raw_key, "agent_id": agent.id})


class SDKChatView(APIView):
    permission_classes = []

    def post(self, request):
        api_key = request.data.get("api_key")
        message = request.data.get("message")
        session_id = request.data.get("session_id")

        if not api_key or not message:
            return Response({"success": False, "error": "api_key and message are required"}, status=400)

        key_hash = AgentAPIKey.hash_key(api_key)
        api_key_obj = get_object_or_404(AgentAPIKey.objects.select_related("agent"), key_hash=key_hash, is_active=True)

        agent = api_key_obj.agent  # BusinessSession
        plan_limit = agent.plan.max_messages if agent.plan else 10

        # Load or create SDK session
        chat_history = []
        if session_id:
            sdk_session, _ = SDKChatSession.objects.get_or_create(api_key=api_key_obj, session_id=session_id)
            chat_history = sdk_session.chat_history

        usage_count = sum(1 for m in chat_history if m["role"] == "user")
        if usage_count >= plan_limit:
            return Response({"success": False, "error": "Message limit reached"}, status=403)

        # Append user message
        chat_history.append({"role": "user", "content": message})

        # System prompt
        system_prompt = f"""
You are an AI Customer Service agent for the following business:
Business Name: {agent.name}
Business Type: {agent.business_type}
Description: {agent.business_description}

Speak as the business itself. Be professional, polite, and helpful.
"""
        messages = [{"role": "system", "content": system_prompt}] + chat_history

        # OpenAI request
        completion = client.chat.completions.create(model="gpt-4", messages=messages, temperature=0.7, max_tokens=500)
        reply = completion.choices[0].message.content

        chat_history.append({"role": "assistant", "content": reply})

        if session_id:
            sdk_session.chat_history = chat_history
            sdk_session.save(update_fields=["chat_history"])

        return Response({"success": True, "response": reply, "session_id": session_id})


class ConnectTelegramBotView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        business_session_id = request.data.get("session_id")
        bot_token = request.data.get("bot_token")

        if not business_session_id or not bot_token:
            return Response({"error": "session_id and bot_token are required"}, status=400)

        session = get_object_or_404(BusinessSession, id=business_session_id, user=request.user)

        # Validate Telegram bot token
        tg_check = requests.get(f"https://api.telegram.org/bot{bot_token}/getMe")
        if tg_check.status_code != 200:
            return Response({"error": "Invalid Telegram bot token"}, status=400)

        TelegramBot.objects.update_or_create(
            bot_token=bot_token, defaults={"business_session": session, "is_active": True}
        )

        # Set webhook
        webhook_url = f"{settings.BACKEND_BASE_URL}/telegram/webhook/{bot_token}/"
        requests.post(f"https://api.telegram.org/bot{bot_token}/setWebhook", json={"url": webhook_url})

        return Response({"success": True, "message": "Telegram bot connected successfully", "business_session_id": session.id})


class TelegramWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, bot_token):
        data = request.data
        message = data.get("message")
        if not message or "text" not in message:
            return Response({"ok": True})

        chat_id = str(message["chat"]["id"])
        text = message["text"]

        try:
            telegram_bot = TelegramBot.objects.select_related("business_session").get(bot_token=bot_token)
        except TelegramBot.DoesNotExist:
            return Response({"ok": True})

        session = telegram_bot.business_session
        chat_history = session.chat_history or []

        plan_limit = session.plan.max_messages if session.plan else 10
        usage_count = sum(1 for msg in chat_history if msg.get("role") == "user" and msg.get("chat_id") == chat_id)

        if usage_count >= plan_limit:
            reply = "Message limit reached for this session."
        else:
            chat_history.append({"chat_id": chat_id, "role": "user", "content": text})

            system_prompt = f"""
You are an AI Customer Service agent for the following business:
Business Name: {session.name}
Business Type: {session.business_type}
Description: {session.business_description}

Speak as the business itself. Be professional, polite, and helpful.
"""
            messages = [{"role": "system", "content": system_prompt}] + chat_history
            completion = client.chat.completions.create(model="gpt-4", messages=messages, temperature=0.7, max_tokens=500)
            reply = completion.choices[0].message.content

            chat_history.append({"chat_id": chat_id, "role": "assistant", "content": reply})
            session.chat_history = chat_history
            session.save(update_fields=["chat_history"])

        # Send reply to Telegram
        requests.post(f"https://api.telegram.org/bot{bot_token}/sendMessage", json={"chat_id": chat_id, "text": reply})

        return Response({"ok": True})

    

class CreateStripeCheckoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        session_id = request.data.get("session_id")
        plan_id = request.data.get("plan_id")

        business_session = get_object_or_404(BusinessSession, id=session_id, user=request.user)
        plan = get_object_or_404(Plan, id=plan_id)

        # Create order
        order = BusinessSessionOrder.objects.create(
            user=request.user,
            session=business_session,
            plan=plan,
            status="pending"
        )

        checkout = stripe.checkout.Session.create(
            mode="subscription",
            payment_method_types=["card"],
            line_items=[{
                "price": plan.stripe_price_id,
                "quantity": 1
            }],
            success_url=settings.FRONTEND_URL + "/dashboard/products/bot-builder/",
            cancel_url=settings.FRONTEND_URL + "/dashboard/products/bot-builder/",
            metadata={"order_id": str(order.id)}
        )

        order.stripe_session_id = checkout.id
        order.save(update_fields=["stripe_session_id"])

        return Response({"checkout_url": checkout.url})
    

@csrf_exempt
def stripe_webhook(request):
    payload = request.body
    sig_header = request.META.get("HTTP_STRIPE_SIGNATURE")

    try:
        event = stripe.Webhook.construct_event(
            payload,
            sig_header,
            settings.STRIPE_WEBHOOK_SECRET
        )
    except Exception as e:
        print("Webhook error:", e)
        return HttpResponse(status=400)

    event_type = event["type"]
    data = event["data"]["object"]

    # --------------------------
    # 1️⃣ Checkout completed
    # --------------------------
    if event_type == "checkout.session.completed":
        # Grab metadata to identify what is being paid
        metadata = data.get("metadata", {})

        # --- Order payment ---
        order_id = metadata.get("order_id")
        if order_id:
            order = Order.objects.filter(id=order_id).first()
            if order:
                order.status = "in_progress"  # mark as paid & processing
                order.save(update_fields=["status"])

        # --- BusinessSession plan purchase/upgrade ---
        session_id = metadata.get("business_session_id")
        plan_price_id = data.get("display_items", [{}])[0].get("price", {}).get("id")
        if session_id and plan_price_id:
            session = BusinessSession.objects.filter(id=session_id).first()
            plan = Plan.objects.filter(stripe_price_id=plan_price_id).first()
            if session and plan:
                session.plan = plan
                session.save(update_fields=["plan"])

    # --------------------------
    # 2️⃣ Payment failed
    # --------------------------
    elif event_type == "invoice.payment_failed":
        subscription_id = data.get("subscription")

        # Update Order status if linked
        order = Order.objects.filter(stripe_subscription_id=subscription_id).first()
        if order:
            order.status = "cancelled"
            order.save(update_fields=["status"])

    # --------------------------
    # 3️⃣ Subscription canceled
    # --------------------------
    elif event_type == "customer.subscription.deleted":
        subscription_id = data.get("id")

        # Update Order
        order = Order.objects.filter(stripe_subscription_id=subscription_id).first()
        if order:
            order.status = "cancelled"
            order.save(update_fields=["status"])

        # Update BusinessSession plan to Free if subscription canceled
        session = BusinessSession.objects.filter(stripe_subscription_id=subscription_id).first()
        if session:
            free_plan = Plan.objects.get(name="Free")
            session.plan = free_plan
            session.save(update_fields=["plan"])

    # --------------------------
    # 4️⃣ Optional: payment intent succeeded (info)
    # --------------------------
    elif event_type == "payment_intent.succeeded":
        intent_id = data.get("id")
        order = Order.objects.filter(stripe_payment_intent_id=intent_id).first()
        if order:
            order.status = "in_progress"
            order.save(update_fields=["status"])

    return HttpResponse(status=200)



class PlansListView(APIView):
    permission_classes = []

    def get(self, request):
        plans = Plan.objects.all()
        data = [
            {
                "id": plan.id,
                "name": plan.name,
                "max_messages": plan.max_messages,
                "price": float(plan.price),
            }
            for plan in plans
        ]
        return Response(data)