# accounts/views.py
from django.contrib.auth import get_user_model
from django.http import JsonResponse
from ..models import PasswordResetOTP
from ..utils import generate_otp
from ..service import send_mail  
from django.contrib.auth.hashers import make_password
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.utils import timezone
from rest_framework import status


User = get_user_model()


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def forgot_password_request(request):
    user = request.user
    email = user.email

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
@permission_classes([IsAuthenticated])
def verify_otp(request):
    user = request.user
    code = request.data.get("code")

    try:
        otp_obj = PasswordResetOTP.objects.filter(
            user=user,
            code=code,
            is_used=False
        ).latest("created_at")
    except PasswordResetOTP.DoesNotExist:
        return Response({"error": "Invalid OTP"}, status=400)

    if otp_obj.is_expired():
        return Response({"error": "OTP expired"}, status=400)

    # Mark OTP as verified
    otp_obj.is_verified = True
    otp_obj.save()

    return Response({"message": "OTP verified successfully"})






@api_view(["POST"])
@permission_classes([IsAuthenticated])
def change_password_after_otp(request):
    """
    Change password only after OTP has been verified.
    Requires:
        - new_password
        - confirm_password
    Optional:
        - otp_code  (if you want extra check)
    """
    user = request.user
    new_password = request.data.get("new_password")
    confirm_password = request.data.get("confirm_password")

    if not new_password or not confirm_password:
        return Response(
            {"error": "Both new_password and confirm_password are required"},
            status=status.HTTP_400_BAD_REQUEST
        )

    if new_password != confirm_password:
        return Response(
            {"error": "Passwords do not match"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # 1️⃣ Check for a verified OTP
    try:
        otp_obj = PasswordResetOTP.objects.filter(
            user=user,
            is_used=False
        ).latest("created_at")
    except PasswordResetOTP.DoesNotExist:
        return Response(
            {"error": "You must verify your OTP first"},
            status=status.HTTP_403_FORBIDDEN
        )

    # 2️⃣ Ensure OTP is verified
    if not otp_obj.is_verified:  # you need a boolean field in model
        return Response(
            {"error": "You must verify your OTP before changing password"},
            status=status.HTTP_403_FORBIDDEN
        )

    # Optional: check OTP expiration
    if otp_obj.is_expired():
        return Response(
            {"error": "Your verified OTP has expired"},
            status=status.HTTP_400_BAD_REQUEST
        )

    # 3️⃣ Change password
    user.password = make_password(new_password)
    user.save()

    # 4️⃣ Mark OTP as used
    otp_obj.is_used = True
    otp_obj.save()

    return Response({"message": "Password changed successfully"})
