import stripe
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from ..models import  Order,Payment
import os
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from automation_app.utils import send_real_time_notification



stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

@api_view(['POST'])
def create_payment(request):
    """Create or reuse a Stripe PaymentIntent based on order total_price."""
    order_id = request.data.get("order_id")
    if not order_id:
        return Response({"error": "Missing order_id"}, status=status.HTTP_400_BAD_REQUEST)

    # ✅ Get order
    order = Order.objects.filter(id=order_id).first()
    if not order:
        return Response({"error": "Order not found"}, status=status.HTTP_404_NOT_FOUND)

    amount = order.total_price
    if not amount or float(amount) <= 0:
        return Response({"error": "Invalid order total price"}, status=status.HTTP_400_BAD_REQUEST)

    # ✅ Check if order already has a payment
    existing_payment = getattr(order, "payment", None)

    # Case 1: Payment already completed
    if existing_payment and existing_payment.status == "paid":
        return Response({
            "message": "Payment already completed for this order.",
            "payment_id": existing_payment.id,
            "status": existing_payment.status,
            "transaction_id": existing_payment.transaction_id
        }, status=status.HTTP_200_OK)

    # Case 2: Pending payment — reuse
    if existing_payment and existing_payment.status == "pending":
        try:
            intent = stripe.PaymentIntent.retrieve(existing_payment.transaction_id)
            client_secret = getattr(intent, "client_secret", None)
        except Exception as e:
            print(f"⚠️ Stripe retrieve failed: {e}")
            client_secret = None

        # If no client_secret, recreate PaymentIntent
        if not client_secret:
            try:
                new_intent = stripe.PaymentIntent.create(
                    amount=int(float(amount) * 100),
                    currency="usd",
                    metadata={"payment_id": existing_payment.id, "order_id": order.id},
                    automatic_payment_methods={"enabled": True},
                )
                existing_payment.transaction_id = new_intent.id
                existing_payment.save()
                client_secret = new_intent.client_secret
            except Exception as e:
                return Response({"error": f"Failed to recreate PaymentIntent: {str(e)}"},
                                status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "message": "Payment already exists for this order.",
            "payment_id": existing_payment.id,
            "status": existing_payment.status,
            "transaction_id": existing_payment.transaction_id,
            "client_secret": client_secret
        }, status=status.HTTP_200_OK)

    # Case 3: No payment exists yet — create new
    try:
        payment = Payment.objects.create(order=order, amount=amount, status="pending")

        intent = stripe.PaymentIntent.create(
            amount=int(float(amount) * 100),
            currency="usd",
            metadata={"payment_id": payment.id, "order_id": order.id},
            automatic_payment_methods={"enabled": True},
        )

        payment.transaction_id = intent.id
        payment.save()

        return Response({
            "payment_id": payment.id,
            "transaction_id": payment.transaction_id,
            "client_secret": intent.client_secret,
            "amount": str(amount),
            "currency": "usd"
        }, status=status.HTTP_201_CREATED)

    except Exception as e:
        print(f"⚠️ Stripe PaymentIntent create failed: {e}")
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

    # Messages to send
    messages_map = {
        "paid": f"💰 Your order #{payment.order.id} has been paid successfully.",
        "in_progress": f"🔧 Your order #{payment.order.id} is now in progress.",
        "failed": f"❌ Payment for order #{payment.order.id} failed."
    }

    # Fetch PaymentIntent from Stripe
    try:
        intent = stripe.PaymentIntent.retrieve(payment.transaction_id)
        stripe_status = intent.status  # e.g. 'succeeded', 'requires_payment_method', etc.

        # Map Stripe status to your model
        if stripe_status == "succeeded":
            payment.status = "paid"
            if payment.order:
                payment.order.status = "in_progress"
                payment.order.save()
                # ✅ Send real-time notification for the order status update
                send_real_time_notification(payment.order.user.id, messages_map["in_progress"])
            # ✅ Send notification for payment success
            send_real_time_notification(payment.order.user.id, messages_map["paid"])

        elif stripe_status in ["requires_payment_method", "requires_action"]:
            payment.status = "pending"
        else:
            payment.status = "failed"
            if payment.order:
                send_real_time_notification(payment.order.user.id, messages_map["failed"])

        payment.save()

        return Response({
            "payment_id": payment.id,
            "stripe_status": stripe_status,
            "local_status": payment.status,
            "order_status": payment.order.status if payment.order else None
        }, status=status.HTTP_200_OK)

    except Exception as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)


