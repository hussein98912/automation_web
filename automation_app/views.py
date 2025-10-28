# views.py
import re
from django.conf import settings
from rest_framework.views import APIView
from django.contrib.auth import get_user_model, login, authenticate
from django.views.decorators.csrf import csrf_exempt
from rest_framework import status, viewsets, permissions, generics
from rest_framework.decorators import api_view, permission_classes, authentication_classes, action
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import AllowAny,IsAuthenticated,IsAdminUser
from .models import Category, Service, Order, Project,Notification,ChatHistory,Payment
from .serializers import CategorySerializer, ServiceSerializer, OrderSerializer, ProjectSerializer,CustomUserSerializer,NotificationSerializer
from .Ai import ai_chat_response, suggest_workflow_name, suggest_workflow_details
from .price import calculate_order_price  # KB pricing function
from rest_framework_simplejwt.authentication import JWTAuthentication
from difflib import get_close_matches
from django.contrib.auth.models import User
from django.shortcuts import get_object_or_404
import stripe
import os
from dotenv import load_dotenv

User = get_user_model()
load_dotenv()
stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

class UserListView(generics.ListAPIView):
    queryset = User.objects.all()
    serializer_class = CustomUserSerializer
    permission_classes = [AllowAny]

# -------------------------------
# User Authentication APIs
# -------------------------------
@api_view(['POST'])
def signup_api(request):
    data = request.data
    required_fields = ["full_name", "address", "email", "phone_number", "username", "password"]
    
    for field in required_fields:
        if field not in data:
            return Response({"error": f"{field} is required"}, status=status.HTTP_400_BAD_REQUEST)
    
    if User.objects.filter(username=data["username"]).exists():
        return Response({"error": "Username already exists"}, status=status.HTTP_400_BAD_REQUEST)
    if User.objects.filter(email=data["email"]).exists():
        return Response({"error": "Email already exists"}, status=status.HTTP_400_BAD_REQUEST)
    
    user = User.objects.create_user(
        username=data["username"],
        password=data["password"],
        email=data["email"],
        full_name=data["full_name"],
        phone_number=data["phone_number"],
        address=data["address"]
    )
    
    login(request, user)
    return Response({"message": "Account created and logged in successfully!"}, status=status.HTTP_201_CREATED)


@csrf_exempt
@api_view(['POST'])
@permission_classes([AllowAny])
@authentication_classes([])
def login_api(request):
    username = request.data.get("username")
    password = request.data.get("password")
    
    if not username or not password:
        return Response({"error": "Username and password are required"}, status=status.HTTP_400_BAD_REQUEST)
    
    user = authenticate(request, username=username, password=password)
    if user:
        refresh = RefreshToken.for_user(user)
        return Response({
            "message": f"Welcome, {username}!",
            "user_id": user.id,
            "username": user.username,
            "access": str(refresh.access_token),
            "refresh": str(refresh)
        }, status=status.HTTP_200_OK)
    return Response({"error": "Invalid username or password"}, status=status.HTTP_400_BAD_REQUEST)


@csrf_exempt
@api_view(['GET'])
@permission_classes([AllowAny])
@authentication_classes([])
def logout_api(request):
    return Response({"message": "Logged out successfully. Delete the token in frontend."}, status=status.HTTP_200_OK)


# -------------------------------
# Category & Service APIs
# -------------------------------
class CategoryListAPIView(generics.ListAPIView):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.AllowAny]


class ServiceViewSet(viewsets.ModelViewSet):
    queryset = Service.objects.all()
    serializer_class = ServiceSerializer
    permission_classes = [permissions.AllowAny]


class ProjectViewSet(viewsets.ModelViewSet):
    queryset = Project.objects.all()
    serializer_class = ProjectSerializer
    permission_classes = [permissions.AllowAny]


# -------------------------------
# Order APIs
# -------------------------------
class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        return Order.objects.filter(user=self.request.user).order_by("-created_at")

    def perform_create(self, serializer):
        service = serializer.validated_data.get("service")
        host_duration = serializer.validated_data.get("host_duration")
        industry = serializer.validated_data.get("industry", None)
        workflow_name = serializer.validated_data.get("workflow_name", "")
        workflow_details = serializer.validated_data.get("workflow_details", "")

        total_price = calculate_order_price(service.title, host_duration, industry)

        serializer.save(
            user=self.request.user,
            total_price=total_price,
            industry=industry,
            workflow_name=workflow_name,
            workflow_details=workflow_details
        )


        Notification.objects.create(
            user=Order.user,
            message=f"✅ Your order #{Order.id} has been received. "
                    f"Our admin will review it within 24 hours."
        )

    @action(detail=False, methods=["get"], permission_classes=[AllowAny])
    def all(self, request):
        """Admin-only endpoint to list all orders."""
        orders = Order.objects.all().order_by("-created_at")
        serializer = self.get_serializer(orders, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["post"])
    def manual_create(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = serializer.validated_data.get("service")
        host_duration = serializer.validated_data.get("host_duration")
        industry = serializer.validated_data.get("industry", None)
        workflow_name = serializer.validated_data.get("workflow_name", "")
        workflow_details = serializer.validated_data.get("workflow_details", "")

        total_price = calculate_order_price(service.title, host_duration, industry)

        order = serializer.save(
            user=request.user,
            total_price=total_price,
            industry=industry,
            workflow_name=workflow_name,
            workflow_details=workflow_details
        )

        Notification.objects.create(
            user=order.user,
            message=f"✅ Your order #{order.id} has been received. "
                    f"Our admin will review it within 24 hours."
        )

        return Response({
            "message": "Order created successfully! A notification has been sent to the user.",
            "order": self.get_serializer(order).data
        }, status=status.HTTP_201_CREATED)

# -------------------------------
# Chatbot API
# -------------------------------
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

# -------------------------------
# Chatbot API
# -------------------------------
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









class CurrentUserView(APIView):
    permission_classes = [IsAuthenticated]  # Requires valid access token

    def get(self, request):
        user = request.user  # Automatically set by JWTAuthentication
        serializer = CustomUserSerializer(user)
        return Response(serializer.data, status=status.HTTP_200_OK)




class OrderStatusUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def patch(self, request, order_id, *args, **kwargs):
        """
        Update only the status of the authenticated user's order.
        URL example: PATCH /orders/1/status/
        Body example: { "status": "ready_for_payment" }
        """
        new_status = request.data.get("status")

        if not new_status:
            return Response({"error": "status is required."}, status=status.HTTP_400_BAD_REQUEST)

        order = get_object_or_404(Order, pk=order_id, user=request.user)

        if new_status not in dict(Order.STATUS_CHOICES):
            return Response(
                {"error": f"Invalid status. Allowed: {list(dict(Order.STATUS_CHOICES).keys())}"},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update order
        order.status = new_status
        order.save()

        # Notification messages
        messages = {
            "ready_for_payment": f"💰 Your order #{order.id} is now ready for payment.",
            "completed": f"✅ Your order #{order.id} has been completed successfully.",
            "in_progress": f"🔧 Your order #{order.id} is now in progress.",
        }

        if new_status in messages:
            Notification.objects.create(user=order.user, message=messages[new_status])

        serializer = OrderSerializer(order)
        return Response(serializer.data, status=status.HTTP_200_OK) 
    



class UserNotificationListAPIView(generics.ListAPIView):
    serializer_class = NotificationSerializer
    authentication_classes = [JWTAuthentication]
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Only return notifications for the user from the token
        return Notification.objects.filter(user=self.request.user).order_by('-created_at')
    


class ChatHistoryListAPIView(APIView):
    """
    Get all chat history for the authenticated user.
    Requires JWT token in Authorization header.
    """
    permission_classes = [IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        # Filter chats by authenticated user ID
        user_id = str(request.user.id)
        chats = ChatHistory.objects.filter(user_id=user_id).order_by('-timestamp')

        # Convert to JSON manually (or use a serializer if preferred)
        data = [
            {
                "id": chat.id,
                "message": chat.message,
                "response": chat.response,
                "timestamp": chat.timestamp,
                "is_bot": chat.is_bot
            }
            for chat in chats
        ]

        return Response(data, status=status.HTTP_200_OK)
    

class AdminChatHistoryListAPIView(APIView):
    """
    Get all chat history for all users (Admin only).
    Requires admin privileges and JWT token.
    """
    permission_classes = [IsAdminUser]
    authentication_classes = [JWTAuthentication]

    def get(self, request):
        # Get all chat records ordered by most recent first
        chats = ChatHistory.objects.select_related('user').order_by('-timestamp')

        # Convert to JSON manually (you can use serializer instead)
        data = [
            {
                "id": chat.id,
                "username": chat.user.username if chat.user else None,
                "message": chat.message,
                "response": chat.response,
                "timestamp": chat.timestamp,
                "is_bot": chat.is_bot,
            }
            for chat in chats
        ]

        return Response(data, status=status.HTTP_200_OK)
    

STRIPE_SECRET_KEY = os.environ.get("STRIPE_SECRET_KEY")


@api_view(['POST'])
def create_payment(request):
    """Create Stripe PaymentIntent based on order total_price"""
    order_id = request.data.get("order_id")

    if not order_id:
        return Response({"error": "Missing order_id"}, status=status.HTTP_400_BAD_REQUEST)

    # Get the order
    order = Order.objects.filter(id=order_id).first()
    if not order:
        return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)

    # Use total_price from the order
    amount = order.total_price
    if not amount or float(amount) <= 0:
        return Response({"error": "Invalid order total price"}, status=status.HTTP_400_BAD_REQUEST)

    # Prevent multiple payments for the same order
    existing_payment = getattr(order, "payment", None)
    if existing_payment and existing_payment.status in ["pending", "paid"]:
        return Response({
            "message": "Payment already exists for this order.",
            "payment_id": existing_payment.id,
            "status": existing_payment.status
        }, status=status.HTTP_200_OK)

    # Create Payment record
    payment = Payment.objects.create(order=order, amount=amount, status="pending")

    try:
        # Create Stripe PaymentIntent
        intent = stripe.PaymentIntent.create(
            amount=int(float(amount) * 100),  # Convert to cents
            currency="usd",
            metadata={"payment_id": payment.id, "order_id": order.id},
            automatic_payment_methods={"enabled": True},
        )

        # Save transaction ID
        payment.transaction_id = intent.id
        payment.save()

        return Response({
            "payment_id": payment.id,
            "client_secret": intent.client_secret,
            "amount": str(amount),
            "currency": "usd"
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)
    



@api_view(['POST'])
def confirm_payment(request):
    """Confirm Stripe payment by checking PaymentIntent status"""
    payment_id = request.data.get("payment_id")

    if not payment_id:
        return Response({"error": "Missing payment_id"}, status=status.HTTP_400_BAD_REQUEST)

    # Find the payment in your DB
    payment = Payment.objects.filter(id=payment_id).select_related("order").first()
    if not payment:
        return Response({"error": "Payment not found"}, status=status.HTTP_404_NOT_FOUND)

    # Fetch PaymentIntent from Stripe
    try:
        intent = stripe.PaymentIntent.retrieve(payment.transaction_id)
        stripe_status = intent.status  # e.g. 'succeeded', 'requires_payment_method', etc.

        # Map Stripe status to your model
        if stripe_status == "succeeded":
            payment.status = "paid"
            # ✅ Update the related order status
            if payment.order:
                payment.order.status = "ready_for_payment"
                payment.order.save()

        elif stripe_status in ["requires_payment_method", "requires_action"]:
            payment.status = "pending"
        else:
            payment.status = "failed"

        payment.save()

        return Response({
            "payment_id": payment.id,
            "stripe_status": stripe_status,
            "local_status": payment.status,
            "order_status": payment.order.status if payment.order else None
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)  