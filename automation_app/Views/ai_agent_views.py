# ai_agent/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser,AllowAny
from django.conf import settings
from ..models import BusinessSession,BusinessSessionOrder,AgentAPIKey,SDKChatSession,TelegramBot
from openai import OpenAI
import os
import requests
from dotenv import load_dotenv
from django.shortcuts import get_object_or_404
from rest_framework import status
from ..utils import generate_api_key
from ..serializers import BusinessSessionOrderCreateSerializer,BusinessSessionOrderSerializer, AdminUpdateOrderSerializer

load_dotenv()  # loads .env
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# Create OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)


class AIChatView(APIView):
    permission_classes = [IsAuthenticated]

    MAX_MESSAGES = 10  # max user messages per session

    def post(self, request):
        user = request.user
        message = request.data.get("message")
        session_id = request.data.get("session_id")

        # -------------------------
        # Validate input
        # -------------------------
        if not session_id:
            return Response(
                {"error": "session_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if not message:
            return Response(
                {"error": "message is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # -------------------------
        # Retrieve session safely
        # -------------------------
        session = get_object_or_404(
            BusinessSession,
            id=session_id,
            user=user
        )

        chat_history = session.chat_history or []

        # -------------------------
        # Enforce usage limit
        # -------------------------
        usage_count = sum(
            1 for msg in chat_history if msg.get("role") == "user"
        )

        if usage_count >= self.MAX_MESSAGES:
            return Response(
                {
                    "error": "Message limit reached",
                    "usage_count": usage_count,
                    "usage_limit": self.MAX_MESSAGES
                },
                status=status.HTTP_403_FORBIDDEN
            )

        # -------------------------
        # Append user message
        # -------------------------
        chat_history.append({
            "role": "user",
            "content": message
        })

        # -------------------------
        # Build system prompt
        # -------------------------
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

        messages = [
            {"role": "system", "content": system_prompt},
            *chat_history
        ]

        # -------------------------
        # OpenAI request
        # -------------------------
        try:
            completion = client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                temperature=0.7,
                max_tokens=500
            )
        except Exception as e:
            return Response(
                {"error": "AI service unavailable", "details": str(e)},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )

        reply = completion.choices[0].message.content

        # -------------------------
        # Save assistant reply
        # -------------------------
        chat_history.append({
            "role": "assistant",
            "content": reply
        })

        session.chat_history = chat_history
        session.save(update_fields=["chat_history"])

        # Update usage count
        usage_count += 1

        # -------------------------
        # Final response
        # -------------------------
        return Response(
            {
                "message_id": len(chat_history),
                "response": reply,
                "usage_count": usage_count,
                "usage_limit": self.MAX_MESSAGES
            },
            status=status.HTTP_200_OK
        )


class CreateBusinessSessionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        name = request.data.get("name")  
        business_type = request.data.get("business_type")
        business_description = request.data.get("business_description")

        if not name:
            return Response(
                {"error": "Agent name is required."},
                status=400
            )

        if not business_type or not business_description:
            return Response(
                {"error": "Business type and description are required."},
                status=400
            )

        session = BusinessSession.objects.create(
            user=user,
            name=name,  
            business_type=business_type,
            business_description=business_description,
            chat_history=[]
        )

        return Response({
            "message": f"AI Customer Service '{name}' for {business_type} created successfully.",
            "session_id": session.id,
            "name": session.name
        })
    

class ChatHistoryView(APIView):
    permission_classes = [IsAuthenticated]

    USAGE_LIMIT = 10

    def get(self, request, session_id):
        user = request.user

        session = get_object_or_404(
            BusinessSession,
            id=session_id,
            user=user
        )

        chat_history = session.chat_history or []

        messages = []
        for index, msg in enumerate(chat_history, start=1):
            messages.append({
                "id": index,
                "role": msg.get("role"),
                "content": msg.get("content"),
                "timestamp": session.created_at.isoformat()
            })

        usage_count = sum(
            1 for msg in chat_history if msg.get("role") == "user"
        )

        # -------------------------
        # Order info (if exists)
        # -------------------------
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
                "messages": messages,
                "usage_count": usage_count,
                "usage_limit": self.USAGE_LIMIT,

                # Order metadata
                "order": {
                    "order_id": order.id if order else None,
                    "status": order.status if order else None,
                    "status_label": (
                        dict(BusinessSessionOrder.STATUS_CHOICES).get(order.status)
                        if order else None
                    ),
                }
            },
            status=status.HTTP_200_OK
        )
    


class UserBotsView(APIView):
    permission_classes = [IsAuthenticated]

    DEFAULT_USAGE_LIMIT = 10

    def get(self, request):
        user = request.user
        sessions = BusinessSession.objects.filter(user=user).order_by("-created_at")

        bots = []

        for session in sessions:
            chat_history = session.chat_history or []

            usage_count = sum(
                1 for msg in chat_history if msg.get("role") == "user"
            )

            order = (
                BusinessSessionOrder.objects
                .filter(session=session, user=user)
                .order_by("-created_at")
                .first()
            )

            bots.append({
                "id": str(session.id),
                "name": session.name,
                "business_type": session.business_type,
                "business_description": session.business_description,
                "createdAt": session.created_at.isoformat(),
                "usageCount": usage_count,
                "usageLimit": self.DEFAULT_USAGE_LIMIT,

                # Order metadata
                "order": {
                    "order_id": order.id if order else None,
                    "status": order.status if order else None,
                    "status_label": (
                        dict(BusinessSessionOrder.STATUS_CHOICES).get(order.status)
                        if order else None
                    ),
                }
            })

        return Response(bots, status=status.HTTP_200_OK)
    

    

class BusinessSessionOrderCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = BusinessSessionOrderCreateSerializer(
            data=request.data,
            context={"request": request}
        )

        if serializer.is_valid():
            order = serializer.save()
            return Response(
                serializer.data,
                status=status.HTTP_201_CREATED
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )
    
 #1. Get orders of the logged-in user
class UserOrdersView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user_orders = BusinessSessionOrder.objects.filter(user=request.user)
        serializer = BusinessSessionOrderSerializer(user_orders, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# 2. Get all orders (admin)
class AdminAllOrdersView(APIView):
    permission_classes = [IsAdminUser]

    def get(self, request):
        all_orders = BusinessSessionOrder.objects.all()
        serializer = BusinessSessionOrderSerializer(all_orders, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


# 3. Admin updates an order
class AdminUpdateOrderView(APIView):
    permission_classes = [IsAdminUser]

    def patch(self, request, order_id):
        try:
            order = BusinessSessionOrder.objects.get(id=order_id)
        except BusinessSessionOrder.DoesNotExist:
            return Response(
                {"error": "Order not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = AdminUpdateOrderSerializer(order, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"message": "Order updated successfully"},
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    

class GenerateAgentAPIKeyView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        agent_id = request.data.get("agent_id")

        if not agent_id:
            return Response(
                {"success": False, "error": "agent_id is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        agent = get_object_or_404(
            BusinessSession,
            id=agent_id,
            user=request.user
        )

        raw_key = generate_api_key()
        key_hash = AgentAPIKey.hash_key(raw_key)

        AgentAPIKey.objects.create(
            agent=agent,
            key_hash=key_hash
        )

        return Response({
            "success": True,
            "api_key": raw_key,
            "agent_id": agent.id
        })
    

class SDKChatView(APIView):
    permission_classes = []

    MAX_MESSAGES = 20

    def post(self, request):
        api_key = request.data.get("api_key")
        message = request.data.get("message")
        session_id = request.data.get("session_id")

        if not api_key or not message:
            return Response(
                {"success": False, "error": "api_key and message are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        key_hash = AgentAPIKey.hash_key(api_key)

        try:
            api_key_obj = AgentAPIKey.objects.select_related("agent").get(
                key_hash=key_hash,
                is_active=True
            )
        except AgentAPIKey.DoesNotExist:
            return Response(
                {"success": False, "error": "Invalid API key"},
                status=status.HTTP_401_UNAUTHORIZED
            )

        agent = api_key_obj.agent  # BusinessSession

        chat_history = []

        if session_id:
            sdk_session, _ = SDKChatSession.objects.get_or_create(
                api_key=api_key_obj,
                session_id=session_id
            )
            chat_history = sdk_session.chat_history

        usage_count = sum(1 for m in chat_history if m["role"] == "user")
        if usage_count >= self.MAX_MESSAGES:
            return Response(
                {"success": False, "error": "Message limit reached"},
                status=status.HTTP_403_FORBIDDEN
            )

        chat_history.append({
            "role": "user",
            "content": message
        })

        system_prompt = f"""
You are an AI Customer Service agent for the following business:

Business Name: {agent.name}
Business Type: {agent.business_type}
Description: {agent.business_description}

Speak as the business itself.
Be professional, polite, and helpful.
"""

        messages = [
            {"role": "system", "content": system_prompt},
            *chat_history
        ]

        completion = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )

        reply = completion.choices[0].message.content

        chat_history.append({
            "role": "assistant",
            "content": reply
        })

        if session_id:
            sdk_session.chat_history = chat_history
            sdk_session.save(update_fields=["chat_history"])

        return Response({
            "success": True,
            "response": reply,
            "session_id": session_id
        })


class ConnectTelegramBotView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        business_session_id = request.data.get("session_id")
        bot_token = request.data.get("bot_token")

        if not business_session_id or not bot_token:
            return Response(
                {"error": "session_id and bot_token are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        session = get_object_or_404(
            BusinessSession,
            id=business_session_id,
            user=request.user
        )

        # Validate Telegram bot token
        tg_check = requests.get(
            f"https://api.telegram.org/bot{bot_token}/getMe"
        )

        if tg_check.status_code != 200:
            return Response(
                {"error": "Invalid Telegram bot token"},
                status=status.HTTP_400_BAD_REQUEST
            )

        TelegramBot.objects.update_or_create(
            bot_token=bot_token,
            defaults={
                "business_session": session,
                "is_active": True
            }
        )

        # IMPORTANT: webhook includes the bot token
        webhook_url = (
            f"{settings.BACKEND_BASE_URL}"
            f"/telegram/webhook/{bot_token}/"
        )

        requests.post(
            f"https://api.telegram.org/bot{bot_token}/setWebhook",
            json={"url": webhook_url}
        )

        return Response({
            "success": True,
            "message": "Telegram bot connected successfully",
            "business_session_id": session.id
        })
    

class TelegramWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, bot_token):
        data = request.data
        message = data.get("message")
        if not message or "text" not in message:
            return Response({"ok": True})

        chat_id = str(message["chat"]["id"])
        text = message["text"]

        # Get session from bot token
        try:
            telegram_bot = TelegramBot.objects.select_related("business_session").get(bot_token=bot_token)
        except TelegramBot.DoesNotExist:
            return Response({"ok": True})

        session = telegram_bot.business_session
        chat_history = session.chat_history or []

        # Track usage for this chat
        usage_count = sum(
            1 for msg in chat_history if msg.get("role") == "user" and msg.get("chat_id") == chat_id
        )

        if usage_count >= 10:  # or use session.DEFAULT_USAGE_LIMIT
            reply = "Message limit reached for this session."
        else:
            # Append user message
            chat_history.append({
                "chat_id": chat_id,
                "role": "user",
                "content": text
            })

            # Build system prompt
            system_prompt = f"""
You are an AI Customer Service agent for the following business:

Business Name: {session.name}
Business Type: {session.business_type}
Description: {session.business_description}

Speak as the business itself.
Be professional, polite, and helpful.
"""

            messages = [
                {"role": "system", "content": system_prompt},
                *chat_history
            ]

            # Call OpenAI
            completion = client.chat.completions.create(
                model="gpt-4",
                messages=messages,
                temperature=0.7,
                max_tokens=500
            )
            reply = completion.choices[0].message.content

            # Save assistant reply
            chat_history.append({
                "chat_id": chat_id,
                "role": "assistant",
                "content": reply
            })
            session.chat_history = chat_history
            session.save(update_fields=["chat_history"])

        # Send reply to Telegram
        requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": reply}
        )

        return Response({"ok": True})