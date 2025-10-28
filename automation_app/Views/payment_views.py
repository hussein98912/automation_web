import stripe
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from ..models import Payment, Order
import os

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

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
            "status": existing_payment.status,
            "client_secret": intent.client_secret
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
                payment.order.status = "in_progress"
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