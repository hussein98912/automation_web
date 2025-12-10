from django.contrib.auth import authenticate, login, get_user_model
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework import status
from django.views.decorators.csrf import csrf_exempt

User = get_user_model()

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
            "instagram_account_id": user.instagram_account_id,
            "facebook_page_id": user.facebook_page_id,
            "instagram_access_token": user.instagram_access_token,
            "facebook_access_token": user.facebook_access_token,
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
