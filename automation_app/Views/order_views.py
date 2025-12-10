from rest_framework import viewsets, status,permissions
from rest_framework.decorators import action,api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework_simplejwt.authentication import JWTAuthentication
from django.shortcuts import get_object_or_404
from ..models import Order, Notification,Project
from ..serializers import OrderSerializer
from ..price import calculate_order_price
from rest_framework.views import APIView
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from automation_app.utils import send_real_time_notification
from django.core.exceptions import ValidationError





class OrderViewSet(viewsets.ModelViewSet):
    serializer_class = OrderSerializer
    permission_classes = [permissions.AllowAny]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Order.objects.all().order_by("-created_at")
        return Order.objects.filter(user=self.request.user).order_by("-created_at")

    def perform_create(self, serializer):
        service = serializer.validated_data.get("service", None)
        project = serializer.validated_data.get("project", None)
        host_duration = serializer.validated_data.get("host_duration")
        industry = serializer.validated_data.get("industry", None)
        workflow_name = serializer.validated_data.get("workflow_name", "")
        workflow_details = serializer.validated_data.get("workflow_details", "")

        # ✅ Calculate total price based on type of order
        if project:
            total_price = float(project.price or 0)
        elif service:
            total_price = calculate_order_price(service.title, host_duration, industry)
        else:
            raise ValidationError("Order must be linked to a service or a project.")

        order = serializer.save(
            user=self.request.user,
            total_price=total_price,
            industry=industry,
            workflow_name=workflow_name,
            workflow_details=workflow_details
        )

        # ✅ Create notification
        Notification.objects.create(
            user=order.user,
            message=f"✅ Your order #{order.id} has been received. Our admin will review it within 24 hours."
        )

        send_real_time_notification(
            self.request.user.id,
            f"✅ Your order #{order.id} has been received!"
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

        service = serializer.validated_data.get("service", None)
        project = serializer.validated_data.get("project", None)
        host_duration = serializer.validated_data.get("host_duration")
        industry = serializer.validated_data.get("industry", None)
        workflow_name = serializer.validated_data.get("workflow_name", "")
        workflow_details = serializer.validated_data.get("workflow_details", "")

        # ✅ Calculate total price
        if project:
            total_price = float(project.price or 0)
        elif service:
            total_price = calculate_order_price(service.title, host_duration, industry)
        else:
            raise ValidationError("Order must be linked to a service or a project.")

        order = serializer.save(
            user=request.user,
            total_price=total_price,
            industry=industry,
            workflow_name=workflow_name,
            workflow_details=workflow_details
        )

        Notification.objects.create(
            user=order.user,
            message=f"✅ Your order #{order.id} has been received. Our admin will review it within 24 hours."
        )

        return Response({
            "message": "Order created successfully! A notification has been sent to the user.", 
            "order": self.get_serializer(order).data
        }, status=status.HTTP_201_CREATED)
    


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
            send_real_time_notification(order.user.id, messages[new_status])

        serializer = OrderSerializer(order)
        return Response(serializer.data, status=status.HTTP_200_OK) 
    

@api_view(["POST"])
@permission_classes([IsAuthenticated])
def create_project_order(request):
    project_id = request.data.get("project_id")
    if not project_id:
        return Response({"error": "project_id is required"}, status=400)

    project = get_object_or_404(Project, id=project_id)

    order = Order.objects.create(
        user=request.user,
        project=project,
        total_price=project.price,
        status="ready_for_payment",
        workflow_name=f"Purchase of project {project.title}"
    )

    # ✅ Safe notification
    item_name = order.project.title if order.project else (order.service.title if order.service else "Unknown")
    Notification.objects.create(
        user=order.user,
        message=f"✅ Your order #{order.id} ({item_name}) has been received."
    )

    return Response({
        "order_id": order.id,
        "message": "Order created successfully. Proceed to payment."
    })



@api_view(["DELETE"])
@permission_classes([IsAuthenticated])
def delete_order(request, order_id):
    """
    Delete an order created by the authenticated user.
    Admins can delete any order.
    """
    order = get_object_or_404(Order, id=order_id)

    # If user is not admin, ensure the order belongs to them
    if not request.user.is_staff and order.user != request.user:
        return Response(
            {"error": "You do not have permission to delete this order."},
            status=status.HTTP_403_FORBIDDEN
        )

    order.delete()

    return Response(
        {"message": "Order deleted successfully."},
        status=status.HTTP_204_NO_CONTENT
    )