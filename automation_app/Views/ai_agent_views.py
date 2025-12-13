# ai_agent/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
from ..models import BusinessSession
from openai import OpenAI
import os
from dotenv import load_dotenv
from django.shortcuts import get_object_or_404
from rest_framework import status

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

    USAGE_LIMIT = 500  # configurable

    def get(self, request, session_id):
        user = request.user

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
        # Build messages response
        # -------------------------
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
        # Final response
        # -------------------------
        return Response(
            {
                "id": str(session.id),
                "business_type": session.business_type,
                "business_description": session.business_description,
                "created_at": session.created_at.isoformat(),
                "messages": messages,
                "usage_count": usage_count,
                "usage_limit": self.USAGE_LIMIT
            },
            status=status.HTTP_200_OK
        )
    


class UserBotsView(APIView):
    permission_classes = [IsAuthenticated]

    DEFAULT_USAGE_LIMIT = 10  # adjust later per plan

    def get(self, request):
        user = request.user

        sessions = BusinessSession.objects.filter(user=user).order_by("-created_at")

        bots = []

        for session in sessions:
            chat_history = session.chat_history or []

            usage_count = sum(
                1 for msg in chat_history if msg.get("role") == "user"
            )

            bots.append({
                "id": str(session.id),
                "name": session.name,
                "business_type": session.business_type,
                "business_description": session.business_description,
                "createdAt": session.created_at.isoformat(),
                "usageCount": usage_count,
                "usageLimit": self.DEFAULT_USAGE_LIMIT
            })

        return Response(bots, status=status.HTTP_200_OK)