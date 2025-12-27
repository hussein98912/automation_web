from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from ..service import run_ai_agent


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def instagram_ai_chat(request):
    message = request.data.get("message")

    if not message:
        return Response(
            {"error": "message is required"},
            status=400
        )

    reply = run_ai_agent(request.user, message)

    return Response({
        "reply": reply
    })