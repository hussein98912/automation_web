from rest_framework import generics, permissions, viewsets
from ..models import Category, Service, Project
from ..serializers import CategorySerializer, ServiceSerializer, ProjectSerializer
from django.shortcuts import get_object_or_404
from pathlib import Path
from django.http import StreamingHttpResponse, HttpResponse, HttpResponseNotFound


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


def stream_video(request, pk):
    project = get_object_or_404(Project, pk=pk)

    if not project.video:
        return HttpResponseNotFound("Video not found")

    video_path = project.video.path
    file_size = Path(video_path).stat().st_size
    range_header = request.headers.get('Range', '')
    byte_range = 0

    if "bytes=" in range_header:
        # Example: "bytes=1000-"
        byte_range = int(range_header.replace("bytes=", "").replace("-", ""))

    # Open the file and read from the requested byte
    with open(video_path, 'rb') as f:
        f.seek(byte_range)
        data = f.read(1024 * 1024)  # 1MB chunks

    response = HttpResponse(
        data,
        status=206,
        content_type="video/mp4"
    )

    response["Content-Range"] = f"bytes {byte_range}-{file_size-1}/{file_size}"
    response["Accept-Ranges"] = "bytes"
    response["Content-Length"] = str(file_size - byte_range)

    return response