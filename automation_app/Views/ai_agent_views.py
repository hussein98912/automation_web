# ai_agent/views.py
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.conf import settings
from ..models import BusinessSession
from openai import OpenAI
import os
from dotenv import load_dotenv

load_dotenv()  # loads .env
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

# Create OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)


class AIChatView(APIView):
    permission_classes = [IsAuthenticated]

    MAX_MESSAGES = 10  # limit per session

    def post(self, request):
        user = request.user
        message = request.data.get("message")
        session_id = request.data.get("session_id")

        if not message:
            return Response({"error": "Message is required"}, status=400)

        # Retrieve session
        if session_id:
            session = BusinessSession.objects.get(id=session_id, user=user)
        else:
            return Response({
                "message": "Please create a business session first."
            }, status=400)

        chat_history = session.chat_history or []

        # ✅ Check if user has exceeded message limit
        user_messages_count = len([m for m in chat_history if m["role"] == "user"])
        if user_messages_count >= self.MAX_MESSAGES:
            return Response({
                "error": f"You have reached the limit of {self.MAX_MESSAGES} messages. "
                         "you can order your custome ai agent"
            }, status=403)

        # Append new user message
        chat_history.append({"role": "user", "content": message})

        # System prompt including business info
        system_prompt = f"""
        You are an AI Customer Service agent for the following business:

        Business Type: {session.business_type}
        Description: {session.business_description}

        From now on, respond as the business speaking directly to customers.
        Be professional, polite, and helpful. Answer questions, share offers, explain services, 
        and provide information based on the business description. 
        Only ask clarifying questions if absolutely necessary.
        """

        messages = [{"role": "system", "content": system_prompt}] + chat_history

        response = client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )

        reply = response.choices[0].message.content

        # Save reply
        chat_history.append({"role": "assistant", "content": reply})
        session.chat_history = chat_history
        session.save()

        return Response({"reply": reply, "session_id": session.id})


class CreateBusinessSessionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        user = request.user
        business_type = request.data.get("business_type")
        business_description = request.data.get("business_description")

        if not business_type or not business_description:
            return Response({"error": "Business type and description are required."}, status=400)

        session = BusinessSession.objects.create(
            user=user,
            business_type=business_type,
            business_description=business_description,
            chat_history=[]
        )

        return Response({
            "message": f"You are now the AI Customer Service for {business_type}. Speak as a customer!",
            "session_id": session.id
        })
