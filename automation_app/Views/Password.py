from django.contrib.auth import get_user_model
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status
from ..utils import generate_otp
from ..models import PasswordResetOTP
from ..service.email_service import send_mail
from django.contrib.auth.hashers import make_password


User = get_user_model()


@api_view(["POST"])
@permission_classes([AllowAny])
def forgot_password_request(request):
    email = request.data.get("email")

    if not email:
        return Response(
            {"error": "Email is required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        # Security best practice: do NOT reveal whether email exists
        return Response(
            {"message": "If the email exists, an OTP has been sent"},
            status=status.HTTP_200_OK
        )

    otp = generate_otp()

    PasswordResetOTP.objects.create(
        user=user,
        code=otp
    )

    send_mail(
        subject="Password Reset Code",
        message=(
            f"Hello {user.full_name},\n\n"
            f"Your password reset code is: {otp}\n"
            f"This code expires in 10 minutes."
        ),
        recipient_list=[email],
    )

    return Response({"message": "OTP sent successfully"})


@api_view(["POST"])
@permission_classes([AllowAny])
def verify_otp(request):
    email = request.data.get("email")
    code = request.data.get("code")

    if not email or not code:
        return Response(
            {"error": "Email and OTP code are required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        user = User.objects.get(email=email)
        otp_obj = PasswordResetOTP.objects.filter(
            user=user,
            code=code,
            is_used=False
        ).latest("created_at")
    except (User.DoesNotExist, PasswordResetOTP.DoesNotExist):
        return Response({"error": "Invalid OTP"}, status=400)

    if otp_obj.is_expired():
        return Response({"error": "OTP expired"}, status=400)

    otp_obj.is_verified = True
    otp_obj.save()

    return Response({"message": "OTP verified successfully"})







@api_view(["POST"])
@permission_classes([AllowAny])
def change_password_after_otp(request):
    email = request.data.get("email")
    new_password = request.data.get("new_password")
    confirm_password = request.data.get("confirm_password")

    if not all([email, new_password, confirm_password]):
        return Response(
            {"error": "Email, new_password and confirm_password are required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    if new_password != confirm_password:
        return Response(
            {"error": "Passwords do not match"},
            status=status.HTTP_400_BAD_REQUEST
        )

    try:
        user = User.objects.get(email=email)
        otp_obj = PasswordResetOTP.objects.filter(
            user=user,
            is_used=False,
            is_verified=True
        ).latest("created_at")
    except (User.DoesNotExist, PasswordResetOTP.DoesNotExist):
        return Response(
            {"error": "OTP verification required"},
            status=status.HTTP_403_FORBIDDEN
        )

    if otp_obj.is_expired():
        return Response(
            {"error": "OTP expired"},
            status=status.HTTP_400_BAD_REQUEST
        )

    user.password = make_password(new_password)
    user.save()

    otp_obj.is_used = True
    otp_obj.save()

    return Response({"message": "Password changed successfully"})

